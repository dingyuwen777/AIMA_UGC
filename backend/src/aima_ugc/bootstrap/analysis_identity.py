"""HTTP/Worker 共用的 current Analysis 配置身份装配。"""

import hashlib
import json
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from aima_ugc.adapters.llm import resolve_openai_compatible_provider_name
from aima_ugc.adapters.persistence.postgres.analysis_schemes import (
    PostgresAnalysisSchemeRepository,
)
from aima_ugc.adapters.persistence.postgres.system import PostgresAuditRepository
from aima_ugc.modules.analysis.persistence import AnalysisConfigurationIdentity
from aima_ugc.modules.analysis.prompt_taxonomy import PromptTaxonomy
from aima_ugc.modules.analysis.schemes import (
    AnalysisSchemeVersionRecord,
    prompt_taxonomy_from_version,
)
from aima_ugc.modules.system.models import AuditEvent, ProviderConfig
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.time import beijing_now

from .runtime_config import active_llm_provider


@dataclass(frozen=True, slots=True)
class GitPromptPromotion:
    """部署期 Git Prompt promotion 的安全可观察结果。"""

    action: str
    scheme: AnalysisSchemeVersionRecord
    taxonomy: PromptTaxonomy


@dataclass(frozen=True, slots=True)
class ActiveAnalysisConfiguration:
    """数据库 active Scheme 与 LLM Provider 形成的原子运行快照。"""

    scheme: AnalysisSchemeVersionRecord
    taxonomy: PromptTaxonomy
    identity: AnalysisConfigurationIdentity | None
    llm_provider: ProviderConfig | None


def promote_git_analysis_scheme(session: Session) -> GitPromptPromotion:
    """部署期幂等发布镜像内 Git Prompt，并把实际写入记录为系统审计。"""

    scheme, action = PostgresAnalysisSchemeRepository(session).promote_git_prompt()
    taxonomy = prompt_taxonomy_from_version(scheme)
    if action != "unchanged":
        PostgresAuditRepository(session).append(
            AuditEvent(
                id=uuid4(),
                actor_kind="system",
                actor_ref="system:git-promotion",
                event_type=(
                    "analysis_scheme_bootstrapped"
                    if action == "bootstrapped"
                    else "analysis_scheme_git_promoted"
                ),
                object_type="analysis_scheme_version",
                object_id=str(scheme.id),
                request_id=None,
                safe_detail={
                    "action": action,
                    "scheme_id": str(scheme.scheme_id),
                    "version": scheme.version,
                    "prompt_version": taxonomy.output_protocol_version,
                    "prompt_sha256": scheme.prompt_sha256,
                    "taxonomy_sha256": scheme.taxonomy_sha256,
                },
                created_at=beijing_now(),
            )
        )
    return GitPromptPromotion(action=action, scheme=scheme, taxonomy=taxonomy)


def active_analysis_configuration(
    session: Session,
    settings: PlatformSettings,
    *,
    refresh_unused_git_bootstrap: bool = False,
) -> ActiveAnalysisConfiguration:
    """读取 active Scheme；仅显式首次打标入口允许刷新未使用的 Git bootstrap。"""

    repository = PostgresAnalysisSchemeRepository(session)
    bootstrap_changed = False
    if refresh_unused_git_bootstrap:
        scheme, bootstrap_changed = repository.bootstrap_default(actor_ref="system:git-bootstrap")
    else:
        active = repository.get_active_version()
        if active is None:
            scheme, bootstrap_changed = repository.bootstrap_default(
                actor_ref="system:git-bootstrap"
            )
        else:
            scheme = active
    if bootstrap_changed:
        PostgresAuditRepository(session).append(
            AuditEvent(
                id=uuid4(),
                actor_kind="system",
                actor_ref="system:git-bootstrap",
                event_type=(
                    "analysis_scheme_bootstrapped"
                    if scheme.version == 1
                    else "analysis_scheme_bootstrap_refreshed"
                ),
                object_type="analysis_scheme_version",
                object_id=str(scheme.id),
                request_id=None,
                safe_detail={
                    "scheme_id": str(scheme.scheme_id),
                    "version": scheme.version,
                    "prompt_sha256": scheme.prompt_sha256,
                    "taxonomy_sha256": scheme.taxonomy_sha256,
                },
                created_at=beijing_now(),
            )
        )
    taxonomy = prompt_taxonomy_from_version(scheme)
    llm_provider = active_llm_provider(session, settings)
    identity = None
    if llm_provider is not None and llm_provider.model is not None:
        identity = AnalysisConfigurationIdentity(
            prompt_version=taxonomy.prompt_version,
            prompt_sha256=taxonomy.prompt_sha256,
            taxonomy_sha256=taxonomy.taxonomy_sha256,
            model_provider=resolve_openai_compatible_provider_name(
                llm_provider.base_url,
                provider_name=llm_provider.provider,
            ),
            model=llm_provider.model,
        )
    return ActiveAnalysisConfiguration(
        scheme=scheme,
        taxonomy=taxonomy,
        identity=identity,
        llm_provider=llm_provider,
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


__all__ = [
    "ActiveAnalysisConfiguration",
    "GitPromptPromotion",
    "active_analysis_configuration",
    "current_analysis_generation_config",
    "promote_git_analysis_scheme",
]
