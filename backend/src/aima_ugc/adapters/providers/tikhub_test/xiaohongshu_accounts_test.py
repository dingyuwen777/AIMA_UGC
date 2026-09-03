"""小红书指定账号人工采集配置入口；业务实现全部复用 tikhub_test 公共链。"""

from __future__ import annotations

import os
from typing import Literal

from aima_ugc.adapters.providers.tikhub_test import (
    XiaohongshuAccountTarget,
    run_xiaohongshu_accounts,
)

# ==================== 常用参数：通常只需要修改这一段 ====================

# True 会清除本机软件注入的 SSLKEYLOGFILE，避免无权限写该文件导致请求尚未发出就失败；
# 这不会关闭 HTTPS 证书校验。
DISABLE_SSL_KEY_LOGGING = True

# 要采集的账号。当前六行全部启用；注释不需要的行可缩小范围。
# nickname 用于人工核对，red_id 是小红书号。
ACCOUNTS = (
    XiaohongshuAccountTarget(nickname="爱玛电动车", red_id="49328786266"),
    XiaohongshuAccountTarget(nickname="爱玛三轮电动车", red_id="27247301529"),
    XiaohongshuAccountTarget(nickname="爱玛东2楼", red_id="11132750536"),
    XiaohongshuAccountTarget(nickname="我是玛小爱", red_id="1092546221"),
    XiaohongshuAccountTarget(nickname="元宇宙女孩的实验室", red_id="6758835472"),
    XiaohongshuAccountTarget(nickname="爱玛黑翼BWG", red_id="63025176363"),
)

# 笔记发布日期范围，包含开始和结束当天，格式必须为 YYYY-MM-DD。
START_DATE = "2026-08-01"
END_DATE = "2026-08-31"

# None 表示使用本目录默认的 .env；也可填写其他 .env 文件路径。
ENV_FILE: str | None = None
# None 表示输出到默认 output/xiaohongshu 目录；也可填写自定义目录。
OUTPUT_ROOT: str | None = None
# None 表示用当前北京时间生成运行编号；手工指定时必须保证不与已有运行目录重复。
RUN_ID: str | None = None

# 是否采集一级评论；False 时不会请求评论接口。
INCLUDE_COMMENTS = True
# 是否采集一级评论下的二级回复；仅在 INCLUDE_COMMENTS=True 时生效。
INCLUDE_REPLIES = True
# limited 会使用下面的评论/回复数量上限；all 会忽略数量上限并持续到接口耗尽或页数硬保护。
COMMENT_MODE: Literal["limited", "all"] = "all"

# 账号搜索最多翻页数；已缓存稳定 user_id 时通常不会触发搜索。
MAX_ACCOUNT_SEARCH_PAGES = 5
# 每个账号的笔记列表最多翻页数。
MAX_NOTE_PAGES_PER_ACCOUNT = 100
# 整次运行最多处理多少篇笔记；None 表示不限制。
MAX_CONTENTS: int | None = None
# limited 模式下，每篇笔记最多采集 1000 条一级评论。
MAX_COMMENTS_PER_CONTENT = 1000
# 每篇笔记的一级评论最多请求多少页，防止异常分页无限循环。
MAX_COMMENT_PAGES_PER_CONTENT = 200
# limited 模式下，每条一级评论最多采集多少条二级回复。
MAX_REPLIES_PER_ROOT = 20
# 每条一级评论的二级回复最多请求多少页，防止异常分页无限循环。
MAX_REPLY_PAGES_PER_ROOT = 50
# True 会额外调用用户详情接口核验账号；通常保持 False，避免增加请求数。
VALIDATE_USER_INFO = False

# ==================== 常用参数结束 ====================

if DISABLE_SSL_KEY_LOGGING:
    os.environ.pop("SSLKEYLOGFILE", None)


def main() -> None:
    """按本文件配置执行一次文件模式采集，并输出本次可检查产物路径。"""
    result = run_xiaohongshu_accounts(
        accounts=ACCOUNTS,
        start_date=START_DATE,
        end_date=END_DATE,
        env_file=ENV_FILE,
        output_root=OUTPUT_ROOT,
        run_id=RUN_ID,
        max_account_search_pages=MAX_ACCOUNT_SEARCH_PAGES,
        max_note_pages_per_account=MAX_NOTE_PAGES_PER_ACCOUNT,
        max_contents=MAX_CONTENTS,
        max_comments_per_content=MAX_COMMENTS_PER_CONTENT,
        max_comment_pages_per_content=MAX_COMMENT_PAGES_PER_CONTENT,
        max_replies_per_root=MAX_REPLIES_PER_ROOT,
        max_reply_pages_per_root=MAX_REPLY_PAGES_PER_ROOT,
        include_comments=INCLUDE_COMMENTS,
        include_replies=INCLUDE_REPLIES,
        comment_mode=COMMENT_MODE,
        validate_user_info=VALIDATE_USER_INFO,
    )
    print(f"run_dir={result.run_dir}")
    print(f"workbook={result.workbook_path}")
    print(f"summary={result.run_summary_path}")


if __name__ == "__main__":
    main()
