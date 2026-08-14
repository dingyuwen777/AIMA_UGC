"""检查 Stage 1–5B 仓库与架构硬约束。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = [
    ROOT / "pyproject.toml",
    ROOT / "uv.lock",
    ROOT / ".python-version",
    ROOT / ".node-version",
    ROOT / "alembic.ini",
    ROOT / "migrations" / "env.py",
    ROOT / "migrations" / "versions" / "20260813_0001_stage3a_foundation.py",
    ROOT / "migrations" / "versions" / "20260814_0002_stage4_job_runtime.py",
    ROOT / "migrations" / "versions" / "20260814_0003_stage5b_collection_execution.py",
    ROOT / "contracts" / "provider" / "request.v1.schema.json",
    ROOT / "contracts" / "provider" / "attempt.v1.schema.json",
    ROOT / "contracts" / "provider" / "raw-envelope.v1.schema.json",
    ROOT / ".github" / "workflows" / "stage5a-provider-raw.yml",
    ROOT / ".github" / "workflows" / "stage5b-collection-execution.yml",
    ROOT / "backend" / "src" / "aima_ugc" / "__init__.py",
    ROOT / "backend" / "src" / "aima_ugc" / "database_schema.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "config" / "settings.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "security" / "secrets.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "logging" / "formatter.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "database" / "runtime.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "database" / "metadata.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "storage" / "ports.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "storage" / "tables.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "jobs" / "models.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "jobs" / "registry.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "jobs" / "tables.py",
    ROOT / "backend" / "src" / "aima_ugc" / "platform" / "jobs" / "worker.py",
    ROOT / "backend" / "src" / "aima_ugc" / "contracts" / "provider" / "models.py",
    ROOT / "backend" / "src" / "aima_ugc" / "contracts" / "provider" / "raw.py",
    ROOT / "backend" / "src" / "aima_ugc" / "modules" / "collection" / "providers" / "transport.py",
    ROOT
    / "backend"
    / "src"
    / "aima_ugc"
    / "modules"
    / "collection"
    / "providers"
    / "raw_artifact.py",
    ROOT / "backend" / "src" / "aima_ugc" / "modules" / "collection" / "execution.py",
    ROOT / "backend" / "src" / "aima_ugc" / "modules" / "collection" / "tables.py",
    ROOT / "backend" / "src" / "aima_ugc" / "adapters" / "providers" / "fake.py",
    ROOT / "backend" / "src" / "aima_ugc" / "modules" / "system" / "ports.py",
    ROOT / "backend" / "src" / "aima_ugc" / "modules" / "system" / "tables.py",
    ROOT
    / "backend"
    / "src"
    / "aima_ugc"
    / "adapters"
    / "persistence"
    / "postgres"
    / "artifact_metadata.py",
    ROOT / "backend" / "src" / "aima_ugc" / "adapters" / "persistence" / "postgres" / "system.py",
    ROOT / "backend" / "src" / "aima_ugc" / "adapters" / "persistence" / "postgres" / "jobs.py",
    ROOT
    / "backend"
    / "src"
    / "aima_ugc"
    / "adapters"
    / "persistence"
    / "postgres"
    / "collection.py",
    ROOT / "backend" / "src" / "aima_ugc" / "bootstrap" / "runtime.py",
    ROOT / "backend" / "src" / "aima_ugc" / "entrypoints" / "api_main.py",
    ROOT / "backend" / "src" / "aima_ugc" / "entrypoints" / "worker_main.py",
    ROOT / "backend" / "src" / "aima_ugc" / "entrypoints" / "scheduler_main.py",
    ROOT / "backend" / "src" / "aima_ugc" / "entrypoints" / "migrate_main.py",
    ROOT / "frontend" / "package.json",
    ROOT / "frontend" / "package-lock.json",
]
FORBIDDEN = [
    ROOT / "backend" / "pyproject.toml",
    ROOT / "backend" / "uv.lock",
    ROOT / "backend" / "tests",
]


def main() -> int:
    errors: list[str] = []
    for path in REQUIRED:
        if not path.exists():
            errors.append(f"ARCH001 {path.relative_to(ROOT)}: Stage 1–5B 必需文件不存在")
    for path in FORBIDDEN:
        if path.exists():
            errors.append(f"ARCH002 {path.relative_to(ROOT)}: 方案 A 禁止创建第二套 backend 工程")

    if errors:
        print("\n".join(errors))
        return 1

    print("Stage 1–5B 架构骨架检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
