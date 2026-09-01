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
_resolve_file_reference = CHECKER["_resolve_file_reference"]
_suggest_link = CHECKER["_suggest_link"]
FENCE_RE = CHECKER["FENCE_RE"]
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")

VERSION_PATTERNS = {
    "python": re.compile(r"(?i)\bPython\s+v?(3\.\d+(?:\.\d+)?)\b"),
    "python-image": re.compile(r"(?i)\bpython:(3\.\d+(?:\.\d+)?)\b"),
    "node": re.compile(r"(?i)\bNode(?:\.js)?\s+v?(\d+\.\d+(?:\.\d+)?)\b"),
    "node-image": re.compile(r"(?i)\bnode:(\d+\.\d+(?:\.\d+)?)\b"),
    "npm": re.compile(r"(?i)\bnpm\s+v?(\d+\.\d+(?:\.\d+)?)\b"),
    "uv": re.compile(r"(?i)(?<![\w-])uv\s+v?(\d+\.\d+(?:\.\d+)?)\b"),
    "postgresql": re.compile(r"(?i)\bPostgreSQL\s+(\d+(?:\.\d+)?)\b"),
    "postgres-image": re.compile(r"(?i)\bpostgres:(\d+(?:\.\d+)?)\b"),
    "nginx-image": re.compile(r"(?i)\bnginx:(\d+(?:\.\d+){1,2})\b"),
}
STALE_TOKENS = (
    "reliable-vibe-coding",
    ".agents/skills/coding/references/",
    "R0-R3",
    "R0–R3",
)
API_RE = re.compile(r"(?<![\w])(/(?:api/v1|health)/[A-Za-z0-9_{}<>.*:/-]+)")
INLINE_ROUTE_RE = re.compile(r"`(/[^`\s?#]*)`")
JOB_LITERAL_RE = re.compile(r"`((?:collection|ingestion|analysis|reporting)\.[a-z0-9.-]+\.v\d+)`")
AIMA_ENV_RE = re.compile(r"\bAIMA_[A-Z0-9_]+\b")
UUID_SEGMENT_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
TABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,}$")


