"""List available serial ports without opening them or sending hardware commands."""
from serial.tools import list_ports


def show_ports() -> None:
    ports = sorted(list_ports.comports(), key=lambda port: port.device)
    if not ports:
        print('未检测到串口。连接 STM32 或 USB 转串口模块后再运行。')
        return
    for port in ports:
        print(f'{port.device}: {port.description}')
