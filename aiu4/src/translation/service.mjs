// Responsibility: provide optional bilingual paper translation with paragraph pairing and resumable local caches.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {readJson,writeJson,safeName} from '../core/storage.mjs';
import {modelStatus} from '../providers/ollama.mjs';
import {translateSegments} from '../providers/translator.mjs';

const exec = promisify(execFile);
const hash = text => createHash('sha256').update(text).digest('hex');
const metadataHash = p => hash(JSON.stringify([p.title,p.abstract||'']));
function partsOf(text,id) {
  const parts=[]; let remaining=text;
  while (remaining.length) {
    let end=Math.min(1400,remaining.length);
    if(end<remaining.length){const space=remaining.lastIndexOf(' ',end);if(space>700)end=space+1;}
    const source=remaining.slice(0,end); remaining=remaining.slice(end);
    parts.push({id:`${id}-s${parts.length+1}`,source,zh:null});
  }
  return parts;
}
function counts(doc) {
  const parts=doc.paragraphs.flatMap(p=>p.parts);
  return {completed:parts.filter(p=>p.zh!==null).length,total:parts.length,completedParagraphs:doc.paragraphs.filter(p=>p.parts.every(s=>s.zh!==null)).length,totalParagraphs:doc.paragraphs.length};
}
function summary(doc) {return doc?{status:doc.status,model:doc.model,updated:doc.updated,error:doc.error,...counts(doc)}:{status:'not_started',completed:0,total:0,completedParagraphs:0,totalParagraphs:0};}

