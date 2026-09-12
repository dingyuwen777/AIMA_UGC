"""从宽筛后的内容 JSONL 中筛出爱玛车型与竞品车型共现帖子。"""

from __future__ import annotations

import json
import os
import re
import shutil
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from aima_ugc.contracts.analysis import UnifiedContentRecordV1
from aima_ugc.contracts.export import UnifiedDataExcelV1
from aima_ugc.modules.analysis.relevance import normalize_keyword_match_text
from aima_ugc.platform.export import export_unified_data_excel, project_canonical_content
from aima_ugc.platform.time import beijing_now

INPUT_JSONL = Path(
    r"E:\work\03_Aima\code\AIMA_UGC\backend\src\aima_ugc\adapters\providers\imports_test\monitoring_excel_filter\output\runs\20260912T163435.487712+0800\deduplicated\contents.jsonl"
)
OUTPUT_ROOT = Path(__file__).with_name("output")
VEHICLE_CATALOG_FILE = Path(__file__).with_name("vehicle_catalog.json")

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._+-]+$")
_VEHICLE_PAIR_CONTENT_COLUMNS = (
    "平台",
    "内容ID",
    "来源项ID",
    "内容类型",
    "标题",
    "正文",
    "作者",
    "发布时间",
    "内容链接",
    "作者粉丝数",
    "作者关注数",
    "作者内容数",
    "作者获赞数",
    "点赞",
    "评论数",
    "收藏数",
    "分享数",
    "转发数",
    "浏览数",
    "播放数",
    "弹幕数",
    "投币数",
    "下载数",
    "命中关键词",
    "品牌",
    "品牌角色",
    "竞品范围",
    "车型",
    "来源Provider",
    "Raw/来源定位",
)


class VehicleModelConfig(BaseModel):
    """描述一个车型标准名及其附加匹配别名。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=200)
    aliases: tuple[str, ...] = ()

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        """清理车型标准名两端空白。"""

        return value.strip() if isinstance(value, str) else value

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """清理车型别名并拒绝空值或同一车型内的规范化重复。"""

        cleaned = tuple(item.strip() for item in value)
        if any(not item for item in cleaned):
            raise ValueError("车型 alias 不能为空")
        normalized = tuple(normalize_keyword_match_text(item) for item in cleaned)
        if any(not item for item in normalized):
            raise ValueError("车型 alias 规范化后不能为空")
        if len(normalized) != len(set(normalized)):
            raise ValueError("同一车型的 alias 规范化后不能重复")
        return cleaned


class VehicleBrandConfig(BaseModel):
    """描述一个品牌及其需要参与二次筛选的车型。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=200)
    models: tuple[VehicleModelConfig, ...] = Field(min_length=1)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        """清理品牌名称两端空白。"""

        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_model_names(self) -> VehicleBrandConfig:
        """拒绝同一品牌下规范化后重复的车型标准名。"""

        identities = tuple(normalize_keyword_match_text(item.name) for item in self.models)
        if any(not item for item in identities):
            raise ValueError("车型标准名规范化后不能为空")
        if len(identities) != len(set(identities)):
            raise ValueError(f"品牌 {self.name} 下存在重复车型标准名")
        return self


