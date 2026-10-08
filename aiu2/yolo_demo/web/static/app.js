// Own browser controls and presentation state; all inference runs behind the local HTTP API.
const els = {
  model: document.querySelector('#modelSelect'), camera: document.querySelector('#cameraSelect'),
  confidence: document.querySelector('#confidence'), confidenceValue: document.querySelector('#confidenceValue'),
  start: document.querySelector('#startButton'), stop: document.querySelector('#stopButton'),
  image: document.querySelector('#streamImage'), empty: document.querySelector('#emptyState'),
  fps: document.querySelector('#fpsValue'), frames: document.querySelector('#framesValue'),
  deviceReason: document.querySelector('#deviceReason'),
  device: document.querySelector('#deviceValue'), state: document.querySelector('#stateText'),
  badge: document.querySelector('#liveBadge'), modelNote: document.querySelector('#modelNote'),
  frameModel: document.querySelector('#frameModel'), toast: document.querySelector('#toast'),
};
let toastTimer;
let lastStatusError = '';

function notify(message, error = false) {
  els.toast.textContent = message;
  els.toast.className = `toast show${error ? ' error' : ''}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { els.toast.className = 'toast'; }, 3600);
}

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `请求失败（${response.status}）`);
  return payload;
}

function renderStatus(status) {
  const running = Boolean(status.running);
  els.state.textContent = running ? '实时检测运行中' : (status.error ? '检测发生错误' : '本机服务已连接');
  document.querySelector('#appState').classList.toggle('running', running);
  els.badge.classList.toggle('active', running);
  els.badge.innerHTML = `<span></span>${running ? 'LIVE' : 'STANDBY'}`;
  els.start.disabled = running;
  els.stop.disabled = !running;
  els.fps.textContent = running ? Number(status.fps || 0).toFixed(1) : '—';
  els.frames.textContent = String(status.frames || 0);
  els.device.textContent = status.device || '待启动';
  els.deviceReason.textContent = status.device_reason || '自动选择设备：GPU 繁忙或显存不足时切换 CPU，恢复后切回 GPU。';
  if (status.gpu) {
    els.deviceReason.textContent += ` · GPU ${status.gpu.utilization.toFixed(0)}%，剩余显存 ${(status.gpu.free_mib / 1024).toFixed(1)}GB`;
  }
  if (status.model) {
    els.frameModel.textContent = status.model.toUpperCase();
    els.modelNote.textContent = status.weight_path?.includes('coco8_train')
      ? 'COCO8 示例权重，仅用于验证流程；不是针对自定义类别训练。'
      : 'YOLO11n 预训练权重；检测类别取决于所选模型包含的训练类别。';
  }
  if (running && !els.image.classList.contains('visible')) {
    els.empty.hidden = true;
    els.image.classList.add('visible');
    els.image.src = `/api/stream?attached=${Date.now()}`;
  }
  if (!running && els.image.classList.contains('visible')) {
    els.image.classList.remove('visible');
    els.image.removeAttribute('src');
    els.empty.hidden = false;
  }
  if (status.error && status.error !== lastStatusError) notify(status.error, true);
  lastStatusError = status.error || '';
}

async function loadConfig() {
  try {
    const config = await request('/api/config');
    els.model.replaceChildren(...config.weights.map((item) => {
      const option = document.createElement('option');
      option.value = item.path; option.textContent = item.label; return option;
    }));
    if (!config.weights.length) throw new Error('没有找到模型权重，请先完成示例训练。');
    els.frameModel.textContent = config.weights[0].label.toUpperCase();
    els.state.textContent = '本机服务已连接';
    renderStatus(await request('/api/status'));
  } catch (error) {
    els.state.textContent = '无法连接本机服务';
    notify(error.message, true);
  }
}

els.confidence.addEventListener('input', () => { els.confidenceValue.value = Number(els.confidence.value).toFixed(2); });
els.start.addEventListener('click', async () => {
  els.start.disabled = true;
  try {
    const result = await request('/api/start', { method: 'POST', body: JSON.stringify({
      camera: Number(els.camera.value), weight: els.model.value, confidence: Number(els.confidence.value),
    }) });
    els.empty.hidden = true;
    els.image.classList.add('visible');
    els.image.src = `/api/stream?started=${Date.now()}`;
    renderStatus(result.status);
    notify('摄像头推理已启动，首次加载模型可能需要几秒钟。');
  } catch (error) {
    els.start.disabled = false;
    notify(error.message, true);
  }
});
els.stop.addEventListener('click', async () => {
  els.stop.disabled = true;
  try { renderStatus((await request('/api/stop', { method: 'POST', body: '{}' })).status); notify('实时检测已停止。'); }
  catch (error) { notify(error.message, true); }
});

loadConfig();
setInterval(async () => {
  try { renderStatus(await request('/api/status')); } catch { /* Keep the current UI if a brief poll fails. */ }
}, 1000);
