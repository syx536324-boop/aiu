"""Verify real YOLO device migration using controlled GPU pressure samples."""
import gc
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yolo_demo.config import prepare_environment
from yolo_demo.services.adaptive_inference import AdaptiveInference
from yolo_demo.services.device_policy import AutoDevicePolicy, GpuSample, sample_gpu

prepare_environment()
import cv2
import torch

assert torch.cuda.is_available(), 'CUDA unavailable; cannot verify real GPU-to-CPU migration'
actual = sample_gpu()
assert actual is not None, 'Real NVIDIA sampler unavailable'
frame = cv2.imread(str(ROOT / 'datasets/coco8/images/val/000000000036.jpg'))
assert frame is not None
healthy = GpuSample(20, 8151, 2000, 6000)
pressure = GpuSample(95, 8151, 7500, 500)
engine = AdaptiveInference(ROOT / 'runs/coco8_train/weights/best.pt')
records = []

def infer(sample):
    engine.policy.last_poll = float('-inf')
    with patch('yolo_demo.services.device_policy.sample_gpu', return_value=sample):
        output = engine.predict(frame, .25)
    record = {
        **engine.status(),
        'model_device': str(next(engine.model.model.parameters()).device),
        'output_device': str(output[0].boxes.data.device),
        'classes': output[0].boxes.cls.cpu().tolist(),
        'confidence': output[0].boxes.conf.cpu().tolist(),
        'boxes': output[0].boxes.xyxy.cpu().tolist(),
        'torch_allocated_mib': round(torch.cuda.memory_allocated() / 1024**2, 2),
    }
    del output
    records.append(record)
    return record

try:
    gpu = infer(healthy)
    assert gpu['model_device'] == 'cuda:0' and gpu['output_device'] == 'cuda:0', gpu
    cpu = infer(pressure)
    assert cpu['model_device'] == 'cpu' and cpu['output_device'] == 'cpu', cpu
    assert gpu['classes'] == cpu['classes'], 'Detection classes changed'
    confidence_delta = max((abs(a-b) for a,b in zip(gpu['confidence'], cpu['confidence'])), default=0)
    box_delta = max((abs(a-b) for ba,bb in zip(gpu['boxes'],cpu['boxes']) for a,b in zip(ba,bb)), default=0)
    assert confidence_delta < .003 and box_delta < 1, (confidence_delta, box_delta)
finally:
    engine.close()
    del engine
    gc.collect()

# Check sustained utilization and recovery timing without an actual GPU stress load.
policy = AutoDevicePolicy(True)
def decide_at(seconds, sample):
    with patch('yolo_demo.services.device_policy.time', SimpleNamespace(monotonic=lambda: seconds)), patch('yolo_demo.services.device_policy.sample_gpu', return_value=sample):
        return policy.decide()

assert decide_at(0, healthy) == 'cuda:0'
busy = GpuSample(95, 8151, 2000, 6000)
for seconds in range(3, 18, 3):
    assert decide_at(seconds, busy) == 'cuda:0'
assert decide_at(18, busy) == 'cpu'
for seconds in range(21, 51, 3):
    assert decide_at(seconds, healthy) == 'cpu'
assert decide_at(51, healthy) == 'cuda:0'

payload = {'passed': True, 'method': 'simulated pressure; real GPU/CPU inference', 'actual_gpu_sample': actual.__dict__, 'inference': records, 'max_confidence_delta': confidence_delta, 'max_box_delta_pixels': box_delta, 'sustained_load_and_recovery': 'passed'}
output_dir = ROOT / 'runs/auto_device_check'
output_dir.mkdir(parents=True, exist_ok=True)
(output_dir / 'results.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
report = f'''# GPU → CPU 自动切换测试

日期：2026-10-07（北京时间）

## 测试方式

使用现有 best.pt 和 COCO8 验证图片 000000000036.jpg。模拟监测读数，实际在 RTX 5070 与 CPU 上执行推理；没有把显卡真实占满，没有打开摄像头。

## 结果

- GPU 阶段：模型参数和检测结果张量均位于 cuda:0。
- 模拟剩余显存 500MiB、利用率 95% 后：同一模型切换到 CPU，同一图片推理完成，参数和检测结果张量均位于 cpu。
- 两次检测类别相同，共 {len(cpu['classes'])} 个目标。
- 最大置信度差：{confidence_delta:.8f}；检测框最大坐标差：{box_delta:.6f} 像素。
- 持续高利用率测试：不足 15 秒保持 GPU，达到 15 秒切换 CPU，通过。
- 恢复测试：健康状态不足 30 秒保持 CPU，达到 30 秒恢复 GPU，通过。

## 测试范围

确认了设备迁移、继续推理与策略时间条件。未进行真实 Ollama 并发负载、真实显存耗尽或摄像头连续切换测试。网页服务的模型与本测试模型是独立实例，本测试不会改变网页当前设备。

原始结果：runs/auto_device_check/results.json。
'''
(ROOT / 'GPU_CPU自动切换测试报告.md').write_text(report, encoding='utf-8-sig')
print(json.dumps(payload, ensure_ascii=False, indent=2))

