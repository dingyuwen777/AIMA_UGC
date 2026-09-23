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
    feishu_base_url: str = Field(default="https://open.feishu.cn", min_length=1)
    feishu_app_id: str | None = None
    feishu_app_token: str | None = None
    feishu_wiki_token: str | None = None
    feishu_table_id: str | None = None
    feishu_app_secret_filename: str = Field(default="feishu_app_secret", min_length=1)
    feishu_timeout_seconds: float = Field(default=30.0, gt=0, le=1800)
    feishu_max_retries: int = Field(default=3, ge=0, le=8)
    # ── 飞书身份接入（单 ③）───────────────────────────────────────────────
    # ⚠️ 这一组**全部可选**：一个都不配时 `feishu_app_id is None`，进程沿用开发身份，
    # 行为与接入前逐字一致（既有测试与本地开发不受影响）。
    # App Secret **不在这里**：配置只保存"引用"（文件名），内容由 platform/security 读。
    feishu_app_secret_ref: str = Field(default=DEFAULT_FEISHU_APP_SECRET_REF, min_length=1)
    feishu_admin_group_id: str | None = None
    feishu_user_group_id: str | None = None
    feishu_redirect_uri: str | None = None
    feishu_scope: str = Field(default=DEFAULT_FEISHU_SCOPE, min_length=1)
    # `None` = 跟随回调地址协议推断（本地 http 关、生产 https 开）；显式设 true/false 可覆盖。
    feishu_cookie_secure: bool | None = None
    feishu_session_ttl_hours: int = Field(default=8, ge=1, le=720)
    feishu_state_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    # ── 飞书多企业接入（本次新增）─────────────────────────────────────────
    #
    # 上面那组 `feishu_*` 字段是**单企业**形态（一个进程只服务一家企业）。
    # 本字段让一个进程能同时服务**多家企业**：值是**一段 JSON 数组**，
    # 每个元素描述一家企业（code / 显示名 / App ID / Secret 引用 / 两个组 ID / 回调地址）。
    #
    # ⚠️ 与上面那组的关系是**并存而非替代**：
    #   · 本字段**为空** → 行为与改造前**逐字一致**（沿用上面的单企业字段）。
    #     这是"向后兼容"的关键：老 `.env` 不改也能跑。
    #   · 本字段**非空** → 启用多企业，上面的单企业字段被忽略（但仍在配置里，不报错）。
    #
    # ⚠️ 为什么用 JSON 字符串而不是多个扁平环境变量：
    #   ① 一家企业 = 一个对象，增删企业**只动一处**；
    #   ② 能对**整组**做跨字段校验（code 唯一、app_id 唯一等），
    #      而扁平变量只能逐项校验，跨条目的冲突会被漏掉；
    #   ③ 将来若要做"连接器管理"界面，这段 JSON 可直接序列化进库。
    #   实测：单行 JSON（含中文）能被正确解析，`env.local` 已是 UTF-8。
    feishu_connectors_json: str | None = None

    @field_validator(
        "feishu_app_id",
        "feishu_admin_group_id",
        "feishu_user_group_id",
        "feishu_redirect_uri",
        "feishu_connectors_json",
        mode="before",
    )
    @classmethod
    def normalize_blank_to_none(cls, value: object) -> object:
        """空字符串一律归一成 `None`（= 没配）。

        ⚠️ 这条不是洁癖，是**部署正确性**：Compose/CI 常把可选变量写成
        `AIMA_FEISHU_APP_ID=`（留空）。若不归一，`""` 会被当成"配了 App ID"，
        于是进程启用飞书身份却拿不到组 ID → 所有人 403；
        或者反过来，整组校验直接抛错让容器起不来。留空必须与"没写这一项"等价。
        """

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
        """飞书配置**要么整组配齐，要么整组不配**，不允许半配。

        为什么必须拒绝"半配"：只给了 App ID 而没给组 ID 时，进程会启用飞书 Resolver
        却又无法判角色 —— 表现成"所有人登录后 403"，且没有任何配置错误提示。
        与其静默降级，不如在启动/加载配置时直接报错。

        **多企业形态**（`AIMA_FEISHU_CONNECTORS` 非空）走另一条分支：
        逐条解析 + 跨条目校验，任何问题都在**启动时**带着可定位信息报出来。
        """

        # ── 多企业形态（优先判定）──────────────────────────────────────────
        # 一旦配置了多企业，就以它为准：单企业字段被忽略（不报错，便于渐进迁移）。
        if self.feishu_connectors_json is not None and self.feishu_connectors_json.strip():
            self._validate_feishu_connectors()
            return self

        if self.feishu_app_id is None:
            return self

        if self.feishu_app_id != self.feishu_app_id.strip():
            raise ValueError("AIMA_FEISHU_APP_ID 不能有首尾空白")

        # Report publishing uses an App ID + token/table configuration but does not
        # enable the authentication resolver. Keep those settings independent from
        # the login-only group and redirect URI requirements below.
        publishing_configured = any(
            value is not None and (not isinstance(value, str) or bool(value.strip()))
            for value in (self.feishu_app_token, self.feishu_wiki_token, self.feishu_table_id)
        )
        login_configured = any(
            value is not None and bool(value.strip())
            for value in (
                self.feishu_admin_group_id,
                self.feishu_user_group_id,
                self.feishu_redirect_uri,
            )
        )
        if publishing_configured and not login_configured:
            return self

        missing = [
            name
            for name, value in (
                ("AIMA_FEISHU_ADMIN_GROUP_ID", self.feishu_admin_group_id),
                ("AIMA_FEISHU_USER_GROUP_ID", self.feishu_user_group_id),
                ("AIMA_FEISHU_REDIRECT_URI", self.feishu_redirect_uri),
            )
            if value is None or not value.strip()
        ]
        if missing:
            raise ValueError("启用飞书登录必须同时配置 " + "、".join(missing))
        # Secret 引用必须是**相对路径**（不能是绝对路径或含 ..），避免读到批准根之外的文件。
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
                "它应是一段 JSON 数组，每个元素描述一家企业"
            ) from exc
        if not isinstance(payload, list):
            raise ValueError(
                "AIMA_FEISHU_CONNECTORS 必须是 JSON 数组（每个元素一家企业），"
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

    feishu_dry_run: bool = True

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
        """返回身份登录使用的 App Secret 文件路径，不读取 Secret 内容。"""

        return self.external_secret_root / self.feishu_app_secret_ref

    @property
    def feishu_app_secret_path(self) -> Path:
        """返回报告发布使用的 App Secret 文件路径，不读取 Secret 内容。"""

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
    "AIMA_FEISHU_BASE_URL": "feishu_base_url",
    "AIMA_FEISHU_APP_ID": "feishu_app_id",
    "AIMA_FEISHU_APP_TOKEN": "feishu_app_token",
    "AIMA_FEISHU_WIKI_TOKEN": "feishu_wiki_token",
    "AIMA_FEISHU_TABLE_ID": "feishu_table_id",
    "AIMA_FEISHU_APP_SECRET_FILE": "feishu_app_secret_filename",
    "AIMA_FEISHU_TIMEOUT_SECONDS": "feishu_timeout_seconds",
    "AIMA_FEISHU_MAX_RETRIES": "feishu_max_retries",
    "AIMA_FEISHU_APP_SECRET_REF": "feishu_app_secret_ref",
    "AIMA_FEISHU_ADMIN_GROUP_ID": "feishu_admin_group_id",
    "AIMA_FEISHU_USER_GROUP_ID": "feishu_user_group_id",
    "AIMA_FEISHU_REDIRECT_URI": "feishu_redirect_uri",
    "AIMA_FEISHU_SCOPE": "feishu_scope",
    "AIMA_FEISHU_COOKIE_SECURE": "feishu_cookie_secure",
    "AIMA_FEISHU_SESSION_TTL_HOURS": "feishu_session_ttl_hours",
    "AIMA_FEISHU_STATE_TTL_SECONDS": "feishu_state_ttl_seconds",
    "AIMA_FEISHU_CONNECTORS": "feishu_connectors_json",
    "AIMA_FEISHU_DRY_RUN": "feishu_dry_run",
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
