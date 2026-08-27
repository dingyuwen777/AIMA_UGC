"""HTTP/Worker 共用的 current Analysis 配置身份装配。"""

import hashlib
import json

from aima_ugc.adapters.llm import resolve_openai_compatible_provider_name
from aima_ugc.modules.analysis import CONTENT_LABELING_PROMPT_PATH, PromptTaxonomyLoader
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity
from aima_ugc.platform.config import PlatformSettings


def current_analysis_identity(
    settings: PlatformSettings,
) -> AnalysisConfigurationIdentity | None:
    """未配置模型时没有 current 结果；历史结果仍保留并投影为 stale。"""

    if settings.llm_base_url is None or settings.llm_model is None:
        return None
    taxonomy = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH).load()
    return AnalysisConfigurationIdentity(
        prompt_version=taxonomy.prompt_version,
        prompt_sha256=taxonomy.prompt_sha256,
        taxonomy_sha256=taxonomy.taxonomy_sha256,
        model_provider=resolve_openai_compatible_provider_name(
            settings.llm_base_url,
            provider_name=settings.llm_provider_name,
        ),
        model=settings.llm_model,
    )


def current_analysis_generation_config() -> tuple[dict[str, object], str]:
    """冻结正式 Adapter 实际发送的生成参数，不记录模型不支持的虚构参数。"""

    config: dict[str, object] = {"response_format": {"type": "json_object"}}
    encoded = json.dumps(
        config,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return config, hashlib.sha256(encoded).hexdigest()


__all__ = ["current_analysis_generation_config", "current_analysis_identity"]
