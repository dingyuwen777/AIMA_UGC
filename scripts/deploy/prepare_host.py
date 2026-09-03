#!/usr/bin/env python3
"""准备或校验 Internal V1 的宿主持久目录与内部 Secret。"""

from __future__ import annotations

import argparse
import os
import secrets
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

APP_UID = 10001
APP_GID = 10001
POSTGRES_UID = 999
POSTGRES_GID = 999
SECRET_GID = 11001
DEFAULT_ROOT = Path("/data/AIMA_UGC")
_POSTGRES_CLUSTER_MARKER = Path("postgres/18/docker/PG_VERSION")
_POSTGRES_PASSWORD = Path("shared/secrets/postgres_password")
_BIND_COMPATIBLE_RUNTIME_PATHS = frozenset({"runtime/data", "runtime/logs"})


class HostPreparationError(RuntimeError):
    """Internal V1 宿主目录或 Secret 不满足安全前提。"""


@dataclass(frozen=True, slots=True)
class DirectorySpec:
    relative: str
    uid: int
    gid: int
    mode: int


_RUNTIME_DIRECTORY_SPECS = (
    DirectorySpec(".", 0, 0, 0o750),
    DirectorySpec("runtime", 0, 0, 0o750),
    DirectorySpec("runtime/data", APP_UID, APP_GID, 0o750),
    DirectorySpec("runtime/logs", APP_UID, APP_GID, 0o750),
    DirectorySpec("postgres", POSTGRES_UID, POSTGRES_GID, 0o700),
    DirectorySpec("shared", 0, 0, 0o750),
    DirectorySpec("shared/secrets", 0, SECRET_GID, 0o750),
    DirectorySpec("shared/provider-secrets", APP_UID, APP_GID, 0o700),
)
_DIRECTORY_SPECS = (
    *_RUNTIME_DIRECTORY_SPECS,
    DirectorySpec("backups", 0, 0, 0o750),
    DirectorySpec("releases", 0, 0, 0o750),
    DirectorySpec("shared/env", 0, 0, 0o750),
)
_MANAGED_SECRETS = {
    "postgres_password": 32,
    "import_batch_cursor_signing_key": 48,
    "content_cursor_signing_key": 48,
    "collection_runtime_cursor_signing_key": 48,
}


def _stat_without_symlink(path: Path) -> os.stat_result:
    if path.is_symlink():
        raise HostPreparationError(f"不允许符号链接：{path}")
    try:
        return path.stat()
    except OSError as exc:
        raise HostPreparationError(f"无法访问：{path}") from exc


def _ensure_directory(
    root: Path,
    spec: DirectorySpec,
    *,
    check_only: bool,
    strict_permissions: bool = True,
) -> None:
    """准备目录；Windows bind 仅放宽无法可靠表达的精确 POSIX owner/mode。"""

    path = root if spec.relative == "." else root / spec.relative
    if not path.exists():
        if check_only:
            raise HostPreparationError(f"缺少目录：{path}")
        path.mkdir(parents=True, exist_ok=True)
    info = _stat_without_symlink(path)
    if not stat.S_ISDIR(info.st_mode):
        raise HostPreparationError(f"路径不是目录：{path}")
    if not check_only:
        if strict_permissions:
            os.chown(path, spec.uid, spec.gid)
            os.chmod(path, spec.mode)
        else:
            # Docker Desktop 的 Windows bind mount 可能无法回显容器侧 UID/GID/mode；
            # 仍尽力收紧权限，但不让文件系统翻译能力阻塞 Artifact/日志目录。
            try:
                os.chown(path, spec.uid, spec.gid)
            except OSError:
                pass
            try:
                os.chmod(path, spec.mode)
            except OSError:
                pass
        info = _stat_without_symlink(path)
    if not strict_permissions:
        return
    actual_mode = stat.S_IMODE(info.st_mode)
    if (info.st_uid, info.st_gid, actual_mode) != (spec.uid, spec.gid, spec.mode):
        raise HostPreparationError(
            f"目录权限不符合要求：{path} "
            f"owner={info.st_uid}:{info.st_gid} mode={actual_mode:o}，"
            f"预期 {spec.uid}:{spec.gid} {spec.mode:o}"
        )


