#!/usr/bin/env node
/** List JarvisLab MCP tools via official SDK client. */
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const transport = new StdioClientTransport({
  command: 'node',
  args: [join(root, 'bin', 'mcp-voice-bridge.js')],
  cwd: root,
  env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
});
const client = new Client({ name: 'jarvislab-selftest', version: '1.0.0' }, { capabilities: {} });
await client.connect(transport);
const res = await client.listTools();
const names = (res.tools || []).map((t) => t.name);
console.log(names.join(','));
await client.close();
process.exit(names.includes('voice_speak') && names.includes('voice_listen') ? 0 : 1);
