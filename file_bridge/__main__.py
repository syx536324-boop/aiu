"""组合入口：加载本机凭据、启动文件 API，或打开/停止审批服务。"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
import webbrowser

from .config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    clear_runtime_files,
    create_approval_secret,
    load_or_create_api_token,
    read_approval_secret,
    write_pid,
)
from .http import BridgeApp, BridgeHTTPServer


def _local_request(path: str, *, secret: str | None = None) -> None:
    url = f"http://localhost:{DEFAULT_PORT}{path}"
    request = urllib.request.Request(url)
    if secret is not None:
        request.method = "POST"
        request.data = b""
        request.add_header("X-Bridge-Admin", secret)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=3):
        pass


def _open_approval() -> int:
    try:
        _local_request("/health")
        secret = read_approval_secret()
        address = f"http://localhost:{DEFAULT_PORT}/approval/bootstrap/{secret}"
        if not webbrowser.open(address, new=2):
            raise RuntimeError("无法打开默认浏览器。")
    except (OSError, RuntimeError, urllib.error.URLError) as exc:
        print(f"无法打开审批页面：{exc}", file=sys.stderr)
        return 1
    return 0


def _stop_service() -> int:
    try:
        secret = read_approval_secret()
        _local_request("/approval/shutdown", secret=secret)
    except (OSError, RuntimeError, urllib.error.URLError) as exc:
        print(f"无法停止文件服务：{exc}", file=sys.stderr)
        return 1
    print("文件服务已收到停止指令。")
    return 0


def _serve() -> int:
    server: BridgeHTTPServer | None = None
    approval_secret: str | None = None
    try:
        # 先独占端口，再轮换审批密钥，避免第二个实例使首个实例失效。
        server = BridgeHTTPServer()
        api_token = load_or_create_api_token()
        approval_secret = create_approval_secret()
        server.app = BridgeApp(api_token, approval_secret)
        write_pid()
        print(f"文件服务运行于 http://{DEFAULT_HOST}:{DEFAULT_PORT}。")
        print("写入和删除请求需要在本机浏览器中单独审批。")
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError) as exc:
        print(f"文件服务启动失败：{exc}", file=sys.stderr)
        return 1
    finally:
        if server is not None:
            server.server_close()
        if approval_secret is not None:
            clear_runtime_files(approval_secret)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AIU 本地知识文件桥接服务")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--approve", action="store_true", help="在本机浏览器打开审批页面")
    group.add_argument("--stop", action="store_true", help="温和停止文件服务")
    arguments = parser.parse_args()
    if arguments.approve:
        return _open_approval()
    if arguments.stop:
        return _stop_service()
    return _serve()


if __name__ == "__main__":
    raise SystemExit(main())
