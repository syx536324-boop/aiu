// Responsibility: run one resource-bounded job at a time and support cancellation.
import path from 'node:path';
import fs from 'node:fs';
import {randomUUID} from 'node:crypto';
import {readJson, writeJson} from './storage.mjs';

export class Jobs {
  constructor(config, store) { this.config = config; this.store = store; this.active = null; }
  start(kind, work, {timeoutSeconds=this.config.runTimeoutSeconds}={}) {
    if (this.active) throw new Error('已有任务运行，请等待完成或先停止。');
    if (!Number.isInteger(timeoutSeconds) || timeoutSeconds < 1 || timeoutSeconds > 7200) throw new Error('任务时间上限无效。');
    const id = randomUUID();
    const controller = new AbortController();
    const job = {id, kind, status: 'running', started: new Date().toISOString(), progress: '开始任务'};
    const save = () => writeJson(path.join(this.config.data, 'jobs', `${id}.json`), job);
    this.active = {id, controller};
    const progress = text => { job.progress = text; save(); this.store.emit('job_progress', {job}); };
    save(); this.store.emit('job_started', {job});
    const timer = setTimeout(() => controller.abort(new Error('任务超过时间上限。')), timeoutSeconds * 1000);
    Promise.resolve().then(() => work(controller.signal, progress)).then(result => {
      if (controller.signal.aborted) { job.status = 'cancelled'; job.error = '任务已停止，已生成的文件保留。'; }
      else { job.status = 'completed'; job.result = result; }
    }).catch(error => {
      job.status = controller.signal.aborted ? 'cancelled' : 'failed'; job.error = error.message;
    }).finally(() => {
      clearTimeout(timer); job.finished = new Date().toISOString(); save();
      this.active = null; this.store.emit('job_finished', {job});
    });
    return job;
  }
  cancel(id) {
    if (!this.active || this.active.id !== id) throw new Error('该任务没有在运行。');
    this.active.controller.abort(new Error('用户停止任务。'));
  }
  list() {
    const folder = path.join(this.config.data, 'jobs');
    if (!fs.existsSync(folder)) return [];
    return fs.readdirSync(folder).filter(f => f.endsWith('.json')).map(f => {
      const job = readJson(path.join(folder, f));
      if (job.status === 'running' && this.active?.id !== job.id) job.status = 'interrupted';
      return job;
    }).sort((a,b) => b.started.localeCompare(a.started)).slice(0,30);
  }
}
