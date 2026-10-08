// Responsibility: expose local research APIs, static UI, and streamed progress events.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {modelStatus} from '../providers/ollama.mjs';
import {safeName} from '../core/storage.mjs';

function json(response, status, value) {
  response.writeHead(status, {'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store'});
  response.end(JSON.stringify(value));
}
async function body(request) {
  let data = ''; let bytes = 0;
  for await (const chunk of request) { bytes += chunk.length; if (bytes > 128*1024) throw new Error('请求超过大小限制。'); data += chunk; }
  return data ? JSON.parse(data) : {};
}
function serveFile(response, file, type) {
  if (!fs.existsSync(file)) return json(response,404,{error:'文件尚未生成。'});
  response.writeHead(200, {'Content-Type':type, 'X-Content-Type-Options':'nosniff'});
  fs.createReadStream(file).pipe(response);
}

export function serve({config,store,jobs,library,workspace,discovery,reviews,harness,translations}) {
  const url = `http://127.0.0.1:${config.port}`;
  const server = http.createServer(async (request,response) => {
    const allowedHosts = [`127.0.0.1:${config.port}`, `localhost:${config.port}`];
    if (!allowedHosts.includes(request.headers.host)) return json(response,403,{error:'只允许本机访问。'});
    if (request.headers.origin && ![url,`http://localhost:${config.port}`].includes(request.headers.origin)) return json(response,403,{error:'拒绝跨站请求。'});
    response.setHeader('X-Content-Type-Options','nosniff');
    response.setHeader('Referrer-Policy','no-referrer');
    response.setHeader('Content-Security-Policy',"default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
    try {
      const route = new URL(request.url,url);
      const pathname = route.pathname;
      if (request.method === 'GET') {
        if (pathname === '/api/status') return json(response,200,{app:'aiu4',name:config.name,port:config.port,root:config.root,model:await modelStatus(config),activeJob:jobs.active?.id || null,tools:harness.tools.map(t=>({name:t.name,label:t.label})),papers:library.list().filter(p=>p.local.status==='ready').length,notes:workspace.list().length,reviews:reviews.list().length});
        if (pathname === '/api/papers') return json(response,200,library.list(route.searchParams.get('q')||''));
        if (pathname === '/api/paper') return json(response,200,library.read(route.searchParams.get('id'),Number(route.searchParams.get('page')||1),3,null));
        if (pathname === '/api/translations') return json(response,200,translations.snapshot());
        if (pathname === '/api/translation') return json(response,200,translations.read(route.searchParams.get('id'),Number(route.searchParams.get('page')||1)));
        if (pathname === '/api/bilingual-file') return serveFile(response,path.join(library.folder(route.searchParams.get('id')),'bilingual.md'),'text/plain; charset=utf-8');
        if (pathname === '/api/jobs') return json(response,200,jobs.list());
        if (pathname === '/api/sessions') return json(response,200,store.sessions());
        if (pathname === '/api/session') return json(response,200,store.loadSession(safeName(route.searchParams.get('id'))));
        if (pathname === '/api/notes') return json(response,200,workspace.list());
        if (pathname === '/api/note') return json(response,200,{text:workspace.read(route.searchParams.get('name'))});
        if (pathname === '/api/discovery') return json(response,200,discovery.latest());
        if (pathname === '/api/reviews') return json(response,200,reviews.list());
        if (pathname === '/api/pdf') return serveFile(response,path.join(library.folder(route.searchParams.get('id')),'original.pdf'),'application/pdf');
        if (pathname === '/api/events') {
          response.writeHead(200,{'Content-Type':'text/event-stream; charset=utf-8','Cache-Control':'no-cache','Connection':'keep-alive'});
          const write = event => { if (!response.destroyed) response.write(`data: ${JSON.stringify(event)}\n\n`); };
          for (const event of store.recent.slice(-30)) write(event);
          store.listeners.add(write);
          const timer = setInterval(()=>response.write(': keepalive\n\n'),20000);
          request.on('close',()=>{store.listeners.delete(write);clearInterval(timer);});
          return;
        }
        const files = {'/':'index.html','/app.js':'app.js','/translation.js':'translation.js','/style.css':'style.css'};
        if (files[pathname]) return serveFile(response,path.join(config.root,'web',files[pathname]),pathname.endsWith('.js')?'text/javascript; charset=utf-8':pathname.endsWith('.css')?'text/css; charset=utf-8':'text/html; charset=utf-8');
        return json(response,404,{error:'页面不存在。'});
      }
      if (request.method === 'POST') {
        if (!String(request.headers['content-type']||'').startsWith('application/json')) return json(response,415,{error:'请使用 JSON 请求。'});
        const data = await body(request);
        if (pathname === '/api/translate') {
          const ids=Array.isArray(data.ids)?[...new Set(data.ids)]:[];
          if(!ids.length||ids.length>8)throw new Error('请选择 1 至 8 篇论文进行全文翻译。');
          const candidates=discovery.latest().papers;
          ids.forEach(id=>{safeName(id);if(!library.all().some(p=>p.id===id)&&!candidates.some(p=>p.id===id))throw new Error('论文不在文献库或当前检索结果中。');});
          return json(response,202,jobs.start('全文中英对照翻译',(signal,progress)=>translations.translateMany(ids,signal,progress),{timeoutSeconds:7200}));
        }
        if (pathname === '/api/translate-metadata') {
          if(!['discover','papers'].includes(data.scope))throw new Error('翻译列表范围无效。');
          return json(response,202,jobs.start('列表标题与摘要翻译',(signal,progress)=>translations.translateMetadata(data.scope,signal,progress,data.ids),{timeoutSeconds:1800}));
        }
        if (pathname === '/api/collect') {
          const ids = Array.isArray(data.ids) ? [...new Set(data.ids)] : [];
          if (!ids.length || ids.length > 8) throw new Error('请选择 1 至 8 篇论文。');
          ids.forEach(id=>library.paper(id));
          return json(response,202,jobs.start('论文收集',(signal,progress)=>library.collectMany(ids,signal,progress)));
        }
        if (pathname === '/api/chat') {
          if (typeof data.prompt !== 'string' || !data.prompt.trim() || data.prompt.length>8000) throw new Error('请输入 1 至 8000 字的研究问题。');
          const sessionId = safeName(data.sessionId || randomUUID());
          const job = jobs.start('研究对话',(signal,progress)=>harness.chat(data.prompt.trim(),sessionId,signal,progress));
          return json(response,202,{...job,sessionId});
        }
        if (pathname === '/api/cancel') { jobs.cancel(data.id); return json(response,200,{stopping:true}); }
        if (pathname === '/api/discover') return json(response,202,jobs.start('论文在线检索',(signal,progress)=>discovery.search(data,signal,progress)));
        if (pathname === '/api/import') return json(response,201,library.all().some(p=>p.id===data.id)?library.paper(data.id):discovery.import(data.id));
        return json(response,404,{error:'接口不存在。'});
      }
      json(response,405,{error:'不支持该请求方法。'});
    } catch(error) { if (!response.headersSent) json(response,400,{error:error.message}); else response.end(); }
  });
  server.requestTimeout = 30000;
  server.on('error',error=>{console.error(`启动失败：${error.message}`);process.exitCode=1;});
  server.listen(config.port,'127.0.0.1',()=>console.log(`华小牛 Research Harness: ${url}\n项目目录: ${config.root}`));
  return server;
}