def _read_secret(path: Path, *, min_characters: int) -> None:
    info = _stat_without_symlink(path)
    if not stat.S_ISREG(info.st_mode):
        raise HostPreparationError(f"Secret 不是普通文件：{path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise HostPreparationError(f"Secret 无法读取：{path}") from exc
    if b"\x00" in raw:
        raise HostPreparationError(f"Secret 包含 NUL 字节：{path}")
    try:
        value = raw.decode("utf-8").rstrip("\r\n")
    except UnicodeDecodeError as exc:
        raise HostPreparationError(f"Secret 不是 UTF-8：{path}") from exc
    if len(value) < min_characters:
        raise HostPreparationError(f"Secret 长度不足：{path}")


def _write_new_secret(path: Path, *, min_characters: int) -> None:
    value = secrets.token_urlsafe(max(36, min_characters)) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o440)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _secure_secret(
    path: Path,
    *,
    min_characters: int,
    check_only: bool,
) -> None:
    if path.is_symlink():
        raise HostPreparationError(f"不允许符号链接：{path}")
    if not path.exists():
        if check_only:
            raise HostPreparationError(f"缺少基础 Secret：{path}")
        _write_new_secret(path, min_characters=min_characters)
    _read_secret(path, min_characters=min_characters)
    if not check_only:
        os.chown(path, 0, SECRET_GID)
        os.chmod(path, 0o440)
    info = path.stat()
    actual_mode = stat.S_IMODE(info.st_mode)
    if (info.st_uid, info.st_gid, actual_mode) != (0, SECRET_GID, 0o440):
        raise HostPreparationError(
            f"Secret 权限不符合要求：{path} "
            f"owner={info.st_uid}:{info.st_gid} mode={actual_mode:o}，"
            f"预期 0:{SECRET_GID} 440"
        )


def _resolve_host_root(root: Path) -> Path:
    expanded = root.expanduser()
    if not expanded.is_absolute():
        raise HostPreparationError("宿主根目录必须是绝对路径")
    if expanded.is_symlink():
        raise HostPreparationError(f"不允许符号链接：{expanded}")
    return expanded.resolve(strict=False)


def _guard_postgres_password_recovery(root: Path) -> None:
    """已有数据库必须复用原密码；Secret 丢失时拒绝生成一个无法匹配数据库的新值。"""

    marker = root / _POSTGRES_CLUSTER_MARKER
    password = root / _POSTGRES_PASSWORD
    if marker.is_symlink():
        raise HostPreparationError(f"不允许符号链接：{marker}")
    if marker.is_file() and not password.exists() and not password.is_symlink():
        raise HostPreparationError(
            "检测到已有 PostgreSQL 18 数据但缺少 postgres_password；"
            "请恢复与该数据库匹配的原 Secret，禁止自动生成新密码"
        )


def prepare_host(
    root: Path,
    *,
    check_only: bool,
    runtime_only: bool = False,
    runtime_bind_compatible: bool = False,
) -> None:
    """准备/校验宿主目录；已有内部 Secret 只校验和收紧权限，绝不轮换。"""

    if os.name != "posix":
        raise HostPreparationError("Internal V1 宿主准备只支持 Linux/POSIX")
    if runtime_bind_compatible and not runtime_only:
        raise HostPreparationError("bind-compatible 模式只允许与 --runtime-only 一起使用")
    resolved_root = _resolve_host_root(root)
    _guard_postgres_password_recovery(resolved_root)
    if os.geteuid() != 0:
        raise HostPreparationError("宿主准备/校验需要 root 权限，以验证固定容器 UID/GID")

    specs = _RUNTIME_DIRECTORY_SPECS if runtime_only else _DIRECTORY_SPECS
    for spec in specs:
        strict_permissions = not (
            runtime_bind_compatible and spec.relative in _BIND_COMPATIBLE_RUNTIME_PATHS
        )
        _ensure_directory(
            resolved_root,
            spec,
            check_only=check_only,
            strict_permissions=strict_permissions,
        )

    secret_dir = resolved_root / "shared/secrets"
    for name, minimum in _MANAGED_SECRETS.items():
        _secure_secret(
            secret_dir / name,
            min_characters=minimum,
            check_only=check_only,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="准备 Internal V1 宿主持久目录与内部 Secret")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="AIMA_UGC 宿主数据根目录，默认 /data/AIMA_UGC",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="只检查，不创建目录、不生成 Secret、不修改权限",
    )
    parser.add_argument(
        "--runtime-only",
        action="store_true",
        help="只准备 Compose 运行所需 data/log/postgres/secrets；跳过 backups/releases/shared/env",
    )
    parser.add_argument(
        "--runtime-bind-compatible",
        action="store_true",
        help=(
            "仅对 runtime/data 与 runtime/logs 放宽精确 POSIX owner/mode 校验，"
            "用于 Windows bind mount"
        ),
    )
    args = parser.parse_args()
    try:
        prepare_host(
            args.root,
            check_only=args.check_only,
            runtime_only=args.runtime_only,
            runtime_bind_compatible=args.runtime_bind_compatible,
        )
    except HostPreparationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    action = "校验" if args.check_only else "准备"
    print(f"[OK] Internal V1 宿主环境{action}完成：{args.root.expanduser().resolve(strict=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
