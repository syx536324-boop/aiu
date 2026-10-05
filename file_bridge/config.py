"""文件桥接配置：管理本地监听地址、私密凭据和进程标识。"""

from __future__ import annotations

import os
import re
import secrets
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SETUP_DIR = PROJECT_DIR / ".setup"
TOKEN_PATH = SETUP_DIR / "file-bridge-token.txt"
APPROVAL_SECRET_PATH = SETUP_DIR / "file-bridge-approval-secret.txt"
PID_PATH = SETUP_DIR / "file-bridge.pid"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _restrict_file(path: Path) -> None:
    """仅授权当前 Windows 用户、SYSTEM 和管理员读取敏感文件。"""
    if os.name != "nt":
        path.chmod(0o600)
        return

    identity = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    match = re.search(r"S-1-5-(?:\d+-)*\d+", identity.stdout)
    if match is None:
        raise RuntimeError("无法确定当前 Windows 用户 SID，文件服务未启动。")
    grants = [
        f"*{match.group(0)}:(F)",
        "*S-1-5-18:(F)",
        "*S-1-5-32-544:(F)",
    ]
    result = subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", *grants],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError("无法限制文件桥接凭据的访问权限，文件服务未启动。")


def _write_private(path: Path, value: str) -> None:
    """以随机临时名写入凭据，再限制权限并原子替换目标。"""
    SETUP_DIR.mkdir(parents=True, exist_ok=True)
    temporary = SETUP_DIR / f".{path.name}.{secrets.token_hex(8)}.tmp"
    try:
        with temporary.open("x", encoding="ascii", newline="\n") as stream:
            stream.write(value + "\n")
        _restrict_file(temporary)
        os.replace(temporary, path)
        _restrict_file(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_or_create_api_token() -> str:
    """首启生成强随机 Bearer token；若已有文件则重新收紧 ACL。"""
    SETUP_DIR.mkdir(parents=True, exist_ok=True)
    if not TOKEN_PATH.exists():
        _write_private(TOKEN_PATH, secrets.token_urlsafe(48))
    _restrict_file(TOKEN_PATH)
    token = TOKEN_PATH.read_text(encoding="ascii").strip()
    if len(token) < 43 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise RuntimeError("文件桥接凭据文件格式错误，文件服务未启动。")
    return token


def create_approval_secret() -> str:
    """每次启动轮换仅本机审批入口使用的独立密钥。"""
    secret = secrets.token_urlsafe(48)
    _write_private(APPROVAL_SECRET_PATH, secret)
    return secret


def read_approval_secret() -> str:
    """仅供本机 --approve 命令读取当前服务的审批入口密钥。"""
    _restrict_file(APPROVAL_SECRET_PATH)
    return APPROVAL_SECRET_PATH.read_text(encoding="ascii").strip()


def write_pid() -> None:
    """监听成功后记录进程号，便于启动脚本精确停止本服务。"""
    SETUP_DIR.mkdir(parents=True, exist_ok=True)
    temporary = SETUP_DIR / f".{PID_PATH.name}.{secrets.token_hex(8)}.tmp"
    try:
        temporary.write_text(f"{os.getpid()}\n", encoding="ascii")
        os.replace(temporary, PID_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def clear_runtime_files(approval_secret: str) -> None:
    """只清理当前进程创建的 PID 和审批密钥，保留 API token。"""
    try:
        if PID_PATH.read_text(encoding="ascii").strip() == str(os.getpid()):
            PID_PATH.unlink(missing_ok=True)
    except FileNotFoundError:
        pass
    try:
        if APPROVAL_SECRET_PATH.read_text(encoding="ascii").strip() == approval_secret:
            APPROVAL_SECRET_PATH.unlink(missing_ok=True)
    except FileNotFoundError:
        pass
