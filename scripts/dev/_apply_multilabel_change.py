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
        raise RuntimeError(f"{path}: expected one literal match, got {count}: {old[:80]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str) -> None:
    text = read(path)
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, got {count}: {pattern[:80]!r}")
    write(path, new_text)


write(
    "backend/src/aima_ugc/contracts/analysis/content_label.py",
    '''"""Provider-neutral 舆情内容 AI 打标结果契约。"""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class ContentLabelPairV2(BaseModel):
    """一个经过 Taxonomy 校验的一级/二级标签父子对。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_label: str = Field(min_length=1, max_length=256)
    secondary_label: str = Field(min_length=1, max_length=256)


class ContentLabelAnalysisV1(BaseModel):
    """历史单标签成功分析结果；保留用于兼容旧 JSONL/checkpoint。"""

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
    """当前多标签成功分析结果：一个情感 + 一个或多个一级/二级标签对。"""

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
''',
)

write(
    "backend/src/aima_ugc/contracts/analysis/content_record.py",
    '''"""Provider-neutral 内容处理记录。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aima_ugc.contracts.canonical import CanonicalContentV1

from .content_label import ContentLabelAnalysisV1, ContentLabelAnalysisV2

ContentLabelAnalysis = Annotated[
    ContentLabelAnalysisV1 | ContentLabelAnalysisV2,
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

from .content_label import ContentLabelAnalysisV1, ContentLabelAnalysisV2, ContentLabelPairV2
from .content_record import ContentLabelAnalysis, UnifiedContentRecordV1

__all__ = [
    "ContentLabelAnalysis",
    "ContentLabelAnalysisV1",
    "ContentLabelAnalysisV2",
    "ContentLabelPairV2",
    "UnifiedContentRecordV1",
]
''',
)

replace_once(
    "backend/src/aima_ugc/modules/analysis/prompt_taxonomy.py",
    'PROMPT_VERSION = "content-labeling.v1"\nCONTENT_LABELING_PROMPT_PATH = Path(__file__).with_name("prompts") / "content_labeling_v1.md"',
    'PROMPT_VERSION = "content-labeling.v2"\nCONTENT_LABELING_PROMPT_PATH = Path(__file__).with_name("prompts") / "content_labeling_v2.md"',
)

prompt_v1 = read("backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md")
prompt_v2 = prompt_v1.replace(
    "# AIMA 内容舆情单标签分析 Prompt V1",
    "# AIMA 内容舆情多标签分析 Prompt V2",
    1,
).replace(
    "Prompt Version：`content-labeling.v1`",
    "Prompt Version：`content-labeling.v2`",
    1,
).replace(
    "你负责对与爱玛相关的公开内容做舆情单标签分析。必须严格依据本 Prompt 当前版本中的 Taxonomy、判断标准、边界规则和冲突优先级判断，不得创造新标签、改写标签名称、输出近义标签或多标签。",
    "你负责对与爱玛相关的公开内容做舆情多标签分析。必须严格依据本 Prompt 当前版本中的 Taxonomy、判断标准和边界规则判断；不得创造新标签、改写标签名称或输出近义标签。每条内容保留一个整体情感，同时返回所有具有明确、实质语义依据的一级/二级标签对。",
    1,
)
prompt_v2, count = re.subn(
    r"## 输出格式\n.*?## 机器可读 Taxonomy",
    '''## 输出格式

只返回一个 JSON object，不要使用 Markdown 代码块，不要添加解释文字：

```json
{
  "items": [
    {
      "item_no": 1,
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
```

要求：

1. 每个输入 `item_no` 恰好返回一次，顺序与本次请求一致；
2. 每条恰好一个 `sentiment`；
3. 每条 `labels` 至少一个标签对，可以有多个；
4. 每个标签对恰好包含 `primary_label` 和 `secondary_label`，不得输出额外字段；
5. 每个标签名称必须使用下面机器 Taxonomy 中的完整原名，不得输出空字符串、近义词或自造标签；
6. 每个 `secondary_label` 必须属于同一标签对中的 `primary_label`；
7. 同一条内容不得返回重复的一级/二级标签对；
8. 标签对按内容中的重要性排序，最核心的标签对放在前面；
9. 只保留具有明确、实质语义依据的标签，不因轻微联想无限扩展；同样不得为了“只选主标签”而丢掉正文中明确成立的其他核心标签；
10. 信息不足时情感使用“中性”，但标签仍必须基于可见语义选择至少一个合法标签对。

## 机器可读 Taxonomy''',
    prompt_v2,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("prompt output section replacement failed")
prompt_v2, count = re.subn(
    r"## 多主题与边界冲突优先级\n.*?## 示例",
    '''## 多主题与边界冲突优先级

一条内容可以同时覆盖多个一级标签和多个二级标签。判断顺序固定为：

1. 先识别正文中所有具有明确、实质信息量的主题，不再强制压缩成单一主标签；
2. 每个命中的二级标签必须与它真实所属的一级标签组成一个标签对；
3. 同一一级下可以返回多个二级标签，例如“动力与加速表现”与“舒适性”可以同时成立；
4. 不同一级也可以同时成立，例如“骑行性能 / 舒适性”与“售后服务 / 客服与服务态度”可以同时返回；
5. 具体产品/服务事实优先使用对应具体维度，但这不排斥正文中另一个同样明确成立的主题；
6. 明确故障使用“耐用性与质量 / 故障问题与稳定性”，但电池、智能功能、骑行性能存在更具体且独立成立的语义时，对应标签也可以同时返回；
7. 售后维修、保修、配件、投诉与购买前咨询、下单、提车要按各自语义分别标注；同一内容同时描述两个阶段时可以返回多个标签对；
8. 广告、代言、直播、达人、联名等传播内容可以命中“品牌评价 / 营销与传播”；若内容还对产品性能作了实质评价，可同时返回对应产品标签；
9. 不得因关键词出现就机械加标签；只有正文或标题确实表达了对应主题才返回；
10. 标签对不得重复，并按作者主要诉求、主要评价对象、篇幅与信息重要性由高到低排序。

## 示例''',
    prompt_v2,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("prompt multi-topic section replacement failed")
prompt_v2 = prompt_v2.replace(
    "输出应选择：`混合 / 耐用性与质量 / 故障问题与稳定性`。",
    "输出情感应为 `混合`；`labels` 至少同时包含 `外观设计 / 整体造型与颜值` 与 `耐用性与质量 / 故障问题与稳定性`，并按主要诉求排序。",
    1,
)
prompt_v2, count = re.subn(
    r"## 返回前自检\n.*\Z",
    '''## 返回前自检

在输出 JSON 前确认：

- `items` 数量与本次请求一致；
- `item_no` 无缺失、无重复、顺序一致；
- 每条恰好一个合法 `sentiment`；
- 每条 `labels` 至少一个，且每个元素只有 `primary_label` / `secondary_label`；
- 每个一级/二级名称都是机器 Taxonomy 中的当前值；
- 每个二级标签属于同一标签对中的一级标签；
- 同一条内容没有重复标签对；
- 对明确存在的多个核心主题没有强行只保留一个主标签；
- 没有因为轻微联想或关键词命中而牵强增加标签；
- 没有额外字段、解释或 Markdown。
''',
    prompt_v2,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("prompt self-check section replacement failed")
write("backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v2.md", prompt_v2)

path = "backend/src/aima_ugc/modules/analysis/content_labeling.py"
text = read(path)
text = text.replace("P1E Provider-neutral 舆情单标签分析", "Provider-neutral 舆情多标签分析", 1)
text = text.replace(
    "from aima_ugc.contracts.analysis import ContentLabelAnalysisV1",
    "from aima_ugc.contracts.analysis import (\n    ContentLabelAnalysis,\n    ContentLabelAnalysisV2,\n    ContentLabelPairV2,\n)",
    1,
)
text, count = re.subn(
    r"class _ModelLabelItem\(BaseModel\):.*?class RuntimeTaxonomyValidator:",
    '''class _ModelLabelPair(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    primary_label: str = Field(min_length=1)
    secondary_label: str = Field(min_length=1)


class _ModelLabelItemV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    item_no: int = Field(ge=1)
    sentiment: str = Field(min_length=1)
    labels: tuple[_ModelLabelPair, ...] = Field(min_length=1)


class _ModelLabelItemV1(BaseModel):
    """兼容历史单标签模型响应；新 Prompt 不再要求该形状。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    item_no: int = Field(ge=1)
    sentiment: str = Field(min_length=1)
    primary_label: str = Field(min_length=1)
    secondary_label: str = Field(min_length=1)


def _parse_model_label_item(
    value: dict[str, Any],
) -> tuple[str, tuple[ContentLabelPairV2, ...]]:
    if "labels" in value:
        parsed = _ModelLabelItemV2.model_validate(value)
        return parsed.sentiment, tuple(
            ContentLabelPairV2(
                primary_label=pair.primary_label,
                secondary_label=pair.secondary_label,
            )
            for pair in parsed.labels
        )
    parsed = _ModelLabelItemV1.model_validate(value)
    return parsed.sentiment, (
        ContentLabelPairV2(
            primary_label=parsed.primary_label,
            secondary_label=parsed.secondary_label,
        ),
    )


@dataclass(frozen=True, slots=True)
class _ValidatedLabel:
    sentiment: str
    labels: tuple[ContentLabelPairV2, ...]


@dataclass(frozen=True, slots=True)
class _ValidationResult:
    valid_items: dict[int, _ValidatedLabel]
    item_errors: dict[int, tuple[str, ...]]
    error_codes: tuple[str, ...]


class RuntimeTaxonomyValidator:''',
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("content_labeling model block replacement failed")
marker = "    def validate_response(\n"
if text.count(marker) != 1:
    raise RuntimeError("content_labeling validate_response marker mismatch")
text = text.replace(
    marker,
    '''    def validate_label_pairs(
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
''',
    1,
)
old = '''            try:
                parsed = _ModelLabelItem.model_validate(candidates[0])
            except ValidationError:
                item_errors[item_no] = ("invalid_item_structure",)
                aggregate_errors.append("invalid_item_structure")
                continue

            try:
                self.validate_labels(
                    sentiment=parsed.sentiment,
                    primary_label=parsed.primary_label,
                    secondary_label=parsed.secondary_label,
                )
            except ContentLabelingValidationError as exc:
                item_errors[item_no] = exc.error_codes
                aggregate_errors.extend(exc.error_codes)
                continue

            valid_items[item_no] = _ValidatedLabel(
                sentiment=parsed.sentiment,
                primary_label=parsed.primary_label,
                secondary_label=parsed.secondary_label,
            )
'''
new = '''            try:
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
            )
'''
if text.count(old) != 1:
    raise RuntimeError("content_labeling parsed block mismatch")
text = text.replace(old, new, 1)
text = text.replace(
    "    analysis: ContentLabelAnalysisV1 | None\n",
    "    analysis: ContentLabelAnalysis | None\n",
    1,
)
text = text.replace(
    '    """使用唯一 PromptTaxonomy 和 LLM Port 执行严格单标签分析。"""',
    '    """使用唯一 PromptTaxonomy 和 LLM Port 执行严格多标签分析。"""',
    1,
)
text = text.replace(
    "        successful: dict[int, ContentLabelAnalysisV1] = {}",
    "        successful: dict[int, ContentLabelAnalysis] = {}",
    1,
)
old = '''                successful[item_no] = ContentLabelAnalysisV1(
                    sentiment=validated.sentiment,
                    primary_label=validated.primary_label,
                    secondary_label=validated.secondary_label,
                    prompt_version=taxonomy.prompt_version,
'''
new = '''                successful[item_no] = ContentLabelAnalysisV2(
                    sentiment=validated.sentiment,
                    labels=validated.labels,
                    prompt_version=taxonomy.prompt_version,
'''
if text.count(old) != 1:
    raise RuntimeError("content_labeling success constructor mismatch")
text = text.replace(old, new, 1)
write(path, text)

path = "backend/src/aima_ugc/modules/analysis/offline_labeling.py"
text = read(path)
text = text.replace("from pydantic import ValidationError", "from pydantic import TypeAdapter, ValidationError", 1)
text = text.replace(
    "from aima_ugc.contracts.analysis import ContentLabelAnalysisV1, UnifiedContentRecordV1",
    "from aima_ugc.contracts.analysis import ContentLabelAnalysis, UnifiedContentRecordV1",
    1,
)
text = text.replace("ContentLabelAnalysisV1", "ContentLabelAnalysis")
text = text.replace(
    "_CheckpointKey = tuple[str, str, str]\n",
    "_CheckpointKey = tuple[str, str, str]\n_ANALYSIS_ADAPTER = TypeAdapter(ContentLabelAnalysis)\n",
    1,
)
text = text.replace(
    "analysis = ContentLabelAnalysis.model_validate(payload.get(\"analysis\"))",
    "analysis = _ANALYSIS_ADAPTER.validate_python(payload.get(\"analysis\"))",
    1,
)
write(path, text)

path = "backend/src/aima_ugc/contracts/export/models.py"
text = read(path)
text = text.replace(
    "from pydantic import AwareDatetime, BaseModel, ConfigDict, Field",
    "from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator",
    1,
)
text, count = re.subn(
    r"class UnifiedDataExcelAnalysisV1\(_ExportBaseModel\):.*?class UnifiedDataExcelContentV1\(_ExportBaseModel\):",
    '''class UnifiedDataExcelLabelPairV1(_ExportBaseModel):
    """Excel 标签明细与主表多行展示共用的一级/二级标签对。"""

    primary_label: str = Field(min_length=1, max_length=256)
    secondary_label: str = Field(min_length=1, max_length=256)


class UnifiedDataExcelAnalysisV1(_ExportBaseModel):
    """Excel 展示所需的分析投影；兼容单标签字符串并可携带完整标签对。"""

    sentiment: str = Field(min_length=1, max_length=128)
    primary_label: str = Field(min_length=1, max_length=4096)
    secondary_label: str = Field(min_length=1, max_length=4096)
    label_pairs: tuple[UnifiedDataExcelLabelPairV1, ...] = ()
    model: str | None = Field(default=None, max_length=256)
    prompt_version: str | None = Field(default=None, max_length=256)
    taxonomy_version: str | None = Field(default=None, max_length=256)

    @field_validator("label_pairs")
    @classmethod
    def validate_unique_label_pairs(
        cls, value: tuple[UnifiedDataExcelLabelPairV1, ...]
    ) -> tuple[UnifiedDataExcelLabelPairV1, ...]:
        keys = [(item.primary_label, item.secondary_label) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("Excel Analysis label_pairs 不能重复")
        return value


class UnifiedDataExcelContentV1(_ExportBaseModel):''',
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("export models analysis block replacement failed")
write(path, text)

write(
    "backend/src/aima_ugc/contracts/export/__init__.py",
    '''"""统一数据导出公共契约。"""

from .models import (
    UnifiedDataExcelAnalysisV1,
    UnifiedDataExcelCommentV1,
    UnifiedDataExcelContentV1,
    UnifiedDataExcelLabelPairV1,
    UnifiedDataExcelV1,
)

__all__ = [
    "UnifiedDataExcelAnalysisV1",
    "UnifiedDataExcelCommentV1",
    "UnifiedDataExcelContentV1",
    "UnifiedDataExcelLabelPairV1",
    "UnifiedDataExcelV1",
]
''',
)

path = "backend/src/aima_ugc/platform/export/excel.py"
text = read(path)
text = text.replace("from openpyxl.styles import Font, PatternFill", "from openpyxl.styles import Alignment, Font, PatternFill", 1)
text = text.replace(
    "from aima_ugc.contracts.analysis import UnifiedContentRecordV1",
    "from aima_ugc.contracts.analysis import ContentLabelAnalysisV2, UnifiedContentRecordV1",
    1,
)
text = text.replace(
    "    UnifiedDataExcelContentV1,\n    UnifiedDataExcelV1,",
    "    UnifiedDataExcelContentV1,\n    UnifiedDataExcelLabelPairV1,\n    UnifiedDataExcelV1,",
    1,
)
text = text.replace(
    '_CONTENT_SHEET = "内容"\n_COMMENT_SHEET = "评论"',
    '_CONTENT_SHEET = "内容"\n_LABEL_SHEET = "标签明细"\n_COMMENT_SHEET = "评论"',
    1,
)
text = text.replace(
    '_COMMENT_HEADERS = (\n',
    '_LABEL_HEADERS = (\n    "内容ID",\n    "平台",\n    "标题",\n    "情感标签",\n    "一级标签",\n    "二级标签",\n    "内容链接",\n)\n_COMMENT_HEADERS = (\n',
    1,
)
text = text.replace(
    '_COMMENT_COLUMN_WIDTHS = {\n',
    '_LABEL_COLUMN_WIDTHS = {\n    "内容ID": 34,\n    "平台": 15,\n    "标题": 50,\n    "情感标签": 12,\n    "一级标签": 20,\n    "二级标签": 24,\n    "内容链接": 34,\n}\n_COMMENT_COLUMN_WIDTHS = {\n',
    1,
)
text = text.replace(
    "    comment_rows: int\n\n\ndef project_canonical_content",
    "    comment_rows: int\n    label_rows: int = 0\n\n\ndef project_canonical_content",
    1,
)
text, count = re.subn(
    r"def export_unified_data_excel\(.*?\n\ndef _resolve_content_columns\(",
    '''def export_unified_data_excel(
    records: Iterable[UnifiedDataExcelV1],
    output_path: Path,
    *,
    include_analysis: bool,
    content_columns: Iterable[str] | None = None,
) -> ExcelExportSummary:
    """使用 write-only Workbook 流式写出 UnifiedDataExcelV1 的受控展示视图。"""

    content_headers, content_indices = _resolve_content_columns(content_columns)
    target_path = Path(output_path)
    if target_path.suffix.lower() != ".xlsx":
        raise ValueError("统一 Excel 导出目标必须使用 .xlsx 扩展名")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".{target_path.stem}.tmp{target_path.suffix}")
    temp_path.unlink(missing_ok=True)

    workbook = Workbook(write_only=True)
    content_sheet = workbook.create_sheet(_CONTENT_SHEET)
    label_sheet = workbook.create_sheet(_LABEL_SHEET)
    comment_sheet = workbook.create_sheet(_COMMENT_SHEET)
    _configure_sheet(content_sheet, content_headers, _CONTENT_COLUMN_WIDTHS)
    _configure_sheet(label_sheet, _LABEL_HEADERS, _LABEL_COLUMN_WIDTHS)
    _configure_sheet(comment_sheet, _COMMENT_HEADERS, _COMMENT_COLUMN_WIDTHS)
    content_sheet.append(_header_cells(content_sheet, content_headers))
    label_sheet.append(_header_cells(label_sheet, _LABEL_HEADERS))
    comment_sheet.append(_header_cells(comment_sheet, _COMMENT_HEADERS))

    content_rows = 0
    label_rows = 0
    comment_rows = 0
    first_content_id: str | None = None
    first_label_content_id: str | None = None
    first_comment_id: str | None = None
    try:
        for record in records:
            content = record.content
            content_sheet.append(
                _content_cells(
                    content_sheet,
                    content,
                    include_analysis,
                    column_indices=content_indices,
                )
            )
            content_rows += 1
            if first_content_id is None:
                first_content_id = content.external_content_id
            if include_analysis:
                for pair in _analysis_label_pairs(content.analysis):
                    label_sheet.append(_label_detail_cells(label_sheet, content, pair))
                    label_rows += 1
                    if first_label_content_id is None:
                        first_label_content_id = content.external_content_id
            for comment in record.comments:
                comment_sheet.append(_comment_cells(comment_sheet, comment))
                comment_rows += 1
                if first_comment_id is None:
                    first_comment_id = comment.external_comment_id
        _set_auto_filter(content_sheet, len(content_headers), content_rows)
        _set_auto_filter(label_sheet, len(_LABEL_HEADERS), label_rows)
        _set_auto_filter(comment_sheet, len(_COMMENT_HEADERS), comment_rows)
        workbook.save(temp_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        workbook.close()

    try:
        _verify_workbook(
            temp_path,
            content_headers=content_headers,
            content_rows=content_rows,
            label_rows=label_rows,
            comment_rows=comment_rows,
            first_content_id=first_content_id,
            first_label_content_id=first_label_content_id,
            first_comment_id=first_comment_id,
        )
        os.replace(temp_path, target_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    return ExcelExportSummary(
        output_path=target_path,
        content_rows=content_rows,
        comment_rows=comment_rows,
        label_rows=label_rows,
    )


def _resolve_content_columns(''',
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("excel export function replacement failed")
text, count = re.subn(
    r"def _iter_unified_content_jsonl\(path: Path\) -> Iterator\[UnifiedDataExcelV1\]:.*?\n\ndef _content_cells\(",
    '''def _iter_unified_content_jsonl(path: Path) -> Iterator[UnifiedDataExcelV1]:
    with path.open("rb") as input_file:
        for line_number, raw_line in enumerate(input_file, start=1):
            if not raw_line.strip():
                raise ValueError(f"{path}: 第 {line_number} 行为空，拒绝导出")
            try:
                record = UnifiedContentRecordV1.model_validate_json(raw_line)
            except ValidationError as exc:
                raise ValueError(
                    f"{path}: 第 {line_number} 行不是合法 UnifiedContentRecordV1"
                ) from exc
            analysis = None
            if record.analysis is not None:
                if isinstance(record.analysis, ContentLabelAnalysisV2):
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
                analysis = UnifiedDataExcelAnalysisV1(
                    sentiment=record.analysis.sentiment,
                    primary_label=primary_label,
                    secondary_label=secondary_label,
                    label_pairs=label_pairs,
                    model=record.analysis.model,
                    prompt_version=record.analysis.prompt_version,
                    taxonomy_version=record.analysis.taxonomy_sha256,
                )
            yield UnifiedDataExcelV1(
                content=project_canonical_content(
                    record.content,
                    matched_keywords=record.matched_keywords,
                    analysis=analysis,
                )
            )


def _analysis_label_pairs(
    analysis: UnifiedDataExcelAnalysisV1 | None,
) -> tuple[UnifiedDataExcelLabelPairV1, ...]:
    if analysis is None:
        return ()
    if analysis.label_pairs:
        return analysis.label_pairs
    return (
        UnifiedDataExcelLabelPairV1(
            primary_label=analysis.primary_label,
            secondary_label=analysis.secondary_label,
        ),
    )


def _content_cells(''',
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("excel JSONL projection replacement failed")
marker = "\ndef _comment_cells(sheet: Any, comment: UnifiedDataExcelCommentV1) -> list[Cell]:\n"
if text.count(marker) != 1:
    raise RuntimeError("excel comment marker mismatch")
text = text.replace(
    marker,
    '''
def _label_detail_cells(
    sheet: Any,
    content: UnifiedDataExcelContentV1,
    pair: UnifiedDataExcelLabelPairV1,
) -> list[Cell]:
    analysis = content.analysis
    if analysis is None:
        raise ValueError("标签明细只能从存在 Analysis 的内容生成")
    values: tuple[tuple[_ExcelCellValue, bool, bool], ...] = (
        (content.external_content_id, True, False),
        (content.platform, False, False),
        (content.title, False, False),
        (analysis.sentiment, False, False),
        (pair.primary_label, False, False),
        (pair.secondary_label, False, False),
        (content.content_url, False, True),
    )
    return [
        _data_cell(sheet, value, text_id=text_id, hyperlink=hyperlink)
        for value, text_id, hyperlink in values
    ]


def _comment_cells(sheet: Any, comment: UnifiedDataExcelCommentV1) -> list[Cell]:
''',
    1,
)
old = '''    if hyperlink and isinstance(value, str) and _is_http_url(value):
        cell.hyperlink = value
        cell.style = "Hyperlink"
    return cell
'''
new = '''    if hyperlink and isinstance(value, str) and _is_http_url(value):
        cell.hyperlink = value
        cell.style = "Hyperlink"
    if isinstance(safe_value, str) and "\\n" in safe_value:
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    return cell
'''
if text.count(old) != 1:
    raise RuntimeError("excel data cell block mismatch")
text = text.replace(old, new, 1)
text, count = re.subn(
    r"def _verify_workbook\(.*?\n\ndef _verify_sheet\(",
    '''def _verify_workbook(
    path: Path,
    *,
    content_headers: tuple[str, ...],
    content_rows: int,
    label_rows: int,
    comment_rows: int,
    first_content_id: str | None,
    first_label_content_id: str | None,
    first_comment_id: str | None,
) -> None:
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        if workbook.sheetnames != [_CONTENT_SHEET, _LABEL_SHEET, _COMMENT_SHEET]:
            raise OSError("统一 Excel 导出后 Sheet 结构校验失败")
        content_id_column = (
            content_headers.index("内容ID") + 1 if "内容ID" in content_headers else None
        )
        _verify_sheet(
            workbook[_CONTENT_SHEET],
            content_headers,
            expected_rows=content_rows,
            first_id=first_content_id,
            id_column=content_id_column,
        )
        _verify_sheet(
            workbook[_LABEL_SHEET],
            _LABEL_HEADERS,
            expected_rows=label_rows,
            first_id=first_label_content_id,
            id_column=1,
        )
        _verify_sheet(
            workbook[_COMMENT_SHEET],
            _COMMENT_HEADERS,
            expected_rows=comment_rows,
            first_id=first_comment_id,
            id_column=4,
        )
    finally:
        workbook.close()


def _verify_sheet(''',
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("excel verification replacement failed")
write(path, text)

path = "backend/src/aima_ugc/adapters/providers/imports_test/test.py"
text = read(path)
text = text.replace("from zoneinfo import ZoneInfo\n", "from zoneinfo import ZoneInfo\n", 1) if "from zoneinfo import ZoneInfo" in text else text.replace("from typing import Any\n", "from typing import Any\nfrom zoneinfo import ZoneInfo\n", 1)
text = text.replace(
    '_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")',
    '_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._+-]+$")\n_BEIJING = ZoneInfo("Asia/Shanghai")',
    1,
)
text = text.replace(
    "    run_id: str\n    run_summary_path: Path\n    labeled_excel_path: Path",
    "    run_id: str\n    run_dir: Path\n    run_summary_path: Path\n    labeled_excel_path: Path",
    1,
)
text, count = re.subn(
    r"def convert\(\) -> ExcelConversionSummary:.*?\n\ndef _stage_payload\(",
    '''def prepare_run_dir(*, run_id: str | None = None) -> Path:
    """创建一次独立人工运行目录；显式 run_id 不允许覆盖既有目录。"""

    actual_run_id = _resolve_run_id(run_id)
    run_dir = OUTPUT_ROOT / "runs" / actual_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _stage_run_dir(run_dir: Path | None) -> Path:
    if run_dir is None:
        return prepare_run_dir()
    actual = Path(run_dir)
    if not actual.is_dir():
        raise FileNotFoundError(f"imports_test run_dir 不存在: {actual}")
    return actual


def convert(*, run_dir: Path | None = None) -> ExcelConversionSummary:
    """执行 XLSX → Canonical JSONL。"""

    actual_run_dir = _stage_run_dir(run_dir)
    return convert_excel_to_canonical_jsonl(
        input_path=INPUT_XLSX,
        output_path=actual_run_dir / "canonical" / "contents.jsonl",
        profile_name=PROFILE,
        sheet_name=SHEET_NAME,
    )


def filter_keywords(*, run_dir: Path | None = None) -> ContentFilterSummary:
    """执行 Canonical JSONL → 关键词命中过滤后的统一内容记录。"""

    actual_run_dir = _stage_run_dir(run_dir)
    return filter_canonical_content_jsonl(
        input_path=actual_run_dir / "canonical" / "contents.jsonl",
        output_path=actual_run_dir / "filtered" / "contents.jsonl",
        keywords=KEYWORDS,
    )


def deduplicate(*, run_dir: Path | None = None) -> ContentDeduplicationSummary:
    """执行 filtered JSONL → 稳定身份去重后的统一内容记录。"""

    actual_run_dir = _stage_run_dir(run_dir)
    return deduplicate_content_jsonl(
        input_path=actual_run_dir / "filtered" / "contents.jsonl",
        output_path=actual_run_dir / "deduplicated" / "contents.jsonl",
    )


def export_raw_excel(*, run_dir: Path | None = None) -> ExcelExportSummary:
    """可选导出当前 run 的未填分析标签人工审阅视图。"""

    actual_run_dir = _stage_run_dir(run_dir)
    return export_unified_content_jsonl_to_excel(
        input_path=actual_run_dir / "deduplicated" / "contents.jsonl",
        output_path=actual_run_dir / "raw_data.xlsx",
        include_analysis=False,
        content_columns=EXCEL_CONTENT_COLUMNS,
    )


def label_sentiment(*, run_dir: Path | None = None) -> OfflineContentLabelingSummary:
    """显式启用真实 LLM 后，对当前 run 的 deduplicated JSONL 做打标。"""

    if not ENABLE_REAL_LLM:
        raise RuntimeError("真实 LLM 默认关闭；确认费用后将 ENABLE_REAL_LLM 改为 True")

    actual_run_dir = _stage_run_dir(run_dir)
    env = _load_env_file(ENV_FILE)
    timeout_seconds = _parse_positive_float(
        env.get(
            "AIMA_LLM_TIMEOUT_SECONDS",
            str(DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS),
        ),
        name="AIMA_LLM_TIMEOUT_SECONDS",
    )
    prompt_loader = PromptTaxonomyLoader(CONTENT_LABELING_PROMPT_PATH)
    recovery_taxonomy = prompt_loader.load()
    with OpenAICompatibleContentLabelingLLM(
        base_url=_require_env(env, "AIMA_LLM_BASE_URL"),
        api_key=SecretStr(_require_env(env, "AIMA_LLM_API_KEY")),
        model=_require_env(env, "AIMA_LLM_MODEL"),
        timeout_seconds=timeout_seconds,
    ) as llm:
        service = ContentLabelingService(
            prompt_loader=prompt_loader,
            llm=llm,
        )
        return label_unified_content_jsonl(
            input_path=actual_run_dir / "deduplicated" / "contents.jsonl",
            analysis_dir=actual_run_dir / "analysis",
            service=service,
            max_validation_retries=MAX_VALIDATION_RETRIES,
            batch_size=LLM_BATCH_SIZE,
            recovery_taxonomy=recovery_taxonomy,
        )


def export_labeled_excel(
    *,
    run_dir: Path | None = None,
    run_id: str | None = None,
) -> ExcelExportSummary:
    """从当前 run 回写后的 deduplicated JSONL 导出最终带 Analysis 的 Excel。"""

    actual_run_dir = prepare_run_dir(run_id=run_id) if run_dir is None else _stage_run_dir(run_dir)
    return export_unified_content_jsonl_to_excel(
        input_path=actual_run_dir / "deduplicated" / "contents.jsonl",
        output_path=_labeled_output_path(actual_run_dir),
        include_analysis=True,
        content_columns=EXCEL_CONTENT_COLUMNS,
    )


def run_all(*, run_id: str | None = None) -> P1RunSummary:
    """创建一次独立 run 目录并按固定顺序执行完整链路。"""

    actual_run_id = _resolve_run_id(run_id)
    run_dir = prepare_run_dir(run_id=actual_run_id)
    stages: list[dict[str, object]] = []

    conversion = convert(run_dir=run_dir)
    stages.append(_stage_payload("convert", conversion))

    filtering = filter_keywords(run_dir=run_dir)
    stages.append(_stage_payload("filter_keywords", filtering))

    deduplication = deduplicate(run_dir=run_dir)
    stages.append(_stage_payload("deduplicate", deduplication))

    labeling = label_sentiment(run_dir=run_dir)
    stages.append(_stage_payload("label_sentiment", labeling))

    labeled_export = export_labeled_excel(run_dir=run_dir)
    stages.append(_stage_payload("export_labeled_excel", labeled_export))

    run_summary_path = run_dir / "run_summary.json"
    labeled_excel_path = _labeled_output_path(run_dir)
    _atomic_write_json(
        run_summary_path,
        {
            "schema_version": "p1-run-summary.v1",
            "run_id": actual_run_id,
            "source_xlsx": str(INPUT_XLSX),
            "output_root": str(OUTPUT_ROOT),
            "run_dir": str(run_dir),
            "labeled_excel": str(labeled_excel_path),
            "stages": stages,
        },
    )
    return P1RunSummary(
        run_id=actual_run_id,
        run_dir=run_dir,
        run_summary_path=run_summary_path,
        labeled_excel_path=labeled_excel_path,
    )


def _resolve_run_id(run_id: str | None) -> str:
    value = run_id or datetime.now(UTC).astimezone(_BEIJING).strftime("%Y%m%dT%H%M%S.%f%z")
    if not _RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("run_id 只允许字母、数字、点、加号、下划线和连字符")
    return value


def _labeled_output_path(run_dir: Path) -> Path:
    return Path(run_dir) / "labeled_data.xlsx"


def _stage_payload(''',
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("imports_test stage block replacement failed")
write(path, text)

path = "scripts/contracts/generate.py"
text = read(path)
text = text.replace(
    "from aima_ugc.contracts.analysis import ContentLabelAnalysisV1, UnifiedContentRecordV1",
    "from aima_ugc.contracts.analysis import (\n    ContentLabelAnalysisV1,\n    ContentLabelAnalysisV2,\n    UnifiedContentRecordV1,\n)",
    1,
)
text = text.replace(
    '    "content-label-analysis.v1.schema.json": ContentLabelAnalysisV1,\n    "content-record.v1.schema.json": UnifiedContentRecordV1,',
    '    "content-label-analysis.v1.schema.json": ContentLabelAnalysisV1,\n    "content-label-analysis.v2.schema.json": ContentLabelAnalysisV2,\n    "content-record.v1.schema.json": UnifiedContentRecordV1,',
    1,
)
write(path, text)

# Existing regression tests: keep old V1 behavior readable while updating workbook/run layout facts.
path = "tests/unit/platform/test_excel_export.py"
text = read(path)
text = text.replace('assert workbook.sheetnames == ["内容", "评论"]', 'assert workbook.sheetnames == ["内容", "标签明细", "评论"]', 1)
text = text.replace(
    'assert raw_workbook.sheetnames == labeled_workbook.sheetnames == ["内容", "评论"]',
    'assert raw_workbook.sheetnames == labeled_workbook.sheetnames == ["内容", "标签明细", "评论"]',
    1,
)
write(path, text)

path = "tests/unit/collection/test_imports_test_export.py"
text = read(path)
text = text.replace(
    '    deduplicated = output_root / "deduplicated" / "contents.jsonl"\n    deduplicated.parent.mkdir(parents=True)',
    '    run_dir = output_root / "runs" / "test-run"\n    run_dir.mkdir(parents=True)\n    deduplicated = run_dir / "deduplicated" / "contents.jsonl"\n    deduplicated.parent.mkdir(parents=True)',
    1,
)
text = text.replace('    summary = imports_test_entry.export_raw_excel()', '    summary = imports_test_entry.export_raw_excel(run_dir=run_dir)', 1)
text = text.replace('    assert summary.output_path == output_root / "raw_data.xlsx"', '    assert summary.output_path == run_dir / "raw_data.xlsx"', 1)
text = text.replace('        assert workbook.sheetnames == ["内容", "评论"]', '        assert workbook.sheetnames == ["内容", "标签明细", "评论"]', 1)
write(path, text)

path = "tests/unit/collection/test_p1g_imports_run_all.py"
text = read(path)
text = text.replace(
    '    assert summary.run_summary_path == output_root / "run_summary.json"\n',
    '    run_dir = output_root / "runs" / "20260818T160000Z"\n    assert summary.run_dir == run_dir\n    assert summary.run_summary_path == run_dir / "run_summary.json"\n',
    1,
)
text = text.replace(
    '    imports_test_entry.export_labeled_excel(run_id="20260818T160000Z")\n\n    assert captured == {\n        "input_path": output_root / "deduplicated" / "contents.jsonl",\n        "output_path": output_root / "爱玛监测_20260818T160000Z_labeled_data.xlsx",',
    '    imports_test_entry.export_labeled_excel(run_id="20260818T160000Z")\n\n    run_dir = output_root / "runs" / "20260818T160000Z"\n    assert captured == {\n        "input_path": run_dir / "deduplicated" / "contents.jsonl",\n        "output_path": run_dir / "labeled_data.xlsx",',
    1,
)
write(path, text)

# README: keep it as a direct user guide rather than a development-history document.
write(
    "backend/src/aima_ugc/adapters/providers/imports_test/README.md",
    '''# Excel 离线导入、清洗与 AI 多标签打标

本目录提供一个可直接运行的人工入口，把本地舆情 Excel 依次完成：

```text
读取 Excel
→ 转为统一 Canonical JSONL
→ 按关键词过滤
→ 稳定身份去重
→ AI 情感 + 多个一级/二级标签对
→ 导出最终 Excel
```

入口：

```text
backend/src/aima_ugc/adapters/providers/imports_test/test.py
```

脚本复用系统正式 Excel Reader、Canonical Mapper、关键词处理、去重、Analysis Service、LLM Adapter 和共享 Excel Exporter，不需要数据库或 Scheduler。

## 1. 修改顶部配置

至少修改：

```python
INPUT_XLSX = Path(r"E:\\path\\to\\source.xlsx")
OUTPUT_ROOT = Path(__file__).with_name("output")
KEYWORDS = ("爱玛",)
SHEET_NAME = "文章"
PROFILE = "aima-monitoring-excel.v1"

EXCEL_CONTENT_COLUMNS = (
    "平台",
    "标题",
    "正文",
    "作者",
    "发布时间",
    "内容链接",
    "命中关键词",
    "情感标签",
    "一级标签",
    "二级标签",
)

ENABLE_REAL_LLM = True
MAX_VALIDATION_RETRIES = 2
LLM_BATCH_SIZE = 20
```

`EXCEL_CONTENT_COLUMNS` 的顺序就是“内容”Sheet 的列顺序。只能使用共享 Exporter 已定义的列；空、重复或未知列会直接报错。

## 2. 配置模型 `.env`

复制 `.env.example` 为 `.env`，填写：

```dotenv
AIMA_LLM_BASE_URL=
AIMA_LLM_API_KEY=
AIMA_LLM_MODEL=

# 可选；不配置默认 60 秒
# AIMA_LLM_TIMEOUT_SECONDS=60
```

只有 Base URL、API Key、Model 必填。当前入口固定使用 OpenAI-compatible Chat Completions Adapter；JSON mode 默认开启。真实 `.env` 已被 Git 忽略，不要把 API Key 写进源码、README、测试、日志或提交记录。

## 3. 运行

```powershell
D:\\python314\\python.exe E:\\work\\03_Aima\\code\\AIMA_UGC\\backend\\src\\aima_ugc\\adapters\\providers\\imports_test\\test.py
```

直接执行会调用：

```text
run_all()
```

每次 `run_all()` 先创建一个独立 run 目录，再让所有阶段使用同一个目录。默认 run_id 使用北京时间并显式带 `+0800`：

```text
20260819T142000.123456+0800
```

输出结构：

```text
output/
└─ runs/
   └─ <run-id>/
      ├─ canonical/
      │  └─ contents.jsonl
      ├─ filtered/
      │  └─ contents.jsonl
      ├─ deduplicated/
      │  └─ contents.jsonl
      ├─ analysis/
      │  ├─ checkpoints.jsonl
      │  ├─ attempts.jsonl
      │  └─ failed.jsonl
      ├─ labeled_data.xlsx
      └─ run_summary.json
```

只有显式调用 `export_raw_excel(run_dir=...)` 时，当前 run 目录还会生成 `raw_data.xlsx`。

不同 run 不覆盖彼此。显式复用已经存在的 run_id 会直接报 `FileExistsError`，防止误覆盖旧结果。

## 4. 单步运行

如果需要逐阶段调试，先创建一次 run 目录，然后把同一个 `run_dir` 传给后续函数：

```python
run_dir = prepare_run_dir()

convert(run_dir=run_dir)
filter_keywords(run_dir=run_dir)
deduplicate(run_dir=run_dir)
label_sentiment(run_dir=run_dir)
export_labeled_excel(run_dir=run_dir)
```

不要分别无参数调用 `filter_keywords()`、`deduplicate()` 等依赖上一步输入的函数；它们需要读取同一次 run 的上游文件。

## 5. AI 多标签结构

每条内容仍只有一个整体情感：

```text
正面 / 中性 / 负面 / 混合
```

但可以有一个或多个一级/二级标签对。例如：

```text
骑行性能 / 舒适性
售后服务 / 客服与服务态度
```

系统保存的是成对结构，不是两个互不关联的数组，因此不会丢失“二级标签属于哪个一级标签”的关系。模型输出经过本地 Taxonomy Validator；未知标签、错误父子关系、空标签、重复标签对都不会被静默接受。

历史 `content-label-analysis.v1` 单标签 JSONL/checkpoint 仍可读取；新的模型成功结果写 `content-label-analysis.v2`。

## 6. Excel 怎么展示和筛选多标签

最终 Workbook 有三个 Sheet：

```text
内容
标签明细
评论
```

### 内容

仍保持“一条内容一行”，所以帖子数量不会因为标签多而被放大。

如果一条内容有两个标签对：

```text
骑行性能 / 舒适性
售后服务 / 客服与服务态度
```

“一级标签”单元格显示：

```text
骑行性能
售后服务
```

“二级标签”单元格显示：

```text
舒适性
客服与服务态度
```

两个单元格按同一标签对顺序逐行对应，并启用单元格换行。

### 标签明细

为了使用 Excel 普通下拉筛选，每个标签对单独一行：

```text
内容ID | 平台 | 标题 | 情感标签 | 一级标签 | 二级标签 | 内容链接
```

同一内容可以在该 Sheet 出现多行。因此筛选“一级标签 = 骑行性能”会命中它，筛选“一级标签 = 售后服务”也会命中同一内容。

做“内容总数”统计时以“内容”Sheet 为准；做标签筛选、标签频次、一级/二级组合统计时使用“标签明细”Sheet。

raw 导出也保留“标签明细”Sheet 表头，但 `include_analysis=False` 时不会伪造任何标签行。

## 7. 默认内容列与可选列

默认只显示：

```text
平台
标题
正文
作者
发布时间
内容链接
命中关键词
情感标签
一级标签
二级标签
```

想增加、删除或排序，只改 `EXCEL_CONTENT_COLUMNS`。当前可选内容列：

```text
平台
内容ID
来源项ID
内容类型
标题
正文
作者
发布时间
内容链接
作者粉丝数
作者关注数
作者内容数
作者获赞数
点赞
评论数
收藏数
分享数
转发数
浏览数
播放数
弹幕数
投币数
下载数
命中关键词
情感标签
一级标签
二级标签
分析模型
Prompt版本
Taxonomy版本
来源Provider
Raw/来源定位
评论覆盖
```

没有数据的列留空，不制造值。“标签明细”和“评论”Sheet 当前不使用 `EXCEL_CONTENT_COLUMNS` 做列裁剪。

## 8. Excel 公共格式

共享 Exporter 统一负责：

- 冻结首行 `A2`；
- 首行自动筛选；
- 表头 `#FFC000`；
- Calibri 11pt，表头粗体；
- 表头行高 16.5，正文默认行高 14.5；
- 显示网格线；
- 不合并单元格；
- HTTP/HTTPS 链接可点击；
- 多标签主表单元格使用换行；
- 页面纵向，左右页边距 0.7、上下 0.75；
- 使用固定有界列宽，不扫描 9 万行自动算宽度；
- openpyxl `write_only=True` 流式写出。

## 9. 源 Excel 输入要求

Profile：`aima-monitoring-excel.v1`，默认 Sheet：`文章`。必须存在以下 13 个表头，允许额外列：

```text
序号
监测项名称
文章编号
标题
内文
媒体名称（中文）
版面
出版日期
媒体类型
作者
全文情感
原文链接
粉丝数
```

平台字段会经过受控归一化；无法映射的平台、非法日期、非法粉丝数、缺稳定身份等都会写转换错误并 fail-closed，不发布半份 `contents.jsonl`。

## 10. 常见排错

- HTTP 401：模型服务认证失败，先独立验证 API Key；不要通过放宽 Analysis Validator 解决认证问题。
- `platform_unmapped`：源媒体/平台值无法映射到已知平台。
- `conversion_errors.jsonl`：先看转换阶段逐行错误。
- `analysis/attempts.jsonl`：看模型每次 Validation Attempt。
- `analysis/failed.jsonl`：看达到 Validation Retry 上限后仍失败的 item。
- `analysis/checkpoints.jsonl`：只保存已通过 Validator 的成功 Analysis，用于恢复和费用安全。
- run_id 已存在：说明该 run 已有历史产物；不要覆盖，使用新的 run_id。
''',
)

# Analysis README targeted truth updates.
path = "backend/src/aima_ugc/modules/analysis/README.md"
text = read(path)
text = text.replace("ContentLabelAnalysisV1", "ContentLabelAnalysisV2", 1)
text = text.replace(
    '''三个业务标签字段固定使用 `str`：

```text
sentiment
primary_label
secondary_label
```

具体允许值由当前 `PromptTaxonomy` 动态校验，不写进 Python Enum/Literal。''',
    '''当前成功结果使用：

```text
sentiment: str
labels: [
  {primary_label: str, secondary_label: str},
  ...
]
```

`sentiment` 恰好一个；`labels` 至少一个并允许多个。每个二级标签始终和所属一级标签成对保存，标签对不能重复。具体允许值仍由当前 `PromptTaxonomy` 动态校验，不写进 Python Enum/Literal。历史 `ContentLabelAnalysisV1` 保留只读兼容，新 Service 产生 `ContentLabelAnalysisV2`。''',
    1,
)
text = text.replace(
    "- 标签必须是非空单字符串，不能是数组；\n- sentiment 是否属于当前 Taxonomy；\n- primary 是否属于当前 Taxonomy；\n- secondary 是否属于当前 primary。",
    "- sentiment 必须是一个非空字符串；\n- labels 必须是非空标签对数组；\n- 标签对不能重复；\n- 每个 primary 是否属于当前 Taxonomy；\n- 每个 secondary 是否属于同一标签对中的 primary。",
    1,
)
text = text.replace("数组/空标签及其他结构错误", "空 labels、重复标签对、未知标签、父子错配及其他结构错误", 1)
text = text.replace(
    "审计文件：\n\n```text\nanalysis/checkpoints.jsonl",
    "checkpoint 中的 `analysis.schema_version` 决定 V1/V2。历史 V1 checkpoint 仍可恢复；新模型成功结果写 V2。\n\n审计文件：\n\n```text\nanalysis/checkpoints.jsonl",
    1,
)
write(path, text)

# Blueprint 13: workbook/search semantics.
path = "docs/blueprint/13-统一数据Excel导出与调试复用.md"
text = read(path)
text = text.replace(
    "Workbook 固定两个 Sheet：\n\n```text\n内容\n评论\n```",
    "Workbook 固定三个 Sheet：\n\n```text\n内容\n标签明细\n评论\n```",
    1,
)
text = text.replace(
    "- 情感、一级、二级标签必须来自当前 Analysis Validator 已批准的闭集；\n- 没有合法 Analysis 时保持为空，不用源 Excel 的“全文情感”或其他上游标签填充；\n- 是否显示这些列由最终 `content_columns` 投影决定，但不改变 Analysis 数据是否存在。",
    "- 情感标签仍为单值；一级/二级标签由 Analysis 的一个或多个合法标签对投影；\n- `内容` Sheet 保持一条内容一行，一级和二级单元格按同一标签对顺序用换行符逐行展示，两个单元格行与行对应；\n- `标签明细` Sheet 一个标签对一行，固定保存内容ID、平台、标题、情感、一级、二级、内容链接，用于 Excel 原生下拉筛选和标签统计；同一内容因此可以在标签明细中出现多行，但不会在内容 Sheet 重复；\n- 没有合法 Analysis 时内容标签列保持为空，标签明细只保留表头，不用源 Excel 的“全文情感”或其他上游标签填充；\n- 是否显示内容 Sheet 的 Analysis 列由 `content_columns` 决定，但不改变 Analysis 数据或标签明细关系。",
    1,
)
text = text.replace(
    "Sheet 定义\ncontent_columns",
    "三个 Sheet 定义\ncontent_columns",
    1,
)
text = text.replace(
    "- raw/labeled 同展示配置；",
    "- raw/labeled 同内容展示配置，标签明细 Sheet 结构也一致；",
    1,
)
write(path, text)

# Blueprint 15: replace single-label structural rules while preserving the taxonomy table.
path = "docs/blueprint/15-舆情AI打标与统一分析契约.md"
text = read(path)
text = text.replace("→ ContentLabelAnalysisV1", "→ ContentLabelAnalysisV2", 1)
text = text.replace("analysis: ContentLabelAnalysisV1", "analysis: ContentLabelAnalysisV1 | ContentLabelAnalysisV2", 1)
text, count = re.subn(
    r"### 3\.1 代码硬约束“结构和合法性”，不硬编码“标签内容”\n.*?\n## 4\.",
    '''### 3.1 代码硬约束“结构和合法性”，不硬编码“标签内容”

代码固定强制：

```text
每条结果恰好 1 个 sentiment
每条结果至少 1 个 labels 标签对
每个标签对恰好 1 个 primary_label + 1 个 secondary_label
同一条结果不得出现重复标签对
sentiment 必须属于当前 Prompt Taxonomy
每个 primary_label 必须属于当前 Prompt Taxonomy
每个 secondary_label 必须属于同一标签对中的 primary_label
批量 item 必须一一对应
不得缺项、重复 item、多余 item 或未声明字段
```

一条内容可以同时命中同一一级下多个二级，也可以同时命中多个一级。程序保存完整标签对，不把一级数组和二级数组分离，因此父子关系不会丢失。“标签不硬编码”不等于“相信模型自由输出”；最终写入系统的值仍然只能来自当前 Markdown 中的闭集。

历史 `ContentLabelAnalysisV1` 保留用于读取旧 JSONL/checkpoint；当前 Service 新生成的成功结果使用 `ContentLabelAnalysisV2`。

## 4.''',
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("blueprint15 section 3.1 replacement failed")
text, count = re.subn(
    r"## 9\. 模型输出 Contract：结构固定，标签动态\n.*?\n## 10\.",
    '''## 9. 模型输出 Contract：结构固定，标签动态

当前新成功结果使用 `ContentLabelAnalysisV2`：

```text
sentiment: str
labels: tuple[ContentLabelPairV2, ...]   # 至少 1 个
```

每个 `ContentLabelPairV2`：

```text
primary_label: str
secondary_label: str
```

程序固定保存的运行事实继续包括：

```text
schema_version
sentiment
labels
prompt_version
prompt_sha256
taxonomy_sha256
model_provider
model
input_hash
analyzed_at
analysis_status
```

模型只返回业务判断：

```json
{
  "items": [
    {
      "item_no": 1,
      "sentiment": "混合",
      "labels": [
        {"primary_label": "骑行性能", "secondary_label": "舒适性"},
        {"primary_label": "售后服务", "secondary_label": "客服与服务态度"}
      ]
    }
  ]
}
```

模型不负责伪造 model、Hash、时间等运行事实。为兼容历史离线样本/旧模型响应，Validator 可以把合法 V1 单标签响应解释为只有一个标签对；当前 Prompt V2 本身只要求 `labels[]` 形状，新 Service 始终写 V2。

## 10.''',
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("blueprint15 section 9 replacement failed")
text = text.replace(
    "- 一级标签不在 Prompt Taxonomy；\n- 二级标签不在当前一级下；\n- 返回数组、多标签、空标签或其他结构违反。",
    "- 任一一级标签不在 Prompt Taxonomy；\n- 任一二级标签不在同一标签对的一级下；\n- labels 为空、标签对重复、标签字段为空或其他结构违反。",
    1,
)
text, count = re.subn(
    r"## 15\. 未来数据库设计\n.*?\n## 16\.",
    '''## 15. 未来数据库设计

未来数据库不建议把当前标签做 PostgreSQL ENUM，否则只改 Prompt 无法生效。多标签是一对多关系，也不得用逗号/换行字符串塞进单列。

推荐由 Analysis Owner 分成分析结果父事实与标签对子事实：

```text
analysis_results
- content_id
- content/input_hash
- sentiment
- prompt_version
- prompt_sha256
- taxonomy_sha256
- model_provider
- model
- analyzed_at
- analysis_run_id

analysis_label_pairs
- analysis_result_id   FK → analysis_results
- ordinal              标签重要性顺序
- primary_label
- secondary_label
```

同一分析结果的 `(analysis_result_id, primary_label, secondary_label)` 应唯一；`ordinal` 保留模型经过 Validator 后的标签对顺序。正式表名、唯一约束、attempt/费用审计、历史策略和 Migration 在未来 Analysis 数据库阶段单独冻结；本次不建立表。

## 16.''',
    text,
    count=1,
    flags=re.DOTALL,
)
if count != 1:
    raise RuntimeError("blueprint15 database section replacement failed")
text = text.replace("ContentLabelAnalysisV1（固定结构，不硬编码业务标签枚举）", "ContentLabelAnalysisV2（一个情感 + N 个标签对，不硬编码业务标签枚举；V1 保留兼容）", 1)
text = text.replace(
    "- 单一级+二级改成多标签数组；\n- 增加三级标签；",
    "- 改变当前 `labels[]` 标签对结构或标签顺序语义；\n- 增加三级标签；",
    1,
)
write(path, text)

print("multilabel change applied")
