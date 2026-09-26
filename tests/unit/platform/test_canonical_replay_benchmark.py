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


def test_scalar_reference_requires_stable_author_fixture(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="stable_authors"):
        benchmark_canonical_replay.run_benchmark(
            work_dir=tmp_path,
            file_count=1,
            rows_per_file=1,
            workers=1,
            scalar_stable_authors=True,
        )


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



def test_replay_benchmark_validates_low_hit_fixture_bounds(tmp_path: Path) -> None:
    """低命中容量场景不能少于已经预置为 Existing 的命中行。"""

    with pytest.raises(ValueError, match="matched_rows_per_file"):
        benchmark_canonical_replay.run_benchmark(
            work_dir=tmp_path,
            file_count=1,
            rows_per_file=100,
            workers=1,
            existing_rows_per_file=20,
            matched_rows_per_file=10,
        )


def test_replay_benchmark_fixture_can_model_low_hit_input() -> None:
    """容量夹具可显式构造低命中 raw rows，供 5%/25% 场景复测。"""

    payload = benchmark_canonical_replay._fixture_xlsx(
        file_index=0,
        rows_per_file=20,
        existing_rows_per_file=1,
        matched_rows_per_file=5,
        nonce="unit",
    )

    assert payload
