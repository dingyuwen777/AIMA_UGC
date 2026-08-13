"""PostgreSQL 连接与 Schema 元数据基础。"""

from .metadata import metadata
from .runtime import DatabaseRuntime

__all__ = ["DatabaseRuntime", "metadata"]
