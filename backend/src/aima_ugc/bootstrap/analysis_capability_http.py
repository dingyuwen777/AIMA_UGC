"""AI Analysis Runtime Capability 的安全只读 HTTP 装配。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI

from aima_ugc.contracts.runtime import ContentAnalysisCapabilitiesResponse
from aima_ugc.platform.config import PlatformSettings, load_settings
from aima_ugc.platform.security import SecretFileError, read_secret_file

SettingsLoader = Callable[[], PlatformSettings]


def content_analysis_configured(settings: PlatformSettings) -> bool:
    """按正式 Worker 最低前提判断 Analysis 是否可执行，不返回配置细节。"""

    if settings.llm_base_url is None or settings.llm_model is None:
        return False
    try:
        read_secret_file(settings.llm_api_key_file, root=settings.secret_dir)
    except SecretFileError:
        return False
    return True


def install_content_analysis_capability_route(
    application: FastAPI,
    *,
    settings_loader: SettingsLoader = load_settings,
) -> None:
    """把安全的 Analysis Capability Read Model 安装到最终 FastAPI 应用。"""

    @application.get(
        "/api/v1/content-analysis-capabilities",
        operation_id="getContentAnalysisCapabilities",
        response_model=ContentAnalysisCapabilitiesResponse,
        tags=["contents"],
    )
    def get_content_analysis_capabilities() -> ContentAnalysisCapabilitiesResponse:
        return ContentAnalysisCapabilitiesResponse(
            configured=content_analysis_configured(settings_loader()),
        )


__all__ = ["content_analysis_configured", "install_content_analysis_capability_route"]
