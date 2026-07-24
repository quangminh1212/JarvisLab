#!/usr/bin/env python3
"""JarvisLab self-test — devices, TTS, STT(file), LLM, MCP tool list."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "python"
NODE = ROOT / "bin" / "mcp-voice-bridge.js"
results: list[tuple[str, bool, str]] = []


def ok(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def run(cmd: list[str], timeout: float = 120, env: dict | None = None) -> subprocess.CompletedProcess:
    e = os.environ.copy()
    e.setdefault("PYTHONUTF8", "1")
    e.setdefault("PYTHONIOENCODING", "utf-8")
    e["VOICE_QUIET"] = "1"
    if env:
        e.update(env)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(ROOT),
        env=e,
    )


def test_imports() -> None:
    try:
        import edge_tts  # noqa
        import numpy  # noqa
        import sounddevice  # noqa
        import speech_recognition  # noqa

        ok("python_deps", True)
    except Exception as e:
        ok("python_deps", False, str(e))


def test_devices() -> None:
    r = run([sys.executable, str(PY / "devices.py")], timeout=20)
    if r.returncode != 0:
        ok("devices", False, r.stderr[-200:])
        return
    try:
        data = json.loads(r.stdout)
        inputs = [d for d in data if d.get("is_input")]
        ok("devices", len(inputs) > 0, f"{len(inputs)} input device(s)")
    except Exception as e:
        ok("devices", False, str(e))


def test_tts() -> None:
    r = run(
        [sys.executable, str(PY / "speak.py"), "Kiểm tra giọng nói Jarvis Lab.", "vi-VN"],
        timeout=90,
    )
    ok("tts_speak", r.returncode == 0 and "OK" in r.stdout, r.stdout.strip()[:80] or r.stderr[-120:])


def test_stt_file() -> None:
    try:
        import asyncio
        import subprocess as sp

        import edge_tts
        import imageio_ffmpeg
    except Exception as e:
        ok("stt_file", False, f"missing dep: {e}")
        return

    async def synth(path: str, text: str) -> None:
        await edge_tts.Communicate(text, "vi-VN-HoaiMyNeural").save(path)

    mp3 = tempfile.mktemp(suffix=".mp3")
    wav = tempfile.mktemp(suffix=".wav")
    try:
        asyncio.run(synth(mp3, "Xin chào Jarvis, kiểm tra nhận dạng giọng nói"))
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        sp.run([ff, "-y", "-i", mp3, "-ac", "1", "-ar", "16000", wav], capture_output=True, check=False)
        r = run([sys.executable, str(PY / "listen.py"), "--wav", wav, "vi-VN"], timeout=60)
        text = (r.stdout or "").strip()
        # loose match — Google STT is imperfect
        hit = any(k in text.lower() for k in ("chào", "jarvis", "kiểm", "nhận", "giọng", "nói", "xin"))
        ok("stt_file", bool(text) and hit, f"got: {text!r}")
    except Exception as e:
        ok("stt_file", False, str(e))
    finally:
        for p in (mp3, wav):
            try:
                os.unlink(p)
            except Exception:
                pass


def test_llm() -> None:
    r = run([sys.executable, str(PY / "llm.py"), "Xin chào, trả lời đúng một câu ngắn"], timeout=45)
    out = (r.stdout or "").strip()
    ok("llm", r.returncode == 0 and len(out) > 3, out[:120])


def test_call_text() -> None:
    r = run(
        [sys.executable, str(ROOT / "jarvis_call.py"), "--text", "Xin chào Jarvis", "--no-greeting"],
        timeout=120,
    )
    out = (r.stdout or "") + (r.stderr or "")
    ok("voice_call_text", r.returncode == 0 and "Jarvis" in out, out[-200:].replace("\n", " | "))


def test_npm() -> None:
    nm = ROOT / "node_modules" / "@modelcontextprotocol" / "sdk"
    ok("npm_sdk", nm.exists(), str(nm))


def test_mcp_list_tools() -> None:
    """List tools via official MCP SDK client helper."""
    helper = ROOT / "scripts" / "mcp_list.js"
    if not (ROOT / "node_modules" / "@modelcontextprotocol" / "sdk").exists():
        ok("mcp_tools", False, "npm install missing")
        return
    r = run(["node", str(helper)], timeout=30)
    names = [x for x in (r.stdout or "").strip().split(",") if x]
    need = {
        "voice_speak",
        "voice_listen",
        "voice_ask",
        "voice_wait_for_speech",
        "list_audio_devices",
    }
    ok(
        "mcp_tools",
        r.returncode == 0 and need.issubset(set(names)),
        ",".join(names) or (r.stderr or "")[-160:],
    )


def _ensure_utf8_stdio() -> None:
    """Avoid UnicodeEncodeError on Windows consoles using cp1252."""
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main() -> int:
    _ensure_utf8_stdio()
    print("JarvisLab self-test\n" + "=" * 40)
    test_imports()
    test_npm()
    test_devices()
    test_tts()
    test_stt_file()
    test_llm()
    test_call_text()
    test_mcp_list_tools()
    print("=" * 40)
    failed = [n for n, p, _ in results if not p]
    print(f"Result: {len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("Failed:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
