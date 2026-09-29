"""微博指定账号历史微博与全部评论采集的人工配置入口。

先填写本文件顶部的 ``ACCOUNTS``、``START_DATE`` 和 ``END_DATE``，再从仓库
根目录执行：

    uv run python backend/src/aima_ugc/adapters/providers/tikhub_test/weibo_accounts_test.py

TikHub Base URL、API Key 和超时继续从本目录已经配置好的 ``.env`` 读取。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal
from uuid import UUID

from aima_ugc.adapters.providers.tikhub_test import (
    WeiboAccountTarget,
    run_weibo_accounts,
)

# 避免部分 Windows 环境继承的证书日志路径权限影响真实请求。
os.environ.pop("SSLKEYLOGFILE", None)

# 每个账号填写以下标识中的至少一个：
# 1. uid：微博数字 UID，最推荐；可从主页 URL 中取得，例如 weibo.com/u/1234567890；
# 2. nickname：微博昵称。程序会调用用户搜索并只接受唯一的精确匹配；
# 3. homepage_url：完整微博主页地址，程序会从其中提取数字 UID。
ACCOUNTS: list[WeiboAccountTarget] = [
    WeiboAccountTarget(
        nickname="爱玛电动车",
        uid="3193198157",
        homepage_url=None,
    ),
]

# 起止日期均包含，按北京时间（Asia/Shanghai）解释。
START_DATE = "2026-08-01"
END_DATE = "2026-08-31"

INCLUDE_COMMENTS = True
INCLUDE_REPLIES = True
COMMENT_MODE: Literal["limited", "all"] = "all"

OUTPUT_ROOT = Path(__file__).resolve().parent / "output"
RUN_ID: str | None = None
MAX_CONTENTS: int | None = None
MAX_ACCOUNT_SEARCH_PAGES = 5
# None 表示账号历史微博、一级评论和二级回复均不设置人工页数上限，持续到
# TikHub 对应接口报告分页结束；适用于“所有评论”的要求。
MAX_ACCOUNT_POST_PAGES: int | None = None
MAX_COMMENTS_PER_CONTENT = 100
MAX_COMMENT_PAGES_PER_CONTENT: int | None = None
MAX_REPLIES_PER_ROOT = 20
MAX_REPLY_PAGES_PER_ROOT: int | None = None
FORCE_REFRESH = True
WRITE_TO_DATABASE = False
# 只有 WRITE_TO_DATABASE=True 时才填写正式 provider_configs 的 UUID。
PROVIDER_CONFIG_ID: UUID | None = None


def main() -> None:
    if not ACCOUNTS:
        raise ValueError(
            "请先在 weibo_accounts_test.py 的 ACCOUNTS 中填写至少一个真实微博账号"
        )
    placeholders = {"请填写微博官号名称", "请填写微博数字 UID", "请填写微博主页地址"}
    if any(
        value in placeholders
        for account in ACCOUNTS
        for value in (account.nickname, account.uid, account.homepage_url)
    ):
        raise ValueError("请先在 weibo_accounts_test.py 填写真实微博账号配置")

    result = run_weibo_accounts(
        accounts=ACCOUNTS,
        start_date=START_DATE,
        end_date=END_DATE,
        include_comments=INCLUDE_COMMENTS,
        include_replies=INCLUDE_REPLIES,
        comment_mode=COMMENT_MODE,
        output_root=OUTPUT_ROOT,
        run_id=RUN_ID,
        max_contents=MAX_CONTENTS,
        max_account_search_pages=MAX_ACCOUNT_SEARCH_PAGES,
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
    if summary.get("status") == "failed":
        account_errors = sorted(
            {
                str(account.get("error_summary"))
                for account in summary.get("accounts", [])
                if account.get("error_summary")
            }
        )
        details = "；".join(account_errors) or "所有账号均采集失败"
        raise RuntimeError(
            f"采集失败，未生成有效数据：{details}。运行摘要：{result.run_summary_path}"
        )
    if result.content_count == 0:
        raise RuntimeError(
            "采集完成但没有发现日期范围内的微博，Excel 仅包含表头；"
            "请检查账号标识、日期或 TikHub 返回。"
            f"运行摘要：{result.run_summary_path}"
        )
    failed_accounts = [
        str(account.get("nickname") or account.get("configured_uid") or account.get("homepage_url"))
        for account in summary.get("accounts", [])
        if account.get("status") not in {"completed"}
    ]
    if failed_accounts:
        raise RuntimeError(
            "存在未完成的微博账号，未将本次结果视为全量采集："
            f"{'、'.join(failed_accounts)}。运行摘要：{result.run_summary_path}"
        )
    partial_count = int(summary.get("partial_content_count") or 0)
    if partial_count:
        raise RuntimeError(
            f"有 {partial_count} 个微博的评论或二级回复未完整采集。"
            f"覆盖明细：{summary.get('comment_coverage_failures') or []}。"
            f"运行摘要：{result.run_summary_path}"
        )
    print(f"采集完成：{result.workbook_path}")
    print(f"运行摘要：{result.run_summary_path}")


if __name__ == "__main__":
    main()
