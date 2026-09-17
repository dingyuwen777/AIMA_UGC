"""正式代表性筛选与飞书多维表发布用例。"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from pydantic import SecretStr

from aima_ugc.adapters.feishu import FeishuBitableClient, FeishuConfig, FeishuSyncSummary
from aima_ugc.adapters.llm import (
    OpenAICompatibleContentLabelingLLM,
    RetryingContentLabelingLLM,
    load_llm_pricing,
)
from aima_ugc.adapters.llm.request_audit import LLMRequestAuditWriter
from aima_ugc.adapters.providers.imports import (
    REAL_USER_VOICE_TYPE,
    read_labeled_content_files,
)
from aima_ugc.modules.analysis.representative_selection import (
    RepresentativeSelectionService,
    SelectedRepresentative,
    build_candidate_pool,
)
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.reporting.representative_section import (
    format_representative_labels,
    normalize_representative_content_url,
)
from aima_ugc.platform.security import read_secret_file
from aima_ugc.platform.time import beijing_now

_FEISHU_TARGET_KEY_FIELDS = ("声音内容/连接",)
_TARGET_PLATFORMS = frozenset({"抖音", "小红书"})
_DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "modules" / "analysis" / "prompts" / "zhengfu_shaixuan.md"
)


class RepresentativeSelectionPublicationConfigurationError(RuntimeError):
    """代表性筛选发布所需配置不可用。"""


def publish_representative_selection_to_feishu(
    *,
    input_path: Path,
    output_dir: Path,
    settings: PlatformSettings,
    environ: Mapping[str, str] | None = None,
    max_per_group: int = 10,
    selector_pool_size: int = 50,
    progress: Callable[[int], None] | None = None,
) -> FeishuSyncSummary:
    """读取已打标 Excel，筛选代表性内容并写入新建飞书多维表。"""

    if max_per_group <= 0 or selector_pool_size <= 0:
        raise ValueError("筛选数量参数必须大于 0")
    source = Path(input_path)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    actual_environment = dict(os.environ if environ is None else environ)
    contents, _ = read_labeled_content_files((source,))
    candidate_pool = build_candidate_pool(
        contents,
        real_user_voice_type=REAL_USER_VOICE_TYPE,
    )
    if progress is not None:
        progress(15)

    audit_path = target_dir / "llm_requests.jsonl"
    with LLMRequestAuditWriter(audit_path) as audit_writer:
        llm, raw_llm = _create_llm(
            settings,
            audit=audit_writer,
            environment=actual_environment,
        )
        try:
            selection_run = RepresentativeSelectionService(
                prompt_path=_DEFAULT_PROMPT_PATH,
                llm=llm,
                max_per_group=max_per_group,
                selector_pool_size=selector_pool_size,
            ).run(candidate_pool.candidates)
        finally:
            raw_llm.close()
    if progress is not None:
        progress(65)

    return publish_selected_representatives_to_feishu(
        selected=selection_run.selected,
        output_dir=target_dir,
        settings=settings,
        progress=progress,
    )


def publish_selected_representatives_to_feishu(
    *,
    selected: Sequence[SelectedRepresentative],
    output_dir: Path,
    settings: PlatformSettings,
    progress: Callable[[int], None] | None = None,
) -> FeishuSyncSummary:
    """把已完成筛选的结果发布到新建飞书多维表。"""

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    rows = tuple(selected_representative_to_row(item) for item in selected)
    if not rows:
        raise ValueError("没有可写入的代表性结果，未创建飞书新表")
    feishu_config = FeishuConfig.from_settings(settings)
    app_secret = read_secret_file(
        settings.external_secret_root / feishu_config.app_secret_file,
        root=settings.external_secret_root,
    ).get_secret_value()
    table_name = beijing_now().strftime("%Y%m%dT%H%M%S.%f%z")
    with FeishuBitableClient(
        config=feishu_config,
        app_secret=app_secret,
        upsert_key_fields=_FEISHU_TARGET_KEY_FIELDS,
    ) as template_feishu:
        new_table = template_feishu.create_table_from_current(name=table_name)

    target_config = feishu_config.model_copy(update={"table_id": new_table.table_id})
    with FeishuBitableClient(
        config=target_config,
        app_secret=app_secret,
        upsert_key_fields=_FEISHU_TARGET_KEY_FIELDS,
    ) as feishu:
        prepared = feishu.preflight(rows)
        _write_json(target_dir / "feishu_field_mapping.json", prepared.field_mapping.as_dict())
        _write_jsonl(target_dir / "feishu_before_update.jsonl", prepared.before_snapshot)
        sync_summary = feishu.apply(prepared)
    sync_summary = replace(
        sync_summary,
        target_table_id=new_table.table_id,
        target_table_name=new_table.name,
    )
    _write_json(target_dir / "feishu_new_table.json", new_table.as_dict())
    _write_json(target_dir / "feishu_sync_summary.json", sync_summary.as_dict())
    if progress is not None:
        progress(100)
    return sync_summary


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str))
            handle.write("\n")


def _create_llm(
    settings: PlatformSettings,
    *,
    audit: LLMRequestAuditWriter,
    environment: Mapping[str, str],
) -> tuple[RetryingContentLabelingLLM, OpenAICompatibleContentLabelingLLM]:
    if not settings.llm_base_url or not settings.llm_model:
        raise RepresentativeSelectionPublicationConfigurationError(
            "LLM 配置不完整，需要 AIMA_LLM_BASE_URL 和 AIMA_LLM_MODEL"
        )
    api_key = _read_llm_secret(settings, environment=environment)
    raw_llm = OpenAICompatibleContentLabelingLLM(
        base_url=settings.llm_base_url,
        provider_name=settings.llm_provider_name,
        model=settings.llm_model,
        api_key=api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        max_connections=settings.llm_max_connections,
        pricing_catalog=load_llm_pricing(),
        request_audit=audit.record,
    )
    return RetryingContentLabelingLLM(inner=raw_llm), raw_llm


def create_representative_llm(
    settings: PlatformSettings,
    *,
    audit: LLMRequestAuditWriter,
    environment: Mapping[str, str],
) -> tuple[RetryingContentLabelingLLM, OpenAICompatibleContentLabelingLLM]:
    """创建可供筛选和行动建议共用的 LLM 会话。"""

    return _create_llm(settings, audit=audit, environment=environment)


def _read_llm_secret(
    settings: PlatformSettings,
    *,
    environment: Mapping[str, str],
) -> SecretStr:
    if settings.llm_api_key_file.exists():
        return read_secret_file(settings.llm_api_key_file, root=settings.external_secret_root)
    value = environment.get("AIMA_LLM_API_KEY", "")
    if value.strip():
        return SecretStr(value)
    raise RepresentativeSelectionPublicationConfigurationError(
        "未找到 LLM API Key Secret 文件或 AIMA_LLM_API_KEY"
    )


def selected_representative_to_row(item: SelectedRepresentative) -> dict[str, object]:
    content = item.candidate.content
    decision = item.decision
    if content.platform not in _TARGET_PLATFORMS:
        raise ValueError("代表性结果包含非目标平台")
    if decision.sentiment is None:
        raise ValueError("最终选择缺少情感")
    content_url = normalize_representative_content_url(
        content.platform,
        content.content_url,
    )
    return {
        "声音内容/连接": _content_reference(content.title, content_url, content.content_id),
        "典型评论示例": None,
        "来源": content.platform,
        "发布时间": content.published_at,
        "一级标签": format_representative_labels(content.primary_label),
        "二级标签": format_representative_labels(content.secondary_label),
        "用户情绪": decision.sentiment,
        "处理进展": "待处理",
    }


def _content_reference(title: str, content_url: str, content_id: str) -> str:
    title_text = title.strip()
    link = content_url.strip()
    fallback = link or content_id
    if not title_text:
        return fallback
    return f"{title_text}\n{fallback}" if fallback else title_text


__all__ = [
    "RepresentativeSelectionPublicationConfigurationError",
    "publish_selected_representatives_to_feishu",
    "publish_representative_selection_to_feishu",
    "selected_representative_to_row",
]
