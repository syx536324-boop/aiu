"""本机审批队列：让模型提出文件改动，只有用户可执行一次性批准。"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .knowledge import FileSnapshot, KnowledgeError, execute_approved

APPROVAL_TTL_SECONDS = 15 * 60
RESULT_TTL_SECONDS = 60 * 60
MAX_PENDING = 32
MAX_STORED = 256


@dataclass
class Operation:
    """保存一项经校验但尚未执行的文件操作。"""

    operation_id: str
    action: str
    filename: str
    content: str | None
    original: FileSnapshot | None
    created_at: float
    status: str = "pending_approval"
    result: str = ""

    def public_status(self) -> dict[str, object]:
        response: dict[str, object] = {
            "operation_id": self.operation_id,
            "action": self.action,
            "filename": self.filename,
            "status": self.status,
            "message": self.result or _status_message(self.status),
        }
        if self.status == "pending_approval":
            response["expires_in_seconds"] = max(
                0, int(self.created_at + APPROVAL_TTL_SECONDS - time.time())
            )
        return response


def _status_message(status: str) -> str:
    return {
        "pending_approval": "等待这台电脑的用户在本机审批页面确认。",
        "executing": "已批准，正在执行。",
        "rejected": "用户拒绝了文件操作。",
        "expired": "审批已过期，请重新发起操作。",
        "failed": "文件操作未完成。",
        "completed": "文件操作已完成。",
    }.get(status, "未知状态。")


class ApprovalQueue:
    """在锁内变更操作状态，防止重复审批或重复执行。"""

    def __init__(self, on_first_pending: Callable[[], None]) -> None:
        self._lock = threading.Lock()
        self._operations: dict[str, Operation] = {}
        self._on_first_pending = on_first_pending

    def _prune_locked(self) -> None:
        now = time.time()
        for item in self._operations.values():
            if item.status == "pending_approval" and now >= item.created_at + APPROVAL_TTL_SECONDS:
                item.status = "expired"
                item.result = _status_message("expired")
        for key, item in list(self._operations.items()):
            if item.status not in {"pending_approval", "executing"} and now > item.created_at + RESULT_TTL_SECONDS:
                del self._operations[key]
        if len(self._operations) > MAX_STORED:
            finished = sorted(
                (item for item in self._operations.values() if item.status not in {"pending_approval", "executing"}),
                key=lambda item: item.created_at,
            )
            for item in finished[: len(self._operations) - MAX_STORED]:
                del self._operations[item.operation_id]

    def add(
        self,
        action: str,
        filename: str,
        content: str | None,
        original: FileSnapshot | None,
    ) -> dict[str, object]:
        with self._lock:
            self._prune_locked()
            pending_count = sum(
                item.status == "pending_approval" for item in self._operations.values()
            )
            if pending_count >= MAX_PENDING:
                raise KnowledgeError("待审批操作过多，请先处理已有请求。", 429)
            item = Operation(
                operation_id=secrets.token_urlsafe(18),
                action=action,
                filename=filename,
                content=content,
                original=original,
                created_at=time.time(),
            )
            self._operations[item.operation_id] = item
            should_open = pending_count == 0
            response = item.public_status()
        if should_open:
            self._on_first_pending()
        return response

    def get(self, operation_id: str) -> dict[str, object]:
        with self._lock:
            self._prune_locked()
            item = self._operations.get(operation_id)
            if item is None:
                raise KnowledgeError("找不到该操作，或结果已过期。", 404)
            return item.public_status()

    def pending(self) -> list[Operation]:
        with self._lock:
            self._prune_locked()
            return [
                item for item in self._operations.values()
                if item.status == "pending_approval"
            ]

    def decide(self, operation_id: str, decision: str) -> dict[str, object]:
        with self._lock:
            self._prune_locked()
            item = self._operations.get(operation_id)
            if item is None:
                raise KnowledgeError("找不到该操作，或结果已过期。", 404)
            if item.status != "pending_approval":
                raise KnowledgeError("该操作已经处理或过期。", 409)
            if decision == "reject":
                item.status = "rejected"
                item.result = _status_message("rejected")
                return item.public_status()
            if decision != "approve":
                raise KnowledgeError("无效的审批选择。")
            item.status = "executing"

        try:
            result = execute_approved(item.action, item.filename, item.content, item.original)
            final_status = "completed"
        except KnowledgeError as exc:
            result = str(exc)
            final_status = "failed"
        except Exception:
            result = "文件操作遇到意外错误，未能确认完成。"
            final_status = "failed"

        with self._lock:
            item.status = final_status
            item.result = result
            return item.public_status()
