#!/usr/bin/env python3
"""准备或校验 Internal V1 的宿主持久目录与基础 Secret。"""

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


class HostPreparationError(RuntimeError):
    """Internal V1 宿主目录或 Secret 不满足安全前提。"""


@dataclass(frozen=True, slots=True)
class DirectorySpec:
    relative: str
    uid: int
    gid: int
    mode: int


_DIRECTORY_SPECS = (
    DirectorySpec(".", 0, 0, 0o750),
    DirectorySpec("runtime", 0, 0, 0o750),
    DirectorySpec("runtime/data", APP_UID, APP_GID, 0o750),
    DirectorySpec("runtime/logs", APP_UID, APP_GID, 0o750),
    DirectorySpec("postgres", POSTGRES_UID, POSTGRES_GID, 0o700),
    DirectorySpec("backups", 0, 0, 0o750),
    DirectorySpec("releases", 0, 0, 0o750),
    DirectorySpec("shared", 0, 0, 0o750),
    DirectorySpec("shared/env", 0, 0, 0o750),
    DirectorySpec("shared/secrets", 0, SECRET_GID, 0o750),
)

_MANAGED_SECRETS = {
    "postgres_password": 32,
    "import_batch_cursor_signing_key": 48,
    "content_cursor_signing_key": 48,
    "collection_runtime_cursor_signing_key": 48,
}
_OPTIONAL_EXTERNAL_SECRETS = ("tikhub_api_key", "llm_api_key")


def _stat_without_symlink(path: Path) -> os.stat_result:
    if path.is_symlink():
        raise HostPreparationError(f"不允许符号链接：{path}")
    try:
        return path.stat()
    except OSError as exc:
        raise HostPreparationError(f"无法访问：{path}") from exc


def _ensure_directory(root: Path, spec: DirectorySpec, *, check_only: bool) -> None:
    path = root if spec.relative == "." else root / spec.relative
    if not path.exists():
        if check_only:
            raise HostPreparationError(f"缺少目录：{path}")
        path.mkdir(parents=True, exist_ok=True)
    info = _stat_without_symlink(path)
    if not stat.S_ISDIR(info.st_mode):
        raise HostPreparationError(f"路径不是目录：{path}")
    if not check_only:
        os.chown(path, spec.uid, spec.gid)
        os.chmod(path, spec.mode)
        info = path.stat()
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
    create: bool,
) -> None:
    if path.is_symlink():
        raise HostPreparationError(f"不允许符号链接：{path}")
    if not path.exists():
        if check_only or not create:
            if create:
                raise HostPreparationError(f"缺少基础 Secret：{path}")
            return
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


def prepare_host(root: Path, *, check_only: bool) -> None:
    """准备/校验宿主目录；已有 Secret 只校验和收紧权限，绝不轮换。"""

    if os.name != "posix":
        raise HostPreparationError("Internal V1 宿主准备只支持 Linux/POSIX")
    resolved_root = _resolve_host_root(root)
    if os.geteuid() != 0:
        raise HostPreparationError("宿主准备/校验需要 root 权限，以验证固定容器 UID/GID")

    for spec in _DIRECTORY_SPECS:
        _ensure_directory(resolved_root, spec, check_only=check_only)

    secret_dir = resolved_root / "shared/secrets"
    for name, minimum in _MANAGED_SECRETS.items():
        _secure_secret(
            secret_dir / name,
            min_characters=minimum,
            check_only=check_only,
            create=True,
        )
    for name in _OPTIONAL_EXTERNAL_SECRETS:
        path = secret_dir / name
        if path.exists() or path.is_symlink():
            _secure_secret(
                path,
                min_characters=1,
                check_only=check_only,
                create=False,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="准备 Internal V1 宿主持久目录与基础 Secret")
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
    args = parser.parse_args()
    try:
        prepare_host(args.root, check_only=args.check_only)
    except HostPreparationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    action = "校验" if args.check_only else "准备"
    print(f"[OK] Internal V1 宿主环境{action}完成：{args.root.expanduser().resolve(strict=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
