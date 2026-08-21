"""一次性把当前 Analysis V2 增量迁移到语义相关性 + 发声类型 V3。

仅供 feature/analysis-relevance-voice-type 分支开发使用；完成后删除本文件。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: 期望唯一替换片段，实际 {count}")
    write(path, text.replace(old, new, 1))


def replace_regex_once(path: str, pattern: str, repl: str) -> None:
    text = read(path)
    new, count = re.subn(pattern, repl, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: 正则替换失败: {pattern}")
    write(path, new)


VOICE_TYPES = (
    "user_voice",
    "creator_marketing",
    "brand_official",
    "dealer_promotion",
    "media_information",
    "other_organization",
    "unknown",
)


def patch_analysis_contracts() -> None:
    write(
        "backend/src/aima_ugc/contracts/analysis/content_label.py",
        '''"""Provider-neutral 舆情内容 AI 打标结果契约。"""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256_PATTERN = r"^[0-9a-f]{64}$"

type ContentRelevance = Literal["relevant", "irrelevant"]
type ContentVoiceType = Literal[
    "user_voice",
    "creator_marketing",
    "brand_official",
    "dealer_promotion",
    "media_information",
    "other_organization",
    "unknown",
]


class ContentLabelPairV2(BaseModel):
    """一个经过 Taxonomy 校验的一级/二级标签父子对。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_label: str = Field(min_length=1, max_length=256)
    secondary_label: str = Field(min_length=1, max_length=256)


