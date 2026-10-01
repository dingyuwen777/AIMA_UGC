"""抖音指定账号历史评论采集的人工配置入口。

请先填写本文件中的账号、日期以及 TikHub 接口配置，再从仓库根目录执行：

    uv run python backend/src/aima_ugc/adapters/providers/tikhub_test/douyin_accounts_test.py

TikHub Base URL、API Key 和超时继续从本目录的 ``.env`` 读取。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from aima_ugc.adapters.providers.tikhub_test import (
    DouyinAccountTarget,
    run_douyin_accounts,
)

# 在这里填写要采集的抖音官方账号。推荐填写 unique_id（抖音号）或真实 sec_uid；
# 完整 www.douyin.com/user/<sec_uid> 主页会解析为 sec_uid；uid 仅用于交叉核验。
# 旧版配置若把非长格式的抖音号/短用户标识填进 sec_uid，程序也会自动按 unique_id 解析。
ACCOUNTS = [
    # DouyinAccountTarget(
    #     nickname="爱玛电动车",
    #     sec_uid="loveaima123",
    #     uid=None,
    #     homepage_url=None,
    # ),
    # DouyinAccountTarget(
    #         nickname="爱玛马赫",
    #         sec_uid="94370777129",
    #         uid=None,
    #         homepage_url=None,
    #     ),
    # DouyinAccountTarget(
    #         nickname="爱玛电动三轮车",
    #         sec_uid="58054489519",
    #         uid=None,
    #         homepage_url=None,
    #     ),
    # DouyinAccountTarget(
    #         nickname="爱玛科学实验室",
    #         sec_uid="44623137624",
    #         uid=None,
    #         homepage_url=None,
    #     ),
    # DouyinAccountTarget(
    #         nickname="爱玛黑翼BWG",
    #         sec_uid="49863426463",
    #         uid=None,
    #         homepage_url=None,
    #     ),
    DouyinAccountTarget(
        nickname="爱玛电动车生活服务旗舰店",
        unique_id="83283506022",
        uid=None,
        homepage_url=None,
    ),
]

# 起止日期均包含，按北京时间（Asia/Shanghai）解释。
START_DATE = "2026-08-01"
END_DATE = "2026-08-31"

INCLUDE_COMMENTS = True
INCLUDE_REPLIES = True
COMMENT_MODE: Literal["limited", "all"] = "all"

# TikHub 抖音“用户作品列表”接口配置。若你的账号接口版本字段不同，
# 只需修改这些值，不需要改采集逻辑。
# 默认使用 TikHub 文档中与详情/评论接口一致的 App V3 作品接口。
ACCOUNT_POSTS_PATH = "/api/v1/douyin/app/v3/fetch_user_post_videos"
ACCOUNT_POSTS_METHOD: Literal["GET", "POST"] = "GET"
ACCOUNT_ID_PARAM = "sec_user_id"
ACCOUNT_CURSOR_PARAM = "max_cursor"
ACCOUNT_ITEMS_PATH = "data.aweme_list"
ACCOUNT_CURSOR_PATH = "data.max_cursor"
ACCOUNT_HAS_MORE_PATH = "data.has_more"
ACCOUNT_PROFILE_PATH = "/api/v1/douyin/web/handler_user_profile_v2"
ACCOUNT_PROFILE_ID_PARAM = "unique_id"
# 显式选择作品接口；失败时保留 partial，不自动跨 family 切换。
ACCOUNT_POSTS_SOURCE: Literal["app_v3", "douplus"] = "app_v3"
DOUPLUS_POST_PAGE_SIZE = 10

OUTPUT_ROOT = Path(__file__).resolve().parent / "output"
RUN_ID: str | None = None
MAX_CONTENTS: int | None = None
MAX_ACCOUNT_POST_PAGES = 100
MAX_COMMENTS_PER_CONTENT = 100
MAX_COMMENT_PAGES_PER_CONTENT = None
MAX_REPLIES_PER_ROOT = 20
MAX_REPLY_PAGES_PER_ROOT = None
FORCE_REFRESH = True
WRITE_TO_DATABASE = False
# 指定账号固定纯文件模式；WRITE_TO_DATABASE=True 会在发送前拒绝。
PROVIDER_CONFIG_ID: UUID | None = None


def main() -> None:
    placeholders = {
        "请填写抖音官号名称",
        "请填写抖音 sec_uid",
    }
    if any(
        value in placeholders
        for account in ACCOUNTS
        for value in (
            account.nickname,
            account.unique_id,
            account.sec_uid,
            account.uid,
            account.homepage_url,
        )
    ):
        raise ValueError("请先在 douyin_accounts_test.py 填写真实账号配置")
    result = run_douyin_accounts(
        accounts=ACCOUNTS,
        start_date=START_DATE,
        end_date=END_DATE,
        include_comments=INCLUDE_COMMENTS,
        include_replies=INCLUDE_REPLIES,
        comment_mode=COMMENT_MODE,
        account_posts_path=ACCOUNT_POSTS_PATH,
        account_posts_method=ACCOUNT_POSTS_METHOD,
        account_id_param=ACCOUNT_ID_PARAM,
        account_cursor_param=ACCOUNT_CURSOR_PARAM,
        account_items_path=ACCOUNT_ITEMS_PATH,
        account_cursor_path=ACCOUNT_CURSOR_PATH,
        account_has_more_path=ACCOUNT_HAS_MORE_PATH,
        account_profile_path=ACCOUNT_PROFILE_PATH,
        account_profile_id_param=ACCOUNT_PROFILE_ID_PARAM,
        account_posts_source=ACCOUNT_POSTS_SOURCE,
        douplus_post_page_size=DOUPLUS_POST_PAGE_SIZE,
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
        empty_accounts = "、".join(
            str(account.get("nickname") or account.get("unique_id") or account.get("sec_uid"))
            for account in summary.get("accounts", [])
            if account.get("posts_discovered") == 0
        )
        raise RuntimeError(
            "采集完成但没有发现日期范围内的抖音作品，Excel 仅包含表头；"
            f"请检查账号标识或 TikHub 返回。账号：{empty_accounts or '未知'}。"
            f"运行摘要：{result.run_summary_path}"
        )
    failed_accounts = [
        str(account.get("nickname") or account.get("unique_id") or account.get("sec_uid"))
        for account in summary.get("accounts", [])
        if account.get("status") == "failed"
    ]
    if failed_accounts:
        raise RuntimeError(
            "存在未完成的抖音账号，未将本次结果视为全量采集："
            f"{'、'.join(failed_accounts)}。请修正账号标识后重试。"
            f"运行摘要：{result.run_summary_path}"
        )
    partial_count = int(summary.get("partial_content_count") or 0)
    if partial_count:
        coverage_failures = summary.get("comment_coverage_failures") or []
        raise RuntimeError(
            f"有 {partial_count} 个作品的评论未与 TikHub 返回总数对齐，"
            "本次结果不是全量评论，已停止将其视为成功。"
            f"覆盖明细：{coverage_failures}。运行摘要：{result.run_summary_path}"
        )
    count_discrepancies = summary.get("comment_count_discrepancies") or []
    if count_discrepancies:
        print(
            "提示：TikHub 返回了标记为需要修正的评论总数；"
            "App、Web 和重叠游标均已采集完，已按当前可访问评论导出。"
            f"差异明细：{count_discrepancies}"
        )
    print(f"采集完成：{result.workbook_path}")
    print(f"运行摘要：{result.run_summary_path}")


if __name__ == "__main__":
    main()
