"""离线筛选代表性正负面内容并可选同步至飞书。"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from pydantic import SecretStr, ValidationError

from aima_ugc.adapters.feishu import (
    FeishuBitableClient,
    FeishuConfig,
    FeishuConfigError,
    FeishuSyncError,
    FeishuSyncSummary,
)
from aima_ugc.adapters.llm import (
    OpenAICompatibleContentLabelingLLM,
    RetryingContentLabelingLLM,
    load_llm_pricing,
)
from aima_ugc.adapters.llm.request_audit import LLMRequestAuditWriter
from aima_ugc.adapters.providers.imports import (
    REAL_USER_VOICE_TYPE,
    LabeledContent,
    LabeledContentReadSummary,
    read_labeled_content_files,
)
from aima_ugc.modules.analysis.representative_selection import (
    CandidatePoolSummary,
    RepresentativeCandidate,
    RepresentativeDecisionModel,
    RepresentativeDecisionOutcome,
    RepresentativeSelectionRun,
    RepresentativeSelectionService,
    SelectedRepresentative,
    build_candidate_pool,
)
from aima_ugc.platform.config import PlatformSettings, load_settings
from aima_ugc.platform.security import SecretFileError, read_secret_file

os.environ.pop("SSLKEYLOGFILE", None)

DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "modules" / "analysis" / "prompts" / "zhengfu_shaixuan.md"
)
DEFAULT_ENV_FILE = (
    Path(__file__).resolve().parents[1] / "adapters" / "providers" / "imports_test" / ".env"
)
_SELECTED_CONTENT_FIELDS = frozenset(
    {
        "row_number",
        "platform",
        "content_id",
        "title",
        "text",
        "author",
        "published_at",
        "content_url",
        "voice_type",
        "sentiment_label",
    }
)
_TARGET_PLATFORMS = frozenset({"抖音", "小红书"})
_FEISHU_TARGET_KEY_FIELDS = ("声音内容/连接",)


class SelectedResultsFileError(ValueError):
    """已有 selected_results.jsonl 不满足只同步飞书的输入契约。"""


def build_argument_parser() -> argparse.ArgumentParser:
    """构造独立入口参数。"""

    parser = argparse.ArgumentParser(description="筛选抖音/小红书代表性正负面内容")
    parser.add_argument(
        "--input-xlsx",
        type=Path,
        action="append",
        help="已打标 XLSX 文件；可重复传入多个文件，按顺序合并各文件的‘内容’Sheet",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        default=DEFAULT_PROMPT_PATH,
        help="代表性筛选 Prompt Markdown 文件",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="配置文件；未指定时自动读取 imports_test/.env（进程环境变量优先）",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只生成本地结果，不写飞书")
    mode.add_argument("--write-feishu", action="store_true", help="执行飞书多维表 Upsert")
    mode.add_argument(
        "--write-feishu-from-run",
        type=Path,
        help="读取已有运行目录中的 selected_results.jsonl，只同步飞书，不调用大模型",
    )
    parser.add_argument("--run-dir", type=Path, help="完整筛选运行的产物目录")
    parser.add_argument("--max-per-group", type=int, default=10, help="每个平台/情感最多条数")
    parser.add_argument(
        "--selector-pool-size",
        type=int,
        default=50,
        help="每组交给第二阶段模型的候选上限",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行代表性内容筛选；默认模式为 Dry Run。"""

    parser = build_argument_parser()
    arguments = parser.parse_args(argv)
    if arguments.max_per_group <= 0:
        parser.error("--max-per-group 必须大于 0")
    if arguments.selector_pool_size <= 0:
        parser.error("--selector-pool-size 必须大于 0")

    try:
        settings, environment = _load_entrypoint_settings(arguments.env_file)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    if arguments.write_feishu_from_run is not None:
        if arguments.input_xlsx is not None:
            parser.error("--write-feishu-from-run 不能与 --input-xlsx 同时使用")
        if arguments.run_dir is not None:
            parser.error("--write-feishu-from-run 不能与 --run-dir 同时使用")
        return _sync_selected_results_from_run(
            run_dir=arguments.write_feishu_from_run,
            settings=settings,
            max_per_group=arguments.max_per_group,
        )
    if arguments.input_xlsx is None:
        parser.error("完整筛选模式必须提供 --input-xlsx")

    input_paths = tuple(path.resolve() for path in arguments.input_xlsx)
    input_path = input_paths[0]
    prompt_path = arguments.prompt.resolve()
    output_dir = _resolve_run_dir(input_path, arguments.run_dir)
    output_dir.mkdir(parents=True, exist_ok=False)

    contents, read_summary = read_labeled_content_files(input_paths)
    candidate_pool = build_candidate_pool(
        contents,
        real_user_voice_type=REAL_USER_VOICE_TYPE,
    )
    _write_jsonl(
        output_dir / "candidates.jsonl",
        (
            {"item_no": candidate.item_no, "content": _content_payload(candidate)}
            for candidate in candidate_pool.candidates
        ),
    )

    audit_path = output_dir / "llm_requests.jsonl"
    with LLMRequestAuditWriter(audit_path) as audit_writer:
        llm, raw_llm = _create_llm(
            settings,
            max_connections=settings.llm_max_connections,
            audit=audit_writer,
            environment=environment,
        )
        try:
            service = RepresentativeSelectionService(
                prompt_path=prompt_path,
                llm=llm,
                max_per_group=arguments.max_per_group,
                selector_pool_size=arguments.selector_pool_size,
            )
            selection_run = service.run(candidate_pool.candidates)
        finally:
            raw_llm.close()

    _write_jsonl(
        output_dir / "decisions.jsonl",
        (_outcome_payload(outcome) for outcome in selection_run.outcomes),
    )
    _write_jsonl(
        output_dir / "selected_results.jsonl",
        (
            {
                "content": _content_payload(item.candidate),
                "decision": item.decision.model_dump(),
            }
            for item in selection_run.selected
        ),
    )
    _write_jsonl(
        output_dir / "failed.jsonl",
        (
            _outcome_payload(outcome)
            for outcome in selection_run.outcomes
            if outcome.status == "failed"
        ),
    )

    summary = _selection_summary(
        input_paths=input_paths,
        read_summary=read_summary,
        candidate_summary=candidate_pool.summary,
        selection_run=selection_run,
        output_dir=output_dir,
        mode="write-feishu" if arguments.write_feishu else "dry-run",
    )
    _write_json(output_dir / "selection_summary.json", summary)

    if not arguments.write_feishu:
        _print_json(summary)
        return 0

    try:
        sync_summary = _sync_to_feishu(
            settings=settings,
            selected=selection_run.selected,
            output_dir=output_dir,
        )
    except (FileNotFoundError, SecretFileError, ValueError, RuntimeError) as exc:
        # 只输出错误类型，避免第三方响应正文或 Secret 进入终端/产物。
        _write_json(
            output_dir / "feishu_sync_summary.json",
            _sync_failure_payload(exc),
        )
        _print_line(f"飞书同步失败: {_safe_error_message(exc)}")
        return 2

    if sync_summary.verification_errors:
        _print_line("飞书同步完成但回读核验存在错误")
        return 2
    _print_json(sync_summary.as_dict())
    return 0


