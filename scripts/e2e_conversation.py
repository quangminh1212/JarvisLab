#!/usr/bin/env python3
"""E2E latency + quality checks for real conversation path (no live speech required)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
os.environ["VOICE_QUIET"] = "1"
os.environ.setdefault("PYTHONUTF8", "1")

# load .env
envp = ROOT / ".env"
if envp.exists():
    for line in envp.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from audio_core import speak, transcribe, FS  # noqa: E402
from llm import chat_completion  # noqa: E402
import numpy as np
import asyncio
import tempfile
import subprocess
import edge_tts
import imageio_ffmpeg
import wave


def pass_fail(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def synth_wav(text: str, path: str) -> None:
    mp3 = path + ".mp3"

    async def go():
        await edge_tts.Communicate(text, "vi-VN-HoaiMyNeural").save(mp3)

    asyncio.run(go())
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [ff, "-y", "-i", mp3, "-ac", "1", "-ar", str(FS), path],
        capture_output=True,
        check=True,
    )
    try:
        os.unlink(mp3)
    except Exception:
        pass


def main() -> int:
    results = []
    print("JarvisLab conversation E2E\n" + "=" * 40)

    # 1) TTS latency (sounddevice path)
    t0 = time.time()
    dur = speak("Xin chào, kiểm tra tốc độ nói.", "vi-VN")
    tts_wall = time.time() - t0
    results.append(
        pass_fail("tts_latency", tts_wall < 12 and dur > 0.5, f"wall={tts_wall:.2f}s spoken≈{dur:.2f}s")
    )

    # 2) STT on synthetic utterance (conversation phrases)
    phrases = [
        "Xin chào Jarvis",
        "Bây giờ mấy giờ rồi",
        "Cảm ơn bạn",
        "Tạm biệt",
    ]
    stt_ok = 0
    for p in phrases:
        wav = tempfile.mktemp(suffix=".wav")
        try:
            synth_wav(p, wav)
            with wave.open(wav, "rb") as w:
                raw = w.readframes(w.getnframes())
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            t1 = time.time()
            text = transcribe(audio, "vi-VN") or ""
            dt = time.time() - t1
            hit = any(
                k in text.lower()
                for k in (
                    "chào",
                    "jarvis",
                    "giờ",
                    "cảm",
                    "ơn",
                    "tạm",
                    "biệt",
                    "bye",
                    "mấy",
                    "xin",
                )
            )
            print(f"  STT {p!r} -> {text!r} ({dt:.2f}s)")
            if text and hit:
                stt_ok += 1
        finally:
            try:
                os.unlink(wav)
            except Exception:
                pass
    results.append(pass_fail("stt_phrases", stt_ok >= 3, f"{stt_ok}/{len(phrases)}"))

    # 3) multi-turn LLM feel (short replies)
    history = []
    turns = [
        "Xin chào",
        "Bạn tên gì",
        "Kể một câu ngắn về thời tiết giả định",
    ]
    llm_ok = True
    for u in turns:
        reply, backend = chat_completion(u, history=history)
        history += [{"role": "user", "content": u}, {"role": "assistant", "content": reply}]
        words = len(reply.split())
        print(f"  LLM[{backend}] {u!r} -> {reply!r} ({words} words)")
        if not reply or words > 60:
            llm_ok = False
    results.append(pass_fail("llm_multiturn_short", llm_ok and backend == "llm", f"backend={backend}"))

    # 4) full dry conversation turn timing
    t0 = time.time()
    user = "Xin chào Jarvis, bạn khỏe không"
    reply, backend = chat_completion(user)
    t_llm = time.time() - t0
    t1 = time.time()
    speak(reply, "vi-VN")
    t_speak = time.time() - t1
    total = time.time() - t0
    print(f"  turn: llm={t_llm:.2f}s speak={t_speak:.2f}s total={total:.2f}s")
    results.append(pass_fail("turn_latency", total < 20 and t_llm < 8, f"total={total:.2f}s"))

    print("=" * 40)
    failed = sum(1 for x in results if not x)
    print(f"Result: {len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
