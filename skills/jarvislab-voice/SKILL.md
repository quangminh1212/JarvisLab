---
name: jarvislab-voice
description: "JarvisLab voice bridge via MCP — talk with user by mic/speaker like a phone call. Use when user wants voice chat, nói chuyện giọng nói, gọi điện AI, voice_speak/listen, jarvis call."
version: 1.3.0
platforms: [windows]
metadata:
  hermes:
    tags: [JarvisLab, voice, STT, TTS, MCP, phone-call, mic, Hermes]
    related_skills: [hermes-agent]
---

# JarvisLab Voice (Hermes)

**SoT:** `C:\Dev\JarvisLab` · MCP server **`jarvislab`**

Goal: talk **like a real phone call** — listen → LLM → speak → loop.

## Tools (Hermes names)

After MCP discovery (double underscore):

| Hermes tool name | What it does |
|------------------|--------------|
| `mcp__jarvislab__voice_speak` | TTS — speak text to speakers |
| `mcp__jarvislab__voice_listen` | Mic + VAD + STT (timeout) |
| `mcp__jarvislab__voice_wait_for_speech` | Wait until user speaks (always-on) |
| `mcp__jarvislab__voice_ask` | Speak question → listen answer |
| `mcp__jarvislab__list_audio_devices` | List mic/speakers |

Some builds use `mcp_jarvislab_*` (single underscore). Match whatever tool list shows.

## Phone-call loop (always-on)

```
1. mcp__jarvislab__voice_speak  "Xin chào..."
2. loop:
     text = mcp__jarvislab__voice_wait_for_speech
     if goodbye in text → speak bye → stop
     think short reply (1–3 sentences, plain speech, no markdown)
     mcp__jarvislab__voice_speak reply
```

Stop phrases: tạm biệt, bye, thôi, dừng, cúp máy.

## Rules for spoken replies

- Vietnamese by default (`language: vi-VN`) unless user switches
- Short, natural, no markdown/bullets/emoji dump
- After TTS, do not call listen until speak returns (echo)
- If listen empty → ask user to speak closer to mic / retry once

## Attach / diagnose

```powershell
powershell -File C:\Dev\JarvisLab\scripts\install.ps1
hermes mcp list
hermes mcp test jarvislab
cd C:/Dev/JarvisLab
npm test
node scripts/mcp_list.js
npm run test:auto   # headless, no human speech
```

## Standalone (no MCP)

```bash
cd C:/Dev/JarvisLab
npm run call
python jarvis_call.py --text "Xin chào" --no-greeting
```

## Config

- Hermes: `%LOCALAPPDATA%/hermes/config.yaml` → `mcp_servers.jarvislab`
- Fix env-in-args bug: `python C:/Dev/JarvisLab/scripts/fix_hermes_mcp.py`
- Required env: `VOICE_PYTHON`, `PYTHONUTF8=1`, `VOICE_LANGUAGE=vi-VN`, gain/timeout knobs
- Mic USB weak: `VOICE_GAIN=70`, `VOICE_THRESHOLD=0.002`, `VOICE_SILENCE_SEC=0.75`

## Pitfalls

1. MCP env stuck in `args` → re-run `fix_hermes_mcp.py`
2. No `VOICE_PYTHON` under Hermes filtered child env → audio scripts fail
3. Block on live mic when user asked auto-test → use inject WAV / `test:auto`
4. Skill not loaded → session still works if MCP tools present, but prefer `/jarvislab-voice`
