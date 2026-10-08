// Responsibility: present optional bilingual lists, full-paper actions, and paragraph-paired reading through APIs.
export function createTranslationUI({api,element,action,toast,getSelected,onChange,onJob}) {
  const $=selector=>document.querySelector(selector);
  let mode=localStorage.getItem('aiu4-translation-mode')==='bilingual'?'bilingual':'original';
  let snapshot={papers:{},metadata:{}};
  let reader=null,pendingJob=null,timer=null,renderVersion=0;
  const labels={not_started:'未翻译',running:'翻译中',partial:'可继续',paused:'已暂停',error:'翻译需重试',ready:'全文已翻译'};
  function syncMode(){
    document.querySelectorAll('[data-translation-mode]').forEach(n=>n.value=mode);
    document.querySelectorAll('[data-translate-list]').forEach(n=>n.disabled=mode==='original');
    $('#translate-selected').disabled=mode==='original';
    document.querySelectorAll('[data-translation-hint]').forEach(n=>n.textContent=mode==='original'?'不调用翻译模型，阅读英文原文。可以随时切换为全文中英对照。':'每段保留英文原文并紧接中文译文。列表按钮翻译标题/摘要；每篇论文的全文入口会翻译全部可提取正文。');
  }
  async function changeMode(value){
    mode=value==='bilingual'?'bilingual':'original';localStorage.setItem('aiu4-translation-mode',mode);syncMode();
    await onChange();if(reader&&$('#reader').open)await renderReader();
  }
  async function refresh(){snapshot=await api('/api/translations');}
  function title(paper){
    const wrap=element('div',undefined,'bilingual-title');wrap.dataset.paperId=paper.id;wrap.append(element('h3',paper.title));
    if(mode==='bilingual'){
      const translated=snapshot.metadata[paper.id]?.paragraphs.find(p=>p.kind==='title')?.zh;
      wrap.append(element('p',translated||'标题待翻译 · 可点击上方“翻译本页标题/摘要”',translated?'translated-title':'translation-placeholder'));
    }
    return wrap;
  }
  function abstract(card,paper){
    if(!paper.abstract)return;
    const box=element('details',undefined,'abstract-preview');box.append(element('summary','摘要 / Abstract'));
    for(const [index,text] of paper.abstract.split(/\n\s*\n/).entries()){
      if(!text.trim())continue;
      const pair=element('div',undefined,'paragraph-pair compact');pair.append(element('small','EN · 英文原文'),element('p',text));
      if(mode==='bilingual'){const zh=snapshot.metadata[paper.id]?.paragraphs.find(p=>p.id===`abstract-${index+1}`)?.zh;pair.append(element('small','ZH · 中文翻译'),element('p',zh||'此段尚未翻译。',zh?'translated-text':'translation-placeholder'));}box.append(pair);
    }
    card.append(box);
  }
  function badge(id){
    if(mode==='original')return null;
    const value=snapshot.papers[id];
    return element('div',value?`${labels[value.status]||value.status}${value.totalParagraphs?` · ${value.completedParagraphs}/${value.totalParagraphs} 段`:''}`:'全文未翻译','translation-card-state');
  }
  function showLoading(id,text){
    reader={id,page:1,total:0};$('#reader-title').textContent='论文阅读';$('#reader-text').replaceChildren(element('div',text,'empty'));
    $('#reader-status').textContent=text;$('#reader-translate').hidden=mode==='original';$('#bilingual-link').hidden=true;
    $('#prev-page').disabled=true;$('#next-page').disabled=true;$('#page-label').textContent='准备全文';
    $('#pdf-link').href=`/api/pdf?id=${encodeURIComponent(id)}`;if(!$('#reader').open)$('#reader').showModal();
  }
  async function startFull(ids,openFirst=true){
    if(!ids.length)throw new Error('请先勾选需要翻译的论文。');
    const job=await api('/api/translate',{ids});pendingJob=job.id;
    mode='bilingual';localStorage.setItem('aiu4-translation-mode',mode);syncMode();
    if(openFirst){showLoading(ids[0],'正在准备整篇论文，已完成译文会逐段显示。');await renderReader();}
    toast('全文翻译已启动，可在工作概览停止；再次开始会继续已有进度。');await onJob();
  }
  async function openPaper(id,page=1){
    reader={id,page,total:0};await renderReader();
    if(mode==='bilingual'&&snapshot.papers[id]?.status!=='ready'&&!snapshot.papers[id]?.completed&&$('#reader-translate').hidden===false){
      try{await startFull([id]);}catch(error){toast(error.message);}
    }
  }
  async function candidate(paper){
    if(!(paper.id in snapshot.papers))await api('/api/import',{id:paper.id});
    if(mode==='bilingual'){
      if(snapshot.papers[paper.id]?.status==='ready')await openPaper(paper.id);else await startFull([paper.id]);
    }else{
      try{await api(`/api/paper?id=${encodeURIComponent(paper.id)}&page=1`);await openPaper(paper.id);}
      catch(error){const job=await api('/api/collect',{ids:[paper.id]});pendingJob=job.id;showLoading(paper.id,'正在收集原文，完成后打开英文正文。');toast('原文收集已启动。');await onJob();}
    }
  }
  async function renderReader(){
    if(!reader)return;
    const version=++renderVersion,current={...reader},scroll=$('#reader-text').scrollTop;
    const endpoint=mode==='bilingual'?'/api/translation':'/api/paper';
    let result;
    try{result=await api(`${endpoint}?id=${encodeURIComponent(current.id)}&page=${current.page}`);}
    catch(error){$('#reader-status').textContent=error.message;return;}
    if(version!==renderVersion)return;
    reader.total=result.pages;$('#reader-title').textContent=result.title;
    $('#pdf-link').href=`/api/pdf?id=${encodeURIComponent(current.id)}`;
    $('#page-label').textContent=result.pages?`第 ${current.page}–${Math.min(current.page+2,result.pages)} 页 / 共 ${result.pages} 页`:'正在识别页码';
    $('#prev-page').disabled=current.page<=1;$('#next-page').disabled=current.page+3>result.pages;
    $('#reader-text').replaceChildren();$('#reader-translate').hidden=mode==='original'||result.status==='ready';
    $('#reader-translate').textContent=result.completed?'继续翻译全文':'开始翻译全文';
    $('#bilingual-link').href=`/api/bilingual-file?id=${encodeURIComponent(current.id)}`;$('#bilingual-link').download=`${current.id}-中英对照.md`;
    $('#bilingual-link').hidden=mode==='original'||result.status!=='ready';
    if(mode==='original'){
      $('#reader-status').textContent='英文原文 · 不调用翻译模型';$('#reader-text').append(element('pre',result.text,'original-text'));
    }else{
      $('#reader-status').textContent=`${labels[result.status]||result.status} · ${result.completedParagraphs}/${result.totalParagraphs} 段${result.error?' · '+result.error:''}`;
      if(result.warning)$('#reader-text').append(element('div',result.warning,'reading-warning'));
      if(result.emptyPages?.length)$('#reader-text').append(element('div',`第 ${result.emptyPages.join('、')} 页没有可提取文字，请查看原始 PDF。`,'reading-warning'));
      if(!result.paragraphs.length)$('#reader-text').append(element('div',result.status==='not_started'?'选择“开始翻译全文”，整篇正文会逐段翻译。':'当前页暂时没有文字或尚在识别段落。','empty'));
      let page=0;
      for(const p of result.paragraphs){
        if(p.page!==page){page=p.page;$('#reader-text').append(element('h3',`第 ${page} 页`,'reader-page-title'));}
        const pair=element('article',undefined,'paragraph-pair');
        pair.append(element('small',`EN · 英文原文 · ${p.id}`),element('p',p.original,'source-text'),element('small','ZH · 中文翻译'),element('p',p.zh??'此段尚未翻译，完成后会自动显示。',p.zh===null?'translation-placeholder':'translated-text'));
        $('#reader-text').append(pair);
      }
    }
    if(!$('#reader').open)$('#reader').showModal();$('#reader-text').scrollTop=scroll;
  }
  function onEvent(value){
    if(value.type==='translation_progress'||value.type==='translation_finished'){
      if(reader?.id===value.paperId&&$('#reader').open){clearTimeout(timer);timer=setTimeout(()=>renderReader().catch(e=>toast(e.message)),350);}
    }
    if(value.type==='job_finished'&&pendingJob===value.job.id){
      pendingJob=null;refresh().then(()=>{if(reader&&$('#reader').open)return renderReader();}).catch(e=>toast(e.message));
    }
  }
  document.querySelectorAll('[data-translation-mode]').forEach(n=>n.onchange=()=>changeMode(n.value).catch(e=>toast(e.message)));
  document.querySelectorAll('[data-translate-list]').forEach(n=>n.onclick=async()=>{try{const scope=n.dataset.translateList;const root=scope==='discover'?'#discover-list':'#paper-list';const ids=[...document.querySelectorAll(`${root} [data-paper-id]`)].map(x=>x.dataset.paperId);await api('/api/translate-metadata',{scope,ids});toast('正在翻译本页全部标题及可获得的摘要；全文请从每篇论文进入。');await onJob();}catch(e){toast(e.message);}});
  $('#translate-selected').onclick=()=>startFull(getSelected(),false).catch(e=>toast(e.message));
  $('#reader-translate').onclick=()=>startFull([reader.id]).catch(e=>toast(e.message));
  $('#close-reader').onclick=()=>{$('#reader').close();renderVersion++;};
  $('#reader').addEventListener('close',()=>{renderVersion++;});
  $('#prev-page').onclick=()=>{reader.page=Math.max(1,reader.page-3);$('#reader-text').scrollTop=0;renderReader().catch(e=>toast(e.message));};
  $('#next-page').onclick=()=>{reader.page+=3;$('#reader-text').scrollTop=0;renderReader().catch(e=>toast(e.message));};
  syncMode();
  return {refresh,title,abstract,badge,openPaper,candidate,onEvent,readLabel:()=>mode==='bilingual'?'全文中英对照':'阅读英文原文'};
}
