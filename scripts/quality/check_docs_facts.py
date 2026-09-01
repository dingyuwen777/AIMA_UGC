"""检查权威当前文档是否与仓库中可机器验证的事实保持一致。"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CURRENT_DOC_EXCLUDED_ROOTS = {".agents", ".git", "changes"}
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
TABLE_PATTERNS = (
    re.compile(r'__tablename__\s*=\s*["\']([^"\']+)["\']'),
    re.compile(r'\bTable\(\s*["\']([^"\']+)["\']'),
)
JOB_TYPE_RE = re.compile(r'^[A-Z0-9_]+_JOB_TYPE\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
ROUTE_RE = re.compile(r"\bpath:\s*['\"]([^'\"]+)['\"]")
WORKER_BOOTSTRAP = Path("backend/src/aima_ugc/bootstrap/worker.py")

PROVIDER_DOCS = {
    "xiaohongshu": Path("docs/collection/01_xiaohongshu.md"),
    "douyin": Path("docs/collection/02_douyin.md"),
    "weibo": Path("docs/collection/03_weibo.md"),
    "bilibili": Path("docs/collection/04_bilibili.md"),
    "kuaishou": Path("docs/collection/05_kuaishou.md"),
}


def _read(relative: str | Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _tracked_markdown() -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "*.md"],
        check=True,
        capture_output=True,
        text=False,
    )
    documents: list[Path] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(raw_path.decode("utf-8"))
        if any(part in CURRENT_DOC_EXCLUDED_ROOTS for part in relative.parts):
            continue
        if relative in {Path("README.md"), Path("AGENTS.md")}:
            documents.append(relative)
            continue
        if relative.parts and relative.parts[0] == "docs":
            documents.append(relative)
            continue
        if relative.name == "README.md":
            documents.append(relative)
    return tuple(sorted(documents))


def _package_manager_version() -> str:
    package = json.loads(_read("frontend/package.json"))
    name, version = package["packageManager"].split("@", 1)
    if name != "npm":
        raise RuntimeError(f"unexpected frontend package manager: {name}")
    return version


def _image_version(image: str) -> str:
    pattern = re.compile(rf"(?:FROM\s+|image:\s*){re.escape(image)}:(\d+(?:\.\d+){{0,2}})")
    for relative in ("Dockerfile", "compose.yaml"):
        match = pattern.search(_read(relative))
        if match is not None:
            return match.group(1)
    raise RuntimeError(f"canonical image version not found: {image}")


def _versions() -> dict[str, str]:
    return {
        "python": _read(".python-version").strip(),
        "python-image": _image_version("python"),
        "node": _read(".node-version").strip(),
        "node-image": _image_version("node"),
        "npm": _package_manager_version(),
        "uv": _read(".uv-version").strip(),
        "postgresql": _image_version("postgres"),
        "postgres-image": _image_version("postgres"),
        "nginx-image": _image_version("nginx"),
    }


def _compatible_claim(claim: str, current: str) -> bool:
    return claim == current or current.startswith(f"{claim}.")


def _openapi_paths() -> set[str]:
    payload = json.loads(_read("contracts/openapi/openapi.json"))
    return set(payload.get("paths", {}))


def _current_table_names() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "backend/src/aima_ugc").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in TABLE_PATTERNS:
            names.update(pattern.findall(text))
    return names


def _module_file(module_name: str) -> Path:
    """把 aima_ugc 模块名解析到当前仓库中的 Python 源文件。"""
    module_path = Path(*module_name.split("."))
    source_root = ROOT / "backend/src"
    module_file = source_root / module_path.with_suffix(".py")
    if module_file.is_file():
        return module_file.relative_to(ROOT)
    package_file = source_root / module_path / "__init__.py"
    if package_file.is_file():
        return package_file.relative_to(ROOT)
    raise RuntimeError(f"worker register module not found: {module_name}")


def _relative_import_module(
    current_module: str,
    current_file: Path,
    node: ast.ImportFrom,
) -> str | None:
    """把 ImportFrom 的绝对/相对模块表达解析为完整模块名。"""
    if node.level == 0:
        return node.module

    package_parts = current_module.split(".")
    if current_file.name != "__init__.py":
        package_parts = package_parts[:-1]
    up_levels = node.level - 1
    if up_levels > len(package_parts):
        return None
    base_parts = package_parts[: len(package_parts) - up_levels]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _resolve_register_source(
    module_name: str,
    register_name: str,
    seen: set[tuple[str, str]] | None = None,
) -> Path:
    """跟随 package re-export，定位 register_* 函数真正定义的源码文件。"""
    visited = set() if seen is None else seen
    key = (module_name, register_name)
    if key in visited:
        raise RuntimeError(f"cyclic worker register re-export: {module_name}.{register_name}")
    visited.add(key)

    relative = _module_file(module_name)
    tree = ast.parse(_read(relative))
    if any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == register_name
        for node in tree.body
    ):
        return relative

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if not any(alias.name == register_name for alias in node.names):
            continue
        imported_module = _relative_import_module(module_name, relative, node)
        if imported_module is None:
            break
        return _resolve_register_source(imported_module, register_name, visited)

    raise RuntimeError(f"worker register definition not found: {module_name}.{register_name}")


def _worker_job_source_files() -> tuple[Path, ...]:
    """从生产 Worker 的 register_* 导入自动发现实际 Job 定义模块。"""
    tree = ast.parse(_read(WORKER_BOOTSTRAP))
    sources: set[Path] = set()
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        if not node.module.startswith("aima_ugc.modules."):
            continue
        for alias in node.names:
            if not alias.name.startswith("register_"):
                continue
            sources.add(_resolve_register_source(node.module, alias.name))
    if not sources:
        raise RuntimeError("no production Worker register_* sources discovered")
    return tuple(sorted(sources))


def _current_job_types() -> set[str]:
    """返回当前生产 Worker Registry 实际装配模块声明的持久 Job type。"""
    names: set[str] = set()
    for relative in _worker_job_source_files():
        names.update(JOB_TYPE_RE.findall(_read(relative)))
    return names


def _permanent_workflows() -> set[str]:
    return {
        path.name
        for path in (ROOT / ".github/workflows").glob("*.yml")
        if not path.name.startswith("tmp-")
    }


def _frontend_routes() -> set[str]:
    return set(ROUTE_RE.findall(_read("frontend/src/app/routes.ts")))


def _literal_keyword(call: ast.Call, name: str) -> object | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return ast.literal_eval(keyword.value)
    return None


def _provider_operations() -> dict[str, set[str]]:
    tree = ast.parse(_read("backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py"))
    result: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id.endswith("_TIKHUB_CAPABILITY")
            for target in node.targets
        ):
            continue
        platform = _literal_keyword(node.value, "platform")
        operations_node = next(
            (keyword.value for keyword in node.value.keywords if keyword.arg == "operations"),
            None,
        )
        if not isinstance(platform, str) or not isinstance(operations_node, (ast.Tuple, ast.List)):
            continue
        provider_operations: set[str] = set()
        for operation in operations_node.elts:
            if not isinstance(operation, ast.Call):
                continue
            value = _literal_keyword(operation, "provider_operations")
            if isinstance(value, tuple):
                provider_operations.update(str(item) for item in value)
        result[platform] = provider_operations
    return result


def _analysis_concurrency() -> int:
    match = re.search(
        r"^DEFAULT_OFFLINE_LLM_CONCURRENCY\s*=\s*(\d+)$",
        _read("backend/src/aima_ugc/modules/analysis/offline_labeling.py"),
        re.MULTILINE,
    )
    if match is None:
        raise RuntimeError("DEFAULT_OFFLINE_LLM_CONCURRENCY not found")
    return int(match.group(1))


def _require_all(
    errors: list[str],
    *,
    code: str,
    owner_doc: str,
    values: set[str],
    label: str,
) -> None:
    text = _read(owner_doc)
    for value in sorted(values):
        if value not in text:
            errors.append(f"{code} {owner_doc}: 缺少当前{label}事实 {value}")


def check_repository() -> list[str]:
    errors: list[str] = []

    _require_all(
        errors,
        code="DOCF001",
        owner_doc="docs/03_API接口说明.md",
        values=_openapi_paths(),
        label="OpenAPI 路径",
    )
    _require_all(
        errors,
        code="DOCF002",
        owner_doc="docs/blueprint/03_数据库与文件存储.md",
        values=_current_table_names(),
        label="Schema 表",
    )
    _require_all(
        errors,
        code="DOCF003",
        owner_doc="docs/blueprint/01_总体架构与技术选型.md",
        values=_current_job_types(),
        label="Worker Job type",
    )
    _require_all(
        errors,
        code="DOCF004",
        owner_doc="docs/04_测试与调试说明.md",
        values=_permanent_workflows(),
        label="永久 Workflow",
    )
    _require_all(
        errors,
        code="DOCF005",
        owner_doc="frontend/README.md",
        values=_frontend_routes(),
        label="前端 Route",
    )
    _require_all(
        errors,
        code="DOCF006",
        owner_doc="docs/blueprint/01_总体架构与技术选型.md",
        values=_frontend_routes(),
        label="前端 Route",
    )

    for platform, operations in sorted(_provider_operations().items()):
        owner = PROVIDER_DOCS.get(platform)
        if owner is None:
            errors.append(f"DOCF007 provider={platform}: 缺少平台文档 Owner 映射")
            continue
        text = _read(owner)
        for operation in sorted(operations):
            if operation not in text:
                errors.append(f"DOCF007 {owner}: 缺少当前 TikHub provider operation {operation}")

    current_versions = _versions()
    for relative in _tracked_markdown():
        text = _read(relative)
        for name, pattern in VERSION_PATTERNS.items():
            for match in pattern.finditer(text):
                claim = match.group(1)
                current = current_versions[name]
                if not _compatible_claim(claim, current):
                    errors.append(
                        f"DOCF008 {relative}: {name} 版本声明 {claim} "
                        f"与当前机器事实 {current} 不一致"
                    )

    analysis_job_types = {value for value in _current_job_types() if value.startswith("analysis.")}
    for owner in (
        "backend/src/aima_ugc/modules/analysis/README.md",
        "docs/appendix/07_AI舆情打标与分析实现.md",
    ):
        _require_all(
            errors,
            code="DOCF009",
            owner_doc=owner,
            values=analysis_job_types,
            label="Analysis Job type",
        )
    concurrency = _analysis_concurrency()
    appendix = _read("docs/appendix/07_AI舆情打标与分析实现.md")
    if f"DEFAULT_OFFLINE_LLM_CONCURRENCY = {concurrency}" not in appendix:
        errors.append(
            "DOCF010 docs/appendix/07_AI舆情打标与分析实现.md: "
            f"离线并发默认值未与代码保持一致 {concurrency}"
        )

    release = _read(".github/workflows/release.yml")
    release_doc = _read("docs/appendix/11_生产部署与离线Release方案.md")
    postgres_match = re.search(
        r"^\s*POSTGRES_IMAGE:\s*(postgres:[^\s]+)\s*$", release, re.MULTILINE
    )
    if postgres_match is None:
        errors.append("DOCF011 .github/workflows/release.yml: 无法解析 POSTGRES_IMAGE")
    elif postgres_match.group(1) not in release_doc:
        errors.append(
            "DOCF011 docs/appendix/11_生产部署与离线Release方案.md: "
            f"缺少 Release PostgreSQL 镜像事实 {postgres_match.group(1)}"
        )
    release_facts = {
        "linux/amd64",
        "images.tar",
        "release-manifest.json",
        "migration-manifest.json",
        "SHA256SUMS",
        "DEPLOY.md",
        "--no-build --pull never",
    }
    for fact in sorted(release_facts):
        if fact not in release_doc:
            errors.append(
                "DOCF011 docs/appendix/11_生产部署与离线Release方案.md: "
                f"缺少当前 Release 事实 {fact}"
            )

    return errors


def main() -> int:
    errors = check_repository()
    if errors:
        print("\n".join(errors))
        return 1
    print(
        "当前权威文档与 OpenAPI、Schema、Job、Workflow、Route、Provider、"
        "版本、Analysis、Release 机器事实一致。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
