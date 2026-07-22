#!/usr/bin/env node
/**
 * JarvisLab – MCP Voice Bridge CLI entry point
 *
 * Run:  node bin/mcp-voice-bridge.js
 * Call: python jarvis_call.py
 *
 * Hermes:
 *   hermes mcp add jarvislab --command node --args "C:/Dev/JarvisLab/bin/mcp-voice-bridge.js"
 */
import { startServer } from '../src/server.js';

if (process.stdout.setEncoding) process.stdout.setEncoding('utf8');
if (process.stderr.setEncoding) process.stderr.setEncoding('utf8');

process.env.PYTHONIOENCODING = process.env.PYTHONIOENCODING || 'utf-8';
process.env.PYTHONUTF8 = '1';

startServer().catch((err) => {
  process.stderr.write(`[jarvislab] Fatal: ${err.message}\n`);
  process.exit(1);
});
