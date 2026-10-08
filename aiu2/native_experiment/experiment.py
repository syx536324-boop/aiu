"""Export the existing checkpoint, run controlled backends, compare detections, and write the report."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from yolo_demo.config import DATASETS, ROOT, RUNS, prepare_environment

ORT_VERSION = "1.23.2"
FEATURE = Path(__file__).resolve().parent
CACHE = ROOT / ".native-cache"
OUTPUT = RUNS / "native_benchmark"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _measure(call, items, iterations: int, warmups: int) -> dict:
    import numpy as np

    for i in range(warmups):
        call(items[i % len(items)])
    durations = []
    for i in range(iterations):
        start = time.perf_counter()
        result = call(items[i % len(items)])
        durations.append((time.perf_counter() - start) * 1000)
        del result
    return {
        "iterations": iterations,
        "warmups": warmups,
        "mean_ms": float(np.mean(durations)),
        "p50_ms": float(np.percentile(durations, 50)),
        "p95_ms": float(np.percentile(durations, 95)),
        "samples_ms": durations,
    }


def _first_output(output):
    return output[0] if isinstance(output, (tuple, list)) else output


def _export_model(weight: Path) -> Path:
    import onnx
    import torch
    import ultralytics
    from ultralytics import YOLO

    OUTPUT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT / "best.onnx"
    manifest = OUTPUT / "export_manifest.json"
    signature = {
        "checkpoint_sha256": _hash(weight), "torch": torch.__version__,
        "ultralytics": ultralytics.__version__, "onnx": onnx.__version__,
        "imgsz": 640, "batch": 1, "opset": 17, "half": False,
    }
    if destination.is_file() and manifest.is_file() and json.loads(manifest.read_text(encoding="utf-8")) == signature:
        onnx.checker.check_model(str(destination))
        return destination
    exported = Path(YOLO(str(weight)).export(format="onnx", imgsz=640, batch=1, dynamic=False, simplify=False, opset=17, device="cpu"))
    shutil.copy2(exported, destination)
    onnx.checker.check_model(str(destination))
    manifest.write_text(json.dumps(signature, indent=2), encoding="utf-8")
    return destination


def _prepare_inputs():
    import cv2
    import numpy as np
    from ultralytics.data.augment import LetterBox

    files = sorted((DATASETS / "coco8" / "images" / "val").glob("*.jpg"))
    if len(files) != 4:
        raise RuntimeError("Expected the four COCO8 validation images from the existing demo")
    input_directory = OUTPUT / "inputs"
    input_directory.mkdir(parents=True, exist_ok=True)
    arrays, images = [], []
    letterbox = LetterBox(new_shape=(640, 640), auto=False, stride=32)
    for index, path in enumerate(files):
        image = cv2.imread(str(path))
        if image is None:
            raise RuntimeError(f"Cannot decode {path}")
        padded = letterbox(image=image)
        array = np.ascontiguousarray(padded[:, :, ::-1].transpose(2, 0, 1), dtype=np.float32)[None] / 255.0
        array.tofile(input_directory / f"input_{index}.bin")
        arrays.append(array)
        images.append(image)
    return files, images, arrays, input_directory


def _native_run(model: Path, input_directory: Path, iterations: int, warmups: int, threads: int) -> dict:
    sdk = CACHE / f"onnxruntime-win-x64-{ORT_VERSION}"
    runtime_dll = sdk / "lib" / "onnxruntime.dll"
    if not runtime_dll.is_file():
        raise RuntimeError("Official native SDK is missing; run native_experiment/setup.ps1 first")
    compiler = shutil.which("g++")
    if not compiler:
        raise RuntimeError("g++ is missing from PATH")
    executable = CACHE / "yolo_ort_bench.exe"
    build = subprocess.run([
        compiler, "-O3", "-std=c++17", "-static", "-I", str(sdk / "include"),
        str(FEATURE / "native" / "main.cpp"), str(FEATURE / "native" / "runner.cpp"),
        "-o", str(executable),
    ], capture_output=True, text=True, errors="replace")
    (OUTPUT / "build.log").write_text(build.stdout + build.stderr, encoding="utf-8")
    if build.returncode:
        excerpt = "\n".join(build.stderr.splitlines()[:30])
        raise RuntimeError(f"C++ compilation failed; see {OUTPUT / 'build.log'}\n{excerpt}")
    process = subprocess.run([
        str(executable), str(runtime_dll), str(model), str(input_directory), str(OUTPUT),
        str(iterations), str(warmups), str(threads),
    ], capture_output=True, text=True, errors="replace")
    (OUTPUT / "native.log").write_text(process.stdout + process.stderr, encoding="utf-8")
    if process.returncode:
        raise RuntimeError(f"C++ inference failed; see {OUTPUT / 'native.log'}\n{process.stderr}")
    print(process.stdout, flush=True)
    metrics = json.loads((OUTPUT / "cpp_benchmark.json").read_text(encoding="utf-8"))
    metrics["runtime_sha256"] = _hash(runtime_dll)
    return metrics


def _detections(array):
    import torch
    from ultralytics.utils.nms import non_max_suppression

    return non_max_suppression(torch.from_numpy(array.copy()), conf_thres=0.25, iou_thres=0.7)[0].cpu().numpy()


def _compare(reference, candidate) -> dict:
    import numpy as np
    import torch
    from ultralytics.utils.metrics import box_iou

    reference_detections = _detections(reference)
    candidate_detections = _detections(candidate)
    same_count = len(reference_detections) == len(candidate_detections)
    minimum_iou = 1.0
    maximum_score_delta = 0.0
    matched_indices = set()
    for box in reference_detections:
        compatible = [i for i, other in enumerate(candidate_detections) if other[5] == box[5] and i not in matched_indices]
        if not compatible:
            minimum_iou = 0.0
            continue
        overlaps = box_iou(torch.from_numpy(box[None, :4]), torch.from_numpy(candidate_detections[compatible, :4]))[0].numpy()
        winner = int(np.argmax(overlaps))
        candidate_index = compatible[winner]
        matched_indices.add(candidate_index)
        minimum_iou = min(minimum_iou, float(overlaps[winner]))
        maximum_score_delta = max(maximum_score_delta, abs(float(box[4] - candidate_detections[candidate_index, 4])))
    difference = np.abs(reference - candidate)
    return {
        "raw_max_abs_difference": float(difference.max()),
        "raw_mean_abs_difference": float(difference.mean()),
        "raw_allclose": bool(np.allclose(reference, candidate, atol=0.02, rtol=0.001)),
        "reference_detection_count": len(reference_detections),
        "candidate_detection_count": len(candidate_detections),
        "min_matched_box_iou": minimum_iou,
        "max_confidence_delta": maximum_score_delta,
        "detection_match": same_count and len(matched_indices) == len(reference_detections) and minimum_iou >= 0.99 and maximum_score_delta <= 0.002,
    }


def _save_native_images(files, images, outputs, names) -> None:
    import torch
    from ultralytics.engine.results import Results
    from ultralytics.utils.ops import scale_boxes

    for path, image, output in zip(files, images, outputs):
        boxes = torch.from_numpy(_detections(output).copy())
        if len(boxes):
            boxes[:, :4] = scale_boxes((640, 640), boxes[:, :4], image.shape[:2])
        result = Results(orig_img=image, path=str(path), names=names, boxes=boxes)
        result.save(filename=str(OUTPUT / f"cpp_{path.name}"))


def _write_report(data: dict) -> None:
    metrics = data["metrics"]
    native_mean = metrics["cpp_ort_cpu"]["mean_ms"]
    cpu_speedup = metrics["pytorch_cpu"]["mean_ms"] / native_mean
    binding_speedup = metrics["python_ort_cpu"]["mean_ms"] / native_mean
    language_conclusion = (
        "C++ 与 Python 调用同一个 ONNX Runtime 的平均速度差异在 5% 以内；这轮测试没有显示换成 C++ 带来明确的额外收益。"
        if abs(binding_speedup - 1.0) < 0.05
        else "两种语言路径存在测量差异；需要结合重复测量和整体应用延迟判断是否值得迁移。"
    )
    gpu_conclusion = ""
    if "pytorch_gpu" in metrics:
        gpu_mean = metrics["pytorch_gpu"]["mean_ms"]
        gpu_conclusion = f"现有 PyTorch GPU 平均 {gpu_mean:.3f} ms，原生 CPU 平均 {native_mean:.3f} ms；本次网页保留现有 GPU 推理路径。"
    passed = all(item["detection_match"] for group in data["comparisons"].values() for item in group)
    rows = []
    labels = {
        "pytorch_cpu": "Python / PyTorch CPU",
        "python_ort_cpu": "Python / ONNX Runtime CPU",
        "cpp_ort_cpu": "C++ / ONNX Runtime CPU",
        "pytorch_gpu": "Python / PyTorch GPU（不同硬件基线）",
    }
    for key, value in metrics.items():
        rows.append(f"| {labels[key]} | {value['mean_ms']:.3f} | {value['p50_ms']:.3f} | {value['p95_ms']:.3f} | {1000 / value['mean_ms']:.1f} |")
    per_image_rows = []
    for path, comparison in zip(data["inputs"], data["comparisons"]["cpp_ort_cpu"]):
        per_image_rows.append(f"| {path} | {comparison['reference_detection_count']} / {comparison['candidate_detection_count']} | {comparison['min_matched_box_iou']:.6f} | {comparison['max_confidence_delta']:.8f} | {'通过' if comparison['detection_match'] else '待检查'} |")
    date = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S UTC+08:00")
    report = f"""# C++ YOLO 推理实验报告

