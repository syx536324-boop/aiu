# 电脑端

目前提供只读串口枚举，公开入口为 `python -m host`；`serial_ports.py` 负责设备发现，入口只组合功能。未来在此接入 Ollama 与串口命令，STM32 的实时控制循环由固件负责。

在 E:\aiu3 执行 `.\.venv\Scripts\python.exe -m host`。目前没有点灯或 PID 控制实现。
