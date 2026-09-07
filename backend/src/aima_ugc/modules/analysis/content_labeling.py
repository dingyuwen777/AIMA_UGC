"""Provider-neutral 舆情多标签分析 Service、Port、Fake 与本地 Validator。"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from threading import Event
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aima_ugc.contracts.analysis import (
    ContentLabelAnalysis,
    ContentLabelAnalysisV3,
    ContentLabelPairV2,
    ContentVoiceType,
)
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.platform.time import beijing_now

from .persistence import AnalysisConfigurationIdentity
from .prompt_taxonomy import (
    CONTENT_LABELING_PROMPT_PATH,
    PROMPT_VERSION,
    PromptTaxonomy,
    PromptTaxonomyError,
    PromptTaxonomyLoader,
)

ContentLabelingRequestKind = Literal["primary", "repair", "judge"]
_JUDGE_ERROR_CODES = frozenset(
    {
        "decision_needs_judge",
        "fabricated_evidence",
        "missing_evidence",
        "voice_type_semantic_conflict",
    }
)


class ContentLabelingStopped(RuntimeError):
    """执行已停止，不能再发送模型请求；不属于内容分类失败。"""


def ensure_labeling_running(stop_event: Event | None) -> None:
    """在每次发送或重试前检查同一次执行共享的停止信号。"""

    if stop_event is not None and stop_event.is_set():
        raise ContentLabelingStopped("Analysis 执行已停止")


class ContentLabelingValidationError(ValueError):
    """模型输出未通过固定结构或当前 PromptTaxonomy 校验。"""

    def __init__(self, error_codes: Iterable[str]) -> None:
        codes = _unique_error_codes(error_codes)
        if not codes:
            raise ValueError("ContentLabelingValidationError 至少需要一个错误代码")
        self.error_codes = codes
        super().__init__("模型输出校验失败: " + ", ".join(codes))


@dataclass(frozen=True, slots=True)
class ContentLabelingModelItem:
    """发给模型的一条最小业务输入；item_no 只用于批次配对。"""

    item_no: int
    title: str
    text: str
    author_display_name: str
    author_bio: str
    author_verification_label: str

    def model_payload(self) -> dict[str, object]:
        """生成允许发送给模型的唯一业务字段形状。"""

        return {
            "item_no": self.item_no,
            "title": self.title,
            "text": self.text,
            "author": {
                "display_name": self.author_display_name,
                "bio": self.author_bio,
                "verification_label": self.author_verification_label,
            },
        }


@dataclass(frozen=True, slots=True)
class ContentLabelingLLMRequest:
    """Analysis Service 交给 LLM Adapter 的 Provider-neutral 请求。"""

    prompt: str
    items: tuple[ContentLabelingModelItem, ...]
    request_kind: ContentLabelingRequestKind = "primary"
    previous_validation_error_codes: tuple[str, ...] = ()
    logical_request_id: str | None = None
    stop_event: Event | None = field(default=None, repr=False, compare=False)

    def model_payload(self) -> list[dict[str, object]]:
        """返回批次中只含允许业务字段的 JSON-ready 列表。"""

        return [item.model_payload() for item in self.items]


@dataclass(frozen=True, slots=True)
class ContentLabelingLLMResponse:
    """LLM Adapter 返回的原始文本及可获得的计费元数据。"""

    raw_text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    input_cache_hit_tokens: int | None = None
    input_cache_miss_tokens: int | None = None
    cost_amount: Decimal | None = None
    cost_currency: str | None = None
    pricing_snapshot_sha256: str | None = None
    pricing_source_url: str | None = None


class ContentLabelingLLMPort(Protocol):
    """P1E LLM Port；真实 OpenAI-compatible Adapter 在 P1F 实现。"""

    @property
    def provider_name(self) -> str:
        """返回稳定模型 Provider 名称。"""
        ...

    @property
    def model_name(self) -> str:
        """返回模型名称。"""
        ...

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        """执行恰好一次模型调用；Transport Retry 不属于 Validation Retry。"""
        ...


@dataclass(frozen=True, slots=True)
class ContentLabelingAttempt:
    """一次独立模型 Validation Attempt 的可观察事实。"""

    attempt_no: int
    item_nos: tuple[int, ...]
    validation_error_codes: tuple[str, ...]
    model_provider: str
    model: str
    prompt_sha256: str
    taxonomy_sha256: str
    started_at: datetime
    completed_at: datetime
    request_kind: ContentLabelingRequestKind = "primary"
    logical_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    input_cache_hit_tokens: int | None = None
    input_cache_miss_tokens: int | None = None
    cost_amount: Decimal | None = None
    cost_currency: str | None = None
    pricing_snapshot_sha256: str | None = None
    pricing_source_url: str | None = None


@dataclass(frozen=True, slots=True)
class ContentLabelingItemResult:
    """单条内容在当前 Service 调用中的成功或失败结果。"""

    item_no: int
    input_hash: str
    analysis_status: Literal["succeeded", "failed"]
    analysis: ContentLabelAnalysis | None
    validation_error_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContentLabelingBatchResult:
    """批次结果及全部 Validation Attempt。"""

    items: tuple[ContentLabelingItemResult, ...]
    attempts: tuple[ContentLabelingAttempt, ...]


class _ModelLabelPair(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    primary_label: str = Field(min_length=1)
    secondary_label: str = Field(min_length=1)


class _ModelEvidenceLabelPair(_ModelLabelPair):
    evidence: list[str] = Field(min_length=1)


class _ModelLabelItemV3(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    item_no: int = Field(ge=1)
    relevance: Literal["relevant", "irrelevant"]
    voice_type: ContentVoiceType
    sentiment: str | None = None
    labels: list[_ModelLabelPair] = Field(default_factory=list)


class _ModelLabelItemV4(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    item_no: int = Field(ge=1)
    relevance: Literal["relevant", "irrelevant"]
    relevance_evidence: list[str] = Field(min_length=1)
    source_type: str = Field(min_length=1)
    content_intent: str = Field(min_length=1)
    voice_type: ContentVoiceType
    voice_evidence: list[str] = Field(default_factory=list)
    sentiment: str | None = None
    sentiment_evidence: list[str] = Field(default_factory=list)
    labels: list[_ModelEvidenceLabelPair] = Field(default_factory=list)
    decision_status: Literal["clear", "needs_judge"]


@dataclass(frozen=True, slots=True)
class _ParsedModelLabel:
    relevance: Literal["relevant", "irrelevant"]
    relevance_evidence: tuple[str, ...]
    source_type: str | None
    content_intent: str | None
    voice_type: ContentVoiceType
    voice_evidence: tuple[str, ...]
    sentiment: str | None
    sentiment_evidence: tuple[str, ...]
    labels: tuple[ContentLabelPairV2, ...]
    label_evidence: tuple[tuple[str, ...], ...]
    decision_status: Literal["clear", "needs_judge"] | None


def _parse_model_label_item_v3(
    value: dict[str, Any],
) -> _ParsedModelLabel:
    parsed = _ModelLabelItemV3.model_validate(value)
    return _ParsedModelLabel(
        relevance=parsed.relevance,
        relevance_evidence=(),
        source_type=None,
        content_intent=None,
        voice_type=parsed.voice_type,
        voice_evidence=(),
        sentiment=parsed.sentiment,
        sentiment_evidence=(),
        labels=tuple(
            ContentLabelPairV2(
                primary_label=pair.primary_label,
                secondary_label=pair.secondary_label,
            )
            for pair in parsed.labels
        ),
        label_evidence=tuple(() for _ in parsed.labels),
        decision_status=None,
    )


def _parse_model_label_item_v4(value: dict[str, Any]) -> _ParsedModelLabel:
    parsed = _ModelLabelItemV4.model_validate(value)
    return _ParsedModelLabel(
        relevance=parsed.relevance,
        relevance_evidence=tuple(parsed.relevance_evidence),
        source_type=parsed.source_type,
        content_intent=parsed.content_intent,
        voice_type=parsed.voice_type,
        voice_evidence=tuple(parsed.voice_evidence),
        sentiment=parsed.sentiment,
        sentiment_evidence=tuple(parsed.sentiment_evidence),
        labels=tuple(
            ContentLabelPairV2(
                primary_label=pair.primary_label,
                secondary_label=pair.secondary_label,
            )
            for pair in parsed.labels
        ),
        label_evidence=tuple(tuple(pair.evidence) for pair in parsed.labels),
        decision_status=parsed.decision_status,
    )


@dataclass(frozen=True, slots=True)
class _ValidatedLabel:
    relevance: Literal["relevant", "irrelevant"]
    voice_type: ContentVoiceType
    sentiment: str | None
    labels: tuple[ContentLabelPairV2, ...]


@dataclass(frozen=True, slots=True)
class _ValidationResult:
    valid_items: dict[int, _ValidatedLabel]
    item_errors: dict[int, tuple[str, ...]]
    error_codes: tuple[str, ...]


class RuntimeTaxonomyValidator:
    """用当前 PromptTaxonomy 做模型分类 membership 与标签父子关系校验。"""

    def __init__(self, taxonomy: PromptTaxonomy) -> None:
        self._taxonomy = taxonomy

    def validate_voice_type(self, *, voice_type: str) -> None:
        """严格校验发声类型属于当前 Prompt Taxonomy，不猜测或兼容未知值。"""

        if voice_type not in self._taxonomy.voice_types:
            raise ContentLabelingValidationError(["unknown_voice_type"])

    def validate_labels(
        self,
        *,
        sentiment: str,
        primary_label: str,
        secondary_label: str,
    ) -> None:
        """严格校验三个标签；不做模糊匹配、近义词替换或猜测。"""

        errors: list[str] = []
        if sentiment not in self._taxonomy.sentiments:
            errors.append("unknown_sentiment")
        if primary_label not in self._taxonomy.labels:
            errors.append("unknown_primary_label")
        elif secondary_label not in self._taxonomy.labels[primary_label]:
            errors.append("invalid_secondary_for_primary")
        if errors:
            raise ContentLabelingValidationError(errors)

    def validate_label_pairs(
        self,
        *,
        sentiment: str,
        labels: tuple[ContentLabelPairV2, ...],
    ) -> None:
        """校验一个情感和多个标签对；不去重、不猜测、不模糊匹配。"""

        errors: list[str] = []
        if sentiment not in self._taxonomy.sentiments:
            errors.append("unknown_sentiment")
        seen: set[tuple[str, str]] = set()
        for pair in labels:
            key = (pair.primary_label, pair.secondary_label)
            if key in seen:
                errors.append("duplicate_label_pair")
            seen.add(key)
            if pair.primary_label not in self._taxonomy.labels:
                errors.append("unknown_primary_label")
            elif pair.secondary_label not in self._taxonomy.labels[pair.primary_label]:
                errors.append("invalid_secondary_for_primary")
        if errors:
            raise ContentLabelingValidationError(errors)

    @staticmethod
    def _evidence_errors(
        evidence: tuple[str, ...],
        *,
        item: ContentLabelingModelItem,
        required: bool,
    ) -> tuple[str, ...]:
        """确认模型证据逐项来自五个输入字段，不做关键词分类。"""

        errors: list[str] = []
        if required and not evidence:
            errors.append("missing_evidence")
        source_texts = (
            item.title,
            item.text,
            item.author_display_name,
            item.author_bio,
            item.author_verification_label,
        )
        seen: set[str] = set()
        for fragment in evidence:
            if fragment in seen:
                errors.append("duplicate_evidence")
            seen.add(fragment)
            if (
                not fragment
                or fragment != fragment.strip()
                or not any(fragment in source_text for source_text in source_texts)
            ):
                errors.append("fabricated_evidence")
        return _unique_error_codes(errors)

    def _v4_semantic_errors(
        self,
        parsed: _ParsedModelLabel,
        *,
        item: ContentLabelingModelItem,
    ) -> tuple[str, ...]:
        """校验 V4 主体、意图、证据和发声类型之间的确定性一致性。"""

        rules = self._taxonomy.semantic_rules
        if rules is None:
            return ("missing_semantic_rules",)

        errors: list[str] = []
        errors.extend(self._evidence_errors(parsed.relevance_evidence, item=item, required=True))
        if parsed.source_type not in rules.source_types:
            errors.append("unknown_source_type")
        if parsed.content_intent not in rules.content_intents:
            errors.append("unknown_content_intent")

        derived_voice_type: str | None = None
        if (
            parsed.source_type in rules.source_types
            and parsed.content_intent in rules.content_intents
        ):
            derived_voice_type = rules.derive_voice_type(
                source_type=parsed.source_type,
                content_intent=parsed.content_intent,
            )
            if parsed.voice_type != derived_voice_type:
                errors.append("voice_type_semantic_conflict")
        errors.extend(
            self._evidence_errors(
                parsed.voice_evidence,
                item=item,
                required=derived_voice_type != rules.unknown_voice_type,
            )
        )

        if parsed.relevance == "relevant":
            errors.extend(
                self._evidence_errors(
                    parsed.sentiment_evidence,
                    item=item,
                    required=True,
                )
            )
            for label_evidence in parsed.label_evidence:
                errors.extend(self._evidence_errors(label_evidence, item=item, required=True))
        elif parsed.sentiment_evidence:
            errors.append("irrelevant_has_sentiment_evidence")

        if parsed.decision_status == "needs_judge":
            errors.append("decision_needs_judge")
        return _unique_error_codes(errors)

    def validate_response(
        self,
        raw_text: str,
        *,
        expected_item_nos: Sequence[int],
        expected_items: Sequence[ContentLabelingModelItem] = (),
    ) -> _ValidationResult:
        """严格校验固定输出结构，并保留同批中已经合法的 item。"""

        expected = tuple(expected_item_nos)
        expected_set = set(expected)
        validation_inputs = {item.item_no: item for item in expected_items}
        if self._taxonomy.output_protocol_version == "content-labeling.v4" and (
            tuple(validation_inputs) != expected
        ):
            return _all_invalid(expected, "missing_validation_input")
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return _all_invalid(expected, "invalid_json")

        if not isinstance(payload, dict) or set(payload) != {"items"}:
            return _all_invalid(expected, "invalid_response_structure")
        raw_items = payload["items"]
        if not isinstance(raw_items, list):
            return _all_invalid(expected, "invalid_response_structure")

        by_item_no: dict[int, list[dict[str, Any]]] = {}
        structural_errors: list[str] = []
        returned_order: list[int] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                structural_errors.append("invalid_item_structure")
                continue
            raw_item_no = raw_item.get("item_no")
            if isinstance(raw_item_no, bool) or not isinstance(raw_item_no, int):
                structural_errors.append("invalid_item_no")
                continue
            returned_order.append(raw_item_no)
            if raw_item_no not in expected_set:
                structural_errors.append("unexpected_item_no")
                continue
            by_item_no.setdefault(raw_item_no, []).append(raw_item)

        if structural_errors:
            return _all_invalid(expected, *structural_errors)

        present_unique_order = tuple(dict.fromkeys(returned_order))
        expected_present_order = tuple(item_no for item_no in expected if item_no in by_item_no)
        if present_unique_order != expected_present_order:
            return _all_invalid(expected, "item_order_mismatch")

        valid_items: dict[int, _ValidatedLabel] = {}
        item_errors: dict[int, tuple[str, ...]] = {}
        aggregate_errors: list[str] = []

        for item_no in expected:
            candidates = by_item_no.get(item_no)
            if candidates is None:
                item_errors[item_no] = ("missing_item",)
                aggregate_errors.append("missing_item")
                continue
            if len(candidates) != 1:
                item_errors[item_no] = ("duplicate_item",)
                aggregate_errors.append("duplicate_item")
                continue

            try:
                if self._taxonomy.output_protocol_version == "content-labeling.v4":
                    parsed = _parse_model_label_item_v4(candidates[0])
                else:
                    parsed = _parse_model_label_item_v3(candidates[0])
            except ValidationError:
                item_errors[item_no] = ("invalid_item_structure",)
                aggregate_errors.append("invalid_item_structure")
                continue

            shape_errors: list[str] = []
            try:
                self.validate_voice_type(voice_type=parsed.voice_type)
            except ContentLabelingValidationError as exc:
                shape_errors.extend(exc.error_codes)

            if parsed.relevance == "relevant":
                if parsed.sentiment is None:
                    shape_errors.append("relevant_missing_sentiment")
                if not parsed.labels:
                    shape_errors.append("relevant_missing_labels")
                if parsed.sentiment is not None and parsed.labels:
                    try:
                        self.validate_label_pairs(
                            sentiment=parsed.sentiment,
                            labels=parsed.labels,
                        )
                    except ContentLabelingValidationError as exc:
                        shape_errors.extend(exc.error_codes)
            else:
                if parsed.sentiment is not None:
                    shape_errors.append("irrelevant_has_sentiment")
                if parsed.labels:
                    shape_errors.append("irrelevant_has_labels")
            if self._taxonomy.output_protocol_version == "content-labeling.v4":
                shape_errors.extend(
                    self._v4_semantic_errors(
                        parsed,
                        item=validation_inputs[item_no],
                    )
                )
            if shape_errors:
                codes = _unique_error_codes(shape_errors)
                item_errors[item_no] = codes
                aggregate_errors.extend(codes)
                continue

            valid_items[item_no] = _ValidatedLabel(
                relevance=parsed.relevance,
                voice_type=parsed.voice_type,
                sentiment=parsed.sentiment,
                labels=parsed.labels,
            )

        return _ValidationResult(
            valid_items=valid_items,
            item_errors=item_errors,
            error_codes=_unique_error_codes(aggregate_errors),
        )


class FakeContentLabelingLLM:
    """无网络、无费用的确定性 P1E Fake；只复用正式 Service/Validator。"""

    def __init__(
        self,
        *,
        responses: Sequence[str | ContentLabelingLLMResponse],
        provider_name: str = "fake",
        model_name: str = "fake-content-labeler-v1",
    ) -> None:
        self._responses = list(responses)
        self._provider_name = provider_name
        self._model_name = model_name
        self.calls: list[ContentLabelingLLMRequest] = []

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def complete(self, request: ContentLabelingLLMRequest) -> ContentLabelingLLMResponse:
        self.calls.append(request)
        if not self._responses:
            raise RuntimeError("FakeContentLabelingLLM 没有剩余响应")
        response = self._responses.pop(0)
        if isinstance(response, ContentLabelingLLMResponse):
            return response
        return ContentLabelingLLMResponse(raw_text=response)


class ContentLabelingService:
    """使用唯一 PromptTaxonomy 和 LLM Port 执行严格多标签分析。"""

    def __init__(
        self,
        *,
        prompt_loader: PromptTaxonomyLoader,
        llm: ContentLabelingLLMPort,
    ) -> None:
        self._prompt_loader = prompt_loader
        self._llm = llm

    @property
    def provider_name(self) -> str:
        """返回当前 Service 实际使用的 LLM Provider 身份。"""

        return self._llm.provider_name

    @property
    def model_name(self) -> str:
        """返回当前 Service 实际使用的模型身份。"""

        return self._llm.model_name

    @property
    def configuration_identity(self) -> AnalysisConfigurationIdentity:
        """返回本次执行实际使用的 Prompt、Taxonomy 与模型身份。"""

        taxonomy = self._prompt_loader.load()
        return AnalysisConfigurationIdentity(
            prompt_version=taxonomy.prompt_version,
            prompt_sha256=taxonomy.prompt_sha256,
            taxonomy_sha256=taxonomy.taxonomy_sha256,
            model_provider=self._llm.provider_name,
            model=self._llm.model_name,
        )

    def label_contents(
        self,
        contents: Sequence[CanonicalContentV1],
        *,
        max_validation_retries: int,
        stop_event: Event | None = None,
    ) -> ContentLabelingBatchResult:
        """分析一个批次；Validation Retry 只重新请求当前尚未成功的 item。"""

        if (
            isinstance(max_validation_retries, bool)
            or not isinstance(max_validation_retries, int)
            or max_validation_retries < 0
        ):
            raise ValueError("max_validation_retries 必须是大于等于 0 的整数")

        taxonomy = self._prompt_loader.load()
        validator = RuntimeTaxonomyValidator(taxonomy)
        model_items = tuple(
            _to_model_item(content, item_no=index)
            for index, content in enumerate(contents, start=1)
        )
        if not model_items:
            return ContentLabelingBatchResult(items=(), attempts=())

        input_hashes = {item.item_no: _input_hash(item) for item in model_items}
        unresolved: OrderedDict[int, ContentLabelingModelItem] = OrderedDict(
            (item.item_no, item) for item in model_items
        )
        successful: dict[int, ContentLabelAnalysis] = {}
        latest_errors: dict[int, tuple[str, ...]] = {}
        attempts: list[ContentLabelingAttempt] = []

        total_rounds = max_validation_retries + 1
        for retry_round in range(total_rounds):
            if not unresolved:
                break
            request_groups: tuple[
                tuple[ContentLabelingRequestKind, tuple[ContentLabelingModelItem, ...]], ...
            ]
            if retry_round == 0:
                request_groups = (("primary", tuple(unresolved.values())),)
            else:
                repair_items: list[ContentLabelingModelItem] = []
                judge_items: list[ContentLabelingModelItem] = []
                for item_no, item in unresolved.items():
                    target = (
                        judge_items
                        if _JUDGE_ERROR_CODES.intersection(latest_errors.get(item_no, ()))
                        else repair_items
                    )
                    target.append(item)
                grouped_retries: list[
                    tuple[ContentLabelingRequestKind, tuple[ContentLabelingModelItem, ...]]
                ] = []
                if repair_items:
                    grouped_retries.append(("repair", tuple(repair_items)))
                if judge_items:
                    grouped_retries.append(("judge", tuple(judge_items)))
                request_groups = tuple(grouped_retries)

            for request_kind, request_items in request_groups:
                ensure_labeling_running(stop_event)
                request_item_nos = tuple(item.item_no for item in request_items)
                previous_errors = _unique_error_codes(
                    error_code
                    for item_no in request_item_nos
                    for error_code in latest_errors.get(item_no, ())
                )
                request = ContentLabelingLLMRequest(
                    prompt=taxonomy.prompt_text,
                    items=request_items,
                    request_kind=request_kind,
                    previous_validation_error_codes=previous_errors,
                    logical_request_id=uuid4().hex,
                    stop_event=stop_event,
                )
                started_at = beijing_now()
                response = self._llm.complete(request)
                completed_at = beijing_now()

                validation = validator.validate_response(
                    response.raw_text,
                    expected_item_nos=request_item_nos,
                    expected_items=request_items,
                )
                attempts.append(
                    ContentLabelingAttempt(
                        attempt_no=len(attempts) + 1,
                        item_nos=request_item_nos,
                        validation_error_codes=validation.error_codes,
                        model_provider=self._llm.provider_name,
                        model=self._llm.model_name,
                        prompt_sha256=taxonomy.prompt_sha256,
                        taxonomy_sha256=taxonomy.taxonomy_sha256,
                        started_at=started_at,
                        completed_at=completed_at,
                        request_kind=request.request_kind,
                        logical_request_id=request.logical_request_id,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        input_cache_hit_tokens=response.input_cache_hit_tokens,
                        input_cache_miss_tokens=response.input_cache_miss_tokens,
                        cost_amount=response.cost_amount,
                        cost_currency=response.cost_currency,
                        pricing_snapshot_sha256=response.pricing_snapshot_sha256,
                        pricing_source_url=response.pricing_source_url,
                    )
                )

                for item_no, validated in validation.valid_items.items():
                    successful[item_no] = ContentLabelAnalysisV3(
                        relevance=validated.relevance,
                        voice_type=validated.voice_type,
                        sentiment=validated.sentiment,
                        labels=validated.labels,
                        prompt_version=taxonomy.prompt_version,
                        prompt_sha256=taxonomy.prompt_sha256,
                        taxonomy_sha256=taxonomy.taxonomy_sha256,
                        model_provider=self._llm.provider_name,
                        model=self._llm.model_name,
                        input_hash=input_hashes[item_no],
                        analyzed_at=completed_at,
                    )
                    unresolved.pop(item_no, None)
                    latest_errors.pop(item_no, None)

                for item_no, error_codes in validation.item_errors.items():
                    if item_no in unresolved:
                        latest_errors[item_no] = error_codes

        item_results: list[ContentLabelingItemResult] = []
        for item in model_items:
            analysis = successful.get(item.item_no)
            if analysis is not None:
                item_results.append(
                    ContentLabelingItemResult(
                        item_no=item.item_no,
                        input_hash=input_hashes[item.item_no],
                        analysis_status="succeeded",
                        analysis=analysis,
                    )
                )
                continue
            item_results.append(
                ContentLabelingItemResult(
                    item_no=item.item_no,
                    input_hash=input_hashes[item.item_no],
                    analysis_status="failed",
                    analysis=None,
                    validation_error_codes=latest_errors.get(item.item_no, ("validation_failed",)),
                )
            )

        return ContentLabelingBatchResult(
            items=tuple(item_results),
            attempts=tuple(attempts),
        )


def _to_model_item(content: CanonicalContentV1, *, item_no: int) -> ContentLabelingModelItem:
    author_display_name = ""
    author_bio = ""
    author_verification_label = ""
    if content.author is not None:
        author_display_name = content.author.display_name or ""
        author_bio = content.author.bio or ""
        author_verification_label = content.author.verification_label or ""
    return ContentLabelingModelItem(
        item_no=item_no,
        title=content.title or "",
        text=content.text or "",
        author_display_name=author_display_name,
        author_bio=author_bio,
        author_verification_label=author_verification_label,
    )


def _input_hash(item: ContentLabelingModelItem) -> str:
    payload = {
        "title": item.title,
        "text": item.text,
        "author": {
            "display_name": item.author_display_name,
            "bio": item.author_bio,
            "verification_label": item.author_verification_label,
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def content_labeling_input_hash(content: CanonicalContentV1) -> str:
    """返回正式模型输入的稳定 Hash，供持久化幂等与 current 校验复用。"""

    return _input_hash(_to_model_item(content, item_no=1))


def _all_invalid(expected_item_nos: Sequence[int], *error_codes: str) -> _ValidationResult:
    codes = _unique_error_codes(error_codes)
    return _ValidationResult(
        valid_items={},
        item_errors={item_no: codes for item_no in expected_item_nos},
        error_codes=codes,
    )


def _unique_error_codes(error_codes: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(error_codes))


__all__ = [
    "CONTENT_LABELING_PROMPT_PATH",
    "PROMPT_VERSION",
    "ContentLabelingAttempt",
    "ContentLabelingBatchResult",
    "ContentLabelingItemResult",
    "ContentLabelingLLMPort",
    "ContentLabelingLLMRequest",
    "ContentLabelingLLMResponse",
    "ContentLabelingModelItem",
    "ContentLabelingService",
    "ContentLabelingValidationError",
    "content_labeling_input_hash",
    "FakeContentLabelingLLM",
    "PromptTaxonomy",
    "PromptTaxonomyError",
    "PromptTaxonomyLoader",
    "RuntimeTaxonomyValidator",
]
