"""HTTP 边界：为 Dify 提供文件工具，为本机浏览器提供独立审批页。"""

from __future__ import annotations

import hmac
import html
import json
import re
import socket
import threading
import time
import webbrowser
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .approvals import ApprovalQueue, Operation
from .config import DEFAULT_HOST, DEFAULT_PORT
from .knowledge import KnowledgeError, list_files, read_file, validate_proposal
from .schema import openapi_document

MAX_REQUEST_BYTES = 100_000
MAX_URL_LENGTH = 4096
MAX_WORKERS = 16
REQUEST_TIMEOUT_SECONDS = 10
APPROVAL_ORIGIN = f"http://localhost:{DEFAULT_PORT}"


class BridgeApp:
    """保存 API 凭据及与之完全独立的本机审批会话。"""

    def __init__(self, api_token: str, approval_secret: str) -> None:
        import secrets

        self.api_token = api_token
        self.approval_secret = approval_secret
        self.browser_session = secrets.token_urlsafe(48)
        self.csrf_token = secrets.token_urlsafe(32)
        self.approvals = ApprovalQueue(self.open_approval_browser)

    def open_approval_browser(self) -> None:
        """只在本机进程中拼接私密地址，且不把地址写入工具响应。"""
        url = f"{APPROVAL_ORIGIN}/approval/bootstrap/{self.approval_secret}"

        def _open() -> None:
            try:
                webbrowser.open(url, new=2)
            except Exception:
                pass

        threading.Thread(target=_open, name="file-bridge-approval-browser", daemon=True).start()


class BridgeHTTPServer(ThreadingHTTPServer):
    """持有桥接服务状态并限制处理线程在主进程退出时结束。"""

    daemon_threads = True
    request_queue_size = MAX_WORKERS

    def __init__(self, app: BridgeApp | None = None) -> None:
        super().__init__((DEFAULT_HOST, DEFAULT_PORT), BridgeHandler)
        self.app = app
        self._workers = threading.BoundedSemaphore(MAX_WORKERS)

    def process_request(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        if not self._workers.acquire(blocking=False):
            try:
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\n"
                    b"Content-Length: 0\r\nConnection: close\r\n\r\n"
                )
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            request.settimeout(REQUEST_TIMEOUT_SECONDS)
            super().process_request(request, client_address)
        except Exception:
            self._workers.release()
            raise

    def process_request_thread(
        self, request: socket.socket, client_address: tuple[str, int]
    ) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._workers.release()


