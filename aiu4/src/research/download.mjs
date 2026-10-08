// Responsibility: download bounded PDFs from verified public sources with readable progress and timeouts.
const MAX_BYTES = 40 * 1024 * 1024;
const HOSTS = new Set(['openaccess.thecvf.com', 'arxiv.org', 'export.arxiv.org', 'openreview.net', 'papers.nips.cc', 'papers.neurips.cc', 'proceedings.neurips.cc', 'aclanthology.org', 'proceedings.mlr.press']);

export function allowedPdf(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && !u.username && !u.password && (
      HOSTS.has(u.hostname) ||
      (u.hostname === 'raw.githubusercontent.com' && /^\/mlresearch\/v\d+\/main\/assets\//.test(u.pathname)) ||
      (u.hostname === 'pjreddie.com' && u.pathname === '/static/papers/yolo_1.pdf')
    );
  } catch { return false; }
}

export async function downloadPdf(initialUrl, signal, progress = () => {}) {
  let url = initialUrl;
  for (let redirects = 0; redirects < 5; redirects++) {
    if (!allowedPdf(url)) throw new Error('论文下载地址不在已核对的公开来源名单中。');
    const host = new URL(url).hostname;
    const deadline = new AbortController();
    let timer = setTimeout(() => deadline.abort(new Error(`${host}：30 秒内未收到响应，尝试其他来源。`)), 30000);
    const requestSignal = signal ? AbortSignal.any([signal, deadline.signal]) : deadline.signal;
    try {
      progress(`${host}，正在连接`);
      const response = await fetch(url, {redirect: 'manual', signal: requestSignal, headers: {'User-Agent': 'AIU4ResearchHarness/0.1 (local educational literature collector)'}});
      clearTimeout(timer);
      timer = setTimeout(() => deadline.abort(new Error(`${host}：PDF 传输超过 180 秒，尝试其他来源。`)), 180000);
      if ([301, 302, 303, 307, 308].includes(response.status)) {
        const location = response.headers.get('location');
        await response.body?.cancel();
        if (!location) throw new Error(`${host}：重定向缺少地址。`);
        url = new URL(location, url).href;
        continue;
      }
      if (!response.ok) {
        await response.body?.cancel();
        throw new Error(`${host}：HTTP ${response.status}`);
      }
      const declared = Number(response.headers.get('content-length'));
      if (declared > MAX_BYTES) { await response.body?.cancel(); throw new Error('PDF 超过 40MB 限制。'); }
      if (!response.body) throw new Error(`${host}：响应没有 PDF 内容。`);
      const parts = []; let size = 0; let lastUpdate = 0;
      for await (const chunk of response.body) {
        size += chunk.length;
        if (size > MAX_BYTES) throw new Error('PDF 超过 40MB 限制。');
        parts.push(chunk);
        if (Date.now() - lastUpdate >= 1500) {
          const total = declared > 0 ? ` / ${(declared / 1048576).toFixed(1)} MB` : ' MB';
          progress(`${host}，已接收 ${(size / 1048576).toFixed(1)}${total}`);
          lastUpdate = Date.now();
        }
      }
      const data = Buffer.concat(parts);
      if (!data.subarray(0, 5).equals(Buffer.from('%PDF-'))) throw new Error(`${host}：返回内容不是 PDF，可能遇到网络验证页面。`);
      progress(`${host}，下载完成 ${(size / 1048576).toFixed(1)} MB`);
      return {data, url, bytes: size};
    } catch (error) {
      if (signal?.aborted) throw signal.reason || error;
      if (deadline.signal.aborted) throw deadline.signal.reason;
      if (error.message === 'fetch failed') throw new Error(`${host}：网络连接失败${error.cause?.code ? ` (${error.cause.code})` : ''}`);
      throw error;
    } finally { clearTimeout(timer); }
  }
  throw new Error('重定向次数过多。');
}
