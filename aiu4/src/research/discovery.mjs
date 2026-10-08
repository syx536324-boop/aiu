// Responsibility: search official proceedings and metadata indexes while retaining evidence and uncertainty.
import path from 'node:path';
import {createHash} from 'node:crypto';
import {readJson,writeJson,safeName} from '../core/storage.mjs';

const OFFICIAL = [
  {key:'icml2025',venue:'ICML',year:2025,url:'https://proceedings.mlr.press/v267/',kind:'pmlr'},
  {key:'neurips2025',venue:'NeurIPS',year:2025,url:'https://proceedings.neurips.cc/paper_files/paper/2025/vol38-main-conference',kind:'neurips'}
];
const ALIASES = {'多智能体':'multi agent','智能体':'agent','目标检测':'object detection','计算机视觉':'computer vision','大语言模型':'large language model','大模型':'language model','强化学习':'reinforcement learning','扩散模型':'diffusion','图像分割':'segmentation','推理':'reasoning','微调':'fine tuning','量化':'quantization','机器人':'robot','注意力':'attention'};
const decode = s => String(s||'').replace(/<[^>]*>/g,' ').replace(/&#x([0-9a-f]+);/gi,(_,n)=>String.fromCodePoint(parseInt(n,16))).replace(/&#(\d+);/g,(_,n)=>String.fromCodePoint(Number(n))).replace(/&amp;/g,'&').replace(/&quot;/g,'"').replace(/&#39;|&apos;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&nbsp;/g,' ').replace(/\s+/g,' ').trim();
const idFor = source => `paper-${createHash('sha256').update(source).digest('hex').slice(0,20)}`;
const links = block => [...block.matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)].map(m=>({url:decode(m[1]),label:decode(m[2])}));
const positiveUrl = value => { try { const u=new URL(value);return u.protocol==='https:'?u.href:null; } catch{return null;} };
function venueName(value) {
  const s=String(value||'');
  if(/workshop|companion|findings|arxiv/i.test(s))return null;
  const names=[['CVPR',/\bCVPR\b|Computer Vision and Pattern Recognition/i],['ICCV',/\bICCV\b|International Conference on Computer Vision/i],['ECCV',/\bECCV\b|European Conference on Computer Vision/i],['ICLR',/\bICLR\b|International Conference on Learning Representations/i],['ICML',/\bICML\b|International Conference on Machine Learning/i],['NeurIPS',/\bNeurIPS\b|\bNIPS\b|Neural Information Processing Systems/i],['AAAI',/\bAAAI\b/],['IJCAI',/\bIJCAI\b|International Joint Conference on Artificial Intelligence/i],['ACL',/^ACL$|Annual Meeting of the Association for Computational Linguistics/i],['EMNLP',/\bEMNLP\b|Empirical Methods in Natural Language Processing/i],['NAACL',/\bNAACL\b|North American Chapter of the Association for Computational Linguistics/i],['TPAMI',/Pattern Analysis and Machine Intelligence/i],['JMLR',/Journal of Machine Learning Research/i]];
  return names.find(([,re])=>re.test(s))?.[0] || null;
}
function evidence(p,verified=false) {
  return {...p,short:p.short||p.title.slice(0,42),topics:p.topics||['ai'],verified:verified?new Date().toISOString().slice(0,10):null,
    verification:verified?'official_proceedings':'metadata_candidate',authority:verified?'已在官方主会目录核对题名及发表出处':'检索平台元数据指向重点会议/期刊，正式出处仍需核对',
    intro:p.intro||'先核查研究问题、实验设置、基线与局限，再决定是否精读。',
    quality:{publication:verified?'官方主会目录已核对':'元数据候选，待核对正式发表页',relevance:'按检索词匹配，需结合研究问题确认',reproducibility:p.code?'官方目录提供代码链接；尚未运行':'未核实代码、数据、算力需求',evidence:'尚未阅读全文核对基线、消融与统计证据',limitations:'尚未阅读全文核对局限与适用范围',decision:'候选阅读清单；不等于已判定高质量'}};
}
async function fetchText(url,signal,limit=10*1024*1024) {
  const response=await fetch(url,{signal:AbortSignal.any([signal||new AbortController().signal,AbortSignal.timeout(60000)]),headers:{'User-Agent':'AIU4-Literature/0.1'}});
  if(!response.ok){await response.body?.cancel();throw new Error(`HTTP ${response.status}${response.status===429?'：接口限流，请稍后再试':''}`);}
  let size=0;const chunks=[];for await(const chunk of response.body){size+=chunk.length;if(size>limit)throw new Error('目录响应超过大小限制。');chunks.push(chunk);}
  return Buffer.concat(chunks).toString('utf8');
}
function parseOfficial(html,source) {
  const papers=[];
  if(source.kind==='pmlr') {
    for(const match of html.matchAll(/<div\s+class="paper">([\s\S]*?)<\/div>/gi)) {
      const block=match[1], found=links(block), title=decode(block.match(/<p\s+class="title">([\s\S]*?)<\/p>/i)?.[1]);
      const url=found.find(x=>x.label==='abs')?.url, pdf=found.find(x=>/Download PDF/i.test(x.label))?.url;
      if(!title||!url||!pdf)continue;
      const review=found.find(x=>x.label==='OpenReview')?.url;let reviewPdf;try{const id=new URL(review).searchParams.get('id');if(id&&/^[\w-]+$/.test(id))reviewPdf=`https://openreview.net/pdf?id=${id}`;}catch{}
      papers.push(evidence({id:idFor(url),title,authors:decode(block.match(/<span\s+class="authors">([\s\S]*?)<\/span>/i)?.[1]).split(/,\s*/),venue:source.venue,year:source.year,source:url,pdfs:[pdf,reviewPdf].filter(Boolean),code:positiveUrl(found.find(x=>x.label==='Software')?.url),indexSource:source.url,track:'Main Conference'},true));
    }
  } else {
    for(const match of html.matchAll(/<li\b[^>]*>([\s\S]*?)<\/li>/gi)) {
      const block=match[1],found=links(block),link=found.find(x=>/\/hash\/.*-Abstract/i.test(x.url));
      if(!link||!/Main Conference Track/i.test(decode(block)))continue;
      const url=new URL(link.url,source.url).href;
      const pdf=url.replace('/hash/','/file/').replace(/-Abstract(?:-Conference)?\.html$/,'-Paper-Conference.pdf');
      const title=link.label;
      papers.push(evidence({id:idFor(url),title,authors:decode(block.match(/<span\s+class="paper-authors">([\s\S]*?)<\/span>/i)?.[1]).split(/,\s*/).filter(Boolean),venue:source.venue,year:source.year,source:url,pdfs:[pdf],indexSource:source.url,track:'Main Conference Track'},true));
    }
  }
  if(!papers.length)throw new Error('官方目录结构与解析规则不符，未将其标为已核对。');
  return papers;
}
function fromSemantic(p) {
  const venue=venueName(p.venue||p.publicationVenue?.name);if(!venue||!p.title)return null;
  const primary=p.externalIds?.DOI?`https://doi.org/${p.externalIds.DOI}`:p.externalIds?.ArXiv?`https://arxiv.org/abs/${p.externalIds.ArXiv}`:positiveUrl(p.url);
  if(!primary)return null;
  const pdfs=[positiveUrl(p.openAccessPdf?.url),p.externalIds?.ArXiv?`https://arxiv.org/pdf/${p.externalIds.ArXiv}`:null].filter(Boolean);
  return evidence({id:idFor(primary),title:p.title,authors:(p.authors||[]).map(a=>a.name),venue,year:p.year,source:primary,pdfs,doi:p.externalIds?.DOI,abstract:p.abstract||'',citationCount:p.citationCount,indexSource:'https://www.semanticscholar.org/',track:'待核对主会/期刊类别'});
}
function fromCrossref(p) {
  const full=(p['container-title']||[]).join(' '),venue=venueName(full);if(!venue||!['journal-article','proceedings-article'].includes(p.type))return null;
  const title=p.title?.[0];if(!title)return null;
  const source=`https://doi.org/${p.DOI}`;
  return evidence({id:idFor(source),title,authors:(p.author||[]).map(a=>`${a.given||''} ${a.family||''}`.trim()),venue,year:p.published?.['date-parts']?.[0]?.[0],source,pdfs:(p.link||[]).filter(x=>x['content-type']==='application/pdf').map(x=>positiveUrl(x.URL)).filter(Boolean),doi:p.DOI,abstract:decode(p.abstract||''),citationCount:p['is-referenced-by-count'],indexSource:'https://api.crossref.org/',track:p.type==='journal-article'?'Journal / 待核对':'Conference / 待核对'});
}

