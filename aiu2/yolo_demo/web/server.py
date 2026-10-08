"""Compose the local HTTP API and static web UI for live YOLO inference."""

from __future__ import annotations

import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ..config import ROOT, prepare_environment
from ..services.live_inference import LiveInferenceService

WEB_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = WEB_ROOT / "static"
SERVICE = LiveInferenceService()


class AppServer(ThreadingHTTPServer):
    """HTTP server that shares one inference service across browser requests."""

    daemon_threads = True
    allow_reuse_address = True


class RequestHandler(BaseHTTPRequestHandler):
    """Serve same-origin REST endpoints, MJPEG frames, and static assets."""

    server_version = "AIU-YOLO/1.0"

    def log_message(self, format: str, *args: object) -> None:
        print(f"[web] {self.address_string()} - {format % args}", flush=True)

    def _json(self, payload: dict, status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 16_384:
            raise ValueError("请求内容过大。")
        raw = self.rfile.read(length) if length else b"{}"
        parsed = json.loads(raw.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("请求格式应为 JSON 对象。")
        return parsed

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        if route == "/api/config":
            self._json({"weights": SERVICE.available_weights(), "default_camera": 0})
        elif route == "/api/status":
            self._json(SERVICE.status())
        elif route == "/api/stream":
            self._stream()
        else:
            self._static(route)

    def do_POST(self) -> None:
        route = urlsplit(self.path).path
        try:
            if route == "/api/start":
                body = self._body()
                camera = int(body.get("camera", 0))
                confidence = float(body.get("confidence", 0.25))
                weight_path = str(body.get("weight", ""))
                if not 0 <= camera <= 8:
                    raise ValueError("摄像头编号需在 0 到 8 之间。")
                if not 0.05 <= confidence <= 0.95:
                    raise ValueError("置信度需在 0.05 到 0.95 之间。")
                SERVICE.start(camera, weight_path, confidence)
                self._json({"ok": True, "status": SERVICE.status()})
            elif route == "/api/stop":
                SERVICE.stop()
                self._json({"ok": True, "status": SERVICE.status()})
            elif route == "/api/shutdown":
                SERVICE.stop()
                self._json({"ok": True, "message": "本地服务正在关闭。"})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self._json({"error": "未找到该接口。"}, 404)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def _stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Connection", "close")
        self.end_headers()
        previous: bytes | None = None
        try:
            while True:
                frame = SERVICE.latest_frame()
                if frame and frame is not previous:
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
                    self.wfile.flush()
                    previous = frame
                time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _static(self, route: str) -> None:
        relative = "index.html" if route == "/" else unquote(route.lstrip("/"))
        path = (STATIC_ROOT / relative).resolve()
        if not path.is_relative_to(STATIC_ROOT.resolve()) or not path.is_file():
            self._json({"error": "未找到该页面或静态文件。"}, 404)
            return
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


def serve_web(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the local app and stop its camera cleanly on exit."""
    prepare_environment()
    server = AppServer((host, port), RequestHandler)
    print(f"AIU YOLO app: http://{host}:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping AIU YOLO app...", flush=True)
    finally:
        SERVICE.stop()
        server.server_close()
