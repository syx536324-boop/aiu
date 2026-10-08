// Responsibility: supply public catalog data to the original UI without connecting to local services.
export const isPreview = true;
const catalogPromise = fetch(new URL('./catalog.json', import.meta.url)).then(response => {
  if (!response.ok) throw new Error('基础文献目录加载失败，请刷新页面。');
  return response.json();
});
const aliases = {'视觉':'vision','检测':'detection','智能体':'agent','微调':'finetuning','分割':'segmentation','语言':'language','全部':''};

export async function previewApi(path, data) {
  if (data !== undefined) throw new Error('当前是华小牛静态界面预览。检索、收集、翻译与对话请在本机华小牛中使用。');
  const route = new URL(path, 'https://preview.invalid');
  switch (route.pathname) {
    case '/api/status':
      return {activeJob:null,model:{online:false,ready:false},papers:0,tools:[],notes:0,reviews:0};
    case '/api/papers': {
      const query = (route.searchParams.get('q') || '').trim().toLowerCase();
      const term = aliases[query] ?? query;
      return (await catalogPromise).filter(paper => !term || JSON.stringify(paper).toLowerCase().includes(term))
        .map(paper => ({...paper,local:{status:'目录示例'}}));
    }
    case '/api/translations':
      return {papers:Object.fromEntries((await catalogPromise).map(paper => [paper.id,{status:'not_started',completed:0,total:0}])),metadata:{}};
    case '/api/jobs':
    case '/api/sessions':
    case '/api/notes':
      return [];
    case '/api/session':
      return {messages:[]};
    case '/api/discovery':
      return {query:'',normalizedQuery:'',papers:[],warnings:['公开静态预览不执行在线检索。基础文献目录可在“我的文献库”中浏览。']};
    default:
      throw new Error('此内容由本机版提供，公开预览不包含个人文献正文或翻译缓存。');
  }
}
