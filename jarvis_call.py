#!/usr/bin/env python3
"""
JarvisLab Voice Call — hội thoại giọng nói kiểu gọi điện (in-process, low latency).

Flow: chào → nghe (VAD+STT) → LLM → nói → lặp
Kết thúc: "tạm biệt" / bye / thôi / Ctrl+C

  python jarvis_call.py
  python jarvis_call.py --once
  python jarvis_call.py --text "xin chào"
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY_DIR = ROOT / "python"
sys.path.insert(0, str(PY_DIR))

# Load .env if present (simple parse, no extra dep required at runtime)
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import sounddevice as sd  # noqa: E402

from audio_core import (  # noqa: E402
    default_mic_index,
    listen,
    post_tts_pause,
    speak,
)
from llm import chat_completion, is_goodbye, resolve_llm_config  # noqa: E402


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def pick_mic(index: int) -> int:
    if index >= 0:
        return index
    return default_mic_index()


def print_banner(mic: int, lang: str) -> None:
    cfg = resolve_llm_config()
    backend = "llm" if cfg["api_key"] else "rules"
    try:
        mic_name = sd.query_devices(mic if mic >= 0 else sd.default.device[0])["name"]
    except Exception:
        mic_name = f"index={mic}"
    print("=== JARVISLAB VOICE CALL ===")
    print(f"Mic: {mic_name}")
    print(f"Lang: {lang} | AI: {backend} ({cfg['model'] if backend == 'llm' else 'rules'})")
    print("Nói tự nhiên. Nói 'tạm biệt' để kết thúc. Ctrl+C dừng.\n")


def conversation_loop(args: argparse.Namespace) -> int:
    lang = args.lang
    mic = pick_mic(args.mic)
    history: list[dict[str, str]] = []
    os.environ.setdefault("VOICE_LANGUAGE", lang)

    print_banner(mic, lang)

    if not args.no_greeting:
        greet = "Xin chào, tôi là Jarvis. Bạn cần gì nào?"
        print(f"🤖 Jarvis: {greet}")
        dur = speak(greet, lang)
        post_tts_pause(dur)

    turns = 0
    while args.max_turns <= 0 or turns < args.max_turns:
        try:
            if args.text and turns == 0:
                user = args.text.strip()
            else:
                print("🎤 Đang nghe... (nói đi)")
                t0 = time.time()
                user = listen(
                    lang=lang,
                    mic_index=mic,
                    timeout=args.listen_timeout,
                    wait_for_speech=True,
                )
                print(f"   (listen {time.time() - t0:.1f}s)", file=sys.stderr)

            if not user:
                print("(Chưa nghe rõ — nói lại gần mic hơn)")
                if args.once or args.text:
                    return 1
                continue

            print(f"👂 Bạn: {user}")
            t1 = time.time()
            reply, backend = chat_completion(user, history=history)
            print(f"   (llm {time.time() - t1:.1f}s [{backend}])", file=sys.stderr)
            print(f"🤖 Jarvis: {reply}")

            history.append({"role": "user", "content": user})
            history.append({"role": "assistant", "content": reply})
            # keep history short for voice
            if len(history) > 16:
                history = history[-16:]

            dur = speak(reply, lang)
            turns += 1

            if is_goodbye(user) or is_goodbye(reply):
                print("\nCuộc gọi kết thúc.")
                return 0
            if args.once or args.text:
                return 0

            post_tts_pause(dur)
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
            time.sleep(0.3)
            if args.once or args.text:
                return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JarvisLab voice call")
    p.add_argument("--lang", default=os.environ.get("VOICE_LANGUAGE", "vi-VN"))
    p.add_argument("--mic", type=int, default=env_int("VOICE_MIC_INDEX", -1))
    p.add_argument(
        "--listen-timeout",
        type=float,
        default=0.0,
        help="0 = wait until you speak (recommended)",
    )
    p.add_argument("--max-turns", type=int, default=0, help="0 = unlimited")
    p.add_argument("--once", action="store_true")
    p.add_argument("--text", default="", help="Inject text (skip mic)")
    p.add_argument("--no-greeting", action="store_true")
    return p


def main() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    args = build_parser().parse_args()
    raise SystemExit(conversation_loop(args))


if __name__ == "__main__":
    main()
