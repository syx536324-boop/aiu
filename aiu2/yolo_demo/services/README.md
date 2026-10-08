# 实时推理服务

`live_inference.py` 管理摄像头、检测循环和 JPEG 帧；`adaptive_inference.py` 管理 YOLO 模型设备迁移；`device_policy.py` 管理 GPU 监测和切换策略。网页通过 HTTP API 调用服务，不在浏览器中计算负载阈值。

公开入口为 `LiveInferenceService.start/stop/status/latest_frame`。自动模式每 3 秒采样，显存紧张或持续高负载时切换 CPU，余量持续恢复后切回 GPU。详细阈值与限制见根目录 `自动设备切换说明.md`。

在项目根目录执行 `.\.venv\Scripts\python.exe -m yolo_demo web` 启动本机应用。
