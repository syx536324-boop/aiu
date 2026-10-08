"""Compose the initial serial-port discovery command."""
from .serial_ports import show_ports

if __name__ == '__main__':
    show_ports()
