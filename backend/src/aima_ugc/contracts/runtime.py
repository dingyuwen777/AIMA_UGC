"""运行能力只读 HTTP Contract。"""

from pydantic import BaseModel, ConfigDict


class ContentAnalysisCapabilitiesResponse(BaseModel):
    """只公开 AI Analysis 当前是否具备可执行配置，不暴露配置细节。"""

    model_config = ConfigDict(extra="forbid")

    configured: bool


__all__ = ["ContentAnalysisCapabilitiesResponse"]
