// Responsibility: provide bounded access to research notes inside the project data folder.
import fs from 'node:fs';
import path from 'node:path';
import {Type} from 'typebox';

export function result(value) { return {content: [{type: 'text', text: JSON.stringify(value)}], details: value}; }
export class Workspace {
  constructor(config) { this.root = path.join(config.data, 'workspace'); fs.mkdirSync(this.root, {recursive: true}); }
  file(name) {
    if (typeof name !== 'string' || !/^[\p{L}\p{N}_ .-]{1,100}\.(md|json|csv|bib)$/u.test(name)) throw new Error('文件名须为无路径的 md/json/csv/bib 文件名。');
    const file = path.join(this.root, name);
    // Reject reparse points as well as path traversal.
    if (fs.existsSync(file) && fs.lstatSync(file).isSymbolicLink()) throw new Error('不允许访问符号链接。');
    if (fs.realpathSync(this.root) !== path.resolve(this.root)) throw new Error('工作目录不能是符号链接。');
    return file;
  }
  list() { return fs.readdirSync(this.root).filter(f => /\.(md|json|csv|bib)$/.test(f)); }
  read(name) { return fs.readFileSync(this.file(name), 'utf8').slice(0, 15000); }
  write(name, content) {
    if (typeof content !== 'string' || content.length > 60000) throw new Error('笔记超过大小限制。');
    const file = this.file(name);
    if (fs.existsSync(file)) throw new Error('同名文件已存在，请使用新名称保留旧版本。');
    fs.writeFileSync(file, content, {encoding: 'utf8', flag: 'wx'});
    return {file: name, characters: content.length};
  }
  tools() { return [
    {name: 'list_notes', label: '列出研究笔记', description: '列出本项目研究工作区的笔记文件。', parameters: Type.Object({}), execute: async () => result(this.list())},
    {name: 'read_note', label: '读取研究笔记', description: '读取工作区的一份研究笔记。', parameters: Type.Object({name: Type.String()}), execute: async (_,p) => result({name: p.name, text: this.read(p.name)})},
    {name: 'write_note', label: '保存研究笔记', description: '创建新 Markdown/JSON/CSV/BibTeX 笔记。已有文件不能覆盖，使用新版本文件名。', parameters: Type.Object({name: Type.String(), content: Type.String()}), execute: async (_,p) => result(this.write(p.name, p.content))}
  ]; }
}
