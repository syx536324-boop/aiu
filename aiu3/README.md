# AIU3 · STM32 与本地 AI

统一仓库中的项目位于 `aiu3/`，本机独立目录仍在 `E:\aiu3`。目标依次为点亮 LED、让本地 AI 控灯、辅助调整 PID、评估适合芯片的小型模型。

## 当前状态

已建立 STM32F103C8T6 的 CubeMX/CMake 工程，板载 LED 使用 PC13。固件当前设置为常亮；实际效果需要在板上观察确认。`host/` 已提供串口枚举；AI 控灯、PID 调参与板端模型尚未实现。电脑上的千问继续由已有 Ollama 提供，无需在本项目复制模型。

## 使用

在本项目目录打开 PowerShell，查看电脑识别到的串口：

```powershell
.\.venv\Scripts\python.exe -m host
```

没有接入硬件时显示“未检测到串口”是正常情况。串口枚举不会向板子发送命令。

重新安装环境：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-environment.ps1
```

## 模块

- `host/`：电脑端串口与未来 AI 调用；`__main__.py` 只负责入口组合。
- `firmware/led_blink/`：STM32F103C8T6 固件、PC13 LED 控制模块和编译说明。
- `docs/工具下载与准备清单.md`：缺少的软件、官方链接与硬件准备项。
- `pyproject.toml`、`uv.lock`：Python 依赖声明与版本锁定。

虚拟环境、项目依赖缓存和 uv 管理的 Python 解释器均放在当前项目目录，解释器位于 `.python/`。Git 忽略环境、密钥、日志、编译产物与 IDE 本机状态。