export class Translations {
  constructor(config,store,library,discovery){this.config=config;this.store=store;this.library=library;this.discovery=discovery;this.folder=path.join(config.data,'translations');}
  paperFile(id){return path.join(this.library.folder(id),'bilingual.json');}
  metadataFile(id){return path.join(this.folder,`meta-${safeName(id)}.json`);}
  document(sourceHash,paragraphs,extra={}){return {schemaVersion:1,sourceHash,model:this.config.model,status:'partial',paragraphs:paragraphs.map(p=>({...p,parts:partsOf(p.original,p.id)})),...extra};}
  current(doc,sourceHash){return doc?.schemaVersion===1&&doc.sourceHash===sourceHash&&doc.model===this.config.model;}
  snapshot(){
    const local=this.library.list(),papers={},metadata={};
    for(const p of local){const doc=readJson(this.paperFile(p.id));papers[p.id]=this.current(doc,p.local.sha256)?summary(doc):summary(null);}
    for(const p of [...local,...this.discovery.latest().papers]){const doc=readJson(this.metadataFile(p.id));if(this.current(doc,metadataHash(p)))metadata[p.id]={...summary(doc),paragraphs:doc.paragraphs.map(x=>({id:x.id,kind:x.kind,original:x.original,zh:x.parts.every(s=>s.zh!==null)?x.parts.map(s=>s.zh).join(''):null}))};}
    return {plugin:{id:'local-bilingual',name:'本地中英对照翻译',model:this.config.model},papers,metadata};
  }
  async ready(){const value=await modelStatus(this.config);if(!value.ready)throw new Error('翻译需要本机 Ollama 和 '+this.config.model+'，请先启动桌面“华小牛论文助手”。');}
  async runDocument(doc,file,signal,progress,label,id) {
    if(doc.status==='ready')return doc;
    const save=()=>{doc.updated=new Date().toISOString();writeJson(file,doc);};
    doc.status='running';delete doc.error;save();
    this.store.emit('translation_progress',{paperId:id,...summary(doc)});
    try {
      await this.ready();
      while(true){
        signal.throwIfAborted();
        const pending=doc.paragraphs.flatMap(p=>p.parts).filter(p=>p.zh===null);
        if(!pending.length)break;
        const batch=[];let size=0;
        for(const part of pending){if(batch.length>=6||(batch.length&&size+part.source.length>2200))break;batch.push(part);size+=part.source.length;}
        const before=counts(doc);progress(`${label}：${before.completedParagraphs}/${before.totalParagraphs} 段，${before.completed}/${before.total} 个片段`);
        // Non-language material remains paired with the original instead of being omitted.
        const prose=batch.filter(p=>/[a-zA-Z]{2}/.test(p.source));
        const values=new Map(prose.length?(await translateSegments(this.config,prose,signal)).map(v=>[v.id,v.zh]):[]);
        signal.throwIfAborted();
        for(const part of batch)part.zh=values.get(part.id)??part.source;
        save();this.store.emit('translation_progress',{paperId:id,...summary(doc)});
      }
      doc.status='ready';delete doc.error;save();
      const done=counts(doc);progress(`${label}：全部 ${done.totalParagraphs} 段已翻译`);
      this.store.emit('translation_finished',{paperId:id,...summary(doc)});return doc;
    }catch(error){doc.status=signal.aborted?'paused':'error';doc.error=signal.aborted?'翻译已停止，已完成部分保留。':error.message;save();throw error;}
  }
  async translatePaper(id,signal,progress){
    safeName(id);
    if(!this.library.all().some(p=>p.id===id))this.discovery.import(id);
    const local=await this.library.collect(id,signal,progress),paper=this.library.paper(id),file=this.paperFile(id);
    let doc=readJson(file);
    if(!this.current(doc,local.sha256)){
      progress(`识别 ${paper.short} 的全部正文段落`);
      const paragraphFile=path.join(this.library.folder(id),'paragraphs.json');
      await exec(this.config.python,['-I',path.join(this.config.root,'python','extract_paragraphs.py'),path.join(this.library.folder(id),'original.pdf'),paragraphFile],{signal,timeout:120000,windowsHide:true,maxBuffer:1024*1024});
      const extracted=readJson(paragraphFile);
      doc=this.document(local.sha256,extracted.paragraphs,{id,title:paper.title,pages:extracted.pages,emptyPages:extracted.emptyPages,warning:extracted.warning,source:paper.source,pdfUrl:local.pdfUrl,pdfVersion:local.pdfVersion,method:extracted.method});
    }
    const result=await this.runDocument(doc,file,signal,progress,`全文翻译 ${paper.short}`,id);
    const lines=[`# ${paper.title} · 中英逐段对照`,'',`来源：${paper.source}`,`PDF：${local.pdfUrl}`,`版本：${local.pdfVersion}`,`本地模型：${result.model}`,'','机器翻译，需核查术语、公式与数字。'+result.warning,''];
    let page=0;
    for(const p of result.paragraphs){if(p.page!==page){page=p.page;lines.push(`## 第 ${page} 页`,'');}lines.push(`### 段落 ${p.id}`,'','**English 原文**','',p.original,'','**中文翻译**','',p.parts.map(s=>s.zh).join(''),'');}
    const exportFile=path.join(this.library.folder(id),'bilingual.md');
    fs.writeFileSync(exportFile+'.tmp',lines.join('\n'),'utf8');fs.renameSync(exportFile+'.tmp',exportFile);
    return {id,...summary(result)};
  }
  async translateMany(ids,signal,progress){
    if(!Array.isArray(ids)||!ids.length||ids.length>8)throw new Error('请选择 1 至 8 篇论文进行全文翻译。');
    await this.ready();const results=[];
    for(const id of [...new Set(ids)]){
      signal.throwIfAborted();
      try{results.push(await this.translatePaper(id,signal,progress));}catch(error){if(signal.aborted)throw error;results.push({id,status:'error',error:error.message});}
    }
    const failed=results.filter(p=>p.status!=='ready').length;
    if(failed===results.length)throw new Error(results.map(p=>`${p.id}：${p.error}`).join('；'));
    return {papers:results,ready:results.length-failed,failed};
  }
  async translateMetadata(scope,signal,progress,ids){
    if(!['discover','papers'].includes(scope))throw new Error('翻译列表范围无效。');
    await this.ready();let list=scope==='discover'?this.discovery.latest().papers:this.library.list();const results=[];
    if(ids!==undefined){if(!Array.isArray(ids)||!ids.length||ids.length>100)throw new Error('列表翻译请选择 1 至 100 篇论文。');ids.forEach(safeName);if(ids.some(id=>!list.some(p=>p.id===id)))throw new Error('列表已变化，请刷新后再翻译。');const selected=new Set(ids);list=list.filter(p=>selected.has(p.id));}
    if(!list.length)throw new Error('当前列表没有论文。请先检索或加入文献库。');
    if(list.length>100)throw new Error('文献库超过 100 篇，请逐篇使用全文翻译。');
    for(const paper of list){
      signal.throwIfAborted();const file=this.metadataFile(paper.id);let doc=readJson(file);
      if(!this.current(doc,metadataHash(paper))){const paragraphs=[{id:'title',kind:'title',original:paper.title}];for(const [i,text] of (paper.abstract||'').split(/\n\s*\n/).entries())if(text.trim())paragraphs.push({id:`abstract-${i+1}`,kind:'abstract',original:text.trim()});doc=this.document(metadataHash(paper),paragraphs,{id:paper.id});}
      try{await this.runDocument(doc,file,signal,progress,`列表翻译 ${paper.short||paper.title}`,paper.id);results.push({id:paper.id,status:'ready'});}catch(error){if(signal.aborted)throw error;results.push({id:paper.id,status:'error',error:error.message});}
    }
    const failed=results.filter(p=>p.status!=='ready').length;if(failed===results.length)throw new Error('列表翻译失败：'+results[0]?.error);
    return {papers:results,ready:results.length-failed,failed,scope};
  }
  read(id,startPage=1){
    const paper=this.library.paper(id),local=readJson(path.join(this.library.folder(id),'metadata.json'),{}),doc=readJson(this.paperFile(id));
    if(!this.current(doc,local.sha256))return {id,title:paper.title,pages:local.extraction?.pages||0,...summary(null),paragraphs:[]};
    const page=Math.max(1,Math.trunc(startPage||1));
    return {id,title:doc.title,pages:doc.pages,emptyPages:doc.emptyPages,warning:doc.warning,pdfVersion:doc.pdfVersion,...summary(doc),paragraphs:doc.paragraphs.filter(p=>p.page>=page&&p.page<page+3).map(p=>({id:p.id,page:p.page,original:p.original,zh:p.parts.every(s=>s.zh!==null)?p.parts.map(s=>s.zh).join(''):null}))};
  }
}
