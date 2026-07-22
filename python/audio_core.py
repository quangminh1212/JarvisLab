#!/usr/bin/env python3
"""
Shared audio core for JarvisLab — in-process TTS/STT (no subprocess hop).
Used by jarvis_call.py and tests; CLI scripts remain for MCP.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

FS = 16000
_ROOT = Path(__file__).resolve().parent


# ── devices ───────────────────────────────────────────────────────────────────
def default_mic_index() -> int:
    try:
        d = sd.default.device[0]
        return int(d) if d is not None else -1
    except Exception:
        return -1


def query_inputs() -> list[dict]:
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            out.append({"id": i, "name": d["name"], "sr": int(d["default_samplerate"])})
    return out


# ── chimes ────────────────────────────────────────────────────────────────────
def chime(up: bool = True, vol: float = 0.15) -> None:
    if os.environ.get("VOICE_QUIET") or os.environ.get("VOICE_CHIME", "1") in (
        "0",
        "false",
        "no",
    ):
        return
    try:
        dur = 0.16
        t = np.linspace(0, dur, int(44100 * dur), endpoint=False)
        f0, f1 = (700, 1100) if up else (1100, 700)
        freq = np.linspace(f0, f1, len(t))
        phase = np.cumsum(2 * np.pi * freq / 44100)
        w = vol * np.sin(phase) * np.exp(-3.5 * t / dur)
        sd.play(w.astype(np.float32), 44100, blocking=True)
    except Exception:
        pass


# ── TTS ───────────────────────────────────────────────────────────────────────
VOICE_MAP = {
    "vi-VN": "vi-VN-HoaiMyNeural",
    "vi": "vi-VN-HoaiMyNeural",
    "en-US": "en-US-AriaNeural",
    "en": "en-US-AriaNeural",
}


def resolve_voice(lang: str) -> str:
    ov = os.environ.get("VOICE_TTS_VOICE") or os.environ.get("JARVIS_TTS_VOICE")
    if ov:
        return ov
    return VOICE_MAP.get(lang, VOICE_MAP.get(lang.split("-")[0], "vi-VN-HoaiMyNeural"))


def _mp3_to_wav_pcm(mp3_path: str, wav_path: str, sr: int = FS) -> None:
    try:
        import imageio_ffmpeg

        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ff = "ffmpeg"
    r = subprocess.run(
        [ff, "-y", "-i", mp3_path, "-ac", "1", "-ar", str(sr), wav_path],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0 or not os.path.exists(wav_path):
        raise RuntimeError(f"ffmpeg convert failed: {r.stderr[-200:]}")


def _read_wav_f32(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        raw = w.readframes(n)
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    return audio, sr


def _play_pcm(audio: np.ndarray, sr: int) -> None:
    # prevent clipping
    peak = float(np.max(np.abs(audio))) or 1.0
    if peak > 1.0:
        audio = audio / peak
    sd.play(audio.astype(np.float32), sr, blocking=True)
    sd.wait()


def _speak_sapi(text: str) -> None:
    safe = text.replace('"', "'").replace("`", "").replace("$", "").replace("\n", " ")
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f'$s.Speak("{safe}")'
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        timeout=120,
    )


def speak(text: str, lang: str = "vi-VN") -> float:
    """Speak text; return duration seconds (approx)."""
    text = (text or "").strip()
    if not text:
        return 0.0
    voice = resolve_voice(lang)
    t0 = time.time()
    fd_mp3, mp3 = tempfile.mkstemp(suffix=".mp3")
    os.close(fd_mp3)
    fd_wav, wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd_wav)
    try:
        import edge_tts

        async def _gen():
            await edge_tts.Communicate(text, voice).save(mp3)

        asyncio.run(_gen())
        if not os.path.exists(mp3) or os.path.getsize(mp3) < 32:
            raise RuntimeError("empty tts")
        try:
            _mp3_to_wav_pcm(mp3, wav, FS)
            audio, sr = _read_wav_f32(wav)
            _play_pcm(audio, sr)
            return max(0.1, time.time() - t0)
        except Exception as e:
            print(f"[audio] pcm play fail ({e}), SAPI/edge fallback", file=sys.stderr)
            # fallback: old windows player via speak.py path
            from speak import play_mp3_windows, speak_sapi

            if play_mp3_windows(mp3):
                return max(0.1, time.time() - t0)
            speak_sapi(text)
            return max(0.1, time.time() - t0)
    except Exception as e:
        print(f"[audio] tts error: {e}", file=sys.stderr)
        _speak_sapi(text)
        return max(0.1, time.time() - t0)
    finally:
        for p in (mp3, wav):
            try:
                os.unlink(p)
            except Exception:
                pass


# ── VAD + STT ─────────────────────────────────────────────────────────────────
def _envf(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def record_vad(
    mic_index: int = -1,
    timeout: float = 0.0,
    wait_for_speech: bool = True,
) -> np.ndarray | None:
    """
    Record one utterance with VAD.
    timeout<=0 and wait_for_speech => wait indefinitely for speech start.
    """
    device = None if mic_index < 0 else mic_index
    chunk_sec = 0.08
    silence_sec = _envf("VOICE_SILENCE_SEC", 0.75)
    min_speech = _envf("VOICE_MIN_SPEECH_SEC", 0.4)
    base_thr = _envf("VOICE_THRESHOLD", 0.0020)
    gain = _envf("VOICE_GAIN", 70.0)
    noise_sec = _envf("VOICE_NOISE_FLOOR_SEC", 0.7)
    dyn_mult = _envf("VOICE_DYN_MULT", 2.0)

    buffer: list[np.ndarray] = []
    speaking = False
    silence_start = None
    start = time.time()
    warm_until = time.time() + noise_sec
    indefinite = wait_for_speech and timeout <= 0
    noise: list[float] = []
    thr = base_thr
    last_dbg = 0.0

    print(
        f"[listen] mic={mic_index} gain={gain} wait={wait_for_speech} "
        f"timeout={'inf' if indefinite else timeout}",
        file=sys.stderr,
        flush=True,
    )
    chime(True)

    while indefinite or (time.time() - start < timeout):
        frames = int(chunk_sec * FS)
        chunk = sd.rec(frames, samplerate=FS, channels=1, dtype="float32", device=device)
        sd.wait()
        chunk = chunk.reshape(-1)
        boosted = np.clip(chunk * gain, -1.0, 1.0)
        rms = float(np.sqrt(np.mean(boosted**2)) + 1e-12)
        now = time.time()

        if wait_for_speech and now < warm_until and not speaking:
            noise.append(rms)
            if len(noise) >= 4:
                p90 = float(np.percentile(noise[-16:], 90))
                thr = max(base_thr, p90 * dyn_mult)
            continue

        if wait_for_speech and not speaking and now - last_dbg > 2.0:
            print(f"[listen] waiting rms={rms:.4f} thr={thr:.4f}", file=sys.stderr, flush=True)
            last_dbg = now

        if rms > thr:
            if not speaking:
                print("[listen] speech detected", file=sys.stderr, flush=True)
                speaking = True
                silence_start = None
            buffer.append(boosted)
        else:
            if speaking:
                buffer.append(boosted)
                if silence_start is None:
                    silence_start = now
                elif now - silence_start >= silence_sec:
                    dur = len(buffer) * chunk_sec
                    print(f"[listen] end utterance {dur:.2f}s", file=sys.stderr, flush=True)
                    if dur >= min_speech:
                        chime(False)
                        return np.concatenate(buffer)
                    buffer = []
                    speaking = False
                    silence_start = None
                    warm_until = time.time() + 0.35
                    noise = []

    if speaking and len(buffer) * chunk_sec >= min_speech:
        chime(False)
        return np.concatenate(buffer)
    return None


def transcribe(audio: np.ndarray, lang: str = "vi-VN") -> str | None:
    try:
        import speech_recognition as sr
    except ImportError:
        print("[listen] SpeechRecognition missing", file=sys.stderr)
        return None

    # AGC peak normalize
    peak = float(np.max(np.abs(audio))) or 1.0
    audio = np.clip(audio / peak * 0.92, -1.0, 1.0)
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        i16 = (audio * 32767.0).astype(np.int16)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(FS)
            w.writeframes(i16.tobytes())
        r = sr.Recognizer()
        r.energy_threshold = 30
        with sr.AudioFile(path) as src:
            data = r.record(src)
        text = r.recognize_google(data, language=lang)
        return (text or "").strip() or None
    except Exception as e:
        if type(e).__name__ != "UnknownValueError":
            print(f"[listen] STT error: {e}", file=sys.stderr)
        return None
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def listen(
    lang: str = "vi-VN",
    mic_index: int = -1,
    timeout: float = 0.0,
    wait_for_speech: bool = True,
) -> str:
    audio = record_vad(mic_index=mic_index, timeout=timeout, wait_for_speech=wait_for_speech)
    if audio is None:
        return ""
    return transcribe(audio, lang=lang) or ""


def post_tts_pause(spoken_sec: float | None = None) -> None:
    """Pause so TTS tail / room echo doesn't poison the next listen."""
    base = _envf("VOICE_POST_TTS_DELAY", 0.35)
    extra = 0.0
    if spoken_sec and spoken_sec > 2.5:
        extra = 0.15
    time.sleep(base + extra)
