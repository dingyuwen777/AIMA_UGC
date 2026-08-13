"""以只读文件方式读取 Secret。"""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

_MAX_SECRET_BYTES = 65_536


class SecretFileError(RuntimeError):
    """Secret 文件不可安全读取。"""


def read_secret_file(path: Path, *, max_bytes: int = _MAX_SECRET_BYTES) -> SecretStr:
    """读取 UTF-8 Secret，仅移除尾部换行，不在错误中包含 Secret 内容。"""
    try:
        stat = path.stat()
    except OSError as exc:
        raise SecretFileError(f"Secret 文件不可访问: {path}") from exc

    if not path.is_file():
        raise SecretFileError(f"Secret 路径不是普通文件: {path}")
    if stat.st_size > max_bytes:
        raise SecretFileError(f"Secret 文件超过允许大小: {path}")

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SecretFileError(f"Secret 文件读取失败: {path}") from exc

    if b"\x00" in raw:
        raise SecretFileError(f"Secret 文件包含非法 NUL 字节: {path}")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SecretFileError(f"Secret 文件不是 UTF-8: {path}") from exc

    value = text.rstrip("\r\n")
    if value == "":
        raise SecretFileError(f"Secret 文件为空: {path}")
    return SecretStr(value)
