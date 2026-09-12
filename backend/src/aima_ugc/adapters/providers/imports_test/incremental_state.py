"""imports_test 离线工具共用的文件化增量状态基础设施。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SHARD_NAMES = tuple(f"{value:02x}" for value in range(256))


def sha256_file(path: Path) -> str:
    """流式计算文件 SHA-256，避免把大文件一次性读入内存。"""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def content_identity_key(platform: str, external_content_id: str) -> str:
    """把正式内容身份编码成稳定、无歧义的本地索引键。"""

    return f"{platform}\0{external_content_id}"


def shard_name(key: str) -> str:
    """按 identity hash 把本地索引稳定分到 256 个分片。"""

    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:2]


def atomic_write_json(path: Path, payload: object) -> None:
    """用临时文件、fsync 和原子替换写 JSON 状态。"""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp")
    temp.unlink(missing_ok=True)
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def load_json_object(path: Path) -> dict[str, Any]:
    """读取 JSON Object；文件不存在时返回空字典。"""

    target = Path(path)
    if not target.is_file():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"增量状态必须为 JSON Object: {target}")
    return payload


def iter_completed_run_dirs(output_root: Path) -> Iterator[Path]:
    """按目录名稳定枚举存在 run_summary.json 的历史成功 run。"""

    runs_root = Path(output_root) / "runs"
    if not runs_root.is_dir():
        return
    for run_dir in sorted((item for item in runs_root.iterdir() if item.is_dir()), key=lambda p: p.name):
        if (run_dir / "run_summary.json").is_file():
            yield run_dir


def resolve_summary_output(
    *,
    run_dir: Path,
    summary: dict[str, Any],
    output_key: str,
    fallback_relative: str,
) -> Path:
    """优先使用旧摘要中的真实路径，失效时回退到 run 内稳定相对路径。"""

    outputs = summary.get("outputs")
    if isinstance(outputs, dict):
        value = outputs.get(output_key)
        if isinstance(value, str) and value:
            candidate = Path(value)
            if candidate.is_file():
                return candidate
    return Path(run_dir) / fallback_relative


@contextmanager
def state_lock(output_root: Path) -> Iterator[None]:
    """用原子 mkdir 防止两个本地进程同时推进同一份增量 state。"""

    state_root = Path(output_root) / "state"
    state_root.mkdir(parents=True, exist_ok=True)
    lock_dir = state_root / ".lock"
    try:
        lock_dir.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise RuntimeError(
            f"增量状态正在被其他进程使用；若确认没有运行中的任务，请人工删除: {lock_dir}"
        ) from exc
    try:
        yield
    finally:
        try:
            lock_dir.rmdir()
        except FileNotFoundError:
            pass


class AppendOnlyShardIndex:
    """用 256 个 JSONL 分片保存可重建的 append-only 本地索引。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def load_shard(self, shard: str) -> dict[str, dict[str, Any]]:
        """读取一个分片并以最后一次记录覆盖同 key 的旧 locator/metadata。"""

        path = self.root / f"{shard}.jsonl"
        latest: dict[str, dict[str, Any]] = {}
        if not path.is_file():
            return latest
        with path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"增量索引损坏: {path}: 第 {line_number} 行") from exc
                if not isinstance(payload, dict) or not isinstance(payload.get("key"), str):
                    raise ValueError(f"增量索引记录非法: {path}: 第 {line_number} 行")
                latest[payload["key"]] = payload
        return latest

    def append_delta_dir(self, delta_root: Path) -> None:
        """把一次成功 run 生成的各分片 delta 原子合并进持久索引。"""

        source_root = Path(delta_root)
        if not source_root.is_dir():
            return
        for delta_path in sorted(source_root.glob("*.jsonl"), key=lambda path: path.name):
            shard = delta_path.stem
            if shard not in SHARD_NAMES or delta_path.stat().st_size == 0:
                continue
            target = self.root / delta_path.name
            temp = target.with_name(f".{target.name}.tmp")
            temp.unlink(missing_ok=True)
            try:
                with temp.open("wb") as output:
                    if target.is_file():
                        with target.open("rb") as existing:
                            shutil.copyfileobj(existing, output, length=1024 * 1024)
                    with delta_path.open("rb") as delta:
                        shutil.copyfileobj(delta, output, length=1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temp, target)
            except BaseException:
                temp.unlink(missing_ok=True)
                raise

    def iter_latest_entries(self) -> Iterator[dict[str, Any]]:
        """逐分片产生当前每个 key 的最后一条 metadata，内存上限约为单分片。"""

        for shard in SHARD_NAMES:
            latest = self.load_shard(shard)
            for key in sorted(latest):
                yield latest[key]
