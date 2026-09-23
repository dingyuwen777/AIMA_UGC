"""统一历史导入容量基准的本机磁盘误用防护。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts/performance/benchmark_stage12_historical.py"
)
_SPEC = importlib.util.spec_from_file_location("benchmark_stage12_historical", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
benchmark_stage12_historical = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(benchmark_stage12_historical)


def test_historical_benchmark_refuses_nonempty_work_directory(tmp_path: Path) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="work_dir 必须为空"):
        benchmark_stage12_historical.run_benchmark(
            work_dir=tmp_path,
            row_count=1000,
            rows_per_file=1000,
            chunk_rows=1000,
            max_in_flight=1,
        )

    assert existing.read_text(encoding="utf-8") == "keep"


def test_historical_benchmark_refuses_fixture_over_disk_budget(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="磁盘预算"):
        benchmark_stage12_historical.run_benchmark(
            work_dir=tmp_path,
            row_count=1000,
            rows_per_file=1000,
            chunk_rows=1000,
            max_in_flight=1,
            disk_budget_bytes=1024,
        )


def test_historical_benchmark_checks_database_before_writing_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Settings:
        db_name = "aima_ugc"

    monkeypatch.setattr(benchmark_stage12_historical, "load_settings", lambda: _Settings())

    with pytest.raises(RuntimeError, match="_stage12_capacity"):
        benchmark_stage12_historical.run_benchmark(
            work_dir=tmp_path,
            row_count=1000,
            rows_per_file=1000,
            chunk_rows=1000,
            max_in_flight=1,
        )

    assert list(tmp_path.iterdir()) == []


def test_historical_benchmark_cleans_generated_fixture_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Settings:
        db_name = "aima_issue587_stage12_capacity"

    def fail_fixture(root: Path, **kwargs: object) -> tuple[Path, ...]:
        del kwargs
        (root / "partial.xlsx").write_bytes(b"partial")
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(benchmark_stage12_historical, "load_settings", lambda: _Settings())
    monkeypatch.setattr(benchmark_stage12_historical, "_write_fixture", fail_fixture)

    with pytest.raises(RuntimeError, match="synthetic failure"):
        benchmark_stage12_historical.run_benchmark(
            work_dir=tmp_path,
            row_count=1000,
            rows_per_file=1000,
            chunk_rows=1000,
            max_in_flight=1,
        )

    assert list(tmp_path.iterdir()) == []