def _sync_selected_results_from_run(
    *,
    run_dir: Path,
    settings: PlatformSettings,
    max_per_group: int,
) -> int:
    """只读取已有筛选结果并同步飞书，不初始化或调用 LLM。"""

    output_dir = Path(run_dir).resolve()
    try:
        selected = _read_selected_results(output_dir, max_per_group=max_per_group)
        sync_summary = _sync_to_feishu(
            settings=settings,
            selected=selected,
            output_dir=output_dir,
        )
    except (
        FileNotFoundError,
        SecretFileError,
        ValueError,
        RuntimeError,
    ) as exc:
        if output_dir.is_dir():
            _write_json(
                output_dir / "feishu_sync_summary.json",
                _sync_failure_payload(exc),
            )
        _print_line(f"飞书同步失败: {_safe_error_message(exc)}")
        return 2

    if sync_summary.verification_errors:
        _print_line("飞书同步完成但回读核验存在错误")
        return 2
    _print_json(sync_summary.as_dict())
    return 0


def _sync_to_feishu(
    *,
    settings: PlatformSettings,
    selected: Sequence[SelectedRepresentative],
    output_dir: Path,
) -> FeishuSyncSummary:
    """新建本次运行的数据表，将结果写入新表并保存同步审计产物。"""

    feishu_config = FeishuConfig.from_settings(settings)
    app_secret = _read_feishu_secret(settings, feishu_config.app_secret_file)
    rows = tuple(_selected_row(item) for item in selected)
    if not rows:
        raise ValueError("没有可写入的代表性结果，未创建飞书新表")

    table_name = _new_feishu_table_name()
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
        _write_json(output_dir / "feishu_field_mapping.json", prepared.field_mapping.as_dict())
        _write_jsonl(output_dir / "feishu_before_update.jsonl", prepared.before_snapshot)
        sync_summary = feishu.apply(prepared)
    sync_summary = replace(
        sync_summary,
        target_table_id=new_table.table_id,
        target_table_name=new_table.name,
    )
    _write_json(output_dir / "feishu_new_table.json", new_table.as_dict())
    _write_json(output_dir / "feishu_sync_summary.json", sync_summary.as_dict())
    return sync_summary


def _new_feishu_table_name() -> str:
    """返回本次写入新数据表的生成时间名称。"""

    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S.%f%z")


def _create_llm(
    settings: PlatformSettings,
    *,
    max_connections: int,
    audit: LLMRequestAuditWriter,
    environment: Mapping[str, str] | None = None,
) -> tuple[RetryingContentLabelingLLM, OpenAICompatibleContentLabelingLLM]:
    if not settings.llm_base_url or not settings.llm_model:
        raise ValueError("LLM 配置不完整，需要 AIMA_LLM_BASE_URL 和 AIMA_LLM_MODEL")
    api_key = _read_llm_secret(settings, environment=environment)
    raw_llm = OpenAICompatibleContentLabelingLLM(
        base_url=settings.llm_base_url,
        provider_name=settings.llm_provider_name,
        model=settings.llm_model,
        api_key=api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        max_connections=max(max_connections, settings.llm_max_connections),
        pricing_catalog=load_llm_pricing(),
        request_audit=audit.record,
    )
    return RetryingContentLabelingLLM(inner=raw_llm), raw_llm


def _read_llm_secret(
    settings: PlatformSettings,
    *,
    environment: Mapping[str, str] | None = None,
) -> SecretStr:
    secret_path = settings.llm_api_key_file
    if secret_path.exists():
        return read_secret_file(secret_path, root=settings.external_secret_root)
    source = os.environ if environment is None else environment
    value = source.get("AIMA_LLM_API_KEY", "")
    if value.strip():
        return SecretStr(value)
    raise ValueError("未找到 LLM API Key Secret 文件或 AIMA_LLM_API_KEY")


def _load_entrypoint_settings(
    env_file: Path | None,
) -> tuple[PlatformSettings, Mapping[str, str]]:
    """加载入口配置；显式 `.env` 是本地离线入口的配置来源。"""

    selected_file = env_file.resolve() if env_file is not None else DEFAULT_ENV_FILE
    file_values: dict[str, str] = {}
    if selected_file.is_file():
        file_values = _read_env_file(selected_file)
    elif env_file is not None:
        raise FileNotFoundError(f"配置文件不存在: {selected_file}")

    merged = dict(file_values)
    merged.update(os.environ)
    return load_settings(environ=merged), merged


