# AIU2 · YOLO11n 本地视觉应用

本机 YOLO 示例与摄像头实时推理网页。项目使用 Ultralytics、PyTorch CUDA 和 OpenCV；Web API 使用 Python 标准库，并通过 MJPEG 将本地推理画面显示在浏览器中。服务默认只绑定 `127.0.0.1`。

统一仓库中的本项目位于 `aiu2/`；本文原有的 `D:\aiu2` 命令仍对应这台电脑上的独立安装。从统一仓库克隆时，先在 `aiu2/` 目录打开 PowerShell，再执行各命令中除 `cd D:\aiu2` 以外的部分。

## 启动网页应用

双击桌面快捷方式 **YOLO 实时推理应用**，或在 PowerShell 执行：

```powershell
cd D:\aiu2
.\.venv\Scripts\python.exe -m yolo_demo web
```

浏览器地址：<http://127.0.0.1:8765/>。在网页选择权重和摄像头，再启动检测；点击“停止检测”释放摄像头。关闭浏览器不会自动关闭后台服务；停止服务请执行：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8765/api/shutdown
```

## 训练和图片推理

```powershell
cd D:\aiu2
.\.venv\Scripts\python.exe -m yolo_demo train
.\.venv\Scripts\python.exe -m yolo_demo predict --source "D:\照片\示例.jpg"
```

示例训练使用 YOLO11n、COCO8、640 像素、batch 2 和 3 个 epoch；权重输出到 `runs\coco8_train\weights\best.pt`。它用于验证流程，不是针对自定义目标训练完成的模型。模型和数据缓存保存在 D 盘项目目录中。

## 模块结构

- `yolo_demo/__main__.py`：命令行组合入口。
- `yolo_demo/tasks.py`：训练与单张图片推理。
- `yolo_demo/services/live_inference.py`：摄像头采集、模型推理和帧状态。
- `yolo_demo/web/server.py`：本地 REST/MJPEG API 与静态页面服务。
- `yolo_demo/web/static/`：网页展示和交互。
- `实时推理应用使用说明.md`：快捷方式、网页和摄像头的操作手册。

## C++ 推理实验

使用官方 ONNX Runtime，在相同输入与 CPU 线程数下对比 PyTorch、Python ORT、C++ ORT，并单独记录 GPU 基线：

```powershell
cd D:\aiu2
.\.venv\Scripts\python.exe -m native_experiment --iterations 80 --warmups 12 --threads 4
```

准备依赖见 `native_experiment/README.md`；结果见 `C++推理实验报告.md`。本实验只测模型前向推理，摄像头网页继续使用现有后端。

## 自动设备选择

摄像头网页已启用 GPU/CPU 自动切换，页面显示设备和切换原因。阈值、恢复条件与限制见 [自动设备切换说明](自动设备切换说明.md)。策略与模型迁移模块位于 yolo_demo/services/。

## 在另一台电脑安装

需要 Python 3.12 和 uv。在克隆后的项目目录运行：

```powershell
uv venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.\.venv\Scripts\python.exe -m yolo_demo train
.\.venv\Scripts\python.exe -m yolo_demo web
```

训练会下载 YOLO11n 与 COCO8 示例数据，并生成 best.pt。GPU 运行需要匹配显卡驱动的 CUDA 版 PyTorch；没有可用 CUDA 时网页使用 CPU。现有 train 示例要求可用 CUDA。

仓库发布的是源码、网页和说明文档，不上传虚拟环境、模型权重、数据集、运行缓存或本机相机画面。GitHub 仓库不提供在线摄像头推理服务；需在本机启动 Python 后端。
