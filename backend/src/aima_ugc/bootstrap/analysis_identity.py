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
from aima_ugc.modules.system.models import AuditEvent
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.time import beijing_now


@dataclass(frozen=True, slots=True)
class ActiveAnalysisConfiguration:
    """数据库 active Scheme 与模型配置形成的原子运行快照。"""

    scheme: AnalysisSchemeVersionRecord
    taxonomy: PromptTaxonomy
    identity: AnalysisConfigurationIdentity | None


def active_analysis_configuration(
    session: Session,
    settings: PlatformSettings,
) -> ActiveAnalysisConfiguration:
    """读取数据库 active Scheme；首次 bootstrap 与系统审计同事务提交。"""

    repository = PostgresAnalysisSchemeRepository(session)
    scheme, created = repository.bootstrap_default(actor_ref="system:git-bootstrap")
    if created:
        PostgresAuditRepository(session).append(
            AuditEvent(
                id=uuid4(),
                actor_kind="system",
                actor_ref="system:git-bootstrap",
                event_type="analysis_scheme_bootstrapped",
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
    identity = None
    if settings.llm_base_url is not None and settings.llm_model is not None:
        identity = AnalysisConfigurationIdentity(
            prompt_version=taxonomy.prompt_version,
            prompt_sha256=taxonomy.prompt_sha256,
            taxonomy_sha256=taxonomy.taxonomy_sha256,
            model_provider=resolve_openai_compatible_provider_name(
                settings.llm_base_url,
                provider_name=settings.llm_provider_name,
            ),
            model=settings.llm_model,
        )
    return ActiveAnalysisConfiguration(
        scheme=scheme,
        taxonomy=taxonomy,
        identity=identity,
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
    "active_analysis_configuration",
    "current_analysis_generation_config",
]
