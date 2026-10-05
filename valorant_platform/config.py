"""Load local server settings and the private Dify application API key."""

from __future__ import annotations

import os
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = Path(__file__).resolve().parent / "web"
DEFAULT_DIFY_API_BASE = "http://127.0.0.1/v1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8780


def load_dify_api_key() -> str:
    """Read an override or the already-protected project secret file."""
    override = os.environ.get("DIFY_API_KEY", "").strip()
    if override:
        return override

    key_file = Path(os.environ.get("DIFY_API_KEY_FILE", PROJECT_ROOT / ".setup" / "dify-agent-api.txt"))
    try:
        content = key_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("无法读取本机 Dify API 密钥；请使用 Windows 用户 shao 启动此应用。") from exc

    match = re.search(r"^API key:\s*(\S+)\s*$", content, re.IGNORECASE | re.MULTILINE)
    if not match:
        raise RuntimeError("本机 Dify API 密钥文件格式不正确。")
    return match.group(1)


def dify_api_base() -> str:
    """Return the Dify API base URL without a trailing slash."""
    return os.environ.get("DIFY_API_BASE", DEFAULT_DIFY_API_BASE).strip().rstrip("/")
