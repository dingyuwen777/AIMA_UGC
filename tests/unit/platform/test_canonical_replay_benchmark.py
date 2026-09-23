"""Canonical Replay 容量基准的误用防护。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts/performance/benchmark_canonical_replay.py"
_SPEC = importlib.util.spec_from_file_location("benchmark_canonical_replay", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
benchmark_canonical_replay = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(benchmark_canonical_replay)


def test_replay_benchmark_requires_dedicated_database_name() -> None:
    with pytest.raises(ValueError, match="_canonical_replay_capacity"):
        benchmark_canonical_replay._require_capacity_database("aima_ugc")

    benchmark_canonical_replay._require_capacity_database("test_canonical_replay_capacity")


def test_replay_benchmark_refuses_nonempty_work_directory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "existing.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(
        benchmark_canonical_replay,
        "load_settings",
        lambda: SimpleNamespace(db_name="test_canonical_replay_capacity"),
    )

    with pytest.raises(ValueError, match="工作目录必须为空"):
        benchmark_canonical_replay.run_benchmark(
            work_dir=tmp_path,
            file_count=1,
            rows_per_file=1,
            workers=1,
        )
    assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "keep"


def test_replay_benchmark_refuses_fixture_over_disk_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        benchmark_canonical_replay,
        "load_settings",
        lambda: SimpleNamespace(db_name="test_canonical_replay_capacity"),
    )

    with pytest.raises(ValueError, match="磁盘预算"):
        benchmark_canonical_replay.run_benchmark(
            work_dir=tmp_path,
            file_count=1,
            rows_per_file=1000,
            workers=1,
            disk_budget_bytes=1024,
        )


def test_replay_benchmark_cleans_generated_runtime_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Settings:
        db_name = "test_canonical_replay_capacity"

        def model_copy(self, *, update: dict[str, Path]) -> _Settings:
            update["data_dir"].mkdir()
            update["log_dir"].mkdir()
            return self

    def fail_runtime(**kwargs: object) -> None:
        del kwargs
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(benchmark_canonical_replay, "load_settings", lambda: _Settings())
    monkeypatch.setattr(
        benchmark_canonical_replay,
        "create_worker_runtime",
        fail_runtime,
    )

    with pytest.raises(RuntimeError, match="synthetic failure"):
        benchmark_canonical_replay.run_benchmark(
            work_dir=tmp_path,
            file_count=1,
            rows_per_file=1,
            workers=1,
        )

    assert list(tmp_path.iterdir()) == []
