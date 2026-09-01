"""一次性生成当前项目文档与仓库机器事实的语义漂移候选清单。"""

from __future__ import annotations

import json
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = runpy.run_path(str(ROOT / "scripts" / "quality" / "check_docs.py"))
_iter_current_docs = CHECKER["_iter_current_docs"]
_repository_files = CHECKER["_repository_files"]

VERSION_PATTERNS = {
    "python": re.compile(r"(?i)\bPython\s+v?(3\.\d+(?:\.\d+)?)\b"),
    "node": re.compile(r"(?i)\bNode(?:\.js)?\s+v?(\d+\.\d+(?:\.\d+)?)\b"),
    "npm": re.compile(r"(?i)\bnpm\s+v?(\d+\.\d+(?:\.\d+)?)\b"),
    "uv": re.compile(r"(?i)(?<![\w-])uv\s+v?(\d+\.\d+(?:\.\d+)?)\b"),
    "postgresql": re.compile(r"(?i)\bPostgreSQL\s+(\d+(?:\.\d+)?)\b"),
    "postgres-image": re.compile(r"(?i)\bpostgres:(\d+(?:\.\d+)?)\b"),
}
STALE_TOKENS = (
    "reliable-vibe-coding",
    ".agents/skills/coding/references/",
    "R0-R3",
    "R0–R3",
)
API_RE = re.compile(r"(?<![\w])(/(?:api/v1|health)/[A-Za-z0-9_{}<>./:-]+)")
INLINE_ROUTE_RE = re.compile(r"`(/[^`\s?#]*)`")
JOB_LITERAL_RE = re.compile(
    r"`((?:collection|ingestion|analysis|reporting)\.[a-z0-9.-]+\.v\d+)`"
)
UUID_SEGMENT_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def _read_version(path: str) -> str:
    """读取单行版本文件。"""
    return (ROOT / path).read_text(encoding="utf-8").strip()


def _package_manager_version() -> str:
    """从前端 packageManager 字段提取 npm 精确版本。"""
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    manager = package["packageManager"]
    name, version = manager.split("@", 1)
    if name != "npm":
        raise RuntimeError(f"unexpected package manager: {manager}")
    return version


def _postgres_version() -> str:
    """从 canonical Compose 的 postgres image 提取精确版本。"""
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    match = re.search(r"image:\s*postgres:(\d+(?:\.\d+)?)", text)
    if match is None:
        raise RuntimeError("compose.yaml postgres image not found")
    return match.group(1)


def _compatible_claim(claim: str, current: str) -> bool:
    """允许文档用当前精确版本的前缀表达主/次版本。"""
    return current == claim or current.startswith(f"{claim}.")


def _shape(path: str) -> str:
    """把 URL 中动态 segment 归一化，比较 endpoint 结构而非参数名。"""
    clean = path.split("?", 1)[0].rstrip(".,;:，。；：")
    parts: list[str] = []
    for segment in clean.split("/"):
        if not segment:
            continue
        if (
            (segment.startswith("{") and segment.endswith("}"))
            or (segment.startswith("<") and segment.endswith(">"))
            or segment.isdigit()
            or UUID_SEGMENT_RE.match(segment)
        ):
            parts.append("{}")
        else:
            parts.append(segment)
    return "/" + "/".join(parts)


def _openapi_shapes() -> set[str]:
    """读取 generated OpenAPI 当前 endpoint 形状。"""
    payload = json.loads((ROOT / "contracts/openapi/openapi.json").read_text(encoding="utf-8"))
    return {_shape(path) for path in payload.get("paths", {})}


def _frontend_routes() -> set[str]:
    """从 route registry 提取当前页面路径。"""
    text = (ROOT / "frontend/src/app/routes.ts").read_text(encoding="utf-8")
    return set(re.findall(r"\bpath:\s*['\"]([^'\"]+)['\"]", text))


def _worker_job_types() -> set[str]:
    """从 Worker 实际装配涉及的 Job 模块提取持久 Job type。"""
    paths = (
        "backend/src/aima_ugc/modules/collection/collection_run_job.py",
        "backend/src/aima_ugc/modules/ingestion/import_job.py",
        "backend/src/aima_ugc/modules/ingestion/historical_jobs.py",
        "backend/src/aima_ugc/modules/analysis/content_analysis_job.py",
        "backend/src/aima_ugc/modules/reporting/data_export_job.py",
    )
    job_types: set[str] = set()
    pattern = re.compile(r'^\w+_JOB_TYPE\s*=\s*"([^"]+)"', re.MULTILINE)
    for relative in paths:
        job_types.update(pattern.findall((ROOT / relative).read_text(encoding="utf-8")))
    return job_types


def main() -> int:
    """输出供人工语义审计使用的机器事实和疑似漂移位置。"""
    repository_files = _repository_files(ROOT)
    documents = _iter_current_docs(ROOT, repository_files)
    versions = {
        "python": _read_version(".python-version"),
        "node": _read_version(".node-version"),
        "npm": _package_manager_version(),
        "uv": _read_version(".uv-version"),
        "postgresql": _postgres_version(),
        "postgres-image": _postgres_version(),
    }
    openapi_shapes = _openapi_shapes()
    frontend_routes = _frontend_routes()
    job_types = _worker_job_types()
    permanent_workflows = sorted(
        path.name
        for path in (ROOT / ".github/workflows").glob("*.yml")
        if not path.name.startswith("tmp-")
    )

    print("FACT versions", json.dumps(versions, ensure_ascii=False, sort_keys=True))
    print("FACT frontend_routes", json.dumps(sorted(frontend_routes), ensure_ascii=False))
    print("FACT worker_job_types", json.dumps(sorted(job_types), ensure_ascii=False))
    print("FACT permanent_workflows", json.dumps(permanent_workflows, ensure_ascii=False))
    print("FACT openapi_path_count", len(openapi_shapes))

    findings = 0
    for doc in documents:
        relative = doc.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1):
            for name, pattern in VERSION_PATTERNS.items():
                for match in pattern.finditer(line):
                    claim = match.group(1)
                    if not _compatible_claim(claim, versions[name]):
                        findings += 1
                        print(
                            f"VERSION_DRIFT {relative}:{line_number}: "
                            f"{name} claim={claim} current={versions[name]} :: {line.strip()}"
                        )

            for token in STALE_TOKENS:
                if token in line:
                    findings += 1
                    print(f"STALE_TOKEN {relative}:{line_number}: {token} :: {line.strip()}")

            for match in API_RE.finditer(line):
                candidate = match.group(1)
                if _shape(candidate) not in openapi_shapes:
                    findings += 1
                    print(f"API_UNKNOWN {relative}:{line_number}: {candidate} :: {line.strip()}")

            if "路由" in line or "页面" in line or "访问" in line:
                for match in INLINE_ROUTE_RE.finditer(line):
                    candidate = match.group(1)
                    if candidate.startswith(("/api/", "/health/")):
                        continue
                    if candidate not in frontend_routes:
                        findings += 1
                        print(
                            f"FRONTEND_ROUTE_CANDIDATE {relative}:{line_number}: "
                            f"{candidate} current={sorted(frontend_routes)} :: {line.strip()}"
                        )

            if "Job" in line or "job" in line or "任务类型" in line:
                for match in JOB_LITERAL_RE.finditer(line):
                    candidate = match.group(1)
                    if candidate not in job_types:
                        findings += 1
                        print(
                            f"JOB_TYPE_CANDIDATE {relative}:{line_number}: "
                            f"{candidate} current={sorted(job_types)} :: {line.strip()}"
                        )

    print(f"FACT_AUDIT_CANDIDATES {findings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