记录时间：{date}

## 你的问题

你选中“C++/Rust 性能优化还没有实施”，并要求“实验一下”。本次选择 C++，调用微软官方 ONNX Runtime；模型继续使用已有 best.pt 导出的 ONNX，不重新实现 YOLO 网络。

## 实测结论

C++ ONNX Runtime CPU 相对 PyTorch CPU 的平均推理速度比值为 **{cpu_speedup:.2f}×**；相对 Python 调用同一个 ONNX Runtime CPU 的比值为 **{binding_speedup:.2f}×**。比值大于 1 表示 C++ 方案更快，小于 1 表示更慢。结果只适用于此次测量，尤其接近 1 的差异应视作小幅差异或测量波动。

{language_conclusion}

{gpu_conclusion}

检测框/置信度检查：**{'全部通过' if passed else '存在差异，见原始结果'}**。当前网页继续使用既有 PyTorch GPU 路径。本次 CPU 原生实验的速度不能直接当成 RTX 5070 GPU 的优化效果。

## 测量条件

- 同一份 COCO8 训练 3 轮权重，模型 SHA256：{data['model_sha256']}。
- 4 张 COCO8 验证图片，使用同一批预处理后的输入张量。
- FP32、batch=1、固定输入 1×3×640×640；Ultralytics LetterBox(auto=False)、RGB、除以 255。
- CPU 路径统一 {data['threads']} 个计算线程、1 个 inter-op 线程。ORT 启用图优化，关闭空闲线程自旋。
- 每个后端预热 {data['warmups']} 次，再轮流推理 {data['iterations']} 次。GPU 计时使用 CUDA synchronize。
- **计时仅包括已加载模型的前向推理**，不包括读取图片、预处理、加载模型、GPU 输入传输、NMS、画框、网络传输和摄像头采集。因此表中的理论推理吞吐量不是网页/摄像头实际 FPS。
- CPU 和 GPU 分别列出，不能用跨硬件差异归因于编程语言。Windows 后台负载和功耗状态可能影响结果。

