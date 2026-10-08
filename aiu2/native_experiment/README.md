# Native inference experiment

在现有 YOLO11n best.pt 上比较 PyTorch CPU、Python ONNX Runtime CPU、C++ ONNX Runtime CPU，以及现有 PyTorch GPU。所有路径使用同一批 4 张 COCO8 图片的 FP32 640×640 输入。

在 D:\aiu2 的 PowerShell 中运行：

```powershell
.\native_experiment\setup.ps1
.\.venv\Scripts\python.exe -m native_experiment --iterations 80 --warmups 12 --threads 4
```

当前机器已有 MinGW g++。setup.ps1 把依赖装入现有 .venv，并下载微软官方 ONNX Runtime 1.23.2 SDK 到 .native-cache。程序通过官方 C++ API 和运行时 DLL 执行神经网络；Ultralytics 负责导出、LetterBox 和 NMS，没有重新实现 YOLO 算子。

`__main__.py` 是组合入口；`experiment.py` 负责输入准备、编译、对比和报告；`native/main.cpp` 只解析原生程序选项，`native/runner.cpp` 负责原生推理和计时。原生输入为 float32 二进制张量，输出为预测张量和 JSON 测量指标。

报告写入根目录 C++推理实验报告.md；详细结果、输出图片和编译日志在 runs/native_benchmark；SDK 和原生可执行文件在 .native-cache。

计时排除采集、图片解码、预处理、NMS 和绘制，不能视作网页或摄像头端到端 FPS。CPU 固定相同线程数；GPU 作为不同硬件基线独立报告。此实验不切换当前网页后端。