def _read_version(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8").strip()


def _package_manager_version() -> str:
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    name, version = package["packageManager"].split("@", 1)
    if name != "npm":
        raise RuntimeError(f"unexpected package manager: {name}")
    return version


def _image_version(image: str) -> str:
    texts = (
        (ROOT / "Dockerfile").read_text(encoding="utf-8"),
        (ROOT / "compose.yaml").read_text(encoding="utf-8"),
    )
    pattern = re.compile(rf"(?:FROM\s+|image:\s*){re.escape(image)}:(\d+(?:\.\d+){{0,2}})")
    for text in texts:
        match = pattern.search(text)
        if match is not None:
            return match.group(1)
    raise RuntimeError(f"canonical image version not found: {image}")


def _compatible_claim(claim: str, current: str) -> bool:
    return current == claim or current.startswith(f"{claim}.")


def _shape(path: str) -> str:
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


def _openapi_paths() -> set[str]:
    payload = json.loads((ROOT / "contracts/openapi/openapi.json").read_text(encoding="utf-8"))
    return set(payload.get("paths", {}))


def _frontend_routes() -> set[str]:
    text = (ROOT / "frontend/src/app/routes.ts").read_text(encoding="utf-8")
    return set(re.findall(r"\bpath:\s*['\"]([^'\"]+)['\"]", text))


def _worker_job_types() -> set[str]:
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


def _machine_env_names(repository_files: tuple[Path, ...], documents: tuple[Path, ...]) -> set[str]:
    docs = set(documents)
    names: set[str] = set()
    for path in repository_files:
        if path in docs:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError, OSError:
            continue
        names.update(AIMA_ENV_RE.findall(text))
    return names


def _table_names(repository_files: tuple[Path, ...]) -> set[str]:
    names: set[str] = set()
    patterns = (
        re.compile(r'__tablename__\s*=\s*["\']([^"\']+)["\']'),
        re.compile(r'\bTable\(\s*["\']([^"\']+)["\']'),
        re.compile(r'op\.create_table\(\s*["\']([^"\']+)["\']'),
    )
    for path in repository_files:
        if path.suffix != ".py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError, OSError:
            continue
        for pattern in patterns:
            names.update(pattern.findall(text))
    return names


def _provider_doc(relative: str) -> bool:
    return relative.startswith("docs/collection/") or relative in {
        "docs/appendix/02_TikHub五平台真实响应与字段映射.md",
        "docs/appendix/03_TikHub多接口验证与备用策略.md",
        "docs/appendix/04_TikHub接口选型与真实验证台账.md",
    }


def _mixed_fence_file_candidates(
    doc: Path,
    text: str,
    repository_files: tuple[Path, ...],
) -> list[tuple[int, str, str]]:
    """找出混合代码块中仍承担导航职责的精确仓库文件行，供人工复核。"""
    findings: list[tuple[int, str, str]] = []
    in_fence = False
    block: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            if in_fence:
                nonempty = [(no, value.strip()) for no, value in block if value.strip()]
                resolved: list[tuple[int, str, Path]] = []
                unresolved = False
                for no, value in nonempty:
                    target = _resolve_file_reference(ROOT, doc, value, repository_files)
                    if target is None:
                        unresolved = True
                    else:
                        resolved.append((no, value, target))
                if unresolved and resolved:
                    for no, value, target in resolved:
                        findings.append((no, value, _suggest_link(doc, target, value)))
                block = []
            in_fence = not in_fence
            continue
        if in_fence:
            block.append((line_number, line))
    return findings


def _shorthand_api_match(candidate: str, openapi_paths: set[str]) -> str | None:
    """如果省略 /api/v1 后恰好唯一匹配当前 OpenAPI，则返回完整路径。"""
    if candidate.startswith(("/api/", "/health/", "/data/")):
        return None
    matches = [path for path in openapi_paths if path.endswith(candidate)]
    if len(matches) == 1:
        return matches[0]
    return None


def main() -> int:
    repository_files = _repository_files(ROOT)
    documents = _iter_current_docs(ROOT, repository_files)
    versions = {
        "python": _read_version(".python-version"),
        "python-image": _image_version("python"),
        "node": _read_version(".node-version"),
        "node-image": _image_version("node"),
        "npm": _package_manager_version(),
        "uv": _read_version(".uv-version"),
        "postgresql": _image_version("postgres"),
        "postgres-image": _image_version("postgres"),
        "nginx-image": _image_version("nginx"),
    }
    openapi_paths = _openapi_paths()
    openapi_shapes = {_shape(path) for path in openapi_paths}
    frontend_routes = _frontend_routes()
    job_types = _worker_job_types()
    env_names = _machine_env_names(repository_files, documents)
    table_names = _table_names(repository_files)
    permanent_workflows = sorted(
        path.name
        for path in (ROOT / ".github/workflows").glob("*.yml")
        if not path.name.startswith("tmp-")
    )

    print("FACT versions", json.dumps(versions, ensure_ascii=False, sort_keys=True))
    print("FACT frontend_routes", json.dumps(sorted(frontend_routes), ensure_ascii=False))
    print("FACT worker_job_types", json.dumps(sorted(job_types), ensure_ascii=False))
    print("FACT permanent_workflows", json.dumps(permanent_workflows, ensure_ascii=False))
    print("FACT openapi_paths", json.dumps(sorted(openapi_paths), ensure_ascii=False))
    print("FACT table_count", len(table_names))
    print("FACT env_name_count", len(env_names))

    findings = 0
    for doc in documents:
        relative = doc.relative_to(ROOT).as_posix()
        text = doc.read_text(encoding="utf-8")
        provider_doc = _provider_doc(relative)

        for line_number, value, suggestion in _mixed_fence_file_candidates(
            doc, text, repository_files
        ):
            findings += 1
            print(f"MIXED_FILE_NAV {relative}:{line_number}: {value} :: {suggestion}")

        for line_number, line in enumerate(text.splitlines(), start=1):
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

            for env_name in sorted(set(AIMA_ENV_RE.findall(line))):
                if f"{env_name}*" in line:
                    continue
                if env_name not in env_names:
                    findings += 1
                    print(f"ENV_UNKNOWN {relative}:{line_number}: {env_name} :: {line.strip()}")

            if not provider_doc:
                for match in API_RE.finditer(line):
                    candidate = match.group(1)
                    if "*" in candidate:
                        continue
                    if _shape(candidate) not in openapi_shapes:
                        findings += 1
                        print(
                            f"API_UNKNOWN {relative}:{line_number}: {candidate} :: {line.strip()}"
                        )

            for match in INLINE_ROUTE_RE.finditer(line):
                candidate = match.group(1)
                shorthand = _shorthand_api_match(candidate, openapi_paths)
                if shorthand is not None:
                    findings += 1
                    print(
                        f"API_SHORTHAND {relative}:{line_number}: "
                        f"{candidate} -> {shorthand} :: {line.strip()}"
                    )

            if "路由" in line or "页面" in line or "访问" in line:
                for match in INLINE_ROUTE_RE.finditer(line):
                    candidate = match.group(1)
                    if candidate.startswith(("/api/", "/health/", "/data/")):
                        continue
                    if _shorthand_api_match(candidate, openapi_paths) is not None:
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

            if "表" in line or "Table" in line or "table" in line:
                for match in INLINE_CODE_RE.finditer(line):
                    candidate = match.group(1)
                    if not TABLE_NAME_RE.match(candidate) or "_" not in candidate:
                        continue
                    if candidate not in table_names:
                        findings += 1
                        print(
                            f"TABLE_CANDIDATE {relative}:{line_number}: {candidate} :: {line.strip()}"
                        )

    print(f"FACT_AUDIT_CANDIDATES {findings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
