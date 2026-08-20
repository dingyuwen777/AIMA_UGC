"""从显式 AIMA_* 环境变量加载 Platform 配置。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlatformSettings(BaseModel):
    """业务无关的进程运行配置。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data_dir: Path
    log_dir: Path
    secret_dir: Path
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_max_bytes: int = Field(default=20_971_520, gt=0)
    log_backup_count: int = Field(default=10, ge=0)
    log_compress: bool = True
    db_host: str = Field(default="127.0.0.1", min_length=1)
    db_port: int = Field(default=5432, ge=1, le=65_535)
    db_name: str = Field(default="aima_ugc", min_length=1)
    db_user: str = Field(default="aima_ugc", min_length=1)
    db_connect_timeout_seconds: int = Field(default=3, ge=1, le=60)

    @property
    def artifact_dir(self) -> Path:
        """返回 Local ArtifactStore 的字节根目录。"""
        return self.data_dir / "artifacts"

    @property
    def postgres_password_file(self) -> Path:
        """返回 PostgreSQL 密码文件，不读取 Secret 内容。"""
        return self.secret_dir / "postgres_password"

    @property
    def import_batch_cursor_signing_key_file(self) -> Path:
        """返回 Import Batch Cursor 签名密钥文件，不读取 Secret 内容。"""
        return self.secret_dir / "import_batch_cursor_signing_key"


_ENV_TO_FIELD = {
    "AIMA_DATA_DIR": "data_dir",
    "AIMA_LOG_DIR": "log_dir",
    "AIMA_SECRET_DIR": "secret_dir",
    "AIMA_LOG_LEVEL": "log_level",
    "AIMA_LOG_MAX_BYTES": "log_max_bytes",
    "AIMA_LOG_BACKUP_COUNT": "log_backup_count",
    "AIMA_LOG_COMPRESS": "log_compress",
    "AIMA_DB_HOST": "db_host",
    "AIMA_DB_PORT": "db_port",
    "AIMA_DB_NAME": "db_name",
    "AIMA_DB_USER": "db_user",
    "AIMA_DB_CONNECT_TIMEOUT_SECONDS": "db_connect_timeout_seconds",
}

_DEFAULTS = {
    "data_dir": ".runtime/data",
    "log_dir": ".runtime/logs",
    "secret_dir": ".runtime/secrets",
}


def _resolve_path(value: object, base_dir: Path) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve(strict=False)


def load_settings(
    environ: Mapping[str, str] | None = None,
    *,
    base_dir: Path | None = None,
) -> PlatformSettings:
    """加载当前进程配置；只读取显式列出的 AIMA_* 环境变量。"""
    source = os.environ if environ is None else environ
    values: dict[str, object] = dict(_DEFAULTS)
    for env_name, field_name in _ENV_TO_FIELD.items():
        if env_name in source:
            values[field_name] = source[env_name]

    root = (Path.cwd() if base_dir is None else base_dir).resolve(strict=False)
    for field_name in ("data_dir", "log_dir", "secret_dir"):
        values[field_name] = _resolve_path(values[field_name], root)

    return PlatformSettings.model_validate(values)
