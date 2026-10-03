"""初始化和保护跨进程共享的 WisersOne 登录态。"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

_NAMES = ("wisersone_state.json", "wisersone_runtime.json")
_BUNDLE = Path(__file__).parent / "wisersone-auth"


class AuthStateError(RuntimeError):
    """已有认证状态不可用；禁止静默覆盖为旧初始状态。"""


class AuthBusyError(RuntimeError):
    """其他进程正在使用共享认证状态。"""


@dataclass(frozen=True)
class AuthPaths:
    root: Path
    state: Path
    runtime: Path


def default_host_root() -> Path:
    """本地默认与 Compose 使用同一宿主根；不依赖人工入口工作目录。"""
    configured = os.environ.get("AIMA_HOST_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent / ".runtime" / "compose"
    raise AuthStateError("请配置 AIMA_HOST_ROOT，安装包无法推断宿主持久目录。")


def default_auth_root() -> Path:
    configured = os.environ.get("AIMA_WISERSONE_AUTH_DIR")
    return (
        Path(configured).expanduser().resolve()
        if configured
        else default_host_root() / "runtime" / "wisersone-auth"
    )


@contextmanager
def auth_lock(root: Path, *, timeout: float = 60.0) -> Iterator[None]:
    """OS 释放崩溃进程的锁；保留锁文件避免删除导致锁身份分裂。"""
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".auth.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise AuthBusyError("WisersOne 认证目录正在使用，请稍后重试。") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            handle.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _validate(path: Path) -> bytes:
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError
        if path.name == _NAMES[0]:
            if not isinstance(data.get("cookies"), list) or not isinstance(
                data.get("origins"), list
            ):
                raise ValueError
        else:
            url = urlparse(data.get("home_url", ""))
            if url.scheme != "https" or url.hostname != "datacenter.wisersone.com":
                raise ValueError
            if url.path != "/home" and not url.path.startswith("/home/"):
                raise ValueError
        return raw
    except OSError, ValueError, TypeError:
        raise AuthStateError(
            f"WisersOne 认证文件无效：{path.name}；请明确恢复或重新登录，未覆盖现有文件。"
        ) from None


def atomic_write(path: Path, data: bytes) -> None:
    """在调用者持有认证目录锁时，以同文件系统 rename 发布。"""
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "posix":
            temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_auth_locked(root: Path, *, seed: Path = _BUNDLE) -> AuthPaths:
    """调用者已持锁；仅两份运行态都不存在时从 bundle 播种。"""
    paths = AuthPaths(root=root, state=root / _NAMES[0], runtime=root / _NAMES[1])
    exists = (paths.state.exists(), paths.runtime.exists())
    if not any(exists):
        originals = tuple(_validate(seed / name) for name in _NAMES)
        for name, raw in zip(_NAMES, originals, strict=True):
            atomic_write(root / name, raw)
    elif not all(exists):
        raise AuthStateError("WisersOne 认证文件不完整；请恢复完整认证目录，未使用旧初始状态。")
    _validate(paths.state)
    _validate(paths.runtime)
    return paths


def prepare_auth(root: Path, *, seed: Path = _BUNDLE) -> AuthPaths:
    with auth_lock(root):
        return prepare_auth_locked(root, seed=seed)
