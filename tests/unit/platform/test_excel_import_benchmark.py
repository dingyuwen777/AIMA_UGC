"""本地 Excel 容量基准的数据库与磁盘误用防护。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts/performance/benchmark_excel_import.py"
_SPEC = importlib.util.spec_from_file_location("benchmark_excel_import", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
benchmark_excel_import = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(benchmark_excel_import)


def test_excel_benchmark_requires_dedicated_database_name() -> None:
    with pytest.raises(ValueError, match="_import_pipeline_capacity"):
        benchmark_excel_import._require_capacity_database("aima_ugc")

    benchmark_excel_import._require_capacity_database("aima_import_pipeline_capacity")


def test_excel_benchmark_refuses_nonempty_work_directory(tmp_path: Path) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="工作目录必须为空"):
        benchmark_excel_import.run_benchmark(
            work_dir=tmp_path,
            row_count=1,
            runs=1,
        )

    assert existing.read_text(encoding="utf-8") == "keep"


def test_excel_benchmark_refuses_fixture_over_disk_budget(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="磁盘预算"):
        benchmark_excel_import.run_benchmark(
            work_dir=tmp_path,
            row_count=1000,
            runs=1,
            disk_budget_bytes=1024,
        )


def test_excel_benchmark_cleans_generated_run_after_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Settings:
        db_name = "aima_import_pipeline_capacity"

    def fail_after_creating_run(*, run_dir: Path, **kwargs: object) -> dict[str, object]:
        del kwargs
        run_dir.mkdir()
        (run_dir / "partial.xlsx").write_bytes(b"partial")
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(benchmark_excel_import, "load_settings", lambda: _Settings())
    monkeypatch.setattr(benchmark_excel_import, "_run_once", fail_after_creating_run)

    with pytest.raises(RuntimeError, match="synthetic failure"):
        benchmark_excel_import.run_benchmark(
            work_dir=tmp_path,
            row_count=1,
            runs=1,
        )

    assert list(tmp_path.iterdir()) == []
