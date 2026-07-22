---
name: jarvislab-voice
description: "JarvisLab voice bridge via MCP — talk with user by mic/speaker like a phone call. Use when user wants voice chat, nói chuyện giọng nói, gọi điện AI, voice_speak/listen."
version: 1.0.0
---

# JarvisLab Voice (Hermes)

MCP server **jarvislab** exposes real-time voice I/O on this machine.

## Tools (names in Hermes)

After MCP discovery (this install uses **double underscore**):

| Hermes tool name | What it does |
|------------------|--------------|
| `mcp__jarvislab__voice_speak` | TTS — speak text to speakers |
| `mcp__jarvislab__voice_listen` | Mic + VAD + STT (timeout) |
| `mcp__jarvislab__voice_wait_for_speech` | Wait until user speaks (always-on) |
| `mcp__jarvislab__voice_ask` | Speak question → listen answer |
| `mcp__jarvislab__list_audio_devices` | List mic/speakers |

Some Hermes builds use `mcp_jarvislab_*` (single underscore). Match whatever `list tools` shows.

## Phone-call loop (always-on)

When user wants hands-free conversation:

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

## Standalone (no MCP)

```bash
cd C:/Dev/JarvisLab
npm run call
# or
python jarvis_call.py
```

## Diagnose

```bash
hermes mcp list
hermes mcp test jarvislab
cd C:/Dev/JarvisLab && npm test && node scripts/auto_full_test.js
npm run test:devices
```

## Config

Hermes: `~/AppData/Local/hermes/config.yaml` → `mcp_servers.jarvislab`  
Project: `C:/Dev/JarvisLab` — `.env` for gain/mic/language.
