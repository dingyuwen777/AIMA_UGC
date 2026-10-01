"""B站指定账号历史作品与全部评论采集的人工配置入口。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from aima_ugc.adapters.providers.tikhub_test import (
    BilibiliAccountTarget,
    run_bilibili_accounts,
)

# 推荐填写 uid（B站个人空间 space.bilibili.com/<uid> 中的数字）。
ACCOUNTS: list[BilibiliAccountTarget] = [
    BilibiliAccountTarget(uid="433865481", nickname="爱玛电动车"),
    # BilibiliAccountTarget(uid="3706984415103230", nickname="爱玛黑翼BWG"),
]
START_DATE = "2026-08-01"
END_DATE = "2026-08-31"

INCLUDE_COMMENTS = True
INCLUDE_REPLIES = True
COMMENT_MODE: Literal["limited", "all"] = "all"
OUTPUT_ROOT = Path(__file__).resolve().parent / "output"
RUN_ID: str | None = None
MAX_CONTENTS: int | None = None
# None 代表不设置作品、一级评论、二级回复的技术页数上限。
MAX_ACCOUNT_POST_PAGES: int | None = None
MAX_COMMENTS_PER_CONTENT = 100
MAX_COMMENT_PAGES_PER_CONTENT: int | None = None
MAX_REPLIES_PER_ROOT = 20
MAX_REPLY_PAGES_PER_ROOT: int | None = None
FORCE_REFRESH = True
WRITE_TO_DATABASE = False
PROVIDER_CONFIG_ID: UUID | None = None


def main() -> None:
    if not ACCOUNTS:
        raise ValueError("请先在 bilibili_accounts_test.py 的 ACCOUNTS 中填写至少一个 B站账号")
    if any(account.uid == "请填写B站数字UID" for account in ACCOUNTS):
        raise ValueError("请先在 bilibili_accounts_test.py 填写真实 B站 UID")
    result = run_bilibili_accounts(
        accounts=ACCOUNTS,
        start_date=START_DATE,
        end_date=END_DATE,
        include_comments=INCLUDE_COMMENTS,
        include_replies=INCLUDE_REPLIES,
        comment_mode=COMMENT_MODE,
        output_root=OUTPUT_ROOT,
        run_id=RUN_ID,
        max_contents=MAX_CONTENTS,
        max_account_post_pages=MAX_ACCOUNT_POST_PAGES,
        max_comments_per_content=MAX_COMMENTS_PER_CONTENT,
        max_comment_pages_per_content=MAX_COMMENT_PAGES_PER_CONTENT,
        max_replies_per_root=MAX_REPLIES_PER_ROOT,
        max_reply_pages_per_root=MAX_REPLY_PAGES_PER_ROOT,
        force_refresh=FORCE_REFRESH,
        write_to_database=WRITE_TO_DATABASE,
        provider_config_id=PROVIDER_CONFIG_ID,
    )
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    if summary.get("status") == "failed" or result.content_count == 0:
        raise RuntimeError(f"采集未得到有效数据，请检查运行摘要：{result.run_summary_path}")
    if summary.get("partial_content_count"):
        raise RuntimeError(
            f"存在未完整采集的评论：{summary.get('comment_coverage_failures')}。"
            f"运行摘要：{result.run_summary_path}"
        )
    print(f"采集完成：{result.workbook_path}")
    print(f"运行摘要：{result.run_summary_path}")


if __name__ == "__main__":
    main()
