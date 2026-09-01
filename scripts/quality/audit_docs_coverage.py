"""一次性反查权威当前文档是否覆盖其声称负责的机器事实。"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _openapi_paths() -> set[str]:
    payload = json.loads((ROOT / "contracts/openapi/openapi.json").read_text(encoding="utf-8"))
    return set(payload.get("paths", {}))


def _worker_job_types() -> set[str]:
    paths = (
        "backend/src/aima_ugc/modules/collection/collection_run_job.py",
        "backend/src/aima_ugc/modules/ingestion/import_job.py",
        "backend/src/aima_ugc/modules/ingestion/historical_jobs.py",
        "backend/src/aima_ugc/modules/analysis/content_analysis_job.py",
        "backend/src/aima_ugc/modules/reporting/data_export_job.py",
    )
    pattern = re.compile(r'^\w+_JOB_TYPE\s*=\s*"([^"]+)"', re.MULTILINE)
    result: set[str] = set()
    for relative in paths:
        result.update(pattern.findall((ROOT / relative).read_text(encoding="utf-8")))
    return result


def _table_names() -> set[str]:
    """只取当前应用源码注册的表，不把历史 Migration 中已移除的表算作当前 Schema。"""
    patterns = (
        re.compile(r'__tablename__\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'\bTable\(\s*["\']([^"\']+)["\']'),
    )
    result: set[str] = set()
    for path in (ROOT / "backend/src/aima_ugc").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            result.update(pattern.findall(text))
    return result


def _workflow_names() -> set[str]:
    return {
        path.name
        for path in (ROOT / ".github/workflows").glob("*.yml")
        if not path.name.startswith("tmp-")
    }


def _report(kind: str, owner_doc: str, expected: set[str]) -> int:
    text = (ROOT / owner_doc).read_text(encoding="utf-8")
    missing = sorted(value for value in expected if value not in text)
    for value in missing:
        print(f"COVERAGE_MISSING {kind} {owner_doc}: {value}")
    print(f"COVERAGE {kind} {owner_doc}: expected={len(expected)} missing={len(missing)}")
    return len(missing)


def main() -> int:
    total = 0
    total += _report("openapi", "docs/03_API接口说明.md", _openapi_paths())
    total += _report("tables", "docs/blueprint/03_数据库与文件存储.md", _table_names())
    total += _report("worker_jobs", "docs/blueprint/README.md", _worker_job_types())
    total += _report("workflows", "docs/04_测试与调试说明.md", _workflow_names())
    print(f"COVERAGE_MISSING_COUNT {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
