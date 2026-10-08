// Responsibility: persist atomic JSON documents, research sessions, and ordered events.
import fs from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';

export function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), {recursive: true});
  const tmp = `${file}.${randomUUID()}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), 'utf8');
  fs.renameSync(tmp, file);
}
export function readJson(file, fallback = null) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}
export function safeName(value) {
  if (typeof value !== 'string' || !/^[a-zA-Z0-9_-]{1,100}$/.test(value)) throw new Error('名称只能包含英文、数字、下划线和横线。');
  return value;
}
export class Store {
  constructor(config) {
    this.config = config;
    this.listeners = new Set();
    this.recent = [];
  }
  emit(type, detail = {}) {
    const event = {id: randomUUID(), time: new Date().toISOString(), type, ...detail};
    const file = path.join(this.config.data, 'events.jsonl');
    fs.appendFileSync(file, JSON.stringify(event) + '\n');
    this.recent.push(event);
    if (this.recent.length > 150) this.recent.shift();
    for (const listener of this.listeners) listener(event);
    return event;
  }
  sessionFile(id) { return path.join(this.config.data, 'sessions', `${safeName(id)}.json`); }
  saveSession(id, messages) {
    const old = readJson(this.sessionFile(id), {});
    writeJson(this.sessionFile(id), {id, created: old.created || new Date().toISOString(), updated: new Date().toISOString(), model: this.config.model, messages});
  }
  loadSession(id) { return readJson(this.sessionFile(id), {id, messages: []}); }
  sessions() {
    const folder = path.join(this.config.data, 'sessions');
    if (!fs.existsSync(folder)) return [];
    return fs.readdirSync(folder).filter(f => f.endsWith('.json')).map(f => {
      const s = readJson(path.join(folder, f));
      const first = s.messages.find(m => m.role === 'user');
      const text=typeof first?.content==='string'?first.content:(first?.content||[]).filter(c=>c.type==='text').map(c=>c.text).join(' ');
      return {id: s.id, updated: s.updated, title: text?text.slice(0,70):s.id};
    }).sort((a,b) => b.updated.localeCompare(a.updated));
  }
}
