// Responsibility: render research state and send user actions through local HTTP/SSE APIs.
import {createTranslationUI} from './translation.js';
const $ = selector => document.querySelector(selector);
const state = {selected: new Set(['react2023','attention2017','lora2022']), sessionId: localStorage.getItem('aiu4-session') || crypto.randomUUID(), activeJob: null, streaming: null, paper: null, seen: new Set()};
const statuses = {running:'运行中',completed:'已完成',failed:'失败',cancelled:'已停止',interrupted:'已中断',planned:'待运行',ready:'已整理',not_collected:'待收集',downloaded:'待转换',error:'需要重试'};
function element(tag,text,className) { const node = document.createElement(tag); if (text!==undefined) node.textContent=text; if(className)node.className=className; return node; }
function toast(text) { $('#toast').textContent=text; $('#toast').hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('#toast').hidden=true,6000); }
async function api(path, data) {
  const response = await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const value = await response.json(); if(!response.ok)throw new Error(value.error || '请求失败'); return value;
}
function action(label, handler, className='quiet') { const b=element('button',label,className); b.addEventListener('click',()=>Promise.resolve(handler()).catch(e=>toast(e.message))); return b; }
function empty(text) { return element('div',text,'empty'); }
function time(value) { return value ? new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}) : ''; }
const translation=createTranslationUI({api,element,action,toast,getSelected:()=>[...state.selected],onChange:()=>Promise.all([papers(),discoveries()]),onJob:()=>refresh()});

