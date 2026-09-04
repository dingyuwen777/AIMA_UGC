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
    external_secret_dir: Path | None = None
    historical_import_root: Path | None = None
    historical_chunk_rows: int = Field(default=1000, ge=100, le=2000)
    historical_max_scan_files: int = Field(default=10_000, ge=1, le=100_000)
    historical_max_directory_depth: int = Field(default=8, ge=1, le=32)
    historical_max_in_flight_jobs: int = Field(default=2, ge=1, le=16)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_max_bytes: int = Field(default=20_971_520, gt=0)
    log_backup_count: int = Field(default=10, ge=0)
    log_compress: bool = True
    db_host: str = Field(default="127.0.0.1", min_length=1)
    db_port: int = Field(default=5432, ge=1, le=65_535)
    db_name: str = Field(default="aima_ugc", min_length=1)
    db_user: str = Field(default="aima_ugc", min_length=1)
    db_connect_timeout_seconds: int = Field(default=3, ge=1, le=60)
    llm_base_url: str | None = None
    llm_provider_name: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=60.0, gt=0, le=1800)
    llm_max_connections: int = Field(default=10, ge=1, le=100)
    llm_validation_retries: int = Field(default=1, ge=0, le=3)
    analysis_run_max_in_flight_jobs: int = Field(default=2, ge=1, le=16)

    @property
    def artifact_dir(self) -> Path:
        """返回 Local ArtifactStore 的字节根目录。"""
        return self.data_dir / "artifacts"

    @property
    def external_secret_root(self) -> Path:
        """返回 Provider/LLM Secret 根；未分离部署时继续复用既有 Secret 根。"""
        return self.external_secret_dir or self.secret_dir

    @property
    def postgres_password_file(self) -> Path:
        """返回 PostgreSQL 密码文件，不读取 Secret 内容。"""
        return self.secret_dir / "postgres_password"

    @property
    def import_batch_cursor_signing_key_file(self) -> Path:
        """返回 Import Batch Cursor 签名密钥文件，不读取 Secret 内容。"""
        return self.secret_dir / "import_batch_cursor_signing_key"

    @property
    def content_cursor_signing_key_file(self) -> Path:
        """返回声音广场 Cursor 签名密钥文件，不读取 Secret 内容。"""
        return self.secret_dir / "content_cursor_signing_key"

    @property
    def collection_runtime_cursor_signing_key_file(self) -> Path:
        """返回统一采集运行 Cursor 签名密钥文件，不读取 Secret 内容。"""
        return self.secret_dir / "collection_runtime_cursor_signing_key"

    @property
    def llm_api_key_file(self) -> Path:
        """返回正式 Analysis LLM API Key 文件，不读取 Secret 内容。"""
        return self.external_secret_root / "llm_api_key"


_ENV_TO_FIELD = {
    "AIMA_DATA_DIR": "data_dir",
    "AIMA_LOG_DIR": "log_dir",
    "AIMA_SECRET_DIR": "secret_dir",
    "AIMA_EXTERNAL_SECRET_DIR": "external_secret_dir",
    "AIMA_HISTORICAL_IMPORT_ROOT": "historical_import_root",
    "AIMA_HISTORICAL_CHUNK_ROWS": "historical_chunk_rows",
    "AIMA_HISTORICAL_MAX_SCAN_FILES": "historical_max_scan_files",
    "AIMA_HISTORICAL_MAX_DIRECTORY_DEPTH": "historical_max_directory_depth",
    "AIMA_HISTORICAL_MAX_IN_FLIGHT_JOBS": "historical_max_in_flight_jobs",
    "AIMA_LOG_LEVEL": "log_level",
    "AIMA_LOG_MAX_BYTES": "log_max_bytes",
    "AIMA_LOG_BACKUP_COUNT": "log_backup_count",
    "AIMA_LOG_COMPRESS": "log_compress",
    "AIMA_DB_HOST": "db_host",
    "AIMA_DB_PORT": "db_port",
    "AIMA_DB_NAME": "db_name",
    "AIMA_DB_USER": "db_user",
    "AIMA_DB_CONNECT_TIMEOUT_SECONDS": "db_connect_timeout_seconds",
    "AIMA_LLM_BASE_URL": "llm_base_url",
    "AIMA_LLM_PROVIDER_NAME": "llm_provider_name",
    "AIMA_LLM_MODEL": "llm_model",
    "AIMA_LLM_TIMEOUT_SECONDS": "llm_timeout_seconds",
    "AIMA_LLM_MAX_CONNECTIONS": "llm_max_connections",
    "AIMA_LLM_VALIDATION_RETRIES": "llm_validation_retries",
    "AIMA_ANALYSIS_RUN_MAX_IN_FLIGHT_JOBS": "analysis_run_max_in_flight_jobs",
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
    for field_name in (
        "data_dir",
        "log_dir",
        "secret_dir",
        "external_secret_dir",
        "historical_import_root",
    ):
        value = values.get(field_name)
        if value is not None:
            values[field_name] = _resolve_path(value, root)

    return PlatformSettings.model_validate(values)
