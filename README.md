# JarvisLab

> Nói chuyện **ngoài đời** giữa người và AI qua mic + loa — MCP server cho agent (Claude/Codex/Hermes/…) và chế độ gọi điện standalone.

## Tính năng

- **`voice_speak`** – AI đọc to (TTS neural edge-tts, fallback SAPI)
- **`voice_listen`** – Nghe mic + VAD + Google STT
- **`voice_wait_for_speech`** – Chờ đến khi bạn nói (always-on)
- **`voice_ask`** – Hỏi to → chờ trả lời
- **`list_audio_devices`** – Liệt kê mic/loa
- **`jarvis_call.py`** – Vòng gọi điện: nghe → LLM → nói → lặp (tiếng Việt)

## Cài đặt

```bash
cd C:/Dev/JarvisLab
npm install
pip install -r requirements.txt
cp .env.example .env   # hoặc dùng .env có sẵn
```

## Chạy thử

```bash
# Self-test đầy đủ
npm test

# Thiết bị / TTS / nghe
npm run test:devices
npm run test:speak
npm run test:listen

# Gọi điện standalone (LLM qua xAI OAuth Hermes hoặc JARVIS_API_KEY)
npm run call
# hoặc
python jarvis_call.py
python jarvis_call.py --text "Xin chào" --no-greeting   # dry-run không mic
```

## Always-on voice với agent

```
voice_wait_for_speech → hiểu ý → voice_speak → lặp
```

Nói "tạm biệt" / "bye" / "thôi" để dừng.

### Claude Code

`/voice-chat` trong project này.

### Hermes

```bash
hermes mcp add jarvislab node C:/Dev/JarvisLab/bin/mcp-voice-bridge.js
hermes mcp test jarvislab
```

Hoặc trong config:

```yaml
mcp_servers:
  jarvislab:
    command: node
    args:
      - C:/Dev/JarvisLab/bin/mcp-voice-bridge.js
    env:
      PYTHONUTF8: "1"
      PYTHONIOENCODING: "utf-8"
      VOICE_LANGUAGE: "vi-VN"
```

### Agents auto-discovery

| Agent | Config |
|-------|--------|
| Claude Code | `.mcp.json` + `.claude/` |
| Codex | `.codex/config.toml` |
| Cursor | `.cursor/mcp.json` |
| Gemini CLI | `.gemini/settings.json` |
| Goose | `.goose/config.yaml` |
| OpenCode | `opencode.json` |

## Cấu trúc

```
JarvisLab/
├── bin/mcp-voice-bridge.js   # MCP stdio entry
├── src/server.js             # MCP tools
├── src/config.js
├── python/
│   ├── speak.py              # TTS
│   ├── listen.py             # VAD + STT
│   ├── devices.py
│   └── llm.py                # xAI / OpenAI-compatible / rules
├── jarvis_call.py            # Phone-call loop
├── scripts/selftest.py
└── .env
```

## Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|--------|
| `VOICE_LANGUAGE` | `vi-VN` | Ngôn ngữ STT/TTS |
| `VOICE_MIC_INDEX` | `-1` | Index mic |
| `VOICE_GAIN` | `50` | Gain mic yếu |
| `VOICE_TTS_VOICE` | auto | Override edge-tts |
| `JARVIS_API_KEY` | (Hermes xAI OAuth) | LLM key |
| `JARVIS_BASE_URL` | `https://api.x.ai/v1` | LLM endpoint |
| `JARVIS_MODEL` | `grok-4-1-fast-non-reasoning` | Model |

## Tips mic yếu

1. `npm run test:devices` → chọn mic USB đúng index  
2. `.env`: `VOICE_MIC_INDEX=1`, `VOICE_GAIN=60`  
3. Nói rõ, cách mic ~20–40cm; sau TTS có delay chống echo (`VOICE_POST_TTS_DELAY`)
