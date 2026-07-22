# CLAUDE.md

This file provides guidance to Claude Code (and other MCP-compatible agents) when working with this repository.

## Project Overview

**JarvisLab** is a bidirectional voice MCP server for Windows.
It exposes four tools — `voice_listen`, `voice_speak`, `voice_ask`, `list_audio_devices` — enabling AI agents to have real voice conversations with the user via microphone and speakers.

## Quick Start

```bash
npm install
node bin/mcp-voice-bridge.js   # starts the MCP stdio server
```

## Always-On Voice Conversation

The new tool `voice_wait_for_speech` is designed for hands-free voice chats. Unlike `voice_listen` (which times out), it will **block indefinitely** until the user starts speaking, record the whole utterance, and return the transcript. Combine it with `voice_speak` in a loop to build a continuous voice conversation.

Use the `/voice-chat` slash command to tell Claude Code to enter this loop automatically.

## Agent Auto-Discovery (project-level config files)

| Agent | Config file | Auto-load |
|-------|-------------|-----------|
| Claude Code | `.mcp.json` + `.claude/settings.json` | Yes — just run `claude` |
| OpenAI Codex | `.codex/config.toml` | Yes |
| Mistral Vibe | `.vibe/config.toml` | Yes |
| Gemini CLI | `.gemini/settings.json` | Yes |
| Goose | `.goose/config.yaml` | Yes |
| OpenCode | `opencode.json` | Yes |
| Cursor | `.cursor/mcp.json` | Yes |
| **Hermes** | *global only* | Manual — see below |
| **OpenClaw** | *global only* | Manual — see below |

### Hermes (NousResearch) — global setup

Hermes does not support project-level MCP config yet. Add manually to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  jarvislab:
    command: node
    args:
      - C:/Dev/JarvisLab/bin/mcp-voice-bridge.js
    env:
      PYTHONUTF8: "1"
      PYTHONIOENCODING: "utf-8"
```

Or use the Hermes CLI (from the project directory):
```bash
hermes mcp add jarvislab node bin/mcp-voice-bridge.js
```

### OpenClaw — global setup

OpenClaw manages MCP servers via CLI:
```bash
# From the project directory
openclaw mcp add jarvislab --command "node" --args "bin/mcp-voice-bridge.js" --env PYTHONUTF8=1 --env PYTHONIOENCODING=utf-8

# Verify
openclaw mcp status
```

The repo includes `.mcp.json`, so Claude Code auto-discovers the server when opened from this directory:
```bash
cd JarvisLab
claude
```

## Architecture

**Node.js MCP server** (`src/server.js`) communicates over stdio (JSON-RPC 2.0).
Audio I/O happens via **Python subprocesses** in the `python/` directory.

```
voice_listen  → python/listen.py   → sounddevice (VAD) + Google STT
voice_speak   → python/speak.py    → edge-tts (Microsoft neural) + Windows SAPI fallback
voice_ask     → speak.py + listen.py (sequential)
list_audio_devices → python/devices.py → sounddevice.query_devices()
```

**IMPORTANT — stdout is sacred:**
Never log to stdout in `src/server.js`. All debug output must go to stderr.
The MCP stdio protocol uses stdout exclusively for JSON-RPC messages.

## Commands

```bash
npm start                  # Run MCP server
npm run test:devices       # List audio devices
npm run test:speak         # Test TTS output
npm run test:listen        # Test mic recording + STT
npm run call               # Standalone phone-call loop
npm test                   # Full self-test
```

## Tools

| Tool | Description |
|------|-------------|
| `voice_speak(text, language?)` | Speak text to user (TTS) |
| `voice_listen(timeout_seconds?, language?)` | Record mic + transcribe (STT) with a timeout |
| `voice_wait_for_speech(language?)` | **Always-on listen**: blocks until the user speaks and finishes, then transcribes |
| `voice_ask(question, timeout_seconds?, language?)` | Speak question, wait for spoken answer |
| `list_audio_devices()` | List microphones and speakers |

## Supported Languages (40+ BCP-47 codes)

`vi-VN` (default), `en-US`/`en-GB`/`en-AU`/`en-CA`/`en-IN`, `zh-CN`/`zh-TW`/`zh-HK`, `ja-JP`, `ko-KR`, `fr-FR`/`fr-CA`, `de-DE`/`de-AT`, `es-ES`/`es-MX`/`es-US`/`es-AR`, `it-IT`, `pt-PT`/`pt-BR`, `ru-RU`, `nl-NL`, `pl-PL`, `sv-SE`, `nb-NO`, `da-DK`, `fi-FI`, `cs-CZ`, `el-GR`, `uk-UA`, `ro-RO`, `hu-HU`, `ar-SA`/`ar-EG`/`ar-AE`, `he-IL`, `tr-TR`, `hi-IN`, `bn-IN`, `ta-IN`, `te-IN`, `th-TH`, `id-ID`, `ms-MY`, `fil-PH`, and more.

## Slash Commands (Claude Code Skills)

- `/listen` — activate microphone and listen to user
- `/voice-chat` — enter an always-on voice conversation loop: listen → respond → speak → repeat
- `/voice [lang]` — change TTS language/voice

## Configuration

Set environment variables to customize behavior:

| Variable | Default | Description |
|---|---|---|
| `VOICE_LANGUAGE` | `vi-VN` | Default language |
| `VOICE_MIC_INDEX` | `-1` | Microphone device index |
| `VOICE_PYTHON` | `python` | Python executable path |

## Dependencies

**Node.js:** `@modelcontextprotocol/sdk`, `dotenv`

**Python (must be installed):**
```bash
pip install sounddevice numpy SpeechRecognition edge-tts
```

## Key Constraints

- **Windows only for TTS playback** (uses PowerShell `System.Windows.Media.MediaPlayer`)
- Falls back to Windows SAPI if edge-tts playback fails
- STT uses Google Speech Recognition (requires internet)
- No sox, ffmpeg, or external audio tools required