class VehiclePairCatalog(BaseModel):
    """冻结一次离线车型共现筛选所需的品牌/车型目录。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["vehicle-pair-catalog.v1"] = "vehicle-pair-catalog.v1"
    target_brand: str = Field(min_length=1, max_length=200)
    brands: tuple[VehicleBrandConfig, ...] = Field(min_length=2)

    @field_validator("target_brand", mode="before")
    @classmethod
    def trim_target_brand(cls, value: object) -> object:
        """清理目标品牌名称两端空白。"""

        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_catalog(self) -> VehiclePairCatalog:
        """保证目标品牌存在、存在竞品车型且 alias 不会跨车型歧义。"""

        brand_ids = tuple(item.name.casefold() for item in self.brands)
        if len(brand_ids) != len(set(brand_ids)):
            raise ValueError("品牌名称不能重复")

        target_id = self.target_brand.casefold()
        target = next((item for item in self.brands if item.name.casefold() == target_id), None)
        if target is None:
            raise ValueError("target_brand 必须存在于 brands 中")
        if not target.models:
            raise ValueError("目标品牌至少需要一个车型")

        competitor_model_count = sum(
            len(item.models) for item in self.brands if item.name.casefold() != target_id
        )
        if competitor_model_count == 0:
            raise ValueError("至少需要一个非目标品牌车型")

        alias_owner: dict[str, tuple[str, str]] = {}
        for brand in self.brands:
            for model in brand.models:
                owner = (brand.name, model.name)
                for alias in (model.name, *model.aliases):
                    normalized = normalize_keyword_match_text(alias)
                    if not normalized:
                        raise ValueError(f"车型 alias 规范化后不能为空: {brand.name}/{model.name}")
                    previous = alias_owner.get(normalized)
                    if previous is not None and previous != owner:
                        raise ValueError(
                            "车型 alias 不能同时归属于多个车型: "
                            f"{alias!r} -> {previous[0]}/{previous[1]} 与 {brand.name}/{model.name}"
                        )
                    alias_owner[normalized] = owner
        return self


class VehicleModelReference(BaseModel):
    """输出中一个已命中的品牌车型引用。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    brand: str
    model: str


class VehiclePairReference(BaseModel):
    """输出中一个爱玛车型与竞品车型的实际共现组合。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_model: str
    competitor_brand: str
    competitor_model: str


class VehicleModelMention(BaseModel):
    """记录一个车型在标题/正文中的命中证据。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    brand: str
    model: str
    fields: tuple[Literal["title", "text"], ...]
    matched_aliases: tuple[str, ...]