class BridgeHandler(BaseHTTPRequestHandler):
    """分派 JSON 工具请求及需浏览器会话和 CSRF 的审批请求。"""

    server: BridgeHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        # 请求路径可能包含仅本机使用的审批密钥，不写入控制台或日志。
        return

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if content_type.startswith("text/html"):
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; "
                "form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            )
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: object) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _html(self, status: int, page: str) -> None:
        self._send(status, page.encode("utf-8"), "text/html; charset=utf-8")

    def _redirect(self, destination: str, cookie: str | None = None) -> None:
        headers = {"Location": destination}
        if cookie:
            headers["Set-Cookie"] = cookie
        self._send(HTTPStatus.SEE_OTHER, b"", "text/plain; charset=utf-8", headers)

    def _requires_bearer(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        expected = "Bearer " + self.server.app.api_token
        if hmac.compare_digest(supplied, expected):
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "需要有效的 Bearer 凭据。"})
        return False

    def _approval_host(self) -> bool:
        return self.headers.get("Host", "").lower() == f"localhost:{DEFAULT_PORT}"

    def _approval_session(self) -> bool:
        if not self._approval_host():
            return False
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            return False
        session = cookies.get("file_bridge_approval")
        return session is not None and hmac.compare_digest(
            session.value, self.server.app.browser_session
        )

    def _query_single(self, query: str, name: str) -> str:
        values = parse_qs(query, keep_blank_values=True).get(name, [])
        if len(values) != 1:
            raise KnowledgeError(f"缺少或重复的 {name} 参数。")
        return values[0]

    def _read_body(self, expected_type: str) -> bytes:
        actual_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if actual_type != expected_type:
            raise KnowledgeError(f"请求必须使用 {expected_type}。", 415)
        size_text = self.headers.get("Content-Length", "")
        if not size_text.isdigit():
            raise KnowledgeError("缺少有效的 Content-Length。", 411)
        size = int(size_text)
        if size <= 0 or size > MAX_REQUEST_BYTES:
            raise KnowledgeError("请求内容为空或过大。", 413)
        deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
        chunks: list[bytes] = []
        remaining = size
        try:
            while remaining:
                wait = deadline - time.monotonic()
                if wait <= 0:
                    raise KnowledgeError("读取请求内容超时。", 408)
                self.connection.settimeout(wait)
                chunk = self.rfile.read1(min(4096, remaining))
                if not chunk:
                    raise KnowledgeError("请求内容不完整。")
                chunks.append(chunk)
                remaining -= len(chunk)
        except TimeoutError as exc:
            raise KnowledgeError("读取请求内容超时。", 408) from exc
        return b"".join(chunks)

    def _json_body(self) -> dict[str, object]:
        raw = self._read_body("application/json")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KnowledgeError("请求需要有效的 UTF-8 JSON。") from exc
        if not isinstance(value, dict):
            raise KnowledgeError("请求 JSON 必须是对象。")
        return value

    def do_GET(self) -> None:
        try:
            self._dispatch_get()
        except KnowledgeError as exc:
            self._json(exc.status_code, {"error": str(exc)})
        except Exception:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "文件服务处理请求失败。"})

    def _dispatch_get(self) -> None:
        if len(self.path) > MAX_URL_LENGTH:
            raise KnowledgeError("请求地址过长。", 414)
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok", "service": "aiu-file-bridge"})
            return
        if path == "/openapi.json":
            self._json(HTTPStatus.OK, openapi_document())
            return
        if path.startswith("/approval"):
            self._approval_get(path, parsed.query)
            return
        if not self._requires_bearer():
            return
        if path == "/files":
            self._json(HTTPStatus.OK, {"files": list_files()})
            return
        if path == "/files/read":
            filename = self._query_single(parsed.query, "filename")
            self._json(HTTPStatus.OK, read_file(filename))
            return
        if path.startswith("/operations/"):
            operation_id = path.removeprefix("/operations/")
            if not re.fullmatch(r"[A-Za-z0-9_-]{20,80}", operation_id):
                raise KnowledgeError("无效的操作编号。")
            self._json(HTTPStatus.OK, self.server.app.approvals.get(operation_id))
            return
        raise KnowledgeError("找不到此接口。", 404)

    def do_POST(self) -> None:
        try:
            self._dispatch_post()
        except KnowledgeError as exc:
            self._json(exc.status_code, {"error": str(exc)})
        except Exception:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "文件服务处理请求失败。"})

    def _dispatch_post(self) -> None:
        if len(self.path) > MAX_URL_LENGTH:
            raise KnowledgeError("请求地址过长。", 414)
        path = urlsplit(self.path).path
        if path == "/approval/shutdown":
            supplied = self.headers.get("X-Bridge-Admin", "")
            if not self._approval_host() or not hmac.compare_digest(
                supplied, self.server.app.approval_secret
            ):
                raise KnowledgeError("无权停止文件服务。", 403)
            self._json(HTTPStatus.OK, {"status": "stopping"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if path == "/approval/decision":
            self._approval_post()
            return
        if not self._requires_bearer():
            return
        action = path.removeprefix("/files/")
        if path not in {"/files/create", "/files/replace", "/files/delete"}:
            raise KnowledgeError("找不到此接口。", 404)
        body = self._json_body()
        required = {"filename", "content"} if action != "delete" else {"filename"}
        if set(body) != required:
            raise KnowledgeError("请求字段不正确。")
        filename = body["filename"]
        content = body.get("content")
        original = validate_proposal(action, filename, content)
        assert isinstance(filename, str)
        assert content is None or isinstance(content, str)
        operation = self.server.app.approvals.add(action, filename, content, original)
        self._json(HTTPStatus.OK, operation)

    def _approval_get(self, path: str, query: str) -> None:
        if not self._approval_host():
            self._html(HTTPStatus.FORBIDDEN, "<h1>仅供本机浏览器访问</h1>")
            return
        if path.startswith("/approval/bootstrap/"):
            supplied = path.removeprefix("/approval/bootstrap/")
            if hmac.compare_digest(supplied, self.server.app.approval_secret):
                cookie = (
                    f"file_bridge_approval={self.server.app.browser_session}; "
                    "HttpOnly; SameSite=Strict; Path=/approval"
                )
                self._redirect("/approval", cookie)
            else:
                self._html(HTTPStatus.FORBIDDEN, "<h1>审批入口已失效</h1>")
            return
        if path != "/approval":
            raise KnowledgeError("找不到此页面。", 404)
        if not self._approval_session():
            self._html(
                HTTPStatus.FORBIDDEN,
                "<h1>需要本机审批会话</h1><p>请使用桌面审批快捷方式打开此页面。</p>",
            )
            return
        notice = ""
        if query == "result=done":
            notice = "审批决定已记录；可让智能体查询操作结果。"
        self._html(HTTPStatus.OK, self._approval_page(self.server.app.approvals.pending(), notice))

    def _approval_page(self, pending: list[Operation], notice: str) -> str:
        blocks: list[str] = []
        if not pending:
            blocks.append("<p>当前没有待审批的文件操作。</p>")
        for item in pending:
            action = {"create": "新建", "replace": "完整覆盖", "delete": "永久删除"}[item.action]
            filename = html.escape(item.filename, quote=True)
            operation_id = html.escape(item.operation_id, quote=True)
            csrf = html.escape(self.server.app.csrf_token, quote=True)
            preview = ""
            if item.content is not None:
                preview = "<p>拟写入的完整内容：</p><pre>" + html.escape(item.content) + "</pre>"
            blocks.append(
                "<section><h2>" + action + "：" + filename + "</h2>"
                + "<p>仅允许操作 aiu/knowledge 中的直接子文件。此请求 15 分钟后过期。</p>"
                + preview
                + '<form method="post" action="/approval/decision">'
                + '<input type="hidden" name="operation_id" value="' + operation_id + '">'
                + '<input type="hidden" name="csrf" value="' + csrf + '">'
                + '<button name="decision" value="approve">批准此操作</button> '
                + '<button name="decision" value="reject">拒绝</button></form></section>'
            )
        message = f"<p>{html.escape(notice)}</p>" if notice else ""
        return (
            '<!doctype html><html lang="zh"><head><meta charset="utf-8">'
            '<meta http-equiv="refresh" content="10">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>AIU 文件操作审批</title>'
            '<style>body{font:16px/1.6 system-ui,sans-serif;max-width:850px;margin:2rem auto;'
            'padding:0 1rem}section{border:1px solid #bbb;border-radius:8px;'
            'padding:1rem;margin:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;'
            'max-height:500px;overflow:auto;background:#f5f5f5;padding:1rem}button{padding:.5rem 1rem}'
            '</style></head><body><h1>AIU 文件操作审批</h1>'
            '<p>请核对文件名和内容后再批准。操作由本机用户确认，Dify 无法自行批准。</p>'
            + message + "".join(blocks) + "</body></html>"
        )

    def _approval_post(self) -> None:
        if not self._approval_session():
            raise KnowledgeError("需要本机审批会话。", 403)
        if self.headers.get("Origin", "") != APPROVAL_ORIGIN:
            raise KnowledgeError("审批请求来源不正确。", 403)
        raw = self._read_body("application/x-www-form-urlencoded")
        try:
            fields = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError as exc:
            raise KnowledgeError("审批表单编码错误。") from exc
        if set(fields) != {"operation_id", "decision", "csrf"} or any(
            len(values) != 1 for values in fields.values()
        ):
            raise KnowledgeError("审批表单字段错误。")
        if not hmac.compare_digest(fields["csrf"][0], self.server.app.csrf_token):
            raise KnowledgeError("审批表单已失效。", 403)
        self.server.app.approvals.decide(fields["operation_id"][0], fields["decision"][0])
        self._redirect("/approval?result=done")
