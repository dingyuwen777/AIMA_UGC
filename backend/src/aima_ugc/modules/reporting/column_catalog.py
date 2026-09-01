"""版本化数据导出列白名单。"""

from __future__ import annotations

from dataclasses import dataclass

EXPORT_COLUMN_CATALOG_VERSION = 1


@dataclass(frozen=True, slots=True)
class ExportColumnDefinition:
    key: str
    label: str
    sensitive: bool = False
    default_selected: bool = False


EXPORT_COLUMNS = (
    ExportColumnDefinition("platform", "平台", default_selected=True),
    ExportColumnDefinition("external_content_id", "内容ID", default_selected=True),
    ExportColumnDefinition("source_item_id", "来源项ID", default_selected=True),
    ExportColumnDefinition("content_type", "内容类型", default_selected=True),
    ExportColumnDefinition("title", "标题", default_selected=True),
    ExportColumnDefinition("text", "正文", default_selected=True),
    ExportColumnDefinition("author_display_name", "作者", default_selected=True),
    ExportColumnDefinition("published_at", "发布时间", default_selected=True),
    ExportColumnDefinition("content_url", "内容链接", default_selected=True),
    ExportColumnDefinition("author_follower_count", "作者粉丝数", default_selected=True),
    ExportColumnDefinition("author_following_count", "作者关注数", default_selected=True),
    ExportColumnDefinition("author_content_count", "作者内容数", default_selected=True),
    ExportColumnDefinition("author_total_like_count", "作者获赞数", default_selected=True),
    ExportColumnDefinition("like_count", "点赞", default_selected=True),
    ExportColumnDefinition("comment_count", "评论数", default_selected=True),
    ExportColumnDefinition("favorite_count", "收藏数", default_selected=True),
    ExportColumnDefinition("share_count", "分享数", default_selected=True),
    ExportColumnDefinition("repost_count", "转发数", default_selected=True),
    ExportColumnDefinition("view_count", "浏览数", default_selected=True),
    ExportColumnDefinition("play_count", "播放数", default_selected=True),
    ExportColumnDefinition("danmaku_count", "弹幕数", default_selected=True),
    ExportColumnDefinition("coin_count", "投币数", default_selected=True),
    ExportColumnDefinition("download_count", "下载数", default_selected=True),
    ExportColumnDefinition("matched_keywords", "命中关键词", default_selected=True),
    ExportColumnDefinition("voice_type", "发声类型", default_selected=True),
    ExportColumnDefinition("sentiment", "情感标签", default_selected=True),
    ExportColumnDefinition("primary_label", "一级标签", default_selected=True),
    ExportColumnDefinition("secondary_label", "二级标签", default_selected=True),
    ExportColumnDefinition("analysis_model", "分析模型", default_selected=True),
    ExportColumnDefinition("prompt_version", "Prompt版本", default_selected=True),
    ExportColumnDefinition("taxonomy_version", "Taxonomy版本", default_selected=True),
    ExportColumnDefinition("source_provider", "来源Provider", default_selected=True),
    ExportColumnDefinition("raw_locator", "Raw/来源定位", default_selected=True),
    ExportColumnDefinition("coverage", "评论覆盖", default_selected=True),
    ExportColumnDefinition("vehicles", "车型"),
    ExportColumnDefinition("availability", "第三方可用状态"),
)


def resolve_export_columns(requested: tuple[str, ...]) -> tuple[str, ...]:
    """空选择使用默认列；任何未知列都 fail closed。"""

    allowed = {item.key for item in EXPORT_COLUMNS}
    selected = requested or tuple(item.key for item in EXPORT_COLUMNS if item.default_selected)
    unknown = set(selected) - allowed
    if unknown:
        raise ValueError(f"不支持的导出列: {', '.join(sorted(unknown))}")
    return selected


def export_column_headers(keys: tuple[str, ...]) -> tuple[str, ...]:
    """把稳定 API key 投影为当前 Excel 表头，映射只由 Reporting Owner 维护。"""

    labels = {item.key: item.label for item in EXPORT_COLUMNS}
    return tuple(labels[key] for key in keys)


__all__ = [
    "EXPORT_COLUMN_CATALOG_VERSION",
    "EXPORT_COLUMNS",
    "ExportColumnDefinition",
    "resolve_export_columns",
    "export_column_headers",
]
