"""以文件方式读写 Secret，并校验稳定 Secret 引用。"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from pydantic import SecretStr

_MAX_SECRET_BYTES = 65_536
_SECRET_REF_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class SecretFileError(RuntimeError):
    """Secret 文件不可安全读写。"""


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


def _secret_path(root: Path, secret_ref: str) -> tuple[Path, Path]:
    """解析 Secret 引用且不要求目标文件已存在。"""

    validated = validate_secret_ref(secret_ref)
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise SecretFileError("Secret Root 不可访问") from exc
    candidate = resolved_root.joinpath(*validated.split("/"))
    current = resolved_root
    for part in validated.split("/")[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise SecretFileError("Secret 目录不允许使用符号链接")
    try:
        candidate.parent.resolve(strict=False).relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise SecretFileError("Secret 引用越过批准根目录") from exc
    return resolved_root, candidate


def read_secret_file(
    path: Path,
    *,
    root: Path | None = None,
    max_bytes: int = _MAX_SECRET_BYTES,
) -> SecretStr:
    """读取 UTF-8 Secret；拒绝 symlink 和可解析到批准根目录之外的路径。"""
    try:
        if path.is_symlink():
            raise SecretFileError("Secret 文件不允许使用符号链接")
        resolved_path = path.resolve(strict=True)
        if root is not None:
            resolved_root = root.resolve(strict=True)
            try:
                resolved_path.relative_to(resolved_root)
            except ValueError as exc:
                raise SecretFileError("Secret 文件越过批准根目录") from exc
        stat = resolved_path.stat()
    except SecretFileError:
        raise
    except OSError as exc:
        raise SecretFileError("Secret 文件不可访问") from exc

    if not resolved_path.is_file():
        raise SecretFileError("Secret 路径不是普通文件")
    if stat.st_size > max_bytes:
        raise SecretFileError("Secret 文件超过允许大小")

    try:
        raw = resolved_path.read_bytes()
    except OSError as exc:
        raise SecretFileError("Secret 文件读取失败") from exc

    if b"\x00" in raw:
        raise SecretFileError("Secret 文件包含非法 NUL 字节")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SecretFileError("Secret 文件不是 UTF-8") from exc

    value = text.rstrip("\r\n")
    if value == "":
        raise SecretFileError("Secret 文件为空")
    return SecretStr(value)


def read_secret_ref(root: Path, secret_ref: str) -> SecretStr:
    """按数据库中的安全引用读取 Secret。"""

    _, path = _secret_path(root, secret_ref)
    return read_secret_file(path, root=root)


def write_secret_ref(root: Path, secret_ref: str, secret: SecretStr) -> Path:
    """原子创建不可变 Secret 引用；禁止覆盖，保证旧 Run Snapshot 可重复读取。"""

    value = secret.get_secret_value()
    if not value or "\x00" in value:
        raise ValueError("Secret 不能为空或包含 NUL")
    encoded = value.encode("utf-8")
    if len(encoded) > _MAX_SECRET_BYTES:
        raise ValueError("Secret 超过允许大小")

    resolved_root, target = _secret_path(root, secret_ref)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.parent.resolve(strict=True).relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise SecretFileError("Secret 目录不可安全创建") from exc
    if target.exists() or target.is_symlink():
        raise SecretFileError("Secret 引用已存在，禁止覆盖历史 Secret")

    fd, temporary_name = tempfile.mkstemp(prefix=".aima-secret-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        # `link` 在目标已存在时原子失败；不能像 os.replace 那样覆盖并发创建的历史 Secret。
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise SecretFileError("Secret 引用已存在，禁止覆盖历史 Secret") from exc
        temporary.unlink()
        target.chmod(0o600)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target


__all__ = [
    "SecretFileError",
    "read_secret_file",
    "read_secret_ref",
    "validate_secret_ref",
    "write_secret_ref",
]
