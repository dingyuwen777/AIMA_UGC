"""Provider-neutral 舆情多标签分析 Service、Port、Fake 与本地 Validator。"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Protocol, cast
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
    previous_validation_error_codes: tuple[str, ...] = ()
    logical_request_id: str | None = None

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


class _ModelLabelItemV3(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    item_no: int = Field(ge=1)
    relevance: Literal["relevant", "irrelevant"]
    voice_type: ContentVoiceType
    sentiment: str | None = None
    labels: list[_ModelLabelPair] = Field(default_factory=list)


def _parse_model_label_item(
    value: dict[str, Any],
) -> tuple[str, ContentVoiceType, str | None, tuple[ContentLabelPairV2, ...]]:
    parsed = _ModelLabelItemV3.model_validate(value)
    return (
        parsed.relevance,
        parsed.voice_type,
        parsed.sentiment,
        tuple(
            ContentLabelPairV2(
                primary_label=pair.primary_label,
                secondary_label=pair.secondary_label,
            )
            for pair in parsed.labels
        ),
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

    def validate_response(
        self,
        raw_text: str,
        *,
        expected_item_nos: Sequence[int],
    ) -> _ValidationResult:
        """严格校验固定输出结构，并保留同批中已经合法的 item。"""

        expected = tuple(expected_item_nos)
        expected_set = set(expected)
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
                relevance, voice_type, sentiment, label_pairs = _parse_model_label_item(
                    candidates[0]
                )
            except ValidationError:
                item_errors[item_no] = ("invalid_item_structure",)
                aggregate_errors.append("invalid_item_structure")
                continue

            shape_errors: list[str] = []
            try:
                self.validate_voice_type(voice_type=voice_type)
            except ContentLabelingValidationError as exc:
                shape_errors.extend(exc.error_codes)

            if relevance == "relevant":
                if sentiment is None:
                    shape_errors.append("relevant_missing_sentiment")
                if not label_pairs:
                    shape_errors.append("relevant_missing_labels")
                if sentiment is not None and label_pairs:
                    try:
                        self.validate_label_pairs(
                            sentiment=sentiment,
                            labels=label_pairs,
                        )
                    except ContentLabelingValidationError as exc:
                        shape_errors.extend(exc.error_codes)
            else:
                if sentiment is not None:
                    shape_errors.append("irrelevant_has_sentiment")
                if label_pairs:
                    shape_errors.append("irrelevant_has_labels")
            if shape_errors:
                codes = _unique_error_codes(shape_errors)
                item_errors[item_no] = codes
                aggregate_errors.extend(codes)
                continue

            valid_items[item_no] = _ValidatedLabel(
                relevance=cast(Literal["relevant", "irrelevant"], relevance),
                voice_type=voice_type,
                sentiment=sentiment,
                labels=label_pairs,
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
        previous_errors: tuple[str, ...] = ()

        total_requests = max_validation_retries + 1
        for attempt_no in range(1, total_requests + 1):
            if not unresolved:
                break

            request = ContentLabelingLLMRequest(
                prompt=taxonomy.prompt_text,
                items=tuple(unresolved.values()),
                previous_validation_error_codes=previous_errors,
                logical_request_id=uuid4().hex,
            )
            started_at = beijing_now()
            response = self._llm.complete(request)
            completed_at = beijing_now()

            validation = validator.validate_response(
                response.raw_text,
                expected_item_nos=tuple(unresolved),
            )
            attempts.append(
                ContentLabelingAttempt(
                    attempt_no=attempt_no,
                    item_nos=tuple(unresolved),
                    validation_error_codes=validation.error_codes,
                    model_provider=self._llm.provider_name,
                    model=self._llm.model_name,
                    prompt_sha256=taxonomy.prompt_sha256,
                    taxonomy_sha256=taxonomy.taxonomy_sha256,
                    started_at=started_at,
                    completed_at=completed_at,
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

            previous_errors = validation.error_codes

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
                    validation_error_codes=latest_errors.get(
                        item.item_no,
                        previous_errors or ("validation_failed",),
                    ),
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
