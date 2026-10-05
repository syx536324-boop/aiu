"""Ollama API 适配器：把智能体对话请求发送到本机的 /api/chat。"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaClientError(RuntimeError):
    """提供适合命令行展示的 Ollama 通信错误。"""


class OllamaClient:
    """通过 Ollama 的 HTTP API 请求聊天回复。"""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: int = 180) -> None:
        self.chat_url = f"{base_url.rstrip('/')}/api/chat"
        self.timeout = timeout

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """提交一轮聊天请求，并返回 Ollama 的 JSON 响应。"""
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        request = Request(
            self.chat_url,
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace").strip()
            message = details or str(exc.reason)
            raise OllamaClientError(f"Ollama 返回 HTTP {exc.code}: {message}") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise OllamaClientError(
                f"无法连接 {self.chat_url}（{reason}）。请确认 Ollama 正在运行。"
            ) from exc
        except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise OllamaClientError(f"Ollama 响应异常：{exc}") from exc

        if not isinstance(result, dict) or not isinstance(result.get("message"), dict):
            raise OllamaClientError("Ollama 响应里缺少 message 对象。")
        return result