function navigate() {
  const view=location.hash.slice(1)||'overview';
  const current=['overview','discover','papers','chat','notes'].includes(view)?view:'overview';
  document.querySelectorAll('.view').forEach(n=>n.hidden=n.id!==current);
  document.querySelectorAll('nav a').forEach(n=>n.classList.toggle('active',n.dataset.view===current));
  $('#breadcrumb').textContent=$(`nav a[data-view="${current}"] span`).textContent;
}
async function status() {
  const value=await api('/api/status'); state.activeJob=value.activeJob;
  $('#model-state').textContent=value.model.ready?`${value.model.model} · 本地已就绪`:value.model.online?'Ollama 已启动 · 模型缺失':'Ollama 未连接';
  $('#model-state').className=`pill ${value.model.ready?'ready':'offline'}`;
  $('#count-papers').textContent=value.papers;$('#count-tools').textContent=value.tools.length;$('#count-notes').textContent=value.notes;$('#count-reviews').textContent=value.reviews;
  $('#discover-submit').disabled=!!value.activeJob;$('#collect').disabled=!!value.activeJob;
}
async function papers() {
  const list=await api(`/api/papers?q=${encodeURIComponent($('#paper-search').value)}`);
  $('#paper-list').replaceChildren();
  for(const paper of list) {
    const card=element('article',undefined,'paper-card'); const top=element('div',undefined,'paper-top');
    const checkbox=element('input');checkbox.type='checkbox';checkbox.checked=state.selected.has(paper.id);checkbox.setAttribute('aria-label',`选择 ${paper.short}`);checkbox.onchange=()=>checkbox.checked?state.selected.add(paper.id):state.selected.delete(paper.id);
    top.append(checkbox,element('strong',paper.short),element('span',statuses[paper.local.status]||paper.local.status,`badge ${paper.local.status==='error'?'error':''}`));
    card.append(top,translation.title(paper),element('div',`${paper.venue} ${paper.year} · ${paper.verified?'发表出处已核对':'元数据候选 / 出处待核对'}`,'meta'),element('p',paper.intro));
    translation.abstract(card,paper);const translated=translation.badge(paper.id);if(translated)card.append(translated);
    if(paper.local.pdfVersion)card.append(element('div',paper.local.pdfVersion,'meta'));
    if(paper.local.error)card.append(element('div',paper.local.error,'paper-error'));
    const actions=element('div',undefined,'paper-actions'); const link=element('a','发表来源 ↗');link.href=paper.source;link.target='_blank';link.rel='noopener noreferrer';actions.append(link);
    actions.append(action(translation.readLabel(),()=>translation.candidate(paper),'quiet'));
    if(paper.local.status==='ready'){actions.append(action('生成评阅',()=>{location.hash='chat';$('#prompt').value=`请阅读文献 ${paper.id} 的正文，分批读取相关页，核查研究问题、方法、实验与局限，然后用 save_review 保存带页码证据的中文评阅卡。未阅读全文或未核实的项目要明确说明。`;}));}
    card.append(actions);$('#paper-list').append(card);
  }
  if(!list.length)$('#paper-list').append(empty('精选目录中没有匹配项。可用英文关键词或短名称搜索。'));
}
async function jobs() {
  const values=await api('/api/jobs');$('#jobs').replaceChildren();
  if(!values.length)$('#jobs').append(empty('还没有任务。从文献库收集几篇论文开始。'));
  for(const job of values.slice(0,8)) {
    const row=element('div',undefined,'job'); const content=element('div',undefined,'job-content');
    content.append(element('strong',job.kind),element('small',job.error||`${job.progress} · ${time(job.started)}`));
    row.append(element('span',job.status==='completed'?'✓':job.status==='running'?'↻':'·','job-icon'),content,element('span',statuses[job.status]||job.status,`badge ${job.status==='failed'?'error':''}`));
    if(job.status==='running')row.append(action('停止',async()=>{await api('/api/cancel',{id:job.id});toast('正在停止任务…');}));
    if(job.result?.failed)content.append(element('small',`${job.result.ready} 篇成功，${job.result.failed} 篇失败。请查看文献库详情。`));
    $('#jobs').append(row);
  }
}
function message(role,text) {
  const node=element('div',undefined,`message ${role}`);node.append(element('span',role==='user'?'你 / RESEARCHER':'华小牛 / LOCAL AGENT','message-label'),element('span',text));$('#messages').append(node);$('#messages').scrollTop=$('#messages').scrollHeight;return node;
}
async function sessions() {
  const values=await api('/api/sessions');$('#sessions').replaceChildren();
  for(const item of values) { const b=action(item.title,async()=>{state.sessionId=item.id;localStorage.setItem('aiu4-session',item.id);await messages();await sessions();},item.id===state.sessionId?'selected':'');$('#sessions').append(b); }
  if(!values.length)$('#sessions').append(element('small','对话开始后自动保存。','muted'));
}
async function messages() {
  const value=await api(`/api/session?id=${encodeURIComponent(state.sessionId)}`);$('#messages').replaceChildren();state.streaming=null;
  for(const m of value.messages) {
    if(!['user','assistant'].includes(m.role))continue;
    const text=typeof m.content==='string'?m.content:(m.content||[]).filter(c=>c.type==='text').map(c=>c.text).join('\n');
    if(text)message(m.role,text);
    if(m.role==='assistant'&&m.stopReason==='error')message('assistant',`模型请求失败：${m.errorMessage||'未知错误'}`);
  }
  if(!$('#messages').children.length)$('#messages').append(empty('提出一个研究问题，让华小牛从证据开始。'));
  $('#session-label').textContent=`会话 ${state.sessionId.slice(0,8)} · 自动保存`;
}
async function notes() {
  const names=await api('/api/notes');$('#note-list').replaceChildren();
  for(const name of names.reverse())$('#note-list').append(action(name,async()=>{$('#note-content').textContent=(await api(`/api/note?name=${encodeURIComponent(name)}`)).text;},''));
  if(!names.length)$('#note-list').append(empty('还没有笔记。收集记录或 AI 保存的笔记会显示在这里。'));
}
async function discoveries() {
  const value=await api('/api/discovery');$('#discover-list').replaceChildren();$('#discover-warnings').replaceChildren();
  $('#discover-summary').textContent=value.query?`“${value.query}” → ${value.normalizedQuery} · ${value.papers.length} 篇候选 · ${time(value.fetched)}`:'输入研究关键词，从官方会议目录开始。';
  for(const warning of value.warnings||[])$('#discover-warnings').append(element('div',warning,'search-warning'));
  if(value.query&&!value.papers.length)$('#discover-list').append(empty('当前来源范围内没有命中。可换用更短英文关键词、降低起始年份，或勾选扩展索引。'));
  for(const p of value.papers) {
    const card=element('article',undefined,'paper-card');const top=element('div',undefined,'paper-top');
    top.append(element('strong',`${p.venue} ${p.year}`),element('span',p.verified?'官方出处已核对':'元数据待核对',`badge ${p.verified?'':'pending'}`));
    card.append(top,translation.title(p),element('p',p.authority),element('div',`检索词命中 ${p.match}/${p.matchTerms} · ${p.track||'正式会议论文'}`,'meta'));
    translation.abstract(card,p);const translated=translation.badge(p.id);if(translated)card.append(translated);
    const details=element('details');details.append(element('summary','查看筛选依据与待核验项'));
    for(const [key,label] of Object.entries({publication:'发表状态',relevance:'相关性',reproducibility:'复现条件',evidence:'实验证据',limitations:'局限',decision:'阅读建议'}))details.append(element('p',`${label}：${p.quality[key]}`));
    if(p.code){const code=element('a','官方目录的代码链接 ↗');code.href=p.code;code.target='_blank';code.rel='noopener noreferrer';details.append(code);}
    card.append(details);const actions=element('div',undefined,'paper-actions');const link=element('a','核查发表来源 ↗');link.href=p.source;link.target='_blank';link.rel='noopener noreferrer';actions.append(link);
    actions.append(action('加入文献库',async()=>{await api('/api/import',{id:p.id});await papers();toast('已加入文献库，可选择下载与阅读。');},'button secondary'),action(translation.readLabel(),()=>translation.candidate(p),'quiet'));card.append(actions);$('#discover-list').append(card);
  }
}
async function refresh() { await Promise.all([status(),translation.refresh()]); await Promise.all([papers(),jobs(),sessions(),notes(),discoveries()]); }
$('#refresh').onclick=()=>refresh().catch(e=>toast(e.message));
$('#collect').onclick=async()=>{try{await api('/api/collect',{ids:[...state.selected]});toast('论文收集已启动，概览中可查看进度。');await refresh();}catch(e){toast(e.message);}};
$('#select-vision').onclick=()=>{state.selected=new Set(['yolo2016','resnet2016','sam2023','vit2021']);$('#paper-search').value='';papers().catch(e=>toast(e.message));};
$('#paper-search').oninput=()=>{clearTimeout(papers.timer);papers.timer=setTimeout(()=>papers().catch(e=>toast(e.message)),250);};
$('#new-session').onclick=()=>{state.sessionId=crypto.randomUUID();localStorage.setItem('aiu4-session',state.sessionId);messages().catch(e=>toast(e.message));sessions().catch(e=>toast(e.message));};
$('#chat-form').onsubmit=async event=>{
  event.preventDefault();const prompt=$('#prompt').value.trim();if(!prompt)return;
  try {await api('/api/chat',{prompt,sessionId:state.sessionId});localStorage.setItem('aiu4-session',state.sessionId);$('#messages .empty')?.remove();message('user',prompt);$('#prompt').value='';state.streaming=null;await refresh();}
  catch(error){toast(error.message);}
};
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{$('#prompt').value=b.dataset.prompt;$('#prompt').focus();});
$('#discover-form').onsubmit=async event=>{event.preventDefault();try{await api('/api/discover',{query:$('#discover-query').value.trim(),minYear:Number($('#discover-year').value),limit:20,broad:$('#discover-broad').checked});toast('检索已启动，可在工作概览查看进度。');await refresh();}catch(error){toast(error.message);}};
const events=new EventSource('/api/events');
events.onmessage=event=>{
  const value=JSON.parse(event.data);
  if(value.id){if(state.seen.has(value.id))return;state.seen.add(value.id);if(state.seen.size>1000)state.seen.delete(state.seen.values().next().value);}
  translation.onEvent(value);
  if(value.type==='text_delta'&&value.sessionId===state.sessionId){$('#messages .empty')?.remove();if(!state.streaming)state.streaming=message('assistant','');state.streaming.lastChild.textContent+=value.delta;$('#messages').scrollTop=$('#messages').scrollHeight;}
  if(value.type==='message'&&value.sessionId===state.sessionId&&value.message.role==='assistant')messages().catch(e=>toast(e.message));
  if(value.type==='job_progress'||value.type==='job_started')jobs().catch(e=>toast(e.message));
  if(value.type==='job_finished'){refresh().catch(e=>toast(e.message));messages().catch(e=>toast(e.message));if(value.job.status==='failed')toast(value.job.error);else if(value.job.status==='completed')toast(`${value.job.kind}已完成`);}
  if(value.type==='paper_collected')papers().catch(e=>toast(e.message));
};
events.onerror=()=>{$('#model-state').textContent='工作台连接中断，正在重连…';};
window.addEventListener('hashchange',navigate);navigate();refresh().then(messages).catch(error=>toast(error.message));
