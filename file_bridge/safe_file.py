"""Windows 文件句柄边界：锁定目标并验证最终路径后再读取或修改。"""

from __future__ import annotations

import ctypes
import os
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import Iterator


class SafeFileError(Exception):
    """文件句柄无法安全打开、验证或操作。"""


if os.name == "nt":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _FileInformation(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD),
            ("created", wintypes.FILETIME),
            ("accessed", wintypes.FILETIME),
            ("modified", wintypes.FILETIME),
            ("volume", wintypes.DWORD),
            ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD),
            ("links", wintypes.DWORD),
            ("index_high", wintypes.DWORD),
            ("index_low", wintypes.DWORD),
        ]

    class _DispositionInformation(ctypes.Structure):
        _fields_ = [("delete_file", wintypes.BOOLEAN)]

    _CreateFileW = _kernel32.CreateFileW
    _CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    _CreateFileW.restype = wintypes.HANDLE
    _GetFileInformationByHandle = _kernel32.GetFileInformationByHandle
    _GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FileInformation)]
    _GetFileInformationByHandle.restype = wintypes.BOOL
    _GetFinalPathNameByHandleW = _kernel32.GetFinalPathNameByHandleW
    _GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
    ]
    _GetFinalPathNameByHandleW.restype = wintypes.DWORD
    _ReadFile = _kernel32.ReadFile
    _ReadFile.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    _ReadFile.restype = wintypes.BOOL
    _WriteFile = _kernel32.WriteFile
    _WriteFile.argtypes = [
        wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    _WriteFile.restype = wintypes.BOOL
    _SetFilePointerEx = _kernel32.SetFilePointerEx
    _SetFilePointerEx.argtypes = [
        wintypes.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD,
    ]
    _SetFilePointerEx.restype = wintypes.BOOL
    _SetEndOfFile = _kernel32.SetEndOfFile
    _SetEndOfFile.argtypes = [wintypes.HANDLE]
    _SetEndOfFile.restype = wintypes.BOOL
    _FlushFileBuffers = _kernel32.FlushFileBuffers
    _FlushFileBuffers.argtypes = [wintypes.HANDLE]
    _FlushFileBuffers.restype = wintypes.BOOL
    _SetFileInformationByHandle = _kernel32.SetFileInformationByHandle
    _SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD,
    ]
    _SetFileInformationByHandle.restype = wintypes.BOOL
    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL

_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_DELETE = 0x00010000
_FILE_READ_ATTRIBUTES = 0x00000080
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_DISPOSITION_INFO = 4
_INVALID_HANDLE = ctypes.c_void_p(-1).value


def _win_error(message: str) -> SafeFileError:
    return SafeFileError(f"{message}（Windows 错误 {ctypes.get_last_error()}）。")


def _canonical(path: str | Path) -> str:
    raw = str(path)
    if raw.startswith("\\\\?\\UNC\\"):
        raw = "\\\\" + raw[8:]
    elif raw.startswith("\\\\?\\"):
        raw = raw[4:]
    return os.path.normcase(os.path.normpath(raw))


def _open_handle(path: Path, access: int, share: int, directory: bool = False) -> int:
    if os.name != "nt":
        raise SafeFileError("安全文件桥接目前仅支持 Windows 主机。")
    flags = _FILE_FLAG_OPEN_REPARSE_POINT
    if directory:
        flags |= _FILE_FLAG_BACKUP_SEMANTICS
    handle = _CreateFileW(str(path), access, share, None, _OPEN_EXISTING, flags, None)
    if handle == _INVALID_HANDLE or handle is None:
        raise _win_error("无法安全打开知识文件")
    return handle


def _information(handle: int) -> _FileInformation:
    details = _FileInformation()
    if not _GetFileInformationByHandle(handle, ctypes.byref(details)):
        raise _win_error("无法检查文件句柄")
    return details


def _final_path(handle: int) -> str:
    buffer = ctypes.create_unicode_buffer(32768)
    length = _GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if length == 0 or length >= len(buffer):
        raise _win_error("无法核对文件最终路径")
    return _canonical(buffer.value)


