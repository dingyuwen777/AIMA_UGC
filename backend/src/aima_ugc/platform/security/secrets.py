"""以只读文件方式读取 Secret，并校验稳定 Secret 引用。"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import SecretStr

_MAX_SECRET_BYTES = 65_536
_SECRET_REF_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class SecretFileError(RuntimeError):
    """Secret 文件不可安全读取。"""


def validate_secret_ref(secret_ref: str) -> str:
    """校验数据库/Contract 可保存的相对 Secret 引用，不读取 Secret 内容。"""
    if not secret_ref or len(secret_ref) > 256:
        raise ValueError("Secret 引用不能为空且长度不能超过 256")
    if secret_ref.startswith("/") or "\\" in secret_ref:
        raise ValueError("Secret 引用必须是使用 / 分隔的相对路径")
    parts = secret_ref.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Secret 引用不能包含空段、. 或 ..")
    if any(_SECRET_REF_PART.fullmatch(part) is None for part in parts):
        raise ValueError("Secret 引用包含不允许的路径字符")
    return secret_ref


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