## 延迟结果

| 路径 | 平均延迟 ms | P50 ms | P95 ms | 理论推理吞吐 帧/s |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

P50 是一半推理能达到的延迟；P95 是 95% 推理不超过的延迟。更低的毫秒数通常更好。

## C++ 与 PyTorch CPU 的检测一致性

统一使用 Ultralytics NMS，conf=0.25、IoU=0.7。匹配要求：同类别和数量、对应框 IoU≥0.99、置信度绝对差≤0.002；同时记录原始张量的数值误差。

| 图片 | PyTorch/C++ 检测数 | 最小匹配框 IoU | 最大置信度差 | 结果 |
|---|---:|---:|---:|---|
{chr(10).join(per_image_rows)}

这只是 4 张示例图的回归检查，不代表完整数据集的精度评估。标注图在 runs/native_benchmark/cpp_*.jpg；详细数值在 runs/native_benchmark/results.json。

## 如何重跑

在 PowerShell 中执行：

```powershell
cd D:\\aiu2
.\\.venv\\Scripts\\python.exe -m native_experiment --iterations 80 --warmups 12 --threads 4
```

依赖准备脚本：native_experiment/setup.ps1。C++ 文件在 native_experiment/native，运行时和编译产物在 .native-cache；模型、张量、日志及测量数据在 runs/native_benchmark。

## 接下来可优化什么

若目标是提高现有 RTX 5070 网页摄像头的速度，下一步应测整条采集/推理/绘制链路，再评估兼容的 GPU ONNX Runtime 或 TensorRT。C++、ONNX Runtime 和 TensorRT 不会保证每个模型都更快；迁移后仍需检查检测精度和端到端延迟。

## 软件版本与来源

