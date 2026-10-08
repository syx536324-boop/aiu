"""Sample NVIDIA GPU pressure and choose a device with recovery hysteresis."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GpuSample:
    utilization: float
    total_mib: float
    used_mib: float
    free_mib: float


def sample_gpu() -> GpuSample | None:
    executable = shutil.which('nvidia-smi')
    if not executable:
        candidate = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'nvidia-smi.exe')
        executable = candidate if os.path.isfile(candidate) else None
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, '--id=0', '--query-gpu=utilization.gpu,memory.total,memory.used,memory.free', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=2, check=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        return GpuSample(*[float(value.strip()) for value in result.stdout.strip().split(',')])
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


class AutoDevicePolicy:
    """Protect GPU headroom; require sustained low pressure before recovery."""

    def __init__(self, cuda_available: bool):
        self.cuda_available = cuda_available
        self.device = 'cpu'
        self.reason = '自动模式：等待 GPU 状态' if cuda_available else '未检测到可用 CUDA，使用 CPU'
        self.sample: GpuSample | None = None
        self.last_poll = float('-inf')
        self.last_switch = float('-inf')
        self.busy_since: float | None = None
        self.healthy_since: float | None = None
        self.initialized = False

    def _choose(self, device: str, reason: str, now: float) -> str:
        if self.device != device:
            self.last_switch = now
        self.device, self.reason = device, reason
        self.busy_since = self.healthy_since = None
        return device

    def decide(self) -> str:
        now = time.monotonic()
        if not self.cuda_available or now - self.last_poll < 3:
            return self.device
        self.last_poll = now
        self.sample = sample_gpu()
        if self.sample is None:
            return self._choose('cpu', 'GPU 监测不可用，保守使用 CPU', now)
        sample = self.sample
        memory_high = sample.free_mib < 1536 or sample.used_mib / max(sample.total_mib, 1) >= .85
        if not self.initialized:
            self.initialized = True
            if memory_high or sample.utilization >= 90:
                return self._choose('cpu', '启动时 GPU 繁忙或显存余量不足，使用 CPU', now)
            return self._choose('cuda:0', 'GPU 有余量，自动使用 GPU', now)
        if self.device == 'cuda:0':
            if memory_high:
                return self._choose('cpu', '显存占用达到 85% 或剩余不足 1.5GB，切换 CPU', now)
            if sample.utilization >= 90:
                if self.busy_since is None:
                    self.busy_since = now
                if now - self.busy_since >= 15:
                    return self._choose('cpu', 'GPU 利用率持续 15 秒达到 90%，切换 CPU', now)
            else:
                self.busy_since = None
        else:
            healthy = sample.utilization <= 60 and sample.free_mib >= 3072 and sample.used_mib / max(sample.total_mib, 1) <= .65
            if healthy:
                if self.healthy_since is None:
                    self.healthy_since = now
                if now - self.healthy_since >= 30 and now - self.last_switch >= 30:
                    return self._choose('cuda:0', 'GPU 余量持续恢复 30 秒，切回 GPU', now)
            else:
                self.healthy_since = None
        return self.device

    def gpu_failed(self) -> None:
        self.initialized = True
        self.last_switch = time.monotonic()
        self.device = 'cpu'
        self.reason = 'GPU 推理失败，自动回退 CPU；等待余量恢复'
        self.busy_since = self.healthy_since = None

    def status(self) -> dict:
        return {'device_mode': 'auto', 'device_reason': self.reason, 'gpu': asdict(self.sample) if self.sample else None}
