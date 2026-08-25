"""TikHub 无数据库调试的文件状态、Raw 与 Canonical 输出。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from aima_ugc.contracts.provider import assert_redacted_json, assert_secret_free, redact_json
from aima_ugc.platform.time import beijing_now

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9_.+-]+")
_STATE_SCHEMA = "tikhub-test-state.v1"
_BEIJING_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class RawOutputRecord:
    """一次真实请求在本地调试目录中的可追溯 Raw 记录。"""

    artifact_id: UUID
    request_id: str
    attempt_id: str
    operation: str
    request_no: int
    path: Path
    observed_at: datetime
    status_code: int | None = None
    external_request_id: str | None = None


@dataclass(slots=True)
class DebugState:
    """跨运行轻量去重状态；只保存减少重复请求所需事实。"""

    path: Path
    _platforms: dict[str, dict[str, dict[str, Any]]]

    @classmethod
    def load(cls, path: str | Path) -> DebugState:
        state_path = Path(path)
        if not state_path.exists():
            return cls(path=state_path, _platforms={})
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"TikHub 调试 state.json 无法读取：{state_path}") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != _STATE_SCHEMA:
            raise ValueError("TikHub 调试 state.json schema_version 不受支持")
        platforms = raw.get("platforms")
        if not isinstance(platforms, dict):
            raise ValueError("TikHub 调试 state.json 缺少 platforms")
        normalized: dict[str, dict[str, dict[str, Any]]] = {}
        for platform, contents in platforms.items():
            if not isinstance(platform, str) or not isinstance(contents, dict):
                raise ValueError("TikHub 调试 state.json platforms 结构非法")
            normalized_contents: dict[str, dict[str, Any]] = {}
            for content_id, entry in contents.items():
                if not isinstance(content_id, str) or not isinstance(entry, dict):
                    raise ValueError("TikHub 调试 state.json content 结构非法")
                comment_count = entry.get("comment_count")
                if comment_count is not None and (
                    isinstance(comment_count, bool) or not isinstance(comment_count, int)
                ):
                    raise ValueError("TikHub 调试 state.json comment_count 必须为整数或 null")
                comment_ids = entry.get("comment_ids", [])
                if not isinstance(comment_ids, list) or not all(
                    isinstance(item, str) for item in comment_ids
                ):
                    raise ValueError("TikHub 调试 state.json comment_ids 必须为字符串数组")
                normalized_contents[content_id] = {
                    "comment_count": comment_count,
                    "comment_ids": sorted(set(comment_ids)),
                }
            normalized[platform] = normalized_contents
        return cls(path=state_path, _platforms=normalized)

    def has_content(self, platform: str, external_content_id: str) -> bool:
        return external_content_id in self._platforms.get(platform, {})

    def previous_comment_count(self, platform: str, external_content_id: str) -> int | None:
        entry = self._entry(platform, external_content_id, create=False)
        if entry is None:
            return None
        value = entry.get("comment_count")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def should_refresh_comments(
        self,
        platform: str,
        external_content_id: str,
        comment_count: int | None,
        *,
        force: bool = False,
    ) -> bool:
        if force:
            return True
        entry = self._entry(platform, external_content_id, create=False)
        if entry is None:
            return True
        return entry.get("comment_count") != comment_count

    def known_comment_ids(self, platform: str, external_content_id: str) -> frozenset[str]:
        entry = self._entry(platform, external_content_id, create=False)
        if entry is None:
            return frozenset()
        values = entry.get("comment_ids", [])
        return frozenset(item for item in values if isinstance(item, str) and item)

    def is_known_comment(
        self, platform: str, external_content_id: str, external_comment_id: str
    ) -> bool:
        entry = self._entry(platform, external_content_id, create=False)
        if entry is None:
            return False
        comment_ids = entry.get("comment_ids", [])
        return external_comment_id in comment_ids

    def remember_content(
        self,
        platform: str,
        external_content_id: str,
        *,
        comment_count: int | None,
    ) -> None:
        if comment_count is not None and comment_count < 0:
            raise ValueError("comment_count 不能小于 0")
        entry = self._entry(platform, external_content_id, create=True)
        assert entry is not None
        entry["comment_count"] = comment_count

    def remember_comment(
        self, platform: str, external_content_id: str, external_comment_id: str
    ) -> None:
        if not external_comment_id:
            raise ValueError("external_comment_id 不能为空")
        entry = self._entry(platform, external_content_id, create=True)
        assert entry is not None
        comment_ids = set(entry.get("comment_ids", []))
        comment_ids.add(external_comment_id)
        entry["comment_ids"] = sorted(comment_ids)

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": _STATE_SCHEMA,
            "platforms": self._platforms,
        }
        assert_secret_free(payload, path="tikhub_test.state")
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(_json_text(payload), encoding="utf-8")
        temporary.replace(self.path)
        return self.path

    def _entry(
        self, platform: str, external_content_id: str, *, create: bool
    ) -> dict[str, Any] | None:
        contents = self._platforms.get(platform)
        if contents is None:
            if not create:
                return None
            contents = {}
            self._platforms[platform] = contents
        if create:
            return contents.setdefault(
                external_content_id,
                {"comment_count": None, "comment_ids": []},
            )
        return contents.get(external_content_id)


@dataclass(frozen=True, slots=True)
class RunOutputStore:
    """每次调试运行的独立本地输出目录。"""

    run_dir: Path
    raw_dir: Path
    canonical_dir: Path
    raw_data_dir: Path

    @classmethod
    def create(
        cls,
        *,
        output_root: str | Path,
        platform: str,
        run_id: str,
    ) -> RunOutputStore:
        normalized_run_id = _safe_name(run_id)
        if not normalized_run_id:
            raise ValueError("run_id 不能为空")
        run_dir = Path(output_root) / platform / "runs" / normalized_run_id
        raw_dir = run_dir / "raw"
        canonical_dir = run_dir / "canonical"
        raw_data_dir = run_dir / "raw_data"
        for path in (raw_dir, canonical_dir, raw_data_dir):
            path.mkdir(parents=True, exist_ok=True)
        return cls(
            run_dir=run_dir,
            raw_dir=raw_dir,
            canonical_dir=canonical_dir,
            raw_data_dir=raw_data_dir,
        )

    def save_raw(
        self,
        *,
        operation: str,
        body: object,
        request_no: int,
        status_code: int | None = None,
        external_request_id: str | None = None,
        observed_at: datetime | None = None,
    ) -> RawOutputRecord:
        if request_no < 1:
            raise ValueError("request_no 必须从 1 开始")
        safe_operation = _safe_name(operation) or "request"
        path = self.raw_dir / f"{request_no:04d}_{safe_operation}.json"
        if path.exists():
            raise FileExistsError(f"TikHub 调试 Raw 不允许覆盖：{path}")

        safe_body = redact_json(body)
        assert_redacted_json(safe_body, path=f"tikhub_test.raw.{safe_operation}")
        path.write_text(_json_text(safe_body), encoding="utf-8")
        return RawOutputRecord(
            artifact_id=uuid4(),
            request_id=f"debug-request-{uuid4()}",
            attempt_id=f"debug-attempt-{uuid4()}",
            operation=operation,
            request_no=request_no,
            path=path,
            observed_at=observed_at or beijing_now(),
            status_code=status_code,
            external_request_id=external_request_id,
        )

    def append_canonical(self, kind: str, value: BaseModel | dict[str, object]) -> Path:
        if kind not in {"contents", "comments"}:
            raise ValueError("Canonical kind 只允许 contents 或 comments")
        payload: object
        if isinstance(value, BaseModel):
            payload = value.model_dump(mode="json")
        else:
            payload = value
        assert_secret_free(payload, path=f"tikhub_test.canonical.{kind}")
        path = self.canonical_dir / f"{kind}.jsonl"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            handle.write("\n")
        return path

    def write_run_summary(self, value: dict[str, object]) -> Path:
        assert_secret_free(value, path="tikhub_test.run_summary")
        path = self.run_dir / "run_summary.json"
        path.write_text(_json_text(value), encoding="utf-8")
        return path

    def relative_path(self, path: Path) -> str:
        return path.relative_to(self.run_dir).as_posix()


def default_run_id(now: datetime | None = None) -> str:
    actual = (now or beijing_now()).astimezone(_BEIJING_TZ)
    return actual.strftime("%Y%m%dT%H%M%S.%f%z")


def _safe_name(value: str) -> str:
    return _SAFE_FILENAME.sub("_", value.strip()).strip("._")


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


__all__ = [
    "DebugState",
    "RawOutputRecord",
    "RunOutputStore",
    "default_run_id",
]