- Python {data['versions']['python']}；PyTorch {data['versions']['torch']}；Ultralytics {data['versions']['ultralytics']}；ONNX {data['versions']['onnx']}；ONNX Runtime {data['versions']['onnxruntime']}。
- GPU：{data['gpu']}。
- [ONNX Runtime 原生 API 官方文档](https://onnxruntime.ai/docs/get-started/with-c.html)
- [ONNX Runtime v1.23.2 官方发行包](https://github.com/microsoft/onnxruntime/releases/tag/v1.23.2)
- [Ultralytics ONNX 导出文档](https://docs.ultralytics.com/integrations/onnx/)
"""
    (ROOT / "C++推理实验报告.md").write_text(report, encoding="utf-8")


def run_experiment(iterations: int, warmups: int, threads: int) -> None:
    prepare_environment()
    CACHE.mkdir(exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch
    import ultralytics
    from ultralytics import YOLO

    if ort.__version__ != ORT_VERSION:
        raise RuntimeError(f"Expected ONNX Runtime {ORT_VERSION}, found {ort.__version__}")
    torch.set_num_threads(threads)
    torch.set_num_interop_threads(1)
    ort.disable_telemetry_events()
    weight = RUNS / "coco8_train" / "weights" / "best.pt"
    if not weight.is_file():
        raise FileNotFoundError(weight)
    print("Exporting the existing checkpoint to fixed FP32 ONNX...", flush=True)
    model_path = _export_model(weight)
    files, images, arrays, input_directory = _prepare_inputs()
    print("Compiling and measuring the C++ runtime...", flush=True)
    native_metrics = _native_run(model_path, input_directory, iterations, warmups, threads)
    native_outputs = [np.fromfile(OUTPUT / f"cpp_output_{index}.bin", dtype=np.float32).reshape(native_metrics["output_shape"]) for index in range(len(arrays))]

    cpu_model = YOLO(str(weight)).model.fuse(verbose=False).float().eval().cpu()
    tensor_inputs = [torch.from_numpy(array) for array in arrays]
    with torch.inference_mode():
        print("Measuring PyTorch CPU...", flush=True)
        cpu_call = lambda value: _first_output(cpu_model(value))
        cpu_metrics = _measure(cpu_call, tensor_inputs, iterations, warmups)
        cpu_outputs = [cpu_call(value).numpy() for value in tensor_inputs]

    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = threads
    session_options.inter_op_num_threads = 1
    session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session_options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    session = ort.InferenceSession(str(model_path), sess_options=session_options, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    ort_call = lambda value: session.run(None, {input_name: value})[0]
    print("Measuring Python ONNX Runtime CPU...", flush=True)
    python_ort_metrics = _measure(ort_call, arrays, iterations, warmups)
    ort_outputs = [ort_call(array) for array in arrays]
    metrics = {"pytorch_cpu": cpu_metrics, "python_ort_cpu": python_ort_metrics, "cpp_ort_cpu": native_metrics}
    outputs = {"python_ort_cpu": ort_outputs, "cpp_ort_cpu": native_outputs}
    gpu_name = "CUDA unavailable"
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_model = YOLO(str(weight)).model.fuse(verbose=False).float().eval().cuda()
        gpu_inputs = [value.cuda() for value in tensor_inputs]
        with torch.inference_mode():
            def gpu_call(value):
                result = _first_output(gpu_model(value))
                torch.cuda.synchronize()
                return result
            print("Measuring the existing PyTorch GPU baseline...", flush=True)
            metrics["pytorch_gpu"] = _measure(gpu_call, gpu_inputs, iterations, warmups)
            outputs["pytorch_gpu"] = [gpu_call(value).cpu().numpy() for value in gpu_inputs]
    comparisons = {key: [_compare(reference, candidate) for reference, candidate in zip(cpu_outputs, group)] for key, group in outputs.items()}
    _save_native_images(files, images, native_outputs, cpu_model.names)
    data = {
        "model_sha256": _hash(weight), "onnx_sha256": _hash(model_path),
        "iterations": iterations, "warmups": warmups, "threads": threads,
        "inputs": [path.name for path in files], "gpu": gpu_name,
        "versions": {"python": platform.python_version(), "torch": torch.__version__, "ultralytics": ultralytics.__version__, "onnx": onnx.__version__, "onnxruntime": ort.__version__},
        "metrics": metrics, "comparisons": comparisons,
    }
    (OUTPUT / "results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(data)
    print(json.dumps({key: {field: value[field] for field in ("mean_ms", "p50_ms", "p95_ms")} for key, value in metrics.items()}, indent=2), flush=True)
    print(f"Report: {ROOT / 'C++推理实验报告.md'}", flush=True)
    if not all(item["detection_match"] for group in comparisons.values() for item in group):
        raise RuntimeError("At least one detection comparison failed; inspect results.json before adopting the backend")
