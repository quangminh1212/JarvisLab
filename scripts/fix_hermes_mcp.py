#!/usr/bin/env python3
"""Fix Hermes mcp_servers.jarvislab config (env not args)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

CFG = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "hermes" / "config.yaml"
HV = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "hermes-agent" / "venv" / "Scripts" / "python.exe"
PY314 = Path(r"C:/Python314/python.exe")


def pick_python() -> str:
    for p in (HV, PY314, Path(sys.executable)):
        if p and p.exists():
            r = subprocess.run(
                [str(p), "-c", "import sounddevice,edge_tts,speech_recognition; print('ok')"],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0:
                return str(p).replace("\\", "/")
    return "python"


def main() -> None:
    py = pick_python()
    text = CFG.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    path_env = os.environ.get("Path") or os.environ.get("PATH") or ""
    data.setdefault("mcp_servers", {})
    data["mcp_servers"]["jarvislab"] = {
        "command": "node",
        "args": ["C:/Dev/JarvisLab/bin/mcp-voice-bridge.js"],
        "enabled": True,
        "timeout": 300,
        "connect_timeout": 60,
        "env": {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "VOICE_LANGUAGE": "vi-VN",
            "VOICE_PYTHON": py,
            "VOICE_GAIN": "70",
            "VOICE_THRESHOLD": "0.002",
            "VOICE_SILENCE_SEC": "0.75",
            "VOICE_POST_TTS_DELAY": "0.35",
            "VOICE_CHIME": "0",
            "Path": str(Path(py).parent) + ";" + path_env,
        },
    }
    CFG.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print("OK jarvislab mcp fixed")
    print("VOICE_PYTHON=", py)
    print(yaml.dump(data["mcp_servers"]["jarvislab"], allow_unicode=True))


if __name__ == "__main__":
    main()