class VehiclePairRecordV1(BaseModel):
    """保持一帖一行，并附加该帖实际车型共现关系。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["vehicle-pair-record.v1"] = "vehicle-pair-record.v1"
    record: UnifiedContentRecordV1
    matched_target_models: tuple[str, ...]
    matched_competitor_models: tuple[VehicleModelReference, ...]
    matched_pairs: tuple[VehiclePairReference, ...]
    model_mentions: tuple[VehicleModelMention, ...]


@dataclass(frozen=True, slots=True)
class _PreparedAlias:
    """保存一个展示 alias 及其匹配规范化值。"""

    display_text: str
    match_text: str


@dataclass(frozen=True, slots=True)
class _PreparedModel:
    """保存一次运行中可直接执行匹配的车型配置。"""

    brand: str
    model: str
    is_target: bool
    aliases: tuple[_PreparedAlias, ...]


@dataclass(frozen=True, slots=True)
class _PostModelMatches:
    """保存一篇帖子中所有目标车型、竞品车型及字段命中证据。"""

    target_models: tuple[str, ...]
    competitor_models: tuple[VehicleModelReference, ...]
    mentions: tuple[VehicleModelMention, ...]


@dataclass(frozen=True, slots=True)
class VehiclePairFilterRunSummary:
    """记录一次车型共现二次筛选的统计和产物路径。"""

    run_id: str
    run_dir: Path
    input_path: Path
    catalog_path: Path
    output_path: Path
    workbook_path: Path
    run_summary_path: Path
    target_brand: str
    brand_count: int
    target_model_count: int
    competitor_model_count: int
    rows_seen: int
    rows_with_target_model: int
    rows_with_competitor_model: int
    rows_with_cross_brand_pair: int
    rows_filtered_out: int
    target_model_counts: dict[str, int]
    competitor_model_counts: dict[str, int]
    pair_counts: dict[str, int]


def load_vehicle_catalog(path: Path) -> VehiclePairCatalog:
    """从 JSON 文件加载并严格校验车型目录。"""

    catalog_path = Path(path)
    if not catalog_path.is_file():
        raise FileNotFoundError(catalog_path)
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"车型目录 JSON 非法: {catalog_path}: {exc}") from exc
    try:
        return VehiclePairCatalog.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"车型目录校验失败: {catalog_path}: {exc}") from exc


def prepare_run_dir(*, output_root: Path, run_id: str | None = None) -> tuple[str, Path]:
    """创建一次独立输出目录，避免覆盖既有筛选结果。"""

    actual_run_id = _resolve_run_id(run_id)
    run_dir = Path(output_root) / "runs" / actual_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return actual_run_id, run_dir


def filter_vehicle_pairs(
    *,
    input_path: Path,
    catalog_path: Path,
    output_root: Path,
    run_id: str | None = None,
) -> VehiclePairFilterRunSummary:
    """流式筛出同时命中目标品牌车型和任一竞品车型的帖子，并同步导出 Excel。"""

    source_path = Path(input_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    catalog = load_vehicle_catalog(catalog_path)
    prepared_models = _prepare_models(catalog)
    target_id = catalog.target_brand.casefold()
    target_model_count = sum(
        len(brand.models) for brand in catalog.brands if brand.name.casefold() == target_id
    )
    competitor_model_count = sum(
        len(brand.models) for brand in catalog.brands if brand.name.casefold() != target_id
    )

    actual_run_id, run_dir = prepare_run_dir(output_root=output_root, run_id=run_id)
    output_path = run_dir / "comparison_posts.jsonl"
    workbook_path = run_dir / "comparison_posts.xlsx"
    run_summary_path = run_dir / "run_summary.json"

    try:
        rows_seen = 0
        rows_with_target_model = 0
        rows_with_competitor_model = 0
        rows_with_cross_brand_pair = 0
        target_model_counts: Counter[str] = Counter()
        competitor_model_counts: Counter[str] = Counter()
        pair_counts: Counter[str] = Counter()

        temp_path = output_path.with_name(f".{output_path.name}.tmp")
        temp_path.unlink(missing_ok=True)
        try:
            with (
                source_path.open("rb") as source_file,
                temp_path.open("w", encoding="utf-8", newline="\n") as output_file,
            ):
                for line_number, raw_line in enumerate(source_file, start=1):
                    if not raw_line.strip():
                        continue
                    rows_seen += 1
                    record = _parse_input_record(
                        raw_line,
                        input_path=source_path,
                        line_number=line_number,
                    )
                    matches = _match_post_models(record, prepared_models)
                    if matches.target_models:
                        rows_with_target_model += 1
                    if matches.competitor_models:
                        rows_with_competitor_model += 1
                    if not matches.target_models or not matches.competitor_models:
                        continue

                    result = _build_output_record(record=record, matches=matches)
                    output_file.write(result.model_dump_json())
                    output_file.write("\n")
                    rows_with_cross_brand_pair += 1

                    for model in matches.target_models:
                        target_model_counts[model] += 1
                    for competitor in matches.competitor_models:
                        competitor_model_counts[f"{competitor.brand}/{competitor.model}"] += 1
                    for pair in result.matched_pairs:
                        pair_counts[
                            f"{pair.target_model}|{pair.competitor_brand}|{pair.competitor_model}"
                        ] += 1

                output_file.flush()
                os.fsync(output_file.fileno())
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
        os.replace(temp_path, output_path)

        excel_summary = export_unified_data_excel(
            _iter_vehicle_pair_excel_records(output_path),
            workbook_path,
            include_analysis=False,
            content_columns=_VEHICLE_PAIR_CONTENT_COLUMNS,
        )
        if excel_summary.content_rows != rows_with_cross_brand_pair:
            raise RuntimeError("车型共现 Excel 内容行数与 JSONL 共现帖子数不一致")
        if excel_summary.comment_rows != 0 or excel_summary.label_rows != 0:
            raise RuntimeError("车型共现 Excel 不应生成评论或标签明细数据行")

        summary = VehiclePairFilterRunSummary(
            run_id=actual_run_id,
            run_dir=run_dir,
            input_path=source_path,
            catalog_path=Path(catalog_path),
            output_path=output_path,
            workbook_path=workbook_path,
            run_summary_path=run_summary_path,
            target_brand=catalog.target_brand,
            brand_count=len(catalog.brands),
            target_model_count=target_model_count,
            competitor_model_count=competitor_model_count,
            rows_seen=rows_seen,
            rows_with_target_model=rows_with_target_model,
            rows_with_competitor_model=rows_with_competitor_model,
            rows_with_cross_brand_pair=rows_with_cross_brand_pair,
            rows_filtered_out=rows_seen - rows_with_cross_brand_pair,
            target_model_counts=dict(sorted(target_model_counts.items())),
            competitor_model_counts=dict(sorted(competitor_model_counts.items())),
            pair_counts=dict(sorted(pair_counts.items())),
        )
        _write_run_summary(summary)
        return summary
    except BaseException:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise


def _prepare_models(catalog: VehiclePairCatalog) -> tuple[_PreparedModel, ...]:
    """把车型目录编译为按配置顺序执行的去重 alias 匹配表。"""

    target_id = catalog.target_brand.casefold()
    prepared: list[_PreparedModel] = []
    for brand in catalog.brands:
        for model in brand.models:
            seen: set[str] = set()
            aliases: list[_PreparedAlias] = []
            for display_text in (model.name, *model.aliases):
                match_text = normalize_keyword_match_text(display_text)
                if match_text in seen:
                    continue
                aliases.append(_PreparedAlias(display_text=display_text, match_text=match_text))
                seen.add(match_text)
            prepared.append(
                _PreparedModel(
                    brand=brand.name,
                    model=model.name,
                    is_target=brand.name.casefold() == target_id,
                    aliases=tuple(aliases),
                )
            )
    return tuple(prepared)


def _parse_input_record(
    raw_line: bytes,
    *,
    input_path: Path,
    line_number: int,
) -> UnifiedContentRecordV1:
    """按正式 UnifiedContentRecordV1 校验一行输入并附带定位错误。"""

    try:
        return UnifiedContentRecordV1.model_validate_json(raw_line)
    except (ValidationError, ValueError) as exc:
        raise ValueError(
            f"输入 JSONL 第 {line_number} 行不符合 UnifiedContentRecordV1: {input_path}"
        ) from exc


def _match_post_models(
    record: UnifiedContentRecordV1,
    prepared_models: tuple[_PreparedModel, ...],
) -> _PostModelMatches:
    """分别扫描标题和正文，一次得到帖子实际命中的全部车型集合。"""

    normalized_fields = {
        "title": normalize_keyword_match_text(record.content.title or ""),
        "text": normalize_keyword_match_text(record.content.text or ""),
    }
    target_models: list[str] = []
    competitor_models: list[VehicleModelReference] = []
    mentions: list[VehicleModelMention] = []

    for model in prepared_models:
        matched_fields: list[Literal["title", "text"]] = []
        matched_aliases: list[str] = []
        for alias in model.aliases:
            alias_matched = False
            for field_name in ("title", "text"):
                if alias.match_text and alias.match_text in normalized_fields[field_name]:
                    alias_matched = True
                    if field_name not in matched_fields:
                        matched_fields.append(field_name)
            if alias_matched:
                matched_aliases.append(alias.display_text)

        if not matched_fields:
            continue
        mentions.append(
            VehicleModelMention(
                brand=model.brand,
                model=model.model,
                fields=tuple(matched_fields),
                matched_aliases=tuple(matched_aliases),
            )
        )
        if model.is_target:
            target_models.append(model.model)
        else:
            competitor_models.append(VehicleModelReference(brand=model.brand, model=model.model))

    return _PostModelMatches(
        target_models=tuple(target_models),
        competitor_models=tuple(competitor_models),
        mentions=tuple(mentions),
    )


def _build_output_record(
    *,
    record: UnifiedContentRecordV1,
    matches: _PostModelMatches,
) -> VehiclePairRecordV1:
    """把一帖实际命中的两个车型集合转换为局部笛卡尔积 metadata。"""

    pairs = tuple(
        VehiclePairReference(
            target_model=target_model,
            competitor_brand=competitor.brand,
            competitor_model=competitor.model,
        )
        for target_model in matches.target_models
        for competitor in matches.competitor_models
    )
    return VehiclePairRecordV1(
        record=record,
        matched_target_models=matches.target_models,
        matched_competitor_models=matches.competitor_models,
        matched_pairs=pairs,
        model_mentions=matches.mentions,
    )


def _iter_vehicle_pair_excel_records(path: Path) -> Iterator[UnifiedDataExcelV1]:
    """从最终车型共现 JSONL 流式派生共享 Provider-neutral Excel 输入。"""

    with path.open("rb") as source_file:
        for line_number, raw_line in enumerate(source_file, start=1):
            if not raw_line.strip():
                continue
            try:
                pair_record = VehiclePairRecordV1.model_validate_json(raw_line)
            except (ValidationError, ValueError) as exc:
                raise ValueError(
                    f"车型共现 JSONL 第 {line_number} 行无法导出 Excel: {path}"
                ) from exc

            excel_content = project_canonical_content(
                pair_record.record.content,
                matched_keywords=pair_record.record.matched_keywords,
            )
            target_models = set(pair_record.matched_target_models)
            brands: list[str] = []
            roles: list[str] = []
            vehicles: list[str] = []
            for mention in pair_record.model_mentions:
                if mention.brand not in brands:
                    brands.append(mention.brand)
                    roles.append("owned" if mention.model in target_models else "competitor")
                if mention.model not in vehicles:
                    vehicles.append(mention.model)
            excel_content = excel_content.model_copy(
                update={
                    "brands": tuple(brands),
                    "brand_roles": tuple(roles),
                    "competition_scope": "mixed",
                    "vehicles": tuple(vehicles),
                }
            )
            yield UnifiedDataExcelV1(content=excel_content)


def _write_run_summary(summary: VehiclePairFilterRunSummary) -> None:
    """把成功运行统计原子写入 run_summary.json。"""

    payload: dict[str, object] = {
        "schema_version": "vehicle-pair-filter-run.v1",
        "run_id": summary.run_id,
        "input": str(summary.input_path),
        "catalog": str(summary.catalog_path),
        "target_brand": summary.target_brand,
        "brand_count": summary.brand_count,
        "target_model_count": summary.target_model_count,
        "competitor_model_count": summary.competitor_model_count,
        "rows_seen": summary.rows_seen,
        "rows_with_target_model": summary.rows_with_target_model,
        "rows_with_competitor_model": summary.rows_with_competitor_model,
        "rows_with_cross_brand_pair": summary.rows_with_cross_brand_pair,
        "rows_filtered_out": summary.rows_filtered_out,
        "target_model_counts": summary.target_model_counts,
        "competitor_model_counts": summary.competitor_model_counts,
        "pair_counts": summary.pair_counts,
        "outputs": {
            "comparison_posts": str(summary.output_path),
            "comparison_posts_excel": str(summary.workbook_path),
        },
    }
    _atomic_write_json(summary.run_summary_path, payload)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    """使用临时文件、fsync 和原子替换写 JSON 摘要。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.unlink(missing_ok=True)
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as output_file:
            json.dump(payload, output_file, ensure_ascii=False, indent=2)
            output_file.write("\n")
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _resolve_run_id(run_id: str | None) -> str:
    """生成或校验可安全用于目录名的运行 ID。"""

    value = run_id or beijing_now().strftime("%Y%m%dT%H%M%S.%f%z")
    if not _RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("run_id 只允许字母、数字、点、加号、下划线和连字符")
    return value


def main() -> None:
    """使用文件顶部人工配置执行一次车型共现二次筛选。"""

    summary = filter_vehicle_pairs(
        input_path=INPUT_JSONL,
        catalog_path=VEHICLE_CATALOG_FILE,
        output_root=OUTPUT_ROOT,
    )
    print(
        "车型共现筛选完成: "
        f"run_id={summary.run_id}, "
        f"rows_seen={summary.rows_seen}, "
        f"matched={summary.rows_with_cross_brand_pair}, "
        f"output={summary.output_path}, "
        f"excel={summary.workbook_path}"
    )


if __name__ == "__main__":
    main()
