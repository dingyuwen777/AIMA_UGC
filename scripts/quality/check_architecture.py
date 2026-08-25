"""检查长期仓库骨架与可低误报验证的架构硬约束。"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend" / "src" / "aima_ugc"
MIGRATIONS = ROOT / "migrations" / "versions"


def _path(value: str) -> Path:
    return ROOT / value


REQUIRED = [
    _path("pyproject.toml"),
    _path("uv.lock"),
    _path(".python-version"),
    _path(".node-version"),
    _path("alembic.ini"),
    _path("migrations/env.py"),
    _path("migrations/versions/20260813_0001_stage3a_foundation.py"),
    _path("migrations/versions/20260814_0002_stage4_job_runtime.py"),
    _path("migrations/versions/20260814_0003_stage5b_collection_execution.py"),
    _path("migrations/versions/20260814_0004_stage5c_provider_persistence.py"),
    _path("migrations/versions/20260814_0005_stage5d_provider_dispatch.py"),
    _path("migrations/versions/20260814_0007_stage6_candidate_guard.py"),
    _path("migrations/versions/20260814_0008_stage6_account_external_ids.py"),
    _path("migrations/versions/20260814_0009_stage6_candidate_ledger_guards.py"),
    _path("contracts/provider/request.v1.schema.json"),
    _path("contracts/provider/attempt.v1.schema.json"),
    _path("contracts/provider/raw-envelope.v1.schema.json"),
    _path(".github/workflows/ci.yml"),
    _path(".github/workflows/fullstack.yml"),
    _path(".github/workflows/runtime.yml"),
    _path(".github/workflows/tooling.yml"),
    _path(".github/workflows/change-completion-gate.yml"),
    _path(".github/workflows/release.yml"),
    _path("backend/src/aima_ugc/__init__.py"),
    _path("backend/src/aima_ugc/database_schema.py"),
    _path("backend/src/aima_ugc/platform/config/settings.py"),
    _path("backend/src/aima_ugc/platform/security/secrets.py"),
    _path("backend/src/aima_ugc/platform/logging/formatter.py"),
    _path("backend/src/aima_ugc/platform/database/runtime.py"),
    _path("backend/src/aima_ugc/platform/database/metadata.py"),
    _path("backend/src/aima_ugc/platform/storage/ports.py"),
    _path("backend/src/aima_ugc/platform/storage/tables.py"),
    _path("backend/src/aima_ugc/platform/jobs/models.py"),
    _path("backend/src/aima_ugc/platform/jobs/registry.py"),
    _path("backend/src/aima_ugc/platform/jobs/tables.py"),
    _path("backend/src/aima_ugc/platform/jobs/worker.py"),
    _path("backend/src/aima_ugc/contracts/provider/models.py"),
    _path("backend/src/aima_ugc/contracts/provider/raw.py"),
    _path("backend/src/aima_ugc/modules/collection/providers/transport.py"),
    _path("backend/src/aima_ugc/modules/collection/providers/raw_artifact.py"),
    _path("backend/src/aima_ugc/modules/collection/execution.py"),
    _path("backend/src/aima_ugc/modules/collection/provider_persistence.py"),
    _path("backend/src/aima_ugc/modules/collection/provider_dispatch.py"),
    _path("backend/src/aima_ugc/modules/collection/provider_recovery.py"),
    _path("backend/src/aima_ugc/modules/collection/tables.py"),
    _path("backend/src/aima_ugc/modules/collection/candidate_tables.py"),
    _path("backend/src/aima_ugc/modules/collection/candidates.py"),
    _path("backend/src/aima_ugc/modules/collection/xiaohongshu_replay.py"),
    _path("backend/src/aima_ugc/adapters/providers/tikhub/operations/xiaohongshu.py"),
    _path("backend/src/aima_ugc/adapters/providers/tikhub/mappers/xiaohongshu.py"),
    _path("backend/src/aima_ugc/adapters/providers/fake.py"),
    _path("backend/src/aima_ugc/modules/system/ports.py"),
    _path("backend/src/aima_ugc/modules/system/tables.py"),
    _path("backend/src/aima_ugc/adapters/persistence/postgres/artifact_metadata.py"),
    _path("backend/src/aima_ugc/adapters/persistence/postgres/system.py"),
    _path("backend/src/aima_ugc/adapters/persistence/postgres/jobs.py"),
    _path("backend/src/aima_ugc/adapters/persistence/postgres/collection.py"),
    _path("backend/src/aima_ugc/adapters/persistence/postgres/provider.py"),
    _path("backend/src/aima_ugc/adapters/persistence/postgres/provider_dispatch.py"),
    _path("backend/src/aima_ugc/adapters/persistence/postgres/candidates.py"),
    _path("backend/src/aima_ugc/adapters/persistence/postgres/content.py"),
    _path("backend/src/aima_ugc/adapters/persistence/postgres/xiaohongshu_replay.py"),
    _path("backend/src/aima_ugc/modules/content/ingestion.py"),
    _path("backend/src/aima_ugc/modules/content/tables.py"),
    _path("backend/src/aima_ugc/modules/content/account_tables.py"),
    _path("backend/src/aima_ugc/bootstrap/runtime.py"),
    _path("backend/src/aima_ugc/entrypoints/api_main.py"),
    _path("backend/src/aima_ugc/entrypoints/worker_main.py"),
    _path("backend/src/aima_ugc/entrypoints/scheduler_main.py"),
    _path("backend/src/aima_ugc/entrypoints/migrate_main.py"),
    _path("frontend/package.json"),
    _path("frontend/package-lock.json"),
]
FORBIDDEN = [
    _path("backend/pyproject.toml"),
    _path("backend/uv.lock"),
    _path("backend/tests"),
]


def _migration_revision_exists(revision: str) -> bool:
    """历史 Migration 文件名不可改写，因此按稳定 Revision ID 验证其存在。"""
    for path in MIGRATIONS.glob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                continue
            if node.target.id != "revision" or not isinstance(node.value, ast.Constant):
                continue
            if node.value.value == revision:
                return True
    return False


def _imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return {f"<syntax-error>:{exc.msg}"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _matches_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _check_import_boundaries() -> list[str]:
    """只编码 AGENTS 中可以通过 import 静态证明、且误报风险低的硬边界。"""
    errors: list[str] = []
    modules_root = SRC / "modules"
    provider_root = SRC / "adapters" / "providers"
    entrypoints_root = SRC / "entrypoints"

    for path in modules_root.rglob("*.py"):
        for module in _imports(path):
            if _matches_prefix(module, ("aima_ugc.adapters", "aima_ugc.entrypoints")):
                errors.append(
                    f"ARCH003 {path.relative_to(ROOT)}: "
                    f"领域模块禁止反向依赖 Adapter/Entrypoint ({module})"
                )

    for path in provider_root.rglob("*.py"):
        imports = _imports(path)
        forbidden = (
            "aima_ugc.adapters.persistence",
            "aima_ugc.modules.collection.tables",
            "aima_ugc.modules.content.tables",
            "aima_ugc.modules.system.tables",
            "sqlalchemy",
        )
        for module in imports:
            if _matches_prefix(module, forbidden):
                errors.append(
                    f"ARCH004 {path.relative_to(ROOT)}: "
                    f"Provider Adapter 禁止直接访问持久化/业务表 ({module})"
                )

        if "mappers" in path.parts:
            mapper_forbidden = (
                "httpx",
                "aima_ugc.platform.database",
                "aima_ugc.adapters.persistence",
                "sqlalchemy",
            )
            for module in imports:
                if _matches_prefix(module, mapper_forbidden):
                    errors.append(
                        f"ARCH005 {path.relative_to(ROOT)}: "
                        f"Mapper 必须保持纯转换，禁止 HTTP/数据库依赖 ({module})"
                    )

    for path in entrypoints_root.rglob("*.py"):
        for module in _imports(path):
            if _matches_prefix(module, ("sqlalchemy",)):
                errors.append(
                    f"ARCH006 {path.relative_to(ROOT)}: Entrypoint/Router 禁止直接 SQL ({module})"
                )
    return errors


def main() -> int:
    errors: list[str] = []
    for path in REQUIRED:
        if not path.exists():
            errors.append(f"ARCH001 {path.relative_to(ROOT)}: 长期基线必需文件不存在")
    if not _migration_revision_exists("20260814_0006"):
        errors.append("ARCH001 revision=20260814_0006: 历史 Migration 不存在")
    for path in FORBIDDEN:
        if path.exists():
            errors.append(f"ARCH002 {path.relative_to(ROOT)}: 方案 A 禁止创建第二套 backend 工程")
    errors.extend(_check_import_boundaries())

    if errors:
        print("\n".join(errors))
        return 1

    print("长期仓库骨架与硬边界检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
