"""从显式 AIMA_* 环境变量加载 Platform 配置。"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aima_ugc.platform.identity.connector import (
    ConnectorConfigurationError,
    ConnectorRegistry,
    FeishuConnector,
    build_registry,
    parse_connector,
)

# 飞书登录默认请求的用户身份权限范围：只读当前用户自己的基础资料。
# 与 `bootstrap/feishu_auth_http.py` 的默认值保持一致（避免"两处各写一个字面量"）。
DEFAULT_FEISHU_SCOPE = "contact:user.base:readonly"
# 默认的 App Secret 引用（相对 `external_secret_root`，**只存引用不存 Secret 内容**）。
DEFAULT_FEISHU_APP_SECRET_REF = "feishu_app_secret"


class PlatformSettings(BaseModel):
    """业务无关的进程运行配置。"""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    data_dir: Path
    identity_mode: Literal["development", "feishu"] = "development"
    log_dir: Path
    secret_dir: Path
    external_secret_dir: Path | None = None
    historical_import_root: Path | None = None
    wisersone_auth_dir: Path | None = None
    wisersone_input_dir: Path | None = None
    # 运行容量与目录安全边界只由代码管理；旧 env 值不得在不同机器上造成行为漂移。
    historical_chunk_rows: int = Field(default=4_000, ge=100, le=4_000)
    historical_max_scan_files: int = Field(default=10_000, ge=1, le=100_000)
    historical_max_directory_depth: int = Field(default=8, ge=1, le=32)
    historical_max_in_flight_jobs: int | None = Field(default=None, ge=1)
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
    analysis_run_max_in_flight_jobs: int | None = Field(default=None, ge=1)
    report_artifact_retention_days: int = Field(default=60, ge=1, le=3650)
    # 飞书多维表发布配置；与身份登录配置并存，Secret 仍只保存文件引用。
    feishu_base_url: str = Field(default="https://open.feishu.cn", min_length=1)
    feishu_app_token: str | None = None
    feishu_wiki_token: str | None = None
    feishu_table_id: str | None = None
    feishu_app_secret_filename: str = Field(default="feishu_app_secret", min_length=1)
    feishu_timeout_seconds: float = Field(default=30.0, gt=0, le=1800)
    feishu_max_retries: int = Field(default=3, ge=0, le=8)
    feishu_dry_run: bool = True
    # 报告/多维表的独立应用，不用于网页登录身份装配。
    feishu_app_id: str | None = None
    feishu_app_secret_ref: str = Field(default=DEFAULT_FEISHU_APP_SECRET_REF, min_length=1)
    feishu_scope: str = Field(default=DEFAULT_FEISHU_SCOPE, min_length=1)
    # `None` = 跟随回调地址协议推断（本地 http 关、生产 https 开）；显式设 true/false 可覆盖。
    feishu_cookie_secure: bool | None = None
    feishu_session_ttl_hours: int = Field(default=8, ge=1, le=720)
    feishu_state_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    # 登录唯一配置：一个应用一个数组元素；启动流程已把明文凭据转成文件引用。
    feishu_connectors_json: str | None = Field(default=None, repr=False)

    @field_validator(
        "feishu_app_id",
        "feishu_connectors_json",
        mode="before",
    )
    @classmethod
    def normalize_blank_to_none(cls, value: object) -> object:
        """Compose 可选配置留空等价于未配置，正式身份是否可用由装配校验。"""

        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("feishu_cookie_secure", mode="before")
    @classmethod
    def normalize_optional_flag(cls, value: object) -> object:
        """把"空值"归一成 `None`（= 按环境推断），而不是猜成 `False`。

        环境变量常常被写成 `AIMA_FEISHU_COOKIE_SECURE=`（留空表示"默认"）。
        若把它当成 `False`，生产环境就会在 HTTPS 下漏掉 `Secure` 属性 —— 这是安全缺陷，
        所以留空必须明确表示"没表态，按回调协议推断"。
        """

        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_feishu_configuration(self) -> PlatformSettings:
        """独立校验登录数组与报告应用，报告配置不能替代登录所需的用户组。"""
        if self.feishu_connectors_json is not None:
            self._validate_feishu_connectors()
        if self.feishu_app_id is not None:
            if self.feishu_app_id != self.feishu_app_id.strip():
                raise ValueError("AIMA_FEISHU_APP_ID 不能有首尾空白")
            from aima_ugc.platform.security import validate_secret_ref

            validate_secret_ref(self.feishu_app_secret_ref)
        return self

    def _validate_feishu_connectors(self) -> None:
        """校验多企业配置，并**逐个 Secret 引用**走既有的路径安全校验。

        ⚠️ 这里刻意让异常信息**带上企业标识**：多企业配置出错时，
        "第 2 个 connector 的 app_id 重复" 比 "配置非法" 有用得多。
        """

        raw = self.feishu_connectors_json or ""
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"AIMA_FEISHU_CONNECTORS 不是合法 JSON：{exc}。"
                "它应是一段 JSON 数组，每个元素描述一个应用"
            ) from exc
        if not isinstance(payload, list):
            raise ValueError(
                "AIMA_FEISHU_CONNECTORS 必须是 JSON 数组（每个元素一个应用），"
                f"实际是 {type(payload).__name__}"
            )

        connectors: list[FeishuConnector] = []
        for index, item in enumerate(payload):
            try:
                connectors.append(parse_connector(item, index=index))
            except ConnectorConfigurationError as exc:
                raise ValueError(f"AIMA_FEISHU_CONNECTORS 配置错误：{exc}") from exc

        try:
            build_registry(connectors)
        except ConnectorConfigurationError as exc:
            raise ValueError(f"AIMA_FEISHU_CONNECTORS 配置错误：{exc}") from exc

        # 每个企业的 Secret 引用都要过同一套路径安全校验
        # （防止某一家企业的 ref 写成绝对路径或含 `..` 而读到批准根之外）。
        from aima_ugc.platform.security import validate_secret_ref

        for connector in connectors:
            try:
                validate_secret_ref(connector.app_secret_ref)
            except ValueError as exc:
                raise ValueError(
                    f"connector {connector.code!r} 的 app_secret_ref 不合法：{exc}"
                ) from exc

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

    @property
    def feishu_app_secret_file(self) -> Path:
        """返回飞书 App Secret 文件路径，不读取 Secret 内容。"""
        return self.external_secret_root / self.feishu_app_secret_ref

    @property
    def feishu_app_secret_path(self) -> Path:
        """兼容报告发布配置使用的飞书 App Secret 路径别名。"""
        return self.external_secret_root / self.feishu_app_secret_filename

    # ── 多企业：解析与查询 ────────────────────────────────────────────────

    @property
    def feishu_connectors(self) -> ConnectorRegistry | None:
        """把 `feishu_connectors_json` 解析成注册表；未配置时返回 `None`。

        ⚠️ **解析失败不在这里抛错** —— 校验发生在 `validate_feishu_configuration()`
        （模型校验阶段），本属性只做"能不能解析"的**纯读取**，
        因此可以在任意时刻安全调用（包括测试里直接构造的实例）。
        """

        raw = self.feishu_connectors_json
        if raw is None or not raw.strip():
            return None
        return _parse_connectors_or_none(raw)

    @property
    def has_feishu_connectors(self) -> bool:
        """是否启用了多企业配置。"""

        return self.feishu_connectors is not None

    def connector_for(self, code: str) -> FeishuConnector | None:
        """按企业标识取该企业的配置；未启用多企业或找不到时返回 `None`。"""

        registry = self.feishu_connectors
        return None if registry is None else registry.get(code)


_ENV_TO_FIELD = {
    "AIMA_DATA_DIR": "data_dir",
    "AIMA_LOG_DIR": "log_dir",
    "AIMA_SECRET_DIR": "secret_dir",
    "AIMA_EXTERNAL_SECRET_DIR": "external_secret_dir",
    "AIMA_HISTORICAL_IMPORT_ROOT": "historical_import_root",
    "AIMA_WISERSONE_AUTH_DIR": "wisersone_auth_dir",
    "AIMA_WISERSONE_INPUT_DIR": "wisersone_input_dir",
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
    "AIMA_REPORT_ARTIFACT_RETENTION_DAYS": "report_artifact_retention_days",
    "AIMA_LLM_TIMEOUT_SECONDS": "llm_timeout_seconds",
    "AIMA_LLM_MAX_CONNECTIONS": "llm_max_connections",
    "AIMA_LLM_VALIDATION_RETRIES": "llm_validation_retries",
    "AIMA_IDENTITY_MODE": "identity_mode",
    "AIMA_FEISHU_APP_ID": "feishu_app_id",
    "AIMA_FEISHU_BASE_URL": "feishu_base_url",
    "AIMA_FEISHU_APP_TOKEN": "feishu_app_token",
    "AIMA_FEISHU_WIKI_TOKEN": "feishu_wiki_token",
    "AIMA_FEISHU_TABLE_ID": "feishu_table_id",
    "AIMA_FEISHU_APP_SECRET_FILENAME": "feishu_app_secret_filename",
    "AIMA_FEISHU_APP_SECRET_FILE": "feishu_app_secret_filename",
    "AIMA_FEISHU_TIMEOUT_SECONDS": "feishu_timeout_seconds",
    "AIMA_FEISHU_MAX_RETRIES": "feishu_max_retries",
    "AIMA_FEISHU_DRY_RUN": "feishu_dry_run",
    "AIMA_FEISHU_APP_SECRET_REF": "feishu_app_secret_ref",
    "AIMA_FEISHU_SCOPE": "feishu_scope",
    "AIMA_FEISHU_COOKIE_SECURE": "feishu_cookie_secure",
    "AIMA_FEISHU_SESSION_TTL_HOURS": "feishu_session_ttl_hours",
    "AIMA_FEISHU_STATE_TTL_SECONDS": "feishu_state_ttl_seconds",
    "AIMA_FEISHU_CONNECTORS": "feishu_connectors_json",
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


def _parse_connectors_or_none(raw: str) -> ConnectorRegistry | None:
    """解析多企业配置；**只在能解析出合法注册表时返回值**，否则 `None`。

    ⚠️ 为什么"失败返回 None"而不是抛错：
    本函数被 `feishu_connectors` 属性调用，而属性可能在**校验之前**被访问
    （例如构造实例后立即读它）。真正需要"配置非法就启动失败"的地方是
    `validate_feishu_configuration()` —— 它会在那里**明确指出错误原因**。
    两处职责分开：属性负责"能不能用"，校验负责"合不合法且为什么"。
    """

    try:
        payload = json.loads(raw)
    except TypeError, ValueError:
        return None
    if not isinstance(payload, list):
        return None
    try:
        connectors = [parse_connector(item, index=i) for i, item in enumerate(payload)]
        return build_registry(connectors)
    except ConnectorConfigurationError:
        return None


def load_settings(
    environ: Mapping[str, str] | None = None,
    *,
    base_dir: Path | None = None,
) -> PlatformSettings:
    """加载当前进程配置；只读取显式列出的 AIMA_* 环境变量。"""
    source = os.environ if environ is None else environ
    # 旧登录变量不能静默忽略，否则本地可能误退回开发管理员身份。
    if any(
        source.get(name, "").strip()
        for name in (
            "AIMA_FEISHU_ADMIN_GROUP_ID",
            "AIMA_FEISHU_USER_GROUP_ID",
            "AIMA_FEISHU_REDIRECT_URI",
        )
    ):
        raise ValueError("旧扁平飞书登录配置已移除，请统一使用 AIMA_FEISHU_CONNECTORS")
    values: dict[str, object] = dict(_DEFAULTS)
    for env_name, field_name in _ENV_TO_FIELD.items():
        if env_name in source:
            values[field_name] = source[env_name]

    root = (Path.cwd() if base_dir is None else base_dir).resolve(strict=False)
    # Compose 初始化阶段已将凭据拆出；业务进程只读不含 Secret 的运行配置。
    connector_file = source.get("AIMA_FEISHU_CONNECTORS_FILE")
    if connector_file:
        from aima_ugc.platform.security.secrets import read_secret_file

        raw = read_secret_file(_resolve_path(connector_file, root)).get_secret_value()
        values["feishu_connectors_json"] = None if raw == "null" else raw
    connector_input = values.get("feishu_connectors_json")
    if isinstance(connector_input, str):
        try:
            payload = json.loads(connector_input)
        except ValueError:
            payload = None  # 其余格式错误仍交由现有 Settings 校验。
        if isinstance(payload, list) and any(
            isinstance(item, dict) and "app_secret" in item for item in payload
        ):
            raise ValueError(
                "app_secret 只能由源码 launcher / Compose bootstrap 处理；"
                "业务进程应使用清理后的 Connector 配置"
            )
    for field_name in (
        "data_dir",
        "log_dir",
        "secret_dir",
        "external_secret_dir",
        "historical_import_root",
        "wisersone_auth_dir",
        "wisersone_input_dir",
    ):
        value = values.get(field_name)
        if value is not None:
            values[field_name] = _resolve_path(value, root)

    return PlatformSettings.model_validate(values)
