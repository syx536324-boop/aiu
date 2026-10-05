"""知识文件适配层：复用 agent 的约束并用 Windows 句柄执行安全操作。"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from agent import knowledge as existing
from .safe_file import SafeFileError, locked_directory, verified_file


class KnowledgeError(Exception):
    """供 HTTP 层转换为安全错误响应的文件操作异常。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class FileSnapshot:
    """记录待审批文件的身份和修改时间，防止审批前目标被替换。"""

    device: int
    inode: int
    size: int
    modified_ns: int


def _safe_root() -> Path:
    root = existing.KNOWLEDGE_DIR
    if root.is_symlink() or getattr(root, "is_junction", lambda: False)():
        raise KnowledgeError("knowledge 目录不能是符号链接或目录联接。")
    if root.exists():
        resolved = root.resolve(strict=True)
        absolute = root.absolute()
        if os.path.normcase(str(resolved)) != os.path.normcase(str(absolute)):
            raise KnowledgeError("knowledge 目录不能指向项目外部。")
        if not root.is_dir():
            raise KnowledgeError("knowledge 路径不是目录。")
    return root


def _valid_name(filename: object) -> str:
    error = existing._validate_filename(filename)
    if error:
        raise KnowledgeError(error)
    assert isinstance(filename, str)
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in filename):
        raise KnowledgeError("文件名不能包含控制或隐藏格式字符。")
    return filename


def _existing(filename: object) -> Path:
    _safe_root()
    name = _valid_name(filename)
    candidate, error = existing._existing_file(name)
    if error:
        raise KnowledgeError(error, 404 if "找不到" in error else 400)
    assert candidate is not None
    return candidate


def _new(filename: object) -> Path:
    _safe_root()
    name = _valid_name(filename)
    candidate, error = existing._new_file_path(name)
    if error:
        raise KnowledgeError(error)
    assert candidate is not None
    return candidate


def _content(content: object) -> str:
    encoded, error = existing._validated_content(content)
    if error:
        raise KnowledgeError(error)
    assert encoded is not None and isinstance(content, str)
    return content


def list_files() -> list[str]:
    root = _safe_root()
    if not root.exists():
        return []
    try:
        names = []
        with locked_directory(root):
            for candidate in root.iterdir():
                if candidate.suffix.lower() not in existing.ALLOWED_EXTENSIONS:
                    continue
                try:
                    _valid_name(candidate.name)
                    with verified_file(candidate, "read"):
                        names.append(candidate.name)
                except (KnowledgeError, SafeFileError, OSError):
                    continue
        return sorted(names)
    except (OSError, SafeFileError) as exc:
        raise KnowledgeError(f"无法列出知识文件：{exc}") from exc


def read_file(filename: object) -> dict[str, object]:
    candidate = _existing(filename)
    try:
        with verified_file(candidate, "read") as handle:
            raw = handle.read_bytes(existing.MAX_FILE_BYTES + 1)
        if len(raw) > existing.MAX_FILE_BYTES:
            raise KnowledgeError("读取失败：文件超过 1 MB。")
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise KnowledgeError("读取失败：文件需要使用 UTF-8 编码。") from exc
    except (OSError, SafeFileError) as exc:
        raise KnowledgeError(f"无法读取知识文件：{exc}") from exc
    truncated = len(content) > existing.MAX_FILE_CHARACTERS
    if truncated:
        content = content[: existing.MAX_FILE_CHARACTERS]
    return {"filename": filename, "content": content, "truncated": truncated}


def _snapshot_values(values: tuple[int, int, int, int]) -> FileSnapshot:
    return FileSnapshot(*values)


def _editable_original(raw: bytes) -> None:
    if len(raw) > existing.MAX_FILE_BYTES:
        raise KnowledgeError("无法覆盖：原文件超过 1 MB。")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise KnowledgeError("无法覆盖：原文件需要使用 UTF-8 编码。") from exc
    if len(content) > existing.MAX_FILE_CHARACTERS:
        raise KnowledgeError("无法覆盖：原文件超过 12000 字符，读取时会被截断。")


def validate_proposal(action: str, filename: object, content: object = None) -> FileSnapshot | None:
    """提案时先验证范围、大小及目标状态，不改变任何文件。"""
    if action == "create":
        _new(filename)
        _content(content)
        return None
    if action == "replace":
        _content(content)
    elif action != "delete":
        raise KnowledgeError("不支持的文件操作。")
    candidate = _existing(filename)
    try:
        with verified_file(candidate, "read") as handle:
            if action == "replace":
                _editable_original(handle.read_bytes(existing.MAX_FILE_BYTES + 1))
            return _snapshot_values(handle.snapshot_values())
    except SafeFileError as exc:
        raise KnowledgeError(str(exc)) from exc


def execute_approved(
    action: str,
    filename: str,
    content: str | None,
    original: FileSnapshot | None,
) -> str:
    """仅在本机用户批准后调用；执行前再核对目标没有变化。"""
    if action == "create":
        root = _safe_root()
        _new(filename)
        try:
            with locked_directory(root):
                _new(filename)
                result = existing.create_knowledge_file(
                    filename, _content(content), lambda *_: True
                )
        except SafeFileError as exc:
            raise KnowledgeError(str(exc)) from exc
        if not result.startswith("已新建文件："):
            raise KnowledgeError(result)
        return result

    candidate = _existing(filename)
    try:
        with verified_file(candidate, action) as handle:
            if _snapshot_values(handle.snapshot_values()) != original:
                raise KnowledgeError("文件在等待审批期间发生变化，请重新发起操作。")
            if action == "replace":
                old_content = handle.read_bytes(existing.MAX_FILE_BYTES + 1)
                _editable_original(old_content)
                new_content = _content(content).encode("utf-8")
                handle.replace_bytes(new_content, old_content)
                return f"已覆盖文件：{filename}。"
            if action == "delete":
                handle.delete()
                return f"已删除文件：{filename}。"
    except SafeFileError as exc:
        raise KnowledgeError(str(exc)) from exc
    raise KnowledgeError("不支持的文件操作。")