def _verified_information(handle: int, expected_path: Path, is_directory: bool) -> _FileInformation:
    details = _information(handle)
    if details.attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
        raise SafeFileError("不能访问符号链接或其他重解析点。")
    if bool(details.attributes & _FILE_ATTRIBUTE_DIRECTORY) != is_directory:
        raise SafeFileError("知识文件类型不正确。")
    final = _final_path(handle)
    expected = _canonical(expected_path.absolute())
    if final != expected:
        raise SafeFileError("目标最终路径不在允许的 knowledge 目录中。")
    if not is_directory and details.links != 1:
        raise SafeFileError("不能访问硬链接知识文件。")
    return details


class LockedFile:
    """持有已验证的 Windows 文件句柄，直至操作结束。"""

    def __init__(self, handle: int, details: _FileInformation) -> None:
        self.handle = handle
        self.details = details

    def snapshot_values(self) -> tuple[int, int, int, int]:
        details = self.details
        return (
            details.volume,
            (details.index_high << 32) | details.index_low,
            (details.size_high << 32) | details.size_low,
            (details.modified.dwHighDateTime << 32) | details.modified.dwLowDateTime,
        )

    def _seek_start(self) -> None:
        if not _SetFilePointerEx(self.handle, 0, None, 0):
            raise _win_error("无法定位文件句柄")

    def read_bytes(self, limit: int) -> bytes:
        self._seek_start()
        chunks: list[bytes] = []
        remaining = limit
        while remaining > 0:
            count = min(65536, remaining)
            buffer = ctypes.create_string_buffer(count)
            received = wintypes.DWORD()
            if not _ReadFile(self.handle, buffer, count, ctypes.byref(received), None):
                raise _win_error("读取知识文件失败")
            if received.value == 0:
                break
            chunks.append(buffer.raw[: received.value])
            remaining -= received.value
        return b"".join(chunks)

    def _write_bytes(self, data: bytes) -> None:
        self._seek_start()
        offset = 0
        while offset < len(data):
            chunk = data[offset : offset + 65536]
            buffer = ctypes.create_string_buffer(chunk)
            written = wintypes.DWORD()
            if not _WriteFile(self.handle, buffer, len(chunk), ctypes.byref(written), None):
                raise _win_error("写入知识文件失败")
            if written.value == 0:
                raise SafeFileError("写入知识文件时没有写入任何数据。")
            offset += written.value
        if not _SetEndOfFile(self.handle):
            raise _win_error("无法截断知识文件")
        if not _FlushFileBuffers(self.handle):
            raise _win_error("无法保存知识文件")

    def replace_bytes(self, new_content: bytes, original_content: bytes) -> None:
        try:
            self._write_bytes(new_content)
        except SafeFileError:
            try:
                self._write_bytes(original_content)
            except SafeFileError:
                raise SafeFileError("写入失败，尝试恢复原内容也未成功，请手动检查文件。")
            raise

    def delete(self) -> None:
        details = _DispositionInformation()
        details.delete_file = 1
        if not _SetFileInformationByHandle(
            self.handle, _FILE_DISPOSITION_INFO, ctypes.byref(details), ctypes.sizeof(details)
        ):
            raise _win_error("删除知识文件失败")


@contextmanager
def verified_file(path: Path, purpose: str) -> Iterator[LockedFile]:
    """打开实际文件并锁定；句柄最终路径必须仍是请求的直接子文件。"""
    if purpose == "read":
        access, share = _GENERIC_READ, _FILE_SHARE_READ
    elif purpose == "replace":
        access, share = _GENERIC_READ | _GENERIC_WRITE, 0
    elif purpose == "delete":
        access, share = _GENERIC_READ | _DELETE, 0
    else:
        raise SafeFileError("不支持的文件句柄操作。")
    handle = _open_handle(path, access, share)
    try:
        details = _verified_information(handle, path, is_directory=False)
        yield LockedFile(handle, details)
    finally:
        if not _CloseHandle(handle):
            raise _win_error("无法关闭知识文件句柄")


@contextmanager
def locked_directory(path: Path) -> Iterator[None]:
    """创建文件时固定 knowledge 目录，阻止它在操作中被替换。"""
    handle = _open_handle(
        path,
        _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE,
        directory=True,
    )
    try:
        _verified_information(handle, path, is_directory=True)
        yield
    finally:
        if not _CloseHandle(handle):
            raise _win_error("无法关闭知识目录句柄")
