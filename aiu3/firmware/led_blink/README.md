# LED 点灯工程

目标芯片：STM32F103C8Tx；板载 LED：PC13；保持 CubeMX 默认内部 HSI 时钟。
当前模式：常亮，按本板常见的低电平点亮接法设置 PC13。

## 模块

- Core/Src/main.c：初始化硬件，调用 Led_SetOn()，随后进入主循环。
- Core/Src/led_blink.c、Core/Inc/led_blink.h：LED 控制模块；公开接口 Led_SetOn()，将 PC13 持续设为低电平。
- CMakeLists.txt：将 LED 模块加入编译；保留最初 led_blink 工程和文件名。

## 使用

在 VS Code 打开本文件夹，选择 Debug 配置，执行 CMake: Build。
编译后的 build/Debug/led_blink.elf 可通过 STM32CubeProgrammer 和 ST-LINK 烧录。
烧录并复位运行后，PC13 保持低电平，LED 应常亮；不再调用翻转或延时函数。
PWR 电源灯与程序控制的 PC13 灯不同。
实际亮灯状态需要观察开发板确认。
用户调用与 include 位于 CubeMX USER CODE 区域，重新生成代码时应保留用户代码。