"""小红书指定账号人工采集配置入口；业务实现全部复用 tikhub_test 公共链。"""

from __future__ import annotations

from typing import Literal

from aima_ugc.adapters.providers.tikhub_test import (
    XiaohongshuAccountTarget,
    run_xiaohongshu_accounts,
)
from aima_ugc.platform.time import beijing_now

ACCOUNTS = (
    XiaohongshuAccountTarget(nickname="爱玛电动车", red_id="49328786266"),
    XiaohongshuAccountTarget(nickname="爱玛三轮电动车", red_id="27247301529"),
    XiaohongshuAccountTarget(nickname="爱玛东2楼", red_id="11132750536"),
    XiaohongshuAccountTarget(nickname="我是玛小爱", red_id="1092546221"),
    XiaohongshuAccountTarget(nickname="元宇宙女孩的实验室", red_id="6758835472"),
)

START_DATE = "2026-08-01"
END_DATE = beijing_now().date().isoformat()

INCLUDE_COMMENTS = True
INCLUDE_REPLIES = True
COMMENT_MODE: Literal["limited", "all"] = "all"

MAX_ACCOUNT_SEARCH_PAGES = 5
MAX_NOTE_PAGES_PER_ACCOUNT = 100
MAX_COMMENT_PAGES_PER_CONTENT = 100
MAX_REPLY_PAGES_PER_ROOT = 50


def main() -> None:
    """按本文件配置执行一次文件模式采集，并输出本次可检查产物路径。"""
    result = run_xiaohongshu_accounts(
        accounts=ACCOUNTS,
        start_date=START_DATE,
        end_date=END_DATE,
        max_account_search_pages=MAX_ACCOUNT_SEARCH_PAGES,
        max_note_pages_per_account=MAX_NOTE_PAGES_PER_ACCOUNT,
        max_comment_pages_per_content=MAX_COMMENT_PAGES_PER_CONTENT,
        max_reply_pages_per_root=MAX_REPLY_PAGES_PER_ROOT,
        include_comments=INCLUDE_COMMENTS,
        include_replies=INCLUDE_REPLIES,
        comment_mode=COMMENT_MODE,
    )
    print(f"run_dir={result.run_dir}")
    print(f"workbook={result.workbook_path}")
    print(f"summary={result.run_summary_path}")


if __name__ == "__main__":
    main()
