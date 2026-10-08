// Responsibility: collect curated papers with provenance and extract local PDF text.
import fs from 'node:fs';
import path from 'node:path';
import {createHash, randomUUID} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {readJson, writeJson, safeName} from '../core/storage.mjs';
import {allowedPdf, downloadPdf} from './download.mjs';
export {allowedPdf} from './download.mjs';

const exec = promisify(execFile);
function bibtex(paper) {
  const escape = value => String(value).replace(/[{}]/g, '');
  return `@inproceedings{${paper.id},\n  title = {${escape(paper.title)}},\n  author = {${paper.authors.map(escape).join(' and ')}},\n  booktitle = {${paper.venue}},\n  year = {${paper.year}},\n  url = {${paper.source}}${paper.doi ? `,\n  doi = {${paper.doi}}` : ''}\n}\n`;
}

export class Library {
  constructor(config, store) {
    this.config = config; this.store = store;
    this.catalog = readJson(path.join(config.root, 'src', 'research', 'catalog.json'));
    this.importFile=path.join(config.data,'library.json');
    this.fallbacks=readJson(path.join(config.root,'src','research','fallbacks.json'),{});
  }
  all(){return [...this.catalog,...readJson(this.importFile,[])];}
  add(paper){if(this.all().some(p=>p.id===paper.id))return;safeName(paper.id);const valid={...paper,pdfs:paper.pdfs.filter(allowedPdf)};const imported=readJson(this.importFile,[]);imported.push(valid);writeJson(this.importFile,imported);}
  paper(id) {
    const paper = this.all().find(p => p.id === safeName(id));
    if (!paper) throw new Error('论文不在文献库中，请先从在线检索加入。');
    return paper;
  }
  folder(id) { this.paper(id); return path.join(this.config.data, 'papers', id); }
  list(query = '') {
    const normalized = query.trim().toLowerCase();
    const aliases = {'视觉': 'vision', '检测': 'detection', '智能体': 'agent', '微调': 'finetuning', '分割': 'segmentation', '语言': 'language', '全部': ''};
    const term = aliases[normalized] ?? normalized;
    return this.all().filter(p => !term || JSON.stringify(p).toLowerCase().includes(term)).map(p => ({...p, local: readJson(path.join(this.folder(p.id), 'metadata.json'), {status: 'not_collected'})}));
  }
  async collect(id, signal, progress = () => {}) {
    const paper = this.paper(id); const folder = this.folder(id);
    fs.mkdirSync(folder, {recursive: true});
    let metadata = readJson(path.join(folder, 'metadata.json'), {paper, status: 'not_collected'});
    const pdfFile = path.join(folder, 'original.pdf');
    const textFile = path.join(folder, 'text.md');
    if (metadata.status === 'ready' && fs.existsSync(pdfFile) && fs.existsSync(textFile)) return {id, cached: true, ...metadata};
    const save = () => writeJson(path.join(folder, 'metadata.json'), metadata);
    try {
      if(!paper.pdfs.length)throw new Error('未提供允许下载的开放获取 PDF。请从发表页人工确认；不绕过付费墙。');
      if (!fs.existsSync(pdfFile)) {
        const attempts = [];
        let result;
        const previouslyFailed = new Set((metadata.attempts || []).filter(a => a.error).map(a => a.url));
        const sources = [...new Set([...paper.pdfs, ...(this.fallbacks[paper.source] || [])])];
        // Prefer a newly added source on retry; still retain all original sources.
        sources.sort((a, b) => Number(previouslyFailed.has(a)) - Number(previouslyFailed.has(b)));
        for (const url of sources) {
          signal?.throwIfAborted(); progress(`下载 ${paper.short}：${new URL(url).hostname}`);
          try { result = await downloadPdf(url, signal, detail => progress(`下载 ${paper.short}：${detail}`)); break; }
          catch (error) { attempts.push({url, error: `${error.message}${error.cause?.code?` (${error.cause.code})`:''}`}); if (signal?.aborted) throw error; }
        }
        metadata.attempts=attempts;
        if (!result) throw new Error(`下载失败：${attempts.map(a => a.error).join('；')}`);
        const temp = `${pdfFile}.${randomUUID()}.tmp`;
        fs.writeFileSync(temp, result.data); fs.renameSync(temp, pdfFile);
        const host = new URL(result.url).hostname;
        const pdfVersion = host.includes('arxiv') ? 'arXiv 作者版本；发表出处另见 source' : host === 'pjreddie.com' ? '作者官网公开版本；发表出处另见 source' : '官方会议开放获取版本';
        metadata = {paper, status: 'downloaded', downloaded: new Date().toISOString(), pdfUrl: result.url, pdfVersion, sha256: createHash('sha256').update(result.data).digest('hex'), bytes: result.bytes, attempts};
        save();
      }
      signal?.throwIfAborted(); progress(`转换 ${paper.short}：PDF → 按页文本`);
      const result = await exec(this.config.python, ['-I', path.join(this.config.root, 'python', 'extract_pdf.py'), pdfFile, textFile], {signal, timeout: 90000, windowsHide: true, maxBuffer: 1024 * 1024});
      const extraction = JSON.parse(result.stdout.trim());
      metadata.status = 'ready'; metadata.extraction = extraction; metadata.converted = new Date().toISOString(); delete metadata.error;
      fs.writeFileSync(path.join(folder, 'citation.bib'), bibtex(paper), 'utf8');
      save(); this.store.emit('paper_collected', {id, pages: extraction.pages, pdfVersion: metadata.pdfVersion});
      return {id, ...metadata};
    } catch (error) { metadata.status = 'error'; metadata.error = error.message; save(); throw error; }
  }
  read(id, startPage = 1, pageCount = 3, maxCharacters = 11000) {
    const file = path.join(this.folder(id), 'text.md');
    if (!fs.existsSync(file)) throw new Error('尚未提取正文，请先收集论文。');
    const pages = fs.readFileSync(file, 'utf8').split(/(?=^## Page \d+\s*$)/m).slice(1);
    const start = Math.max(1, Math.trunc(startPage || 1));
    const count = Math.min(5, Math.max(1, Math.trunc(pageCount || 3)));
    const text = pages.slice(start - 1, start - 1 + count).join('\n');
    if (!text) throw new Error(`页码超出范围，共 ${pages.length} 页。`);
    return {id, title: this.paper(id).title, pages: pages.length, startPage: start, pageCount: count, text: maxCharacters===null?text:text.slice(0,maxCharacters), truncated: maxCharacters!==null&&text.length>maxCharacters, extractionWarning:'文本层提取可能有字体编码噪声、图表和公式缺失。只引用实际读到的文字，必要时查看原 PDF。', source: this.paper(id).source};
  }
  async collectMany(ids, signal, progress) {
    if (!Array.isArray(ids) || !ids.length || ids.length > 8) throw new Error('请选择 1 至 8 篇论文。');
    const selected = [...new Set(ids)].map(id => this.paper(id).id);
    const results = [];
    for (const id of selected) {
      signal?.throwIfAborted();
      try { const item = await this.collect(id, signal, progress); results.push({id, status: 'ready', pages: item.extraction.pages}); }
      catch (error) { if (signal?.aborted) throw error; results.push({id, status: 'error', error: error.message}); }
    }
    const folder = path.join(this.config.data, 'workspace'); fs.mkdirSync(folder, {recursive: true});
    const index = ['# 文献收集记录', '', `时间：${new Date().toISOString()}`, '', '这是来源和收集状态记录，不是模型生成的学术综述。', ''];
    for (const result of results) { const p = this.paper(result.id); index.push(`## ${p.short} · ${p.venue} ${p.year}`, '', p.title, '', `- 来源：${p.source}`, `- 结果：${result.status === 'ready' ? `已下载并提取 ${result.pages} 页` : `失败：${result.error}`}`, `- 本地目录：data/papers/${p.id}`, ''); }
    const name = `collection-${new Date().toISOString().replace(/[:.]/g, '-')}.md`;
    fs.writeFileSync(path.join(folder, name), index.join('\n'), 'utf8');
    const failed = results.filter(r => r.status !== 'ready').length;
    if (failed === results.length) throw new Error('本次论文全部收集失败，请查看文献库中对应的错误详情。');
    return {papers: results, ready: results.length - failed, failed, index: name};
  }
}
