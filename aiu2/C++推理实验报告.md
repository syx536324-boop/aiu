# C++ YOLO 推理实验报告

记录时间：2026-10-06 23:45:32 UTC+08:00

## 你的问题

你选中“C++/Rust 性能优化还没有实施”，并要求“实验一下”。本次选择 C++，调用微软官方 ONNX Runtime；模型继续使用已有 best.pt 导出的 ONNX，不重新实现 YOLO 网络。

## 实测结论

C++ ONNX Runtime CPU 相对 PyTorch CPU 的平均推理速度比值为 **1.21×**；相对 Python 调用同一个 ONNX Runtime CPU 的比值为 **0.98×**。比值大于 1 表示 C++ 方案更快，小于 1 表示更慢。结果只适用于此次测量，尤其接近 1 的差异应视作小幅差异或测量波动。

C++ 与 Python 调用同一个 ONNX Runtime 的平均速度差异在 5% 以内；这轮测试没有显示换成 C++ 带来明确的额外收益。

现有 PyTorch GPU 平均 7.103 ms，原生 CPU 平均 31.985 ms；本次网页保留现有 GPU 推理路径。

检测框/置信度检查：**全部通过**。当前网页继续使用既有 PyTorch GPU 路径。本次 CPU 原生实验的速度不能直接当成 RTX 5070 GPU 的优化效果。

## 测量条件

- 同一份 COCO8 训练 3 轮权重，模型 SHA256：232370de7ddf4f40a0c64fe7ce6be77061b240890e24cc939c11b21bd3d7eb75。
- 4 张 COCO8 验证图片，使用同一批预处理后的输入张量。
- FP32、batch=1、固定输入 1×3×640×640；Ultralytics LetterBox(auto=False)、RGB、除以 255。
- CPU 路径统一 4 个计算线程、1 个 inter-op 线程。ORT 启用图优化，关闭空闲线程自旋。
- 每个后端预热 12 次，再轮流推理 80 次。GPU 计时使用 CUDA synchronize。
- **计时仅包括已加载模型的前向推理**，不包括读取图片、预处理、加载模型、GPU 输入传输、NMS、画框、网络传输和摄像头采集。因此表中的理论推理吞吐量不是网页/摄像头实际 FPS。
- CPU 和 GPU 分别列出，不能用跨硬件差异归因于编程语言。Windows 后台负载和功耗状态可能影响结果。

## 延迟结果

| 路径 | 平均延迟 ms | P50 ms | P95 ms | 理论推理吞吐 帧/s |
|---|---:|---:|---:|---:|
| Python / PyTorch CPU | 38.703 | 38.206 | 49.588 | 25.8 |
| Python / ONNX Runtime CPU | 31.431 | 31.472 | 36.536 | 31.8 |
| C++ / ONNX Runtime CPU | 31.985 | 32.287 | 36.035 | 31.3 |
| Python / PyTorch GPU（不同硬件基线） | 7.103 | 5.455 | 11.518 | 140.8 |

P50 是一半推理能达到的延迟；P95 是 95% 推理不超过的延迟。更低的毫秒数通常更好。

## C++ 与 PyTorch CPU 的检测一致性

统一使用 Ultralytics NMS，conf=0.25、IoU=0.7。匹配要求：同类别和数量、对应框 IoU≥0.99、置信度绝对差≤0.002；同时记录原始张量的数值误差。

| 图片 | PyTorch/C++ 检测数 | 最小匹配框 IoU | 最大置信度差 | 结果 |
|---|---:|---:|---:|---|
| 000000000036.jpg | 2 / 2 | 1.000000 | 0.00000054 | 通过 |
| 000000000042.jpg | 2 / 2 | 0.999999 | 0.00000030 | 通过 |
| 000000000049.jpg | 8 / 8 | 0.999999 | 0.00000191 | 通过 |
| 000000000061.jpg | 3 / 3 | 0.999999 | 0.00000209 | 通过 |

这只是 4 张示例图的回归检查，不代表完整数据集的精度评估。标注图在 runs/native_benchmark/cpp_*.jpg；详细数值在 runs/native_benchmark/results.json。

## 如何重跑

在 PowerShell 中执行：

```powershell
cd D:\aiu2
.\.venv\Scripts\python.exe -m native_experiment --iterations 80 --warmups 12 --threads 4
```

依赖准备脚本：native_experiment/setup.ps1。C++ 文件在 native_experiment/native，运行时和编译产物在 .native-cache；模型、张量、日志及测量数据在 runs/native_benchmark。

## 接下来可优化什么

若目标是提高现有 RTX 5070 网页摄像头的速度，下一步应测整条采集/推理/绘制链路，再评估兼容的 GPU ONNX Runtime 或 TensorRT。C++、ONNX Runtime 和 TensorRT 不会保证每个模型都更快；迁移后仍需检查检测精度和端到端延迟。

## 软件版本与来源

- Python 3.12.14；PyTorch 2.14.1+cu130；Ultralytics 8.4.173；ONNX 1.19.1；ONNX Runtime 1.23.2。
- GPU：NVIDIA GeForce RTX 5070 Laptop GPU。
- [ONNX Runtime 原生 API 官方文档](https://onnxruntime.ai/docs/get-started/with-c.html)
- [ONNX Runtime v1.23.2 官方发行包](https://github.com/microsoft/onnxruntime/releases/tag/v1.23.2)
- [Ultralytics ONNX 导出文档](https://docs.ultralytics.com/integrations/onnx/)
