// Responsibility: load project configuration and resolve local runtime paths.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export function loadConfig() {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const defaults = JSON.parse(fs.readFileSync(path.join(root, 'config.example.json'), 'utf8'));
  const local = path.join(root, '.runtime', 'config.json');
  const config = {...defaults, ...(fs.existsSync(local) ? JSON.parse(fs.readFileSync(local, 'utf8')) : {})};
  config.root = root;
  config.data = path.join(root, 'data');
  config.python = path.join(root, '.venv', 'Scripts', 'python.exe');
  config.model = process.env.AIU4_MODEL || config.model;
  config.ollamaUrl = process.env.AIU4_OLLAMA_URL || config.ollamaUrl;
  const url = new URL(config.ollamaUrl);
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) throw new Error('本版本仅连接本机 Ollama。');
  if (!Number.isInteger(config.port) || config.port < 1024 || config.port > 65535) throw new Error('端口配置无效。');
  fs.mkdirSync(config.data, {recursive: true});
  return config;
}
