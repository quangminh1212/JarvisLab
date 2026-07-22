#!/usr/bin/env python3
"""
JarvisLab Voice Call — hội thoại giọng nói kiểu gọi điện.

Flow: chào (TTS) → nghe (VAD+STT) → LLM → nói → lặp
Kết thúc khi user nói tạm biệt / bye / thôi hoặc Ctrl+C.

Run:
  python jarvis_call.py
  python jarvis_call.py --once          # một lượt hỏi-đáp
  python jarvis_call.py --text "xin chào"  # test LLM+TTS không mic
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY_DIR = ROOT / "python"
sys.path.insert(0, str(PY_DIR))

import sounddevice as sd  # noqa: E402

from llm import chat_completion, is_goodbye, resolve_llm_config  # noqa: E402


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def pick_mic(index: int) -> int:
    if index >= 0:
        return index
    try:
        d = sd.default.device[0]
        return int(d) if d is not None and int(d) >= 0 else -1
    except Exception:
        return -1


def run_py(script: str, args: list[str], timeout: float | None = None) -> str:
    cmd = [sys.executable, str(PY_DIR / script), *args]
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # quiet chimes during chained call optional
    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )
    if r.stderr:
        for line in r.stderr.splitlines()[-8:]:
            print(line, file=sys.stderr)
    if r.returncode not in (0, None):
        raise RuntimeError(f"{script} exit {r.returncode}: {r.stderr[-300:]}")
    return (r.stdout or "").strip()


def speak(text: str, lang: str) -> None:
    run_py("speak.py", [text, lang], timeout=180)


def listen(lang: str, mic: int, timeout: float, wait: bool) -> str:
    # wait=1 timeout=0 → infinite until speech
    t_arg = "0" if wait and timeout <= 0 else str(max(5, int(timeout)))
    w_arg = "1" if wait else "0"
    # hard cap: infinite wait still bounded for safety
    hard = 300 if wait and timeout <= 0 else timeout + 30
    return run_py("listen.py", [lang, t_arg, str(mic), w_arg], timeout=hard)


def print_banner(mic: int, lang: str) -> None:
    cfg = resolve_llm_config()
    backend = "llm" if cfg["api_key"] else "rules"
    try:
        mic_name = sd.query_devices(mic if mic >= 0 else sd.default.device[0])["name"]
    except Exception:
        mic_name = f"index={mic}"
    print("=== JARVISLAB VOICE CALL ===")
    print(f"Mic: {mic_name}")
    print(f"Lang: {lang} | AI: {backend} ({cfg['model'] if backend == 'llm' else 'local rules'})")
    print("Nói tự nhiên như gọi điện. Nói 'tạm biệt' để kết thúc. Ctrl+C dừng.\n")


async def conversation_loop(args: argparse.Namespace) -> int:
    lang = args.lang
    mic = pick_mic(args.mic)
    history: list[dict[str, str]] = []

    print_banner(mic, lang)

    if not args.no_greeting:
        greet = "Xin chào, tôi là Jarvis. Bạn cần gì nào?"
        print(f"🤖 Jarvis: {greet}")
        speak(greet, lang)
        # tránh mic ăn tiếng loa
        time.sleep(float(os.environ.get("VOICE_POST_TTS_DELAY", "0.45")))

    turns = 0
    max_turns = args.max_turns

    while max_turns <= 0 or turns < max_turns:
        try:
            if args.text and turns == 0:
                user = args.text
            else:
                print("🎤 Đang nghe...")
                user = listen(
                    lang,
                    mic,
                    timeout=args.listen_timeout,
                    wait=True,
                )
            if not user:
                print("(Không nhận diện được — nói lại nhé)")
                if args.once or args.text:
                    return 1
                continue

            print(f"👂 Bạn: {user}")
            reply, backend = chat_completion(user, history=history)
            print(f"🤖 Jarvis[{backend}]: {reply}")
            history.append({"role": "user", "content": user})
            history.append({"role": "assistant", "content": reply})
            speak(reply, lang)
            turns += 1

            if is_goodbye(user) or is_goodbye(reply):
                print("\nCuộc gọi kết thúc.")
                return 0

            if args.once or args.text:
                return 0

            time.sleep(float(os.environ.get("VOICE_POST_TTS_DELAY", "0.45")))
            print("---")
        except KeyboardInterrupt:
            print("\nKết thúc.")
            try:
                speak("Tạm biệt.", lang)
            except Exception:
                pass
            return 0
        except Exception as e:
            print(f"Lỗi: {e}", file=sys.stderr)
            time.sleep(0.4)
            if args.once or args.text:
                return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JarvisLab voice call")
    p.add_argument("--lang", default=os.environ.get("VOICE_LANGUAGE", "vi-VN"))
    p.add_argument("--mic", type=int, default=env_int("VOICE_MIC_INDEX", -1))
    p.add_argument("--listen-timeout", type=float, default=0.0, help="0=infinite wait for speech")
    p.add_argument("--max-turns", type=int, default=0, help="0=unlimited")
    p.add_argument("--once", action="store_true", help="One listen→reply cycle")
    p.add_argument("--text", default="", help="Inject user text (skip mic) for dry-run")
    p.add_argument("--no-greeting", action="store_true")
    return p


def main() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    args = build_parser().parse_args()
    raise SystemExit(asyncio.run(conversation_loop(args)))


if __name__ == "__main__":
    main()
