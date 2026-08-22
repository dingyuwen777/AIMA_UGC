"""小红书 TikHub 独立测试/调试入口。"""

from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from .runner import TikHubTestRunResult, run_platform


def run_xiaohongshu(
    *,
    keyword: str | None = None,
    keywords: str | Sequence[str] | None = None,
    sort_mode: str = "general",
    published_within: str = "all",
    content_type: str = "all",
    env_file: str | Path | None = None,
    output_root: str | Path | None = None,
    run_id: str | None = None,
    max_search_pages: int = 20,
    max_contents: int | None = None,
    max_comments_per_content: int = 100,
    max_comment_pages_per_content: int = 20,
    max_replies_per_root: int = 20,
    max_reply_pages_per_root: int = 10,
    include_comments: bool = True,
    include_replies: bool = True,
    force_refresh: bool = False,
    write_to_database: bool = False,
    provider_config_id: UUID | None = None,
) -> TikHubTestRunResult:
    return run_platform(
        platform="xiaohongshu",
        keyword=keyword,
        keywords=keywords,
        search_config={
            "sort_mode": sort_mode,
            "published_within": published_within,
            "content_type": content_type,
        },
        env_file=env_file,
        output_root=output_root,
        run_id=run_id,
        max_search_pages=max_search_pages,
        max_contents=max_contents,
        max_comments_per_content=max_comments_per_content,
        max_comment_pages_per_content=max_comment_pages_per_content,
        max_replies_per_root=max_replies_per_root,
        max_reply_pages_per_root=max_reply_pages_per_root,
        include_comments=include_comments,
        include_replies=include_replies,
        force_refresh=force_refresh,
        write_to_database=write_to_database,
        provider_config_id=provider_config_id,
    )


__all__ = ["run_xiaohongshu"]