class ContentLabelAnalysisV1(BaseModel):
    """通过 PromptTaxonomy 与本地 Validator 校验后的单标签分析结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["content-label-analysis.v1"] = "content-label-analysis.v1"
    sentiment: str = Field(min_length=1, max_length=128)
    primary_label: str = Field(min_length=1, max_length=256)
    secondary_label: str = Field(min_length=1, max_length=256)
    prompt_version: str = Field(min_length=1, max_length=256)
    prompt_sha256: str = Field(pattern=_SHA256_PATTERN)
    taxonomy_sha256: str = Field(pattern=_SHA256_PATTERN)
    model_provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=256)
    input_hash: str = Field(pattern=_SHA256_PATTERN)
    analyzed_at: AwareDatetime
    analysis_status: Literal["succeeded"] = "succeeded"


class ContentLabelAnalysisV2(BaseModel):
    """历史多标签成功结果：一个情感 + 一个或多个一级/二级标签对。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["content-label-analysis.v2"] = "content-label-analysis.v2"
    sentiment: str = Field(min_length=1, max_length=128)
    labels: tuple[ContentLabelPairV2, ...] = Field(min_length=1)
    prompt_version: str = Field(min_length=1, max_length=256)
    prompt_sha256: str = Field(pattern=_SHA256_PATTERN)
    taxonomy_sha256: str = Field(pattern=_SHA256_PATTERN)
    model_provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=256)
    input_hash: str = Field(pattern=_SHA256_PATTERN)
    analyzed_at: AwareDatetime
    analysis_status: Literal["succeeded"] = "succeeded"

    @field_validator("labels")
    @classmethod
    def validate_unique_labels(
        cls, value: tuple[ContentLabelPairV2, ...]
    ) -> tuple[ContentLabelPairV2, ...]:
        keys = [(item.primary_label, item.secondary_label) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("labels 不能包含重复一级/二级标签对")
        return value

    @property
    def primary_label(self) -> str:
        """兼容旧只读调用：返回按重要性排序后的第一个一级标签。"""

        return self.labels[0].primary_label

    @property
    def secondary_label(self) -> str:
        """兼容旧只读调用：返回按重要性排序后的第一个二级标签。"""

        return self.labels[0].secondary_label


class ContentLabelAnalysisV3(BaseModel):
    """当前成功分析结果：语义相关性 + 发声类型 + 条件式情感/多标签。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["content-label-analysis.v3"] = "content-label-analysis.v3"
    relevance: ContentRelevance
    voice_type: ContentVoiceType
    sentiment: str | None = Field(default=None, min_length=1, max_length=128)
    labels: tuple[ContentLabelPairV2, ...] = ()
    prompt_version: str = Field(min_length=1, max_length=256)
    prompt_sha256: str = Field(pattern=_SHA256_PATTERN)
    taxonomy_sha256: str = Field(pattern=_SHA256_PATTERN)
    model_provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=256)
    input_hash: str = Field(pattern=_SHA256_PATTERN)
    analyzed_at: AwareDatetime
    analysis_status: Literal["succeeded"] = "succeeded"

    @model_validator(mode="after")
    def validate_relevance_shape(self) -> "ContentLabelAnalysisV3":
        keys = [(item.primary_label, item.secondary_label) for item in self.labels]
        if len(keys) != len(set(keys)):
            raise ValueError("labels 不能包含重复一级/二级标签对")
        if self.relevance == "relevant":
            if self.sentiment is None or not self.labels:
                raise ValueError("relevant 内容必须包含情感和至少一个标签对")
        elif self.sentiment is not None or self.labels:
            raise ValueError("irrelevant 内容不得携带情感或业务标签")
        return self

    @property
    def is_relevant(self) -> bool:
        return self.relevance == "relevant"

    @property
    def is_user_voice(self) -> bool:
        return self.voice_type == "user_voice"

    @property
    def primary_label(self) -> str | None:
        return self.labels[0].primary_label if self.labels else None

    @property
    def secondary_label(self) -> str | None:
        return self.labels[0].secondary_label if self.labels else None
''',
    )
    write(
        "backend/src/aima_ugc/contracts/analysis/content_record.py",
        '''"""Provider-neutral 内容处理记录。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aima_ugc.contracts.canonical import CanonicalContentV1

from .content_label import ContentLabelAnalysisV1, ContentLabelAnalysisV2, ContentLabelAnalysisV3

ContentLabelAnalysis = Annotated[
    ContentLabelAnalysisV1 | ContentLabelAnalysisV2 | ContentLabelAnalysisV3,
    Field(discriminator="schema_version"),
]


class UnifiedContentRecordV1(BaseModel):
    """Canonical 内容、命中关键词及可选的已校验分析结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["content-record.v1"] = "content-record.v1"
    content: CanonicalContentV1
    matched_keywords: list[str] = Field(min_length=1)
    analysis: ContentLabelAnalysis | None = None

    @field_validator("matched_keywords")
    @classmethod
    def validate_matched_keywords(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("matched_keywords 不能包含重复关键词")
        for keyword in value:
            if not keyword or keyword != keyword.strip():
                raise ValueError("matched_keywords 必须是非空且已清洗的字符串")
        return value
''',
    )
    write(
        "backend/src/aima_ugc/contracts/analysis/__init__.py",
        '''"""Provider-neutral 分析与离线处理公共契约。"""

from .content_label import (
    ContentLabelAnalysisV1,
    ContentLabelAnalysisV2,
    ContentLabelAnalysisV3,
    ContentLabelPairV2,
    ContentRelevance,
    ContentVoiceType,
)
from .content_record import ContentLabelAnalysis, UnifiedContentRecordV1
from .relevance import RelevanceSnapshotV1

__all__ = [
    "ContentLabelAnalysis",
    "ContentLabelAnalysisV1",
    "ContentLabelAnalysisV2",
    "ContentLabelAnalysisV3",
    "ContentLabelPairV2",
    "ContentRelevance",
    "ContentVoiceType",
    "RelevanceSnapshotV1",
    "UnifiedContentRecordV1",
]
''',
    )


def patch_prompt() -> None:
    source = read("backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v2.md")
    source = source.replace(
        "# AIMA 内容舆情多标签分析 Prompt V2\n\nPrompt Version：`content-labeling.v2`",
        "# AIMA 内容舆情语义相关性与多标签分析 Prompt V3\n\nPrompt Version：`content-labeling.v3`",
        1,
    )
    source = source.replace(
        "你负责对与爱玛相关的公开内容做舆情多标签分析。必须严格依据本 Prompt 当前版本中的 Taxonomy、判断标准和边界规则判断；不得创造新标签、改写标签名称或输出近义标签。每条内容保留一个整体情感，同时返回所有具有明确、实质语义依据的一级/二级标签对。",
        "你负责对公开内容进行爱玛舆情语义复核与多标签分析。每条内容先判断是否与爱玛具有可用于舆情分析的实质语义关联，再判断内容发声类型；只有相关内容才继续判断情感和一级/二级标签。必须严格依据本 Prompt 当前版本中的规则和 Taxonomy，不得把关键词碰撞当成相关，不得臆测账号真实法律身份，也不得创造或改写标签。",
        1,
    )
    old_input = '''  "author": {
    "display_name": "作者展示名；缺失时为空字符串"
  }
}'''
    new_input = '''  "author": {
    "display_name": "作者展示名；缺失时为空字符串",
    "bio": "作者公开简介；缺失时为空字符串",
    "verification_label": "作者公开认证文案；缺失时为空字符串"
  }
}'''
    if old_input not in source:
        raise RuntimeError("Prompt 输入片段未找到")
    source = source.replace(old_input, new_input, 1)
    source = source.replace(
        "不要要求或推断内容 ID、平台、Provider、URL、互动指标、粉丝数、命中关键词、Raw 定位、源 Excel 情感或其他未提供字段。",
        "不要要求或推断内容 ID、平台、Provider、URL、互动指标、粉丝数、命中关键词、Raw 定位、源 Excel 情感或其他未提供字段。`author` 只提供公开展示名、简介和认证文案；它们只能作为可见证据，不能证明账号真实法律身份或商业合作关系。",
        1,
    )
    source = re.sub(
        r'''```json\n\{\n  "items": \[\n    \{\n      "item_no": 1,\n      "sentiment": "混合",.*?\n\}\n```''',
        '''```json
{
  "items": [
    {
      "item_no": 1,
      "relevance": "relevant",
      "voice_type": "user_voice",
      "sentiment": "混合",
      "labels": [
        {
          "primary_label": "骑行性能",
          "secondary_label": "舒适性"
        },
        {
          "primary_label": "售后服务",
          "secondary_label": "客服与服务态度"
        }
      ]
    }
  ]
}
```''',
        source,
        count=1,
        flags=re.DOTALL,
    )
    source = re.sub(
        r'''要求：\n\n1\. 每个输入 `item_no`.*?10\. 信息不足时情感使用“中性”，但标签仍必须基于可见语义选择至少一个合法标签对。''',
        '''要求：

1. 每个输入 `item_no` 恰好返回一次，顺序与本次请求一致；
2. 每条必须返回 `relevance`，只能是 `relevant` 或 `irrelevant`；
3. 每条必须返回 `voice_type`，只能使用本文定义的 7 个值；
4. `relevance=relevant` 时：必须返回恰好一个合法 `sentiment`，且 `labels` 至少一个合法标签对；
5. `relevance=irrelevant` 时：`sentiment` 必须为 `null`，`labels` 必须为 `[]`，不得为了满足标签格式强行分类；
6. 每个标签对恰好包含 `primary_label` 和 `secondary_label`，不得输出额外字段；
7. 每个标签名称必须使用机器 Taxonomy 中的完整原名，不得输出空字符串、近义词或自造标签；
8. 每个 `secondary_label` 必须属于同一标签对中的 `primary_label`；
9. 同一条相关内容不得返回重复标签对；标签对按重要性排序；
10. 只保留具有明确、实质语义依据的标签，不因轻微联想无限扩展。''',
        source,
        count=1,
        flags=re.DOTALL,
    )
    marker = "## 情感判断标准"
    if source.count(marker) != 1:
        raise RuntimeError("Prompt 情感章节定位失败")
    new_sections = '''## 语义相关性判断标准

先判断 `relevance`，这是关键词粗筛之后的第二层语义复核：

- **relevant**：内容主体对爱玛品牌、爱玛产品/车型、购买与价格、使用体验、质量故障、电池续航、智能功能、销售售后、渠道门店、爱玛营销传播/代言/活动，或与爱玛有明确比较、评价、争议、事件关系，具有可用于舆情分析的实质语义。
- **irrelevant**：仅关键词碰撞、同名实体、标签/热词堆砌、正文主体完全是其他品牌/其他话题且爱玛只是无实质信息的带过、模板尾巴，或从可见文本无法形成任何爱玛舆情含义。

边界规则：

1. 竞品内容只有在明确比较/提及爱玛并形成对爱玛的判断时才算 relevant；
2. “信息少但确实在问/说爱玛”仍是 relevant，不因文本短而删除；
3. 转发、新闻、官方稿、营销稿只要主体确实与爱玛相关，仍是 relevant；相关性和发声类型是两个独立判断；
4. 不得因为作者名里出现“爱玛”就忽略正文语义，也不得因为正文没有重复品牌名就否定标题已明确建立的爱玛语境。

## 内容发声类型判断标准

`voice_type` 判断的是**当前内容的发声属性**，不是对账号真实身份作事实认定。只能使用：

- `user_voice`：普通个人用户的真实体验、使用反馈、购买经历、个人观点、咨询、求助、购买/推荐意愿等非组织化个人表达；不要求必须已购车，但不能有明确组织化推广证据。
- `creator_marketing`：达人/KOL/KOC/博主的商业推广、种草、带货、合作测评、导购式内容，或正文具有明确营销转化目的。
- `brand_official`：爱玛品牌、子品牌、官方账号、品牌工作人员以官方身份发布的品牌传播、活动、产品信息或声明。
- `dealer_promotion`：经销商、门店、销售、加盟商的促销、报价、到店、留资、招商、库存/车型推荐等获客内容。
- `media_information`：媒体、新闻、资讯号、行业号、聚合号的新闻报道、行业信息、转载或编辑内容，主体不是个人使用体验。
- `other_organization`：政府、协会、学校、企业机构等非个人主体的通知、合作或公共事务传播，且不属于品牌官方、经销商或媒体。
- `unknown`：仅凭标题、正文、作者展示名/简介/认证文案无法可靠区分以上类型。

判断优先级与约束：

1. 以正文/标题的表达目的为主，作者公开简介与认证文案只作辅助证据；
2. 不得仅凭昵称、粉丝规模、措辞“像广告”就断言存在商业合作；证据不足用 `unknown`；
3. 普通用户转发活动但同时写了明确个人使用体验，以主要信息量判断；个人体验是主体可判 `user_voice`，纯转发活动信息则按传播主体/内容判断；
4. 达人非商业的真实体验，如果没有可见推广/合作/导购证据，可以判 `user_voice`；不要把“创作者”身份自动等同营销；
5. `is_user_voice` 由系统根据 `voice_type == user_voice` 派生，模型不要额外输出布尔字段。

'''
    source = source.replace(marker, new_sections + marker, 1)
    write("backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md", source)
    replace_once(
        "backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py",
        'PROMPT_VERSION = "content-labeling.v2"\nCONTENT_LABELING_PROMPT_PATH = Path(__file__).with_name("prompts") / "content_labeling_v2.md"',
        'PROMPT_VERSION = "content-labeling.v3"\nCONTENT_LABELING_PROMPT_PATH = Path(__file__).with_name("prompts") / "content_labeling_v3.md"',
    )


def patch_labeling_service() -> None:
    path = "backend/src/aima_ugc/modules/analysis/content_labeling.py"
    replace_once(
        path,
        '''    ContentLabelAnalysisV2,
    ContentLabelPairV2,
)''',
        '''    ContentLabelAnalysisV3,
    ContentLabelPairV2,
    ContentVoiceType,
)''',
    )
    replace_once(
        path,
        '''    author_display_name: str

    def model_payload(self) -> dict[str, object]:''',
        '''    author_display_name: str
    author_bio: str
    author_verification_label: str

    def model_payload(self) -> dict[str, object]:''',
    )
    replace_once(
        path,
        '''            "author": {"display_name": self.author_display_name},''',
        '''            "author": {
                "display_name": self.author_display_name,
                "bio": self.author_bio,
                "verification_label": self.author_verification_label,
            },''',
    )
    replace_regex_once(
        path,
        r'''class _ModelLabelItemV2\(BaseModel\):.*?class _ModelLabelItemV1\(BaseModel\):.*?def _parse_model_label_item\(\n    value: dict\[str, Any\],\n\) -> tuple\[str, tuple\[ContentLabelPairV2, \.\.\.\]\]:.*?\n\n\n@dataclass\(frozen=True, slots=True\)\nclass _ValidatedLabel:\n    sentiment: str\n    labels: tuple\[ContentLabelPairV2, \.\.\.\]''',
        '''class _ModelLabelItemV3(BaseModel):
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
    labels: tuple[ContentLabelPairV2, ...]''',
    )
    old = '''            try:
                sentiment, label_pairs = _parse_model_label_item(candidates[0])
            except ValidationError:
                item_errors[item_no] = ("invalid_item_structure",)
                aggregate_errors.append("invalid_item_structure")
                continue

            try:
                self.validate_label_pairs(sentiment=sentiment, labels=label_pairs)
            except ContentLabelingValidationError as exc:
                item_errors[item_no] = exc.error_codes
                aggregate_errors.extend(exc.error_codes)
                continue

            valid_items[item_no] = _ValidatedLabel(
                sentiment=sentiment,
                labels=label_pairs,
            )'''
    new = '''            try:
                relevance, voice_type, sentiment, label_pairs = _parse_model_label_item(
                    candidates[0]
                )
            except ValidationError:
                item_errors[item_no] = ("invalid_item_structure",)
                aggregate_errors.append("invalid_item_structure")
                continue

            shape_errors: list[str] = []
            if relevance == "relevant":
                if sentiment is None:
                    shape_errors.append("relevant_missing_sentiment")
                if not label_pairs:
                    shape_errors.append("relevant_missing_labels")
                if not shape_errors:
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
                relevance=relevance,
                voice_type=voice_type,
                sentiment=sentiment,
                labels=label_pairs,
            )'''
    replace_once(path, old, new)
    replace_once(
        path,
        '''                successful[item_no] = ContentLabelAnalysisV2(
                    sentiment=validated.sentiment,
                    labels=validated.labels,''',
        '''                successful[item_no] = ContentLabelAnalysisV3(
                    relevance=validated.relevance,
                    voice_type=validated.voice_type,
                    sentiment=validated.sentiment,
                    labels=validated.labels,''',
    )
    replace_once(
        path,
        '''def _to_model_item(content: CanonicalContentV1, *, item_no: int) -> ContentLabelingModelItem:
    author_display_name = ""
    if content.author is not None and content.author.display_name is not None:
        author_display_name = content.author.display_name
    return ContentLabelingModelItem(
        item_no=item_no,
        title=content.title or "",
        text=content.text or "",
        author_display_name=author_display_name,
    )''',
        '''def _to_model_item(content: CanonicalContentV1, *, item_no: int) -> ContentLabelingModelItem:
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
    )''',
    )
    replace_once(
        path,
        '''        "author": {"display_name": item.author_display_name},''',
        '''        "author": {
            "display_name": item.author_display_name,
            "bio": item.author_bio,
            "verification_label": item.author_verification_label,
        },''',
    )


def patch_offline_labeling() -> None:
    path = "backend/src/aima_ugc/modules/analysis/offline_labeling.py"
    replace_once(
        path,
        "from aima_ugc.contracts.analysis import ContentLabelAnalysis, UnifiedContentRecordV1",
        "from aima_ugc.contracts.analysis import (\n    ContentLabelAnalysis,\n    ContentLabelAnalysisV3,\n    UnifiedContentRecordV1,\n)",
    )
    replace_once(
        path,
        '''    rows_failed: int
    llm_attempts: int''',
        '''    rows_failed: int
    llm_attempts: int
    rows_irrelevant_removed: int = 0''',
    )
    replace_once(
        path,
        '''    if rows_recovered or rows_succeeded:
        _rewrite_source_in_original_order(
            source_path,
            checkpoint_index=checkpoint_index,
        )

    return OfflineContentLabelingSummary(''',
        '''    rows_irrelevant_removed = _rewrite_source_in_original_order(
        source_path,
        checkpoint_index=checkpoint_index,
    ) if rows_seen else 0

    return OfflineContentLabelingSummary(''',
    )
    replace_once(
        path,
        '''        llm_attempts=llm_attempts,
        peak_in_flight=peak_in_flight,''',
        '''        llm_attempts=llm_attempts,
        rows_irrelevant_removed=rows_irrelevant_removed,
        peak_in_flight=peak_in_flight,''',
    )
    replace_once(
        path,
        ''') -> None:
    temp_path = source_path.with_name(f".{source_path.name}.labeling.tmp")''',
        ''') -> int:
    temp_path = source_path.with_name(f".{source_path.name}.labeling.tmp")''',
    )
    replace_once(
        path,
        '''    try:
        with (
            source_path.open("rb") as input_file,''',
        '''    removed = 0
    try:
        with (
            source_path.open("rb") as input_file,''',
    )
    replace_once(
        path,
        '''                    if analysis is not None:
                        record = _rewrite_record(record, analysis)
                output_file.write(record.model_dump_json())''',
        '''                    if analysis is not None:
                        record = _rewrite_record(record, analysis)
                if isinstance(record.analysis, ContentLabelAnalysisV3) and not record.analysis.is_relevant:
                    removed += 1
                    continue
                output_file.write(record.model_dump_json())''',
    )
    replace_once(
        path,
        '''        os.replace(temp_path, source_path)
    except BaseException:''',
        '''        os.replace(temp_path, source_path)
        return removed
    except BaseException:''',
    )


def patch_persistence_models_and_tables() -> None:
    write(
        "backend/src/aima_ugc/modules/analysis/persistence.py",
        '''"""Analysis 成功结果的持久化领域模型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aima_ugc.contracts.analysis import ContentLabelAnalysisV3
from aima_ugc.contracts.canonical import CanonicalContentV1


@dataclass(frozen=True, slots=True)
class AnalysisConfigurationIdentity:
    """确定 current Analysis 的当前 Prompt/Taxonomy/Provider/Model 身份。"""

    prompt_version: str
    prompt_sha256: str
    taxonomy_sha256: str
    model_provider: str
    model: str


@dataclass(frozen=True, slots=True)
class AnalysisLabelPair:
    ordinal: int
    primary_label: str
    secondary_label: str


@dataclass(frozen=True, slots=True)
class AnalysisContentResult:
    id: UUID
    content_id: UUID
    content_version: int
    job_id: UUID
    schema_version: str
    relevance: str
    voice_type: str
    sentiment: str | None
    prompt_version: str
    prompt_sha256: str
    taxonomy_sha256: str
    model_provider: str
    model: str
    input_hash: str
    analyzed_at: datetime
    labels: tuple[AnalysisLabelPair, ...]

    @classmethod
    def from_analysis(
        cls,
        *,
        result_id: UUID,
        content_id: UUID,
        content_version: int,
        job_id: UUID,
        analysis: ContentLabelAnalysisV3,
    ) -> AnalysisContentResult:
        if content_version < 1:
            raise ValueError("content_version 必须大于等于 1")
        return cls(
            id=result_id,
            content_id=content_id,
            content_version=content_version,
            job_id=job_id,
            schema_version=analysis.schema_version,
            relevance=analysis.relevance,
            voice_type=analysis.voice_type,
            sentiment=analysis.sentiment,
            prompt_version=analysis.prompt_version,
            prompt_sha256=analysis.prompt_sha256,
            taxonomy_sha256=analysis.taxonomy_sha256,
            model_provider=analysis.model_provider,
            model=analysis.model,
            input_hash=analysis.input_hash,
            analyzed_at=analysis.analyzed_at,
            labels=tuple(
                AnalysisLabelPair(
                    ordinal=ordinal,
                    primary_label=pair.primary_label,
                    secondary_label=pair.secondary_label,
                )
                for ordinal, pair in enumerate(analysis.labels)
            ),
        )


@dataclass(frozen=True, slots=True)
class AnalysisWorkItem:
    request_id: UUID
    ordinal: int
    content_id: UUID
    content_version: int
    content: CanonicalContentV1


__all__ = [
    "AnalysisConfigurationIdentity",
    "AnalysisContentResult",
    "AnalysisLabelPair",
    "AnalysisWorkItem",
]
''',
    )
    path = "backend/src/aima_ugc/modules/analysis/tables.py"
    replace_once(
        path,
        '''    Column("schema_version", Text(), nullable=False),
    Column("sentiment", Text(), nullable=False),''',
        '''    Column("schema_version", Text(), nullable=False),
    Column("relevance", Text(), nullable=False),
    Column("voice_type", Text(), nullable=False),
    Column("sentiment", Text()),''',
    )
    replace_once(
        path,
        '''    CheckConstraint("content_version >= 1", name="content_version_positive"),''',
        '''    CheckConstraint("content_version >= 1", name="content_version_positive"),
    CheckConstraint("relevance in ('relevant','irrelevant')", name="relevance_allowed"),
    CheckConstraint(
        "voice_type in ('user_voice','creator_marketing','brand_official','dealer_promotion',"
        "'media_information','other_organization','unknown')",
        name="voice_type_allowed",
    ),
    CheckConstraint(
        "(relevance = 'relevant' and sentiment is not null) or "
        "(relevance = 'irrelevant' and sentiment is null)",
        name="relevance_sentiment_consistent",
    ),''',
    )


def patch_postgres_analysis() -> None:
    path = "backend/src/aima_ugc/adapters/persistence/postgres/analysis.py"
    replace_once(
        path,
        "from aima_ugc.contracts.analysis import ContentLabelAnalysisV2, ContentLabelPairV2",
        "from aima_ugc.contracts.analysis import ContentLabelAnalysisV3, ContentLabelPairV2",
    )
    replace_once(path, "analysis: ContentLabelAnalysisV2,", "analysis: ContentLabelAnalysisV3,")
    replace_once(
        path,
        '''                schema_version=result.schema_version,
                sentiment=result.sentiment,''',
        '''                schema_version=result.schema_version,
                relevance=result.relevance,
                voice_type=result.voice_type,
                sentiment=result.sentiment,''',
    )
    replace_once(
        path,
        '''            _assert_same_labels(self._session, persisted_id, analysis.labels)''',
        '''            _assert_same_analysis(self._session, persisted_id, analysis)''',
    )
    replace_once(
        path,
        '''    display_name = (
        str(author_snapshot.get("display_name"))
        if isinstance(author_snapshot, dict) and author_snapshot.get("display_name") is not None
        else None
    )
    observed_fields = ["content_type", "title", "text"]
    author = None
    if display_name is not None:
        author = CanonicalAuthorV1(display_name=display_name)
        observed_fields.append("author.display_name")''',
        '''    display_name = _snapshot_text(author_snapshot, "display_name")
    bio = _snapshot_text(author_snapshot, "bio")
    verification_label = _snapshot_text(author_snapshot, "verification_label")
    observed_fields = ["content_type", "title", "text"]
    author = None
    if any(value is not None for value in (display_name, bio, verification_label)):
        author = CanonicalAuthorV1(
            display_name=display_name,
            bio=bio,
            verification_label=verification_label,
        )
        if display_name is not None:
            observed_fields.append("author.display_name")
        if bio is not None:
            observed_fields.append("author.bio")
        if verification_label is not None:
            observed_fields.append("author.verification_label")''',
    )
    replace_regex_once(
        path,
        r'''def _assert_same_labels\(\n    session: Session,\n    result_id: UUID,\n    labels: tuple\[ContentLabelPairV2, \.\.\.\],\n\) -> None:.*?\n\n\ndef _http_url''',
        '''def _assert_same_analysis(
    session: Session,
    result_id: UUID,
    analysis: ContentLabelAnalysisV3,
) -> None:
    persisted_result = session.execute(
        select(
            analysis_content_results_table.c.schema_version,
            analysis_content_results_table.c.relevance,
            analysis_content_results_table.c.voice_type,
            analysis_content_results_table.c.sentiment,
        ).where(analysis_content_results_table.c.id == result_id)
    ).one()
    expected_result = (
        analysis.schema_version,
        analysis.relevance,
        analysis.voice_type,
        analysis.sentiment,
    )
    if tuple(persisted_result) != expected_result:
        raise ValueError("Analysis 幂等身份对应的相关性/发声类型/情感不一致")

    rows = session.execute(
        select(
            analysis_content_label_pairs_table.c.primary_label,
            analysis_content_label_pairs_table.c.secondary_label,
        )
        .where(analysis_content_label_pairs_table.c.analysis_result_id == result_id)
        .order_by(analysis_content_label_pairs_table.c.ordinal)
    )
    persisted = tuple((cast(str, row[0]), cast(str, row[1])) for row in rows)
    expected = tuple((item.primary_label, item.secondary_label) for item in analysis.labels)
    if persisted != expected:
        raise ValueError("Analysis 幂等身份对应的标签集合不一致")


def _snapshot_text(snapshot: object, key: str) -> str | None:
    if not isinstance(snapshot, dict) or snapshot.get(key) is None:
        return None
    return str(snapshot[key])


def _http_url''',
    )


def patch_worker() -> None:
    path = "backend/src/aima_ugc/bootstrap/analysis_worker.py"
    replace_once(
        path,
        "from aima_ugc.contracts.analysis import ContentLabelAnalysisV2",
        "from aima_ugc.contracts.analysis import ContentLabelAnalysisV3",
    )
    replace_once(path, "result.analysis, ContentLabelAnalysisV2", "result.analysis, ContentLabelAnalysisV3")


def patch_query_and_http() -> None:
    path = "backend/src/aima_ugc/modules/content/query.py"
    replace_once(
        path,
        '''    status: str
    sentiment: str | None''',
        '''    status: str
    relevance: str | None
    voice_type: str | None
    sentiment: str | None''',
    )

    path = "backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py"
    replace_once(
        path,
        '''                analysis.c.id.label("analysis_result_id"),
                analysis.c.sentiment,''',
        '''                analysis.c.id.label("analysis_result_id"),
                analysis.c.relevance,
                analysis.c.voice_type,
                analysis.c.sentiment,''',
    )
    replace_once(
        path,
        '''                    status="completed",
                    sentiment=cast(str, row["sentiment"]),''',
        '''                    status="completed",
                    relevance=cast(str, row["relevance"]),
                    voice_type=cast(str, row["voice_type"]),
                    sentiment=cast(str | None, row["sentiment"]),''',
    )
    replace_once(
        path,
        '''                    status="stale" if bool(row["has_any_analysis"]) else "pending",
                    sentiment=None,''',
        '''                    status="stale" if bool(row["has_any_analysis"]) else "pending",
                    relevance=None,
                    voice_type=None,
                    sentiment=None,''',
    )
    replace_once(
        path,
        '''        result.c.content_version,
        result.c.sentiment,''',
        '''        result.c.content_version,
        result.c.relevance,
        result.c.voice_type,
        result.c.sentiment,''',
    )
    replace_once(
        path,
        '''    content = contents_table
    if filters.search is not None:''',
        '''    content = contents_table
    if filters.relevance is None:
        statement = statement.where(
            or_(analysis.c.id.is_(None), analysis.c.relevance != "irrelevant")
        )
    else:
        statement = statement.where(analysis.c.relevance == filters.relevance)
    if filters.voice_type is not None:
        statement = statement.where(analysis.c.voice_type == filters.voice_type)
    if filters.search is not None:''',
    )

    path = "backend/src/aima_ugc/contracts/http.py"
    replace_once(
        path,
        "from aima_ugc.contracts.collection.models import BusinessOperation",
        "from aima_ugc.contracts.analysis import ContentRelevance, ContentVoiceType\nfrom aima_ugc.contracts.collection.models import BusinessOperation",
    )
    replace_once(
        path,
        '''    status: ContentAnalysisStatus
    sentiment: str | None = None''',
        '''    status: ContentAnalysisStatus
    relevance: ContentRelevance | None = None
    voice_type: ContentVoiceType | None = None
    is_user_voice: bool | None = None
    sentiment: str | None = None''',
    )
    replace_regex_once(
        path,
        r'''    @model_validator\(mode="after"\)\n    def validate_completed_shape\(self\) -> ContentAnalysisResponse:\n        if self.status == "completed":.*?        return self''',
        '''    @model_validator(mode="after")
    def validate_completed_shape(self) -> ContentAnalysisResponse:
        if self.status == "completed":
            if self.relevance is None or self.voice_type is None or self.is_user_voice is None:
                raise ValueError("completed Analysis 必须包含相关性与发声类型")
            if self.is_user_voice != (self.voice_type == "user_voice"):
                raise ValueError("is_user_voice 必须由 voice_type 派生")
            if self.relevance == "relevant":
                if self.sentiment is None or self.analyzed_at is None or not self.labels:
                    raise ValueError("relevant completed Analysis 必须包含情感、标签与分析时间")
            elif self.sentiment is not None or self.labels or self.analyzed_at is None:
                raise ValueError("irrelevant completed Analysis 只能携带分类和分析时间")
        elif any(
            value is not None
            for value in (
                self.relevance,
                self.voice_type,
                self.is_user_voice,
                self.sentiment,
                self.analyzed_at,
            )
        ) or self.labels:
            raise ValueError("非 completed Analysis 不能携带结果字段")
        return self''',
    )
    replace_once(
        path,
        '''    analysis_status: ContentAnalysisStatus | None = None
    sentiment: str | None = Field(default=None, min_length=1, max_length=128)''',
        '''    analysis_status: ContentAnalysisStatus | None = None
    relevance: ContentRelevance | None = None
    voice_type: ContentVoiceType | None = None
    sentiment: str | None = Field(default=None, min_length=1, max_length=128)''',
    )

    path = "backend/src/aima_ugc/bootstrap/content_http.py"
    replace_once(
        path,
        '''            status=cast(ContentAnalysisStatus, record.analysis.status),
            sentiment=record.analysis.sentiment,''',
        '''            status=cast(ContentAnalysisStatus, record.analysis.status),
            relevance=record.analysis.relevance,
            voice_type=record.analysis.voice_type,
            is_user_voice=(
                record.analysis.voice_type == "user_voice"
                if record.analysis.voice_type is not None
                else None
            ),
            sentiment=record.analysis.sentiment,''',
    )


def patch_export() -> None:
    path = "backend/src/aima_ugc/contracts/export/models.py"
    replace_once(
        path,
        "from typing import Literal",
        "from typing import Literal\n\nfrom aima_ugc.contracts.analysis import ContentRelevance, ContentVoiceType",
    )
    replace_once(
        path,
        '''    sentiment: str = Field(min_length=1, max_length=128)
    primary_label: str = Field(min_length=1, max_length=4096)
    secondary_label: str = Field(min_length=1, max_length=4096)''',
        '''    relevance: ContentRelevance = "relevant"
    voice_type: ContentVoiceType = "unknown"
    is_user_voice: bool = False
    sentiment: str | None = Field(default=None, min_length=1, max_length=128)
    primary_label: str = Field(default="", max_length=4096)
    secondary_label: str = Field(default="", max_length=4096)''',
    )
    replace_once(
        path,
        '''    @field_validator("label_pairs")
    @classmethod''',
        '''    @field_validator("is_user_voice")
    @classmethod
    def validate_user_voice(cls, value: bool, info: object) -> bool:
        return value

    @field_validator("label_pairs")
    @classmethod''',
    )

    path = "backend/src/aima_ugc/platform/export/excel.py"
    replace_once(
        path,
        "from aima_ugc.contracts.analysis import ContentLabelAnalysisV2, UnifiedContentRecordV1",
        "from aima_ugc.contracts.analysis import (\n    ContentLabelAnalysisV2,\n    ContentLabelAnalysisV3,\n    UnifiedContentRecordV1,\n)",
    )
    replace_once(
        path,
        '''    "命中关键词",
    "情感标签",''',
        '''    "命中关键词",
    "相关性",
    "发声类型",
    "是否用户真实发声",
    "情感标签",''',
    )
    replace_once(
        path,
        '''    "命中关键词": 20,
    "情感标签": 12,''',
        '''    "命中关键词": 20,
    "相关性": 12,
    "发声类型": 18,
    "是否用户真实发声": 16,
    "情感标签": 12,''',
    )
    replace_regex_once(
        path,
        r'''            if record.analysis is not None:\n                if isinstance\(record.analysis, ContentLabelAnalysisV2\):.*?                analysis = UnifiedDataExcelAnalysisV1\(\n                    sentiment=record.analysis.sentiment,\n                    primary_label=primary_label,\n                    secondary_label=secondary_label,\n                    label_pairs=label_pairs,\n                    model=record.analysis.model,\n                    prompt_version=record.analysis.prompt_version,\n                    taxonomy_version=record.analysis.taxonomy_sha256,\n                \)''',
        '''            if record.analysis is not None:
                if isinstance(record.analysis, (ContentLabelAnalysisV2, ContentLabelAnalysisV3)):
                    label_pairs = tuple(
                        UnifiedDataExcelLabelPairV1(
                            primary_label=pair.primary_label,
                            secondary_label=pair.secondary_label,
                        )
                        for pair in record.analysis.labels
                    )
                    primary_label = "\\n".join(pair.primary_label for pair in label_pairs)
                    secondary_label = "\\n".join(pair.secondary_label for pair in label_pairs)
                else:
                    label_pairs = (
                        UnifiedDataExcelLabelPairV1(
                            primary_label=record.analysis.primary_label,
                            secondary_label=record.analysis.secondary_label,
                        ),
                    )
                    primary_label = record.analysis.primary_label
                    secondary_label = record.analysis.secondary_label
                relevance = (
                    record.analysis.relevance
                    if isinstance(record.analysis, ContentLabelAnalysisV3)
                    else "relevant"
                )
                voice_type = (
                    record.analysis.voice_type
                    if isinstance(record.analysis, ContentLabelAnalysisV3)
                    else "unknown"
                )
                analysis = UnifiedDataExcelAnalysisV1(
                    relevance=relevance,
                    voice_type=voice_type,
                    is_user_voice=voice_type == "user_voice",
                    sentiment=record.analysis.sentiment,
                    primary_label=primary_label,
                    secondary_label=secondary_label,
                    label_pairs=label_pairs,
                    model=record.analysis.model,
                    prompt_version=record.analysis.prompt_version,
                    taxonomy_version=record.analysis.taxonomy_sha256,
                )''',
    )
    replace_once(
        path,
        '''        ("；".join(content.matched_keywords) or None, False, False),
        (analysis.sentiment if analysis is not None else None, False, False),''',
        '''        ("；".join(content.matched_keywords) or None, False, False),
        (analysis.relevance if analysis is not None else None, False, False),
        (analysis.voice_type if analysis is not None else None, False, False),
        (
            "是" if analysis is not None and analysis.is_user_voice else "否" if analysis is not None else None,
            False,
            False,
        ),
        (analysis.sentiment if analysis is not None else None, False, False),''',
    )

    path = "backend/src/aima_ugc/adapters/providers/imports_test/test.py"
    replace_once(
        path,
        '''    "命中关键词",
    "情感标签",
    "一级标签",
    "二级标签",
)''',
        '''    "命中关键词",
    "相关性",
    "发声类型",
    "是否用户真实发声",
    "情感标签",
    "一级标签",
    "二级标签",
)''',
    )
    # 文件中“内容”和“标签明细”两组配置相同，第二组继续补齐。
    text = read(path)
    remaining = '''    "命中关键词",
    "情感标签",
    "一级标签",
    "二级标签",
)'''
    if remaining in text:
        write(
            path,
            text.replace(
                remaining,
                '''    "命中关键词",
    "相关性",
    "发声类型",
    "是否用户真实发声",
    "情感标签",
    "一级标签",
    "二级标签",
)''',
                1,
            ),
        )


def patch_migration() -> None:
    write(
        "migrations/versions/20260821_0023_analysis_relevance_voice_type.py",
        '''"""增加 Analysis 语义相关性与发声类型。

Revision ID: 20260821_0023
Revises: 20260821_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0023"
down_revision: str | Sequence[str] | None = "20260821_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("analysis_content_results", sa.Column("relevance", sa.Text(), nullable=True))
    op.add_column("analysis_content_results", sa.Column("voice_type", sa.Text(), nullable=True))
    op.alter_column("analysis_content_results", "sentiment", existing_type=sa.Text(), nullable=True)
    op.execute(
        "UPDATE analysis_content_results "
        "SET relevance = 'relevant', voice_type = 'unknown' "
        "WHERE relevance IS NULL OR voice_type IS NULL"
    )
    op.alter_column("analysis_content_results", "relevance", existing_type=sa.Text(), nullable=False)
    op.alter_column("analysis_content_results", "voice_type", existing_type=sa.Text(), nullable=False)
    op.create_check_constraint(
        op.f("ck_analysis_content_results_relevance_allowed"),
        "analysis_content_results",
        "relevance in ('relevant','irrelevant')",
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_results_voice_type_allowed"),
        "analysis_content_results",
        "voice_type in ('user_voice','creator_marketing','brand_official','dealer_promotion',"
        "'media_information','other_organization','unknown')",
    )
    op.create_check_constraint(
        op.f("ck_analysis_content_results_relevance_sentiment_consistent"),
        "analysis_content_results",
        "(relevance = 'relevant' and sentiment is not null) or "
        "(relevance = 'irrelevant' and sentiment is null)",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE analysis_content_request_items SET status = 'failed', "
        "analysis_result_id = NULL, error_code = 'analysis_v3_irrelevant_downgrade' "
        "WHERE analysis_result_id IN (SELECT id FROM analysis_content_results "
        "WHERE relevance = 'irrelevant')"
    )
    op.execute("DELETE FROM analysis_content_results WHERE relevance = 'irrelevant'")
    op.drop_constraint(
        op.f("ck_analysis_content_results_relevance_sentiment_consistent"),
        "analysis_content_results",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_analysis_content_results_voice_type_allowed"),
        "analysis_content_results",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_analysis_content_results_relevance_allowed"),
        "analysis_content_results",
        type_="check",
    )
    op.alter_column("analysis_content_results", "sentiment", existing_type=sa.Text(), nullable=False)
    op.drop_column("analysis_content_results", "voice_type")
    op.drop_column("analysis_content_results", "relevance")
''',
    )


def patch_contract_generator() -> None:
    path = "scripts/contracts/generate.py"
    replace_once(
        path,
        '''    ContentLabelAnalysisV2,
    RelevanceSnapshotV1,''',
        '''    ContentLabelAnalysisV2,
    ContentLabelAnalysisV3,
    RelevanceSnapshotV1,''',
    )
    replace_once(
        path,
        '''    "content-label-analysis.v2.schema.json": ContentLabelAnalysisV2,
    "content-record.v1.schema.json": UnifiedContentRecordV1,''',
        '''    "content-label-analysis.v2.schema.json": ContentLabelAnalysisV2,
    "content-label-analysis.v3.schema.json": ContentLabelAnalysisV3,
    "content-record.v1.schema.json": UnifiedContentRecordV1,''',
    )


def patch_new_test_compatibility() -> None:
    # 旧测试继续证明 V1/V2 历史可读；当前 Service 断言更新为 V3。
    path = "tests/unit/analysis/test_multilabel_analysis_v2.py"
    text = read(path)
    text = text.replace(
        "    ContentLabelAnalysisV2,\n",
        "    ContentLabelAnalysisV2,\n    ContentLabelAnalysisV3,\n",
        1,
    )
    text = text.replace(
        '                    "sentiment": taxonomy.sentiments[0],\n                    "labels": [',
        '                    "relevance": "relevant",\n                    "voice_type": "unknown",\n                    "sentiment": taxonomy.sentiments[0],\n                    "labels": [',
    )
    text = text.replace(
        "    assert isinstance(analysis, ContentLabelAnalysisV2)\n",
        "    assert isinstance(analysis, ContentLabelAnalysisV3)\n",
        1,
    )
    write(path, text)

    # 主 Analysis 测试的通用合法响应升级到 V3；请求字段期望增加公开作者上下文。
    path = "tests/unit/analysis/test_content_labeling.py"
    text = read(path)
    text = text.replace(
        '''                    "item_no": item_no,
                    "sentiment": sentiment,
                    "primary_label": primary,
                    "secondary_label": secondary,''',
        '''                    "item_no": item_no,
                    "relevance": "relevant",
                    "voice_type": "unknown",
                    "sentiment": sentiment,
                    "labels": [
                        {"primary_label": primary, "secondary_label": secondary}
                    ],''',
        1,
    )
    text = text.replace(
        '''            "author": {"display_name": ""},''',
        '''            "author": {"display_name": "", "bio": "", "verification_label": ""},''',
    )
    # 对旧式非法 item 增加 V3 外层字段，使测试仍命中它真正要验证的标签错误。
    text = text.replace(
        '''                            "item_no": 1,
                            "sentiment": "不存在的情感",''',
        '''                            "item_no": 1,
                            "relevance": "relevant",
                            "voice_type": "unknown",
                            "sentiment": "不存在的情感",''',
    )
    text = text.replace(
        '''                            "item_no": 1,
                            "sentiment": taxonomy.sentiments[0],''',
        '''                            "item_no": 1,
                            "relevance": "relevant",
                            "voice_type": "unknown",
                            "sentiment": taxonomy.sentiments[0],''',
    )
    # 将旧 primary/secondary 形状转成 labels[]（只处理此测试文件中的模型响应字典）。
    text = re.sub(
        r'''"sentiment": (?P<sentiment>[^,\n]+),\n\s+"primary_label": (?P<primary>[^,\n]+),\n\s+"secondary_label": (?P<secondary>[^,\n]+),''',
        '"sentiment": \\g<sentiment>,\n                            "labels": [{"primary_label": \\g<primary>, "secondary_label": \\g<secondary>}],',
        text,
    )
    write(path, text)


def main() -> None:
    patch_analysis_contracts()
    patch_prompt()
    patch_labeling_service()
    patch_offline_labeling()
    patch_persistence_models_and_tables()
    patch_postgres_analysis()
    patch_worker()
    patch_query_and_http()
    patch_export()
    patch_migration()
    patch_contract_generator()
    patch_new_test_compatibility()
    print("Analysis V3 一次性迁移已应用。")


if __name__ == "__main__":
    main()
