"""飞书多维表连接配置。"""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.security import validate_secret_ref


class FeishuConfigError(ValueError):
    """飞书非 Secret 配置不完整。"""

    def __init__(self, missing: Sequence[str]) -> None:
        self.missing = tuple(missing)
        super().__init__("飞书配置不完整，缺少: " + ", ".join(self.missing))


class FeishuConfig(BaseModel):
    """不包含 App Secret 的飞书连接配置。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = Field(default="https://open.feishu.cn", min_length=1)
    app_id: str = Field(min_length=1)
    app_token: str | None = None
    wiki_token: str | None = None
    table_id: str = Field(min_length=1)
    app_secret_file: str = Field(default="feishu_app_secret", min_length=1)
    timeout_seconds: float = Field(default=30.0, gt=0, le=1800)
    max_retries: int = Field(default=3, ge=0, le=8)
    field_aliases: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("飞书 base_url 必须是无凭据、query、fragment 的 HTTP(S) URL")
        return normalized

    @field_validator("app_id", "app_token", "wiki_token", "table_id")
    @classmethod
    def validate_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("飞书配置标识不能为空")
        return cleaned

    @field_validator("app_secret_file")
    @classmethod
    def validate_app_secret_file(cls, value: str) -> str:
        return validate_secret_ref(value.strip())

    @classmethod
    def from_settings(cls, settings: PlatformSettings) -> FeishuConfig:
        """从统一 Settings 装配，缺少关键配置时 fail closed。"""

        missing = [
            name
            for name, value in (
                ("AIMA_FEISHU_APP_ID", settings.feishu_app_id),
                ("AIMA_FEISHU_TABLE_ID", settings.feishu_table_id),
            )
            if not value or not value.strip()
        ]
        if not settings.feishu_app_token and not settings.feishu_wiki_token:
            missing.append("AIMA_FEISHU_APP_TOKEN 或 AIMA_FEISHU_WIKI_TOKEN")
        if missing:
            raise FeishuConfigError(missing)
        return cls(
            base_url=settings.feishu_base_url,
            app_id=settings.feishu_app_id or "",
            app_token=settings.feishu_app_token,
            wiki_token=settings.feishu_wiki_token,
            table_id=settings.feishu_table_id or "",
            app_secret_file=settings.feishu_app_secret_file,
            timeout_seconds=settings.feishu_timeout_seconds,
            max_retries=settings.feishu_max_retries,
        )


__all__ = ["FeishuConfig", "FeishuConfigError"]
