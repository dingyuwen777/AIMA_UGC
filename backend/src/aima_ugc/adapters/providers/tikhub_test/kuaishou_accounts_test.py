"""快手指定账号历史作品与全部评论采集的人工配置入口。

先填写本文件顶部的 ``ACCOUNTS``、``START_DATE`` 和 ``END_DATE``，再从仓库
根目录执行：

    uv run python backend/src/aima_ugc/adapters/providers/tikhub_test/kuaishou_accounts_test.py

TikHub Base URL、API Key 和超时继续从本目录已经配置好的 ``.env`` 读取。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from aima_ugc.adapters.providers.tikhub_test import (
    KuaishouAccountTarget,
    run_kuaishou_accounts,
)

# 避免部分 Windows 环境继承的证书日志路径权限影响真实请求。

# 每个账号填写以下四类标识中的至少一个：
# 1. user_id：纯数字，最推荐，作品接口可直接使用；
# 2. kuaishou_id：个人主页显示的“快手号”，例如 loveaima123；
# 3. eid：快手主页 /profile/<eid> 中的长 eid；
# 4. homepage_url：完整快手主页地址，程序会提取 eid 后解析。
ACCOUNTS = [
    KuaishouAccountTarget(
        nickname="爱玛电动车",
        kuaishou_id="loveaima123",
        eid=None,
        user_id="1493712758",
        homepage_url=None,
    ),
    # KuaishouAccountTarget(
    #     nickname="爱玛三轮电动车",
    #     kuaishou_id="4639870688",
    #     eid=None,
    #     user_id=None,
    #     homepage_url=None,
    #     ),
    # KuaishouAccountTarget(
    #     nickname="爱玛马赫",
    #     kuaishou_id="3561596443",
    #     eid=None,
    #     user_id=None,
    #     homepage_url=None,
    # ),
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
# None 表示账号作品、一级评论、二级回复均不设置人工页数上限，持续到
# TikHub 对应 App/Web 接口都报告分页结束。
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
    placeholders = {
        "请填写快手官号名称",
        "请填写快手号",
        "请填写快手主页 eid",
        "请填写快手数字 user_id",
        "请填写快手主页地址",
    }
    if any(
        value in placeholders
        for account in ACCOUNTS
        for value in (
            account.nickname,
            account.kuaishou_id,
            account.eid,
            account.user_id,
            account.homepage_url,
        )
    ):
        raise ValueError("请先在 kuaishou_accounts_test.py 填写真实快手账号配置")

    result = run_kuaishou_accounts(
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
            "采集完成但没有发现日期范围内的快手作品，Excel 仅包含表头；"
            "请检查账号标识、日期或 TikHub 返回。"
            f"运行摘要：{result.run_summary_path}"
        )
    failed_accounts = [
        str(
            account.get("nickname")
            or account.get("kuaishou_id")
            or account.get("eid")
            or account.get("configured_user_id")
        )
        for account in summary.get("accounts", [])
        if account.get("status") not in {"completed"}
    ]
    if failed_accounts:
        raise RuntimeError(
            "存在未完成的快手账号，未将本次结果视为全量采集："
            f"{'、'.join(failed_accounts)}。运行摘要：{result.run_summary_path}"
        )
    partial_count = int(summary.get("partial_content_count") or 0)
    if partial_count:
        raise RuntimeError(
            f"有 {partial_count} 个作品的 App/Web 评论链未全部耗尽或数量未对齐，"
            "本次结果不是全量评论。"
            f"覆盖明细：{summary.get('comment_coverage_failures') or []}。"
            f"运行摘要：{result.run_summary_path}"
        )
    print(f"采集完成：{result.workbook_path}")
    print(f"运行摘要：{result.run_summary_path}")


if __name__ == "__main__":
    main()
