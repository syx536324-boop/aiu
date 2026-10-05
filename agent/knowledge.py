"""本地文件模块：在 knowledge 目录内列出、读取、新建、覆盖和删除文本文件。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
ALLOWED_EXTENSIONS = {".md", ".txt"}
MAX_FILE_BYTES = 1_000_000
MAX_FILE_CHARACTERS = 12_000
Confirmation = Callable[[str, str], bool]


def list_knowledge_files() -> str:
    """列出知识目录的 Markdown 和纯文本文件名，不访问目录之外的路径。"""
    try:
        if KNOWLEDGE_DIR.is_symlink():
            return "无法访问知识目录：不允许 knowledge 文件夹本身是符号链接。"
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        filenames = sorted(
            path.name
            for path in KNOWLEDGE_DIR.iterdir()
            if not path.is_symlink()
            and path.is_file()
            and path.suffix.lower() in ALLOWED_EXTENSIONS
        )
    except OSError as exc:
        return f"无法列出知识文件：{exc}"

    if not filenames:
        return "知识目录中还没有 .md 或 .txt 文件。请先把资料放入项目的 knowledge 文件夹。"
    return "可用知识文件：\n" + "\n".join(f"- {name}" for name in filenames)


def read_knowledge_file(filename: str) -> str:
    """读取知识目录内一个 UTF-8 文本文件，拒绝路径跳转和超大文件。"""
    candidate, error = _existing_file(filename)
    if error:
        return error
    assert candidate is not None

    try:
        with candidate.open("rb") as file:
            content_bytes = file.read(MAX_FILE_BYTES + 1)
        if len(content_bytes) > MAX_FILE_BYTES:
            return f"读取失败：单个文件不能超过 {MAX_FILE_BYTES // 1_000_000} MB。"
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return "读取失败：请先将文件另存为 UTF-8 编码。"
    except OSError as exc:
        return f"无法读取文件：{exc}"

    if len(content) > MAX_FILE_CHARACTERS:
        content = content[:MAX_FILE_CHARACTERS] + "\n\n[文件内容过长，后续内容已截断]"
    return f"文件：{filename}\n\n{content or '[文件为空]'}"


def create_knowledge_file(
    filename: str, content: str, confirm: Confirmation | None
) -> str:
    """在知识目录中新建文本文件；已存在文件不会被覆盖。"""
    candidate, error = _new_file_path(filename)
    if error:
        return error
    assert candidate is not None
    content_bytes, error = _validated_content(content)
    if error:
        return error
    assert content_bytes is not None
    if not _confirm(
        confirm,
        f"将新建文件：{filename}（{len(content_bytes)} 字节）\n内容：\n{content}",
        f"CREATE {filename}",
    ):
        return "已取消新建文件。"

    try:
        with candidate.open("x", encoding="utf-8", newline="") as file:
            file.write(content)
    except FileExistsError:
        return "新建失败：文件已存在，未覆盖。"
    except OSError as exc:
        return f"新建文件失败：{exc}"
    return f"已新建文件：{filename}。"


def replace_knowledge_file(
    filename: str, content: str, confirm: Confirmation | None
) -> str:
    """完整替换知识目录中的现有文件，先展示新内容并请求确认。"""
    candidate, error = _existing_file(filename)
    if error:
        return error
    assert candidate is not None
    content_bytes, error = _validated_content(content)
    if error:
        return error
    assert content_bytes is not None
    if not _confirm(
        confirm,
        f"将完整覆盖文件：{filename}（新内容 {len(content_bytes)} 字节）\n新内容：\n{content}",
        f"OVERWRITE {filename}",
    ):
        return "已取消覆盖文件。"

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=KNOWLEDGE_DIR,
            prefix=".aiu-write-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
        os.replace(temporary_path, candidate)
    except OSError as exc:
        return f"覆盖文件失败：{exc}"
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return f"已覆盖文件：{filename}。"


def delete_knowledge_file(filename: str, confirm: Confirmation | None) -> str:
    """删除知识目录中的一个现有文本文件，必须输入带文件名的确认词。"""
    candidate, error = _existing_file(filename)
    if error:
        return error
    assert candidate is not None
    if not _confirm(
        confirm,
        f"将永久删除文件：{filename}",
        f"DELETE {filename}",
    ):
        return "已取消删除文件。"

    candidate, error = _existing_file(filename)
    if error:
        return error
    assert candidate is not None
    try:
        candidate.unlink()
    except OSError as exc:
        return f"删除文件失败：{exc}"
    return f"已删除文件：{filename}。"


def _existing_file(filename: str) -> tuple[Path | None, str | None]:
    """验证目录、文件名、链接和文件类型，返回知识目录中的普通文件。"""
    error = _validate_filename(filename)
    if error:
        return None, error
    try:
        if KNOWLEDGE_DIR.is_symlink():
            return None, "文件操作失败：不允许 knowledge 文件夹本身是符号链接。"
        root = KNOWLEDGE_DIR.resolve(strict=True)
        candidate = KNOWLEDGE_DIR / filename
        if candidate.is_symlink():
            return None, "文件操作失败：不允许通过符号链接访问文件。"
        resolved = candidate.resolve(strict=True)
        if resolved.parent != root or not resolved.is_file():
            return None, "文件操作失败：目标必须是 knowledge 文件夹中的直接子文件。"
        return resolved, None
    except FileNotFoundError:
        return None, f"文件操作失败：找不到 knowledge 文件“{filename}”。"
    except OSError as exc:
        return None, f"文件操作失败：{exc}"


def _new_file_path(filename: str) -> tuple[Path | None, str | None]:
    """准备 knowledge 目录中的新文件路径，但不覆盖已有文件。"""
    error = _validate_filename(filename)
    if error:
        return None, error
    try:
        if KNOWLEDGE_DIR.is_symlink():
            return None, "文件操作失败：不允许 knowledge 文件夹本身是符号链接。"
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        candidate = KNOWLEDGE_DIR / filename
        if candidate.is_symlink() or candidate.exists():
            return None, "新建失败：文件已存在，不能用新建操作覆盖。"
        return candidate, None
    except OSError as exc:
        return None, f"文件操作失败：{exc}"


def _validate_filename(filename: str) -> str | None:
    """只接受 knowledge 目录直接子项中的 .md/.txt 普通文件名。"""
    invalid_chars = '<>:"|?*'
    if (
        not isinstance(filename, str)
        or not filename
        or filename in {".", ".."}
        or filename != filename.strip()
        or filename[-1] in {".", " "}
        or "/" in filename
        or "\\" in filename
        or any(character in filename for character in invalid_chars)
    ):
        return "文件操作失败：只能提供不含路径的单个文件名。"
    if Path(filename).name != filename:
        return "文件操作失败：不能访问 knowledge 文件夹之外的路径。"
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        return "文件操作失败：只允许 .md 和 .txt 文件。"
    reserved_names = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
    if filename.split(".", 1)[0].rstrip(" .").upper() in reserved_names:
        return "文件操作失败：文件名与 Windows 系统设备名冲突。"
    return None


def _validated_content(content: str) -> tuple[bytes | None, str | None]:
    """校验模型提供的 UTF-8 文件内容和最大长度。"""
    if not isinstance(content, str):
        return None, "文件操作失败：content 参数必须是字符串。"
    if len(content) > MAX_FILE_CHARACTERS:
        return None, f"文件操作失败：新内容不能超过 {MAX_FILE_CHARACTERS} 个字符。"
    try:
        encoded = content.encode("utf-8")
    except UnicodeEncodeError:
        return None, "文件操作失败：content 中包含无法保存为 UTF-8 的字符。"
    if len(encoded) > MAX_FILE_BYTES:
        return None, f"文件操作失败：新内容不能超过 {MAX_FILE_BYTES // 1_000_000} MB。"
    return encoded, None


def _confirm(
    confirm: Confirmation | None, action: str, phrase: str
) -> bool:
    """通过 CLI 确认回调，要求用户输入与操作对应的精确短语。"""
    return confirm is not None and confirm(action, phrase)
