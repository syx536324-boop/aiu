# YOLO Web

该功能目录提供本机浏览器实时检测应用。`server.py` 是 HTTP/API 组合入口，`services/live_inference.py` 管理摄像头、YOLO 推理与最新 JPEG 帧，`static/` 只负责前端界面与交互。

公开接口：`GET /api/config`、`GET /api/status`、`POST /api/start`、`POST /api/stop`、`GET /api/stream`。前端和 API 同源；MJPEG 用于连续画面，状态通过轻量轮询读取。

从 `D:\aiu2` 启动：

    .\.venv\Scripts\python.exe -m yolo_demo web

浏览器访问 `http://127.0.0.1:8765/`。默认绑定本机回环地址，不对局域网其他设备开放。

实时检测默认自动选择 GPU/CPU；GET /api/status 增加 device_mode、device_reason、gpu 字段，前端展示当前设备和选择原因。策略实现位于 services/device_policy.py，模型迁移位于 services/adaptive_inference.py。
