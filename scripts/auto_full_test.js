#!/usr/bin/env node
/**
 * Full auto test of JarvisLab MCP tools — NO human speech required.
 * Uses VOICE_INJECT_WAV for STT path through the real MCP→Python pipeline.
 */
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { spawn } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { mkdtempSync, writeFileSync, rmSync, existsSync } from 'fs';
import { tmpdir } from 'os';
import { createRequire } from 'module';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const results = [];

function ok(name, passed, detail = '') {
  results.push({ name, passed, detail });
  console.log(`[${passed ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
}

function runPy(args, env = {}, timeoutMs = 120000) {
  return new Promise((resolve, reject) => {
    const py = process.env.VOICE_PYTHON || 'python';
    const proc = spawn(py, args, {
      cwd: root,
      env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', VOICE_QUIET: '1', VOICE_CHIME: '0', ...env },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let out = '', err = '';
    const t = setTimeout(() => { proc.kill(); reject(new Error('timeout ' + args.join(' '))); }, timeoutMs);
    proc.stdout.on('data', d => out += d.toString());
    proc.stderr.on('data', d => err += d.toString());
    proc.on('close', code => {
      clearTimeout(t);
      resolve({ code, out: out.trim(), err });
    });
    proc.on('error', reject);
  });
}

async function synthWav(text, wavPath) {
  const code = `
import asyncio, os, subprocess, sys, edge_tts, imageio_ffmpeg
mp3 = r'''${wavPath}'''.replace('.wav','.mp3')
wav = r'''${wavPath}'''
async def main():
    await edge_tts.Communicate(${JSON.stringify(text)}, 'vi-VN-HoaiMyNeural').save(mp3)
asyncio.run(main())
ff = imageio_ffmpeg.get_ffmpeg_exe()
subprocess.check_call([ff,'-y','-i',mp3,'-ac','1','-ar','16000',wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.unlink(mp3)
print('ok')
`;
  const r = await runPy(['-c', code], {}, 90000);
  if (r.code !== 0 || !existsSync(wavPath)) {
    throw new Error('synth fail: ' + r.err + r.out);
  }
}

async function main() {
  console.log('JarvisLab AUTO full test (no human speech)\n' + '='.repeat(44));
  const tmp = mkdtempSync(join(tmpdir(), 'jarvislab-'));
  const wav = join(tmp, 'utter.wav');

  try {
    // 0) synth phrase
    await synthWav('Xin chào Jarvis, bây giờ mấy giờ rồi', wav);
    ok('synth_wav', existsSync(wav), wav);

    // 1) CLI STT inject
    const stt = await runPy(
      [join(root, 'python', 'listen.py'), 'vi-VN', '5', '-1', '0'],
      { VOICE_INJECT_WAV: wav },
      60000,
    );
    const sttText = stt.out;
    const sttHit = /chào|jarvis|giờ|mấy|xin/i.test(sttText);
    ok('cli_inject_stt', stt.code === 0 && sttHit, JSON.stringify(sttText));

    // 2) MCP tools via SDK
    const transport = new StdioClientTransport({
      command: 'node',
      args: [join(root, 'bin', 'mcp-voice-bridge.js')],
      cwd: root,
      env: {
        ...process.env,
        PYTHONUTF8: '1',
        PYTHONIOENCODING: 'utf-8',
        VOICE_LANGUAGE: 'vi-VN',
        VOICE_CHIME: '0',
        VOICE_QUIET: '1',
        VOICE_PYTHON: process.env.VOICE_PYTHON || 'python',
      },
    });
    const client = new Client({ name: 'auto-test', version: '1.0.0' }, { capabilities: {} });
    await client.connect(transport);

    const listed = await client.listTools();
    const names = (listed.tools || []).map(t => t.name);
    const need = ['voice_speak', 'voice_listen', 'voice_wait_for_speech', 'voice_ask', 'list_audio_devices'];
    ok('mcp_list_tools', need.every(n => names.includes(n)), names.join(','));

    const dev = await client.callTool({ name: 'list_audio_devices', arguments: {} });
    const devText = JSON.stringify(dev);
    ok('mcp_list_audio_devices', /Microphone|DEFAULT_MIC|input/i.test(devText), devText.slice(0, 120));

    const speakRes = await client.callTool({
      name: 'voice_speak',
      arguments: { text: 'Kiểm tra tích hợp Hermes Jarvis Lab.', language: 'vi-VN' },
    });
    const speakText = JSON.stringify(speakRes);
    ok('mcp_voice_speak', /Spoken|voice/i.test(speakText) && !speakRes.isError, speakText.slice(0, 160));

    // listen via inject on a NEW client env — need restart with inject
    await client.close();

    const transport2 = new StdioClientTransport({
      command: 'node',
      args: [join(root, 'bin', 'mcp-voice-bridge.js')],
      cwd: root,
      env: {
        ...process.env,
        PYTHONUTF8: '1',
        PYTHONIOENCODING: 'utf-8',
        VOICE_LANGUAGE: 'vi-VN',
        VOICE_CHIME: '0',
        VOICE_INJECT_WAV: wav,
        VOICE_PYTHON: process.env.VOICE_PYTHON || 'python',
      },
    });
    const client2 = new Client({ name: 'auto-test-2', version: '1.0.0' }, { capabilities: {} });
    await client2.connect(transport2);

    const listenRes = await client2.callTool({
      name: 'voice_listen',
      arguments: { timeout_seconds: 10, language: 'vi-VN' },
    });
    const listenText = JSON.stringify(listenRes);
    ok(
      'mcp_voice_listen_inject',
      /chào|jarvis|giờ|mấy|xin/i.test(listenText) && !listenRes.isError,
      listenText.slice(0, 200),
    );

    // voice_ask with inject = speak question then STT inject answer
    const askRes = await client2.callTool({
      name: 'voice_ask',
      arguments: { question: 'Bạn khỏe không?', timeout_seconds: 10, language: 'vi-VN' },
    });
    const askText = JSON.stringify(askRes);
    ok(
      'mcp_voice_ask_inject',
      !askRes.isError && (/chào|jarvis|giờ|mấy|xin|Spoken|voice/i.test(askText)),
      askText.slice(0, 220),
    );

    await client2.close();

    // 3) dry call + llm
    const call = await runPy(
      [join(root, 'jarvis_call.py'), '--text', 'Xin chào Jarvis', '--no-greeting'],
      {},
      120000,
    );
    ok('jarvis_call_text', call.code === 0 && /Jarvis/i.test(call.out), call.out.slice(-180).replace(/\n/g, ' | '));

    // 4) e2e script
    const e2e = await runPy([join(root, 'scripts', 'e2e_conversation.py')], {}, 180000);
    ok('e2e_conversation', e2e.code === 0, (e2e.out + e2e.err).split('\n').filter(l => l.includes('PASS') || l.includes('FAIL') || l.includes('Result')).join(' | '));

  } catch (e) {
    ok('suite_exception', false, String(e && e.stack || e));
  } finally {
    try { rmSync(tmp, { recursive: true, force: true }); } catch {}
  }

  console.log('='.repeat(44));
  const failed = results.filter(r => !r.passed);
  console.log(`Result: ${results.length - failed.length}/${results.length} passed`);
  if (failed.length) {
    console.log('Failed:', failed.map(f => f.name).join(', '));
    process.exit(1);
  }
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
