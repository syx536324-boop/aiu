// Responsibility: expose collection and persistent research conversations in the terminal.
import readline from 'node:readline/promises';
import {randomUUID} from 'node:crypto';

export async function runCli({config,library,discovery,harness,store},args) {
  const command = args[0];
  if(command==='search'){const value=await discovery.search({query:args[1]||'agent',minYear:Number(args[2]||2022),broad:args.includes('--broad')},AbortSignal.timeout(120000),text=>console.log(text));console.log(JSON.stringify(value,null,2));return;}
  if(command==='import'){console.log(JSON.stringify(discovery.import(args[1]),null,2));return;}
  if (command === 'collect') {
    const ids = args.slice(1).length ? args.slice(1) : ['react2023','attention2017','lora2022'];
    const result = await library.collectMany(ids,AbortSignal.timeout(config.runTimeoutSeconds*1000),text=>console.log(text));
    console.log(JSON.stringify(result,null,2)); return;
  }
  if (command === 'chat') {
    const sessionId = args[1] || randomUUID();
    console.log(`会话 ${sessionId}；输入 /exit 退出。`);
    const reader = readline.createInterface({input:process.stdin,output:process.stdout});
    try {
      while (true) {
        const prompt = await reader.question('你 > ');
        if (prompt.trim() === '/exit') break;
        if (!prompt.trim()) continue;
        try { const result = await harness.chat(prompt,sessionId,AbortSignal.timeout(config.runTimeoutSeconds*1000),text=>console.log(`[${text}]`)); console.log(`华小牛 > ${result.text}`); }
        catch(error) { console.error(error.message); }
      }
    } finally { reader.close(); }
    return;
  }
  if (command === 'list') { console.log(JSON.stringify(library.list().map(p=>({id:p.id,title:p.title,venue:p.venue,year:p.year,status:p.local.status})),null,2)); return; }
  console.log('用法：node src/main.mjs serve | search "研究关键词" [起始年份] [--broad] | import 论文ID | collect [论文ID...] | chat [会话ID] | list');
}
