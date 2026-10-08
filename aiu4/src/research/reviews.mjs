// Responsibility: store evidence-based reading cards without claiming independent scientific verification.
import path from 'node:path';
import fs from 'node:fs';
import {randomUUID} from 'node:crypto';
import {Type} from 'typebox';
import {readJson,writeJson} from '../core/storage.mjs';
import {result} from '../tools/workspace.mjs';

export class Reviews {
  constructor(config,library,workspace){this.folder=path.join(config.data,'reviews');this.library=library;this.workspace=workspace;}
  list(){if(!fs.existsSync(this.folder))return [];return fs.readdirSync(this.folder).filter(x=>x.endsWith('.json')).map(x=>readJson(path.join(this.folder,x))).sort((a,b)=>b.created.localeCompare(a.created));}
  save(card){
    const paper=this.library.paper(card.id),local=this.library.list().find(p=>p.id===paper.id).local;
    if(local.status!=='ready')throw new Error('请先下载并阅读原文，再写评阅卡。');
    if(!card.pages.length||card.pages.some(p=>!Number.isInteger(p)||p<1||p>local.extraction.pages))throw new Error('证据页码无效。');
    for(const key of ['question','method','strengths','limitations','reproducibility','recommendation'])if(typeof card[key]!=='string'||!card[key].trim()||card[key].length>3500)throw new Error(`${key} 需要 1 至 3500 字。`);
    const value={...card,title:paper.title,venue:paper.venue,year:paper.year,source:paper.source,created:new Date().toISOString(),status:'AI 阅读草稿，需人工核查'};
    const name=`review-${paper.id}-${randomUUID().slice(0,8)}`;
    const sections=[['研究问题',card.question],['方法',card.method],['证据与优点',card.strengths],['局限与未核验项',card.limitations],['复现条件',card.reproducibility],['阅读建议',card.recommendation]];
    const text=[`# ${paper.title} · 阅读评阅卡`,'',`状态：${value.status}`,`出处：${paper.venue} ${paper.year} · ${paper.source}`,`引用证据页：${card.pages.join(', ')}`,'',...sections.flatMap(([h,t])=>[`## ${h}`,'',t,''])].join('\n');
    this.workspace.write(`${name}.md`,text);writeJson(path.join(this.folder,`${name}.json`),value);return {...value,note:`${name}.md`};
  }
  tools(){return [{name:'save_review',label:'保存论文评阅卡',description:'阅读全文相关页后，保存含研究问题、方法、证据页、局限和复现条件的中文评阅草稿。未核实的字段明确写未核实；不自动给出质量总分。',parameters:Type.Object({id:Type.String(),pages:Type.Array(Type.Integer({minimum:1}),{minItems:1,maxItems:30}),question:Type.String(),method:Type.String(),strengths:Type.String(),limitations:Type.String(),reproducibility:Type.String(),recommendation:Type.String()}),execute:async(_,p)=>result(this.save(p))}];}
}
