import { createRequire } from 'module';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load .env if present (not required for MCP stdio mode)
const envPath = join(dirname(__dirname), '.env');
if (existsSync(envPath)) {
  const { config: loadEnv } = await import('dotenv');
  loadEnv({ path: envPath });
}

export const config = {
  // Python executable (can override if using venv or python3)
  python: process.env.VOICE_PYTHON || 'python',

  // Microphone device index (-1 = system default)
  micIndex: parseInt(process.env.VOICE_MIC_INDEX ?? '-1', 10),

  // Default language code for STT + TTS
  language: process.env.VOICE_LANGUAGE || 'vi-VN',

  // TTS voice override (edge-tts voice name)
  ttsVoice: process.env.VOICE_TTS_VOICE || null,

  // Path to Python helper scripts directory
  pythonDir: join(dirname(__dirname), 'python'),
};