def _read_env_file(path: Path) -> dict[str, str]:
    """读取简单 KEY=VALUE 配置，不执行变量插值或 Shell 命令。"""

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if "=" not in line:
            raise ValueError(f"{path}: 第 {line_number} 行不是 KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "A").isalnum() or key[0].isdigit():
            raise ValueError(f"{path}: 第 {line_number} 行包含非法配置名")
        if key in values:
            raise ValueError(f"{path}: 第 {line_number} 行变量名重复")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _read_feishu_secret(settings: PlatformSettings, secret_ref: str) -> str:
    secret = read_secret_file(
        settings.external_secret_root / secret_ref,
        root=settings.external_secret_root,
    )
    return secret.get_secret_value()


def _read_selected_results(
    run_dir: Path,
    *,
    max_per_group: int,
) -> tuple[SelectedRepresentative, ...]:
    """严格读取 Dry Run 产物，禁止未经校验的 JSONL 进入飞书。"""

    path = Path(run_dir) / "selected_results.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"找不到筛选结果文件: {path}")
    if max_per_group <= 0:
        raise SelectedResultsFileError("max_per_group 必须大于 0")

    selected: list[SelectedRepresentative] = []
    seen_item_nos: set[int] = set()
    seen_keys: set[tuple[str, str, str]] = set()
    group_counts: Counter[str] = Counter()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                raise SelectedResultsFileError(f"第 {line_number} 行为空")
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise SelectedResultsFileError(f"第 {line_number} 行不是合法 JSON") from exc
            if not isinstance(payload, dict) or set(payload) != {"content", "decision"}:
                raise SelectedResultsFileError(f"第 {line_number} 行结构不正确")

            raw_content = payload.get("content")
            raw_decision = payload.get("decision")
            if not isinstance(raw_content, dict):
                raise SelectedResultsFileError(f"第 {line_number} 行 content 结构不正确")
            try:
                content = _content_from_selected_payload(raw_content)
                decision = RepresentativeDecisionModel.model_validate(raw_decision)
            except (TypeError, ValueError, ValidationError) as exc:
                raise SelectedResultsFileError(f"第 {line_number} 行字段校验失败") from exc
            if not decision.eligible or decision.sentiment is None:
                raise SelectedResultsFileError(f"第 {line_number} 行不是可同步的入选结果")
            if content.platform not in _TARGET_PLATFORMS:
                raise SelectedResultsFileError(f"第 {line_number} 行包含非目标平台")
            if decision.item_no in seen_item_nos:
                raise SelectedResultsFileError(f"第 {line_number} 行 item_no 重复")
            seen_item_nos.add(decision.item_no)

            key = (content.platform, decision.sentiment, content.content_id)
            if key in seen_keys:
                raise SelectedResultsFileError(f"第 {line_number} 行 Upsert 键重复")
            seen_keys.add(key)
            group = f"{content.platform}/{decision.sentiment}"
            group_counts[group] += 1
            if group_counts[group] > max_per_group:
                raise SelectedResultsFileError(f"第 {line_number} 行超过单组数量上限")
            selected.append(
                SelectedRepresentative(
                    candidate=RepresentativeCandidate(
                        item_no=decision.item_no,
                        content=content,
                    ),
                    decision=decision,
                )
            )
    return tuple(selected)


def _content_from_selected_payload(payload: Mapping[str, object]) -> LabeledContent:
    """将本程序生成的 content JSON 恢复为只读的原始内容模型。"""

    if frozenset(payload) != _SELECTED_CONTENT_FIELDS:
        raise ValueError("content 字段集合不正确")
    row_number = payload.get("row_number")
    if isinstance(row_number, bool) or not isinstance(row_number, int) or row_number < 1:
        raise ValueError("row_number 必须是正整数")
    return LabeledContent(
        row_number=row_number,
        platform=_selected_text(payload, "platform"),
        content_id=_selected_text(payload, "content_id"),
        title=_selected_text(payload, "title"),
        text=_selected_text(payload, "text"),
        author=_selected_text(payload, "author"),
        published_at=_selected_text(payload, "published_at"),
        content_url=_selected_text(payload, "content_url"),
        voice_type=_selected_text(payload, "voice_type"),
        sentiment_label=_selected_text(payload, "sentiment_label"),
    )


def _selected_text(payload: Mapping[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是字符串")
    return value


def _resolve_run_dir(input_path: Path, requested: Path | None) -> Path:
    if requested is not None:
        return requested.resolve()
    timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f%z")
    return input_path.parent / f"representative_selection_{timestamp}"


def _content_payload(candidate: RepresentativeCandidate) -> dict[str, object]:
    content = candidate.content
    return {
        "row_number": content.row_number,
        "platform": content.platform,
        "content_id": content.content_id,
        "title": content.title,
        "text": content.text,
        "author": content.author,
        "published_at": content.published_at,
        "content_url": content.content_url,
        "voice_type": content.voice_type,
        "sentiment_label": content.sentiment_label,
    }


def _outcome_payload(outcome: RepresentativeDecisionOutcome) -> dict[str, object]:
    return {
        "item_no": outcome.candidate.item_no,
        "content": _content_payload(outcome.candidate),
        "status": outcome.status,
        "attempts": outcome.attempts,
        "validation_error_codes": list(outcome.validation_error_codes),
        "decision": outcome.decision.model_dump() if outcome.decision is not None else None,
    }


def _selected_row(item: SelectedRepresentative) -> dict[str, object]:
    content = item.candidate.content
    decision = item.decision
    if decision.sentiment is None:
        raise ValueError("最终选择缺少情感")
    return {
        "声音内容/连接": _content_reference(content),
        "典型评论示例": content.text,
        "来源": content.platform,
        "发布时间": content.published_at,
        "一级标签": _primary_tag(decision.theme),
        "用户情绪": decision.sentiment,
    }


def _content_reference(content: LabeledContent) -> str:
    """将标题和原文链接合并到目标表的内容/连接字段。"""

    title = content.title.strip()
    link = content.content_url.strip()
    fallback = link or content.content_id
    if not title:
        return fallback
    return f"{title}\n{fallback}" if fallback else title


def _primary_tag(theme: str) -> str | None:
    """将模型主题收敛到目标表已有的一级标签选项。"""

    if any(token in theme for token in ("电池", "续航", "充电", "电量")):
        return "电池、续航与充电"
    if any(token in theme for token in ("售后", "门店服务", "收费", "假冒", "欺诈")):
        return "售后服务"
    if any(token in theme for token in ("外观", "颜色", "配色")):
        return "外观设计"
    if any(token in theme for token in ("性价比", "价格", "价值")):
        return "价格与价值"
    if any(token in theme for token in ("购车", "购买")):
        return "销售与购买体验"
    if any(token in theme for token in ("智能", "APP", "功能")):
        return "智能化与电子功能"
    if any(token in theme for token in ("质量", "耐用", "零部件", "轮胎", "电机")):
        return "耐用性与质量"
    if any(token in theme for token in ("骑行", "操控", "动力")):
        return "骑行性能"
    return None


def _selection_summary(
    *,
    input_paths: Sequence[Path],
    read_summary: LabeledContentReadSummary,
    candidate_summary: CandidatePoolSummary,
    selection_run: RepresentativeSelectionRun,
    output_dir: Path,
    mode: str,
) -> dict[str, object]:
    counts = Counter(
        f"{item.candidate.content.platform}/{item.decision.sentiment}"
        for item in selection_run.selected
        if item.decision.sentiment is not None
    )
    insufficient = {
        group: arguments_count
        for group, arguments_count in {
            "抖音/正面": counts.get("抖音/正面", 0),
            "抖音/负面": counts.get("抖音/负面", 0),
            "小红书/正面": counts.get("小红书/正面", 0),
            "小红书/负面": counts.get("小红书/负面", 0),
        }.items()
        if arguments_count < 10
    }
    audit_summary = None
    audit_path = output_dir / "llm_requests.jsonl"
    if audit_path.exists():
        audit_summary = {"path": str(audit_path)}
    return {
        "mode": mode,
        "input": {
            "path": str(input_paths[0]),
            "paths": [str(path) for path in input_paths],
            "sheet": read_summary.sheet_name,
        },
        "read": {
            "rows_seen": read_summary.rows_seen,
            "rows_read": read_summary.rows_read,
            "duplicate_rows": read_summary.duplicate_rows,
            "blank_rows": read_summary.blank_rows,
        },
        "candidate_pool": {
            "total_rows": candidate_summary.total_rows,
            "target_platform_rows": candidate_summary.target_platform_rows,
            "real_user_rows": candidate_summary.real_user_rows,
            "candidates": candidate_summary.candidates,
            "excluded_non_target": candidate_summary.excluded_non_target,
            "excluded_non_user": candidate_summary.excluded_non_user,
            "excluded_non_sentiment": candidate_summary.excluded_non_sentiment,
            "excluded_missing_evidence": candidate_summary.excluded_missing_evidence,
        },
        "prompt": {"path": str(selection_run.prompt.path), "sha256": selection_run.prompt.sha256},
        "llm": {
            "provider": selection_run.provider_name,
            "model": selection_run.model_name,
            "audit": audit_summary,
        },
        "selected_counts": dict(counts),
        "insufficient_groups": insufficient,
        "group_selection": [
            {
                "platform": audit.platform,
                "sentiment": audit.sentiment,
                "pool_size": audit.pool_size,
                "selected_count": audit.selected_count,
                "used_model": audit.used_model,
                "error_codes": list(audit.error_codes),
            }
            for audit in selection_run.group_audits
        ],
    }


def _safe_error_code(exc: Exception) -> str:
    if isinstance(exc, SelectedResultsFileError):
        return "selected_results_invalid"
    if isinstance(exc, FeishuConfigError):
        return "feishu_config_incomplete"
    if isinstance(exc, FeishuSyncError):
        return "feishu_sync_error"
    return type(exc).__name__.lower()


def _sync_failure_payload(exc: Exception) -> dict[str, object]:
    """生成不包含 Secret 或第三方响应正文的同步失败摘要。"""

    payload: dict[str, object] = {"status": "failed", "error_code": _safe_error_code(exc)}
    if isinstance(exc, FeishuConfigError):
        payload["missing"] = list(exc.missing)
    elif isinstance(exc, FeishuSyncError):
        payload["detail"] = str(exc)
    return payload


def _safe_error_message(exc: Exception) -> str:
    """返回可展示的安全错误摘要；只暴露非敏感配置名。"""

    if isinstance(exc, FeishuConfigError):
        return f"{_safe_error_code(exc)}（缺少: {', '.join(exc.missing)}）"
    if isinstance(exc, FeishuSyncError):
        return f"{_safe_error_code(exc)}（{exc}）"
    return _safe_error_code(exc)


def _write_json(path: Path, payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"
    path.write_text(serialized, encoding="utf-8")


def _print_json(payload: object) -> None:
    """打印 JSON；Windows 非 UTF-8 控制台回退为 ASCII 转义，避免误报失败。"""

    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def _print_line(message: str) -> None:
    """打印单行消息；控制台不支持中文时回退为安全转义文本。"""

    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", errors="backslashreplace").decode("ascii"))


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str))
            handle.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
