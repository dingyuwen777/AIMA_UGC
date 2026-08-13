"""Migration 进程入口模块；Alembic Revision 在 Stage 3 建立。"""

from aima_ugc.bootstrap.migration import create_migration_runtime

__all__ = ["create_migration_runtime"]
