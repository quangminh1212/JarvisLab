#!/usr/bin/env python3
"""
Voice recording + STT for JarvisLab.
VAD mic capture → Google Speech Recognition.

Usage: python listen.py [language] [timeout_seconds] [mic_index] [wait_for_speech]
  language:        BCP-47 (default: vi-VN)
  timeout_seconds: max wait (default 30, 0 = infinite when wait_for_speech=1)
  mic_index:       device index (-1 = default)
  wait_for_speech: 1 = keep waiting until speech, then until silence

stdout: transcribed text (empty if nothing)
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import wave

import numpy as np
import sounddevice as sd

# ── Audio chimes ──────────────────────────────────────────────────────────────
_CHIME_FS = 44100


def _chime(freq_start: float, freq_end: float, duration: float = 0.18, vol: float = 0.18):
    try:
        t = np.linspace(0, duration, int(_CHIME_FS * duration), endpoint=False)
        freq = np.linspace(freq_start, freq_end, len(t))
        phase = np.cumsum(2 * np.pi * freq / _CHIME_FS)
        w = vol * np.sin(phase)
        envelope = np.exp(-3.5 * t / duration)
        sd.play((w * envelope).astype(np.float32), _CHIME_FS, blocking=True)
    except Exception:
        pass


def chime_listening():
    _chime(700, 1100)


def chime_done():
    _chime(1100, 700)


# ── CLI ───────────────────────────────────────────────────────────────────────
# Support:
#   listen.py [language] [timeout] [mic_index] [wait_for_speech]
#   listen.py --wav file.wav [language]
_WAV_PATH: str | None = None
if len(sys.argv) > 1 and sys.argv[1] == "--wav":
    _WAV_PATH = sys.argv[2] if len(sys.argv) > 2 else ""
    LANGUAGE = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("VOICE_LANGUAGE", "vi-VN")
    TIMEOUT = 30.0
    MIC_INDEX = int(os.environ.get("VOICE_MIC_INDEX", "-1"))
    WAIT_FOR_SPEECH = False
else:
    LANGUAGE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("VOICE_LANGUAGE", "vi-VN")
    TIMEOUT = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    MIC_INDEX = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.environ.get("VOICE_MIC_INDEX", "-1"))
    WAIT_FOR_SPEECH = bool(int(sys.argv[4])) if len(sys.argv) > 4 else False

# ── VAD constants (tuned for weak USB mics) ───────────────────────────────────
FS = 16000
CHUNK_SEC = 0.08
SILENCE_SEC = float(os.environ.get("VOICE_SILENCE_SEC", "0.85"))
MIN_SPEECH_SEC = float(os.environ.get("VOICE_MIN_SPEECH_SEC", "0.45"))
THRESHOLD = float(os.environ.get("VOICE_THRESHOLD", "0.0025"))
GAIN = float(os.environ.get("VOICE_GAIN", "50.0"))
NOISE_FLOOR_SEC = float(os.environ.get("VOICE_NOISE_FLOOR_SEC", "0.9"))
DYNAMIC_THRESHOLD_MULT = float(os.environ.get("VOICE_DYN_MULT", "2.2"))
CHIME = os.environ.get("VOICE_CHIME", "1") not in ("0", "false", "False", "no")


def record_with_vad() -> np.ndarray | None:
    device = None if MIC_INDEX < 0 else MIC_INDEX
    buffer: list[np.ndarray] = []
    speaking = False
    silence_start = None
    start_time = time.time()
    warm_up_until = time.time() + NOISE_FLOOR_SEC
    indefinite = WAIT_FOR_SPEECH and TIMEOUT <= 0
    noise_samples: list[float] = []
    threshold = THRESHOLD
    last_dbg = 0.0

    print(
        f"[listen] lang={LANGUAGE} wait={WAIT_FOR_SPEECH} "
        f"timeout={TIMEOUT if TIMEOUT > 0 else 'inf'}s mic={MIC_INDEX} gain={GAIN}",
        file=sys.stderr,
        flush=True,
    )
    if CHIME and not os.environ.get("VOICE_QUIET"):
        chime_listening()

    while indefinite or (time.time() - start_time < TIMEOUT):
        chunk = sd.rec(
            int(CHUNK_SEC * FS),
            samplerate=FS,
            channels=1,
            dtype="float32",
            device=device,
        )
        sd.wait()
        chunk = chunk.flatten()
        chunk_boosted = np.clip(chunk * GAIN, -1.0, 1.0)
        rms = float(np.sqrt(np.mean(chunk_boosted**2)))

        now = time.time()
        if WAIT_FOR_SPEECH and now < warm_up_until and not speaking:
            noise_samples.append(rms)
            if len(noise_samples) >= 4:
                observed = float(np.percentile(noise_samples[-12:], 90))
                threshold = max(THRESHOLD, observed * DYNAMIC_THRESHOLD_MULT)
            continue

        if WAIT_FOR_SPEECH and not speaking and now - last_dbg > 2.5:
            print(
                f"[listen] waiting rms={rms:.4f} thr={threshold:.4f}",
                file=sys.stderr,
                flush=True,
            )
            last_dbg = now

        if rms > threshold:
            if not speaking:
                print("[listen] speech detected", file=sys.stderr, flush=True)
                speaking = True
                silence_start = None
            buffer.append(chunk_boosted)
        else:
            if speaking:
                if silence_start is None:
                    silence_start = now
                elif now - silence_start > SILENCE_SEC:
                    speech_dur = len(buffer) * CHUNK_SEC
                    print(
                        f"[listen] silence → end ({speech_dur:.2f}s)",
                        file=sys.stderr,
                        flush=True,
                    )
                    if speech_dur >= MIN_SPEECH_SEC:
                        if CHIME and not os.environ.get("VOICE_QUIET"):
                            chime_done()
                        return np.concatenate(buffer)
                    buffer = []
                    speaking = False
                    silence_start = None
                    if WAIT_FOR_SPEECH:
                        warm_up_until = time.time() + 0.4
                        noise_samples = []
                else:
                    buffer.append(chunk_boosted)
            elif speaking is False and buffer and not WAIT_FOR_SPEECH:
                # keep tiny preroll only while not in wait mode
                if len(buffer) > int(0.3 / CHUNK_SEC):
                    buffer = buffer[-int(0.3 / CHUNK_SEC) :]
            # trailing silence while speaking already handled
            if speaking and silence_start is not None:
                buffer.append(chunk_boosted)

    if speaking and len(buffer) * CHUNK_SEC >= MIN_SPEECH_SEC:
        if CHIME and not os.environ.get("VOICE_QUIET"):
            chime_done()
        return np.concatenate(buffer)
    return None


def transcribe(audio: np.ndarray) -> str | None:
    try:
        import speech_recognition as sr
    except ImportError:
        print("[listen] SpeechRecognition not installed", file=sys.stderr)
        return None

    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        # soft peak normalize to help Google STT on weak/loud audio
        peak = float(np.max(np.abs(audio))) or 1.0
        if peak > 0:
            audio = np.clip(audio / peak * 0.9, -1.0, 1.0)
        audio_i16 = (audio * 32767.0).astype(np.int16)
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(FS)
            wf.writeframes(audio_i16.tobytes())

        r = sr.Recognizer()
        r.energy_threshold = 30
        with sr.AudioFile(wav_path) as source:
            audio_data = r.record(source)

        text = r.recognize_google(audio_data, language=LANGUAGE)
        return text.strip() if text else None
    except Exception as e:
        # UnknownValueError and others
        name = type(e).__name__
        if name != "UnknownValueError":
            print(f"[listen] STT error: {e}", file=sys.stderr)
        return None
    finally:
        try:
            if os.path.exists(wav_path):
                os.unlink(wav_path)
        except Exception:
            pass


def transcribe_wav_file(path: str) -> str | None:
    """Test helper: STT from an existing WAV file."""
    try:
        import speech_recognition as sr
    except ImportError:
        return None
    r = sr.Recognizer()
    with sr.AudioFile(path) as source:
        audio_data = r.record(source)
    try:
        return r.recognize_google(audio_data, language=LANGUAGE)
    except Exception:
        return None


def main() -> None:
    if _WAV_PATH is not None:
        if not _WAV_PATH or not os.path.exists(_WAV_PATH):
            print(f"[listen] wav not found: {_WAV_PATH}", file=sys.stderr)
            print("")
            sys.exit(1)
        text = transcribe_wav_file(_WAV_PATH)
        print(text if text else "")
        return

    audio = record_with_vad()
    if audio is None:
        print("")
        sys.exit(0)
    text = transcribe(audio)
    print(text if text else "")


if __name__ == "__main__":
    main()