export class Discovery {
  constructor(config,store,library){this.config=config;this.store=store;this.library=library;this.folder=path.join(config.data,'discovery');}
  latest(){return readJson(path.join(this.folder,'latest.json'),{papers:[],warnings:[],sources:[],query:''});}
  async official(source,signal,warnings) {
    const file=path.join(this.folder,`${source.key}.json`),old=readJson(file);
    if(old && Date.now()-Date.parse(old.fetched)<86400000)return old.papers;
    try{const papers=parseOfficial(await fetchText(source.url,signal),source);writeJson(file,{fetched:new Date().toISOString(),source,papers});return papers;}
    catch(error){if(signal?.aborted)throw error;warnings.push(`${source.venue} ${source.year} 官方目录：${error.message}${old?'；使用已缓存目录':''}`);return old?.papers||[];}
  }
  async metadata(query,minYear,signal,warnings) {
    const file=path.join(this.folder,`meta-${idFor(`${query}/${minYear}`)}.json`),old=readJson(file);
    if(old&&Date.now()-Date.parse(old.fetched)<3600000)return old.papers;
    const endpoint=new URL('https://api.semanticscholar.org/graph/v1/paper/search/bulk');
    endpoint.search=new URLSearchParams({query,year:`${minYear}-`,sort:'citationCount:desc',venue:'CVPR,ICCV,ECCV,ICLR,NeurIPS,ICML,AAAI,IJCAI,ACL,EMNLP,NAACL',fields:'title,year,venue,publicationVenue,openAccessPdf,url,citationCount,authors,externalIds,abstract'}).toString();
    let papers=[];
    try{const value=JSON.parse(await fetchText(endpoint,signal));papers=(value.data||[]).slice(0,1000).map(fromSemantic).filter(Boolean);}
    catch(error){if(signal?.aborted)throw error;warnings.push(`Semantic Scholar：${error.message}；尝试 Crossref 备用索引。`);
      try{const url=new URL('https://api.crossref.org/works');url.search=new URLSearchParams({'query.bibliographic':query,rows:'100',filter:`from-pub-date:${minYear}-01-01`,select:'DOI,title,author,container-title,published,is-referenced-by-count,link,type,URL,abstract'}).toString();const value=JSON.parse(await fetchText(url,signal));papers=(value.message?.items||[]).map(fromCrossref).filter(Boolean);}
      catch(other){warnings.push(`Crossref：${other.message}`);}
    }
    if(papers.length)writeJson(file,{fetched:new Date().toISOString(),papers});
    return papers;
  }
  async search({query,minYear=2022,limit=20,broad=false},signal,progress=()=>{}) {
    if(typeof query!=='string'||!query.trim()||query.length>160)throw new Error('请输入 1 至 160 字的研究关键词。');
    const current=new Date().getFullYear();if(!Number.isInteger(minYear)||minYear<2010||minYear>current)throw new Error(`起始年份必须在 2010 至 ${current} 之间。`);
    if(!Number.isInteger(limit)||limit<1||limit>40)throw new Error('每次最多展示 40 篇。');
    const warnings=[],english=Object.entries(ALIASES).reduce((q,[cn,en])=>q.replaceAll(cn,en),query.trim()).toLowerCase();
    if(/[\u3400-\u9fff]/.test(english))warnings.push('部分中文未能映射到英文；可改用英文研究关键词提高命中率。');
    progress('读取官方主会目录与精选基础文献');
    const lists=await Promise.all(OFFICIAL.filter(s=>s.year>=minYear).map(s=>this.official(s,signal,warnings)));
    if(broad){progress('扩展到公开元数据索引；候选发表状态需要核对');lists.push(await this.metadata(english,minYear,signal,warnings));}
    const terms=english.split(/[^\p{L}\p{N}]+/u).filter(t=>t.length>1&&!['the','and','for','with','of','in','on','a','an','论文'].includes(t));
    if(!terms.length)throw new Error('请输入具体研究关键词。');
    const unique=new Map();
    for(const p of [...this.library.list().map(({local,...p})=>evidence(p,Boolean(p.verified))),...lists.flat()]) {
      if(p.year<minYear)continue;
      const title=p.title.toLowerCase(),abstract=(p.abstract||'').toLowerCase();let matched=0,score=0;
      for(const term of terms){const a=title.includes(term),b=abstract.includes(term);if(a||b){matched++;score+=a?3:1;}}
      if(matched<Math.ceil(terms.length*.6))continue;
      const key=p.title.toLowerCase().replace(/[^a-z0-9]/g,'');const item={...p,match:matched,matchTerms:terms.length,relevanceScore:score};
      if(!unique.has(key)||item.verification==='official_proceedings')unique.set(key,item);
    }
    const papers=[...unique.values()].sort((a,b)=>b.relevanceScore-a.relevanceScore||(a.verification==='official_proceedings'?-1:1)-(b.verification==='official_proceedings'?-1:1)||b.year-a.year).slice(0,limit);
    const result={query:query.trim(),normalizedQuery:english,minYear,broad,fetched:new Date().toISOString(),papers,warnings,sources:[...OFFICIAL.filter(s=>s.year>=minYear).map(s=>({venue:s.venue,year:s.year,url:s.url})),{venue:'精选基础文献',url:'local:catalog'},...(broad?[{venue:'公开元数据索引，非完整覆盖',url:'https://api.semanticscholar.org/'},{venue:'备用元数据索引',url:'https://api.crossref.org/'}]:[])],coverage:'官方在线目录目前覆盖 ICML 2025 与 NeurIPS 2025 主会；其余年份/会议可用扩展索引。不是全网或所有最新论文。排序依据关键词匹配；不代表学术质量排名。'};
    writeJson(path.join(this.folder,'latest.json'),result);
    const catalog=readJson(path.join(this.folder,'candidates.json'),{});for(const p of papers)catalog[p.id]=p;writeJson(path.join(this.folder,'candidates.json'),catalog);
    this.store.emit('search_completed',{query:result.query,count:papers.length});return result;
  }
  import(id){const paper=readJson(path.join(this.folder,'candidates.json'),{})[safeName(id)];if(!paper)throw new Error('请先在线检索这个候选。');this.library.add(paper);return paper;}
}
