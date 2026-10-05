"""Serve the web interface and proxy chat streams to Dify from loopback."""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from .config import DEFAULT_HOST, DEFAULT_PORT, WEB_ROOT, dify_api_base, load_dify_api_key


MAX_REQUEST_BYTES = 24_000
PERSONA_CONTEXT = (
    "【平台人设】你是一位沉迷《无畏契约》、熟悉战术配合和高分段打法的资深玩家。"
    "说话自然、有热情，偶尔使用玩家常用表达，但解释要清楚。给战术建议时说明适用场景；"
    "不确定的版本信息要明确说明，不要编造。当前应用的特工资料页包含技能摘要，"
    "技能点位资料尚未录入；精确机制或版本更新应建议用户核对游戏官网与游戏内信息。\n\n"
    "【用户问题】\n"
)


class PlatformHandler(BaseHTTPRequestHandler):
    """Route static assets and safely stream requests to the Dify app API."""

    server_version = "AIUValorant/0.1"

    def log_message(self, format: str, *args: object) -> None:
        """Keep request logs compact and avoid logging chat bodies or secrets."""
        print(f"[valorant-platform] {self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        """Serve health status, the app shell, or a static frontend asset."""
        parsed = urlsplit(self.path)
        if parsed.path == "/api/health":
            self._send_json(200, {"ok": True, "service": "aiu-valorant-platform"})
            return

        relative = unquote(parsed.path.lstrip("/"))
        if not relative or relative.startswith("agents/"):
            relative = "index.html"
        target = (WEB_ROOT / relative).resolve()
        try:
            target.relative_to(WEB_ROOT.resolve())
        except ValueError:
            self.send_error(404)
            return
        if not target.is_file():
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        payload = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        """Validate a chat request and relay Dify's server-sent event stream."""
        if urlsplit(self.path).path != "/api/chat":
            self.send_error(404)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "请求长度无效。"})
            return
        if content_length < 1 or content_length > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "消息为空或超出长度限制。"})
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "请求内容不是有效 JSON。"})
            return
        query = str(payload.get("query", "")).strip()
        user_id = str(payload.get("user", "aiu-local-user"))[:128]
        conversation_id = str(payload.get("conversation_id", ""))[:128]
        if not query or len(query) > 4_000:
            self._send_json(400, {"error": "请输入 1 到 4000 个字符的问题。"})
            return

        request_body = {
            "inputs": {},
            "query": PERSONA_CONTEXT + query,
            "response_mode": "streaming",
            "user": user_id,
        }
        if conversation_id:
            request_body["conversation_id"] = conversation_id

        try:
            api_key = load_dify_api_key()
        except RuntimeError as exc:
            self._send_json(503, {"error": str(exc)})
            return

        request = Request(
            f"{dify_api_base()}/chat-messages",
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )
        headers_sent = False
        try:
            with urlopen(request, timeout=180) as response:
                self.send_response(response.status)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-transform")
                self.send_header("X-Accel-Buffering", "no")
                self.send_header("Connection", "close")
                self.end_headers()
                headers_sent = True
                while True:
                    chunk = response.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except HTTPError as exc:
            detail = exc.read(4_000).decode("utf-8", errors="replace")
            self._send_json(exc.code, {"error": self._dify_error_message(detail)})
        except (URLError, TimeoutError, OSError) as exc:
            detail = "Dify 暂时无法连接。请先启动桌面的“启动 Dify 智能体”快捷方式。"
            if isinstance(exc, URLError) and isinstance(exc.reason, str):
                detail = f"无法连接本机 Dify：{exc.reason}"
            if not headers_sent and not self.wfile.closed:
                self._send_json(502, {"error": detail})

    def _send_json(self, status: int, data: dict[str, object]) -> None:
        """Write a small JSON response for the local frontend."""
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    @staticmethod
    def _dify_error_message(detail: str) -> str:
        """Return Dify's readable error without echoing request credentials."""
        try:
            parsed = json.loads(detail)
        except json.JSONDecodeError:
            return "Dify 拒绝了请求，请检查智能体 API 配置。"
        message = parsed.get("message") or parsed.get("code") or "Dify 请求失败。"
        return str(message)[:500]


def run() -> None:
    """Bind the local server to loopback and start handling requests."""
    host = DEFAULT_HOST
    port = int(os.environ.get("VALORANT_WEB_PORT", DEFAULT_PORT))
    server = ThreadingHTTPServer((host, port), PlatformHandler)
    server.daemon_threads = True
    print(f"VALORANT web platform ready at http://{host}:{port}")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
