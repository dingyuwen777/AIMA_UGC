"""TikHub 五平台无数据库测试/调试入口。"""

from aima_ugc.adapters.providers.tikhub_test.core.config import TikHubTestConfig
from aima_ugc.adapters.providers.tikhub_test.core.core import DebugState, RunOutputStore
from aima_ugc.adapters.providers.tikhub_test.operations import runner
from aima_ugc.adapters.providers.tikhub_test.operations.bilibili import (
    BilibiliAccountTarget,
    run_bilibili,
    run_bilibili_accounts,
)
from aima_ugc.adapters.providers.tikhub_test.operations.douyin import (
    DouyinAccountTarget,
    run_douyin,
    run_douyin_accounts,
)
from aima_ugc.adapters.providers.tikhub_test.operations.kuaishou import (
    KuaishouAccountTarget,
    run_kuaishou,
    run_kuaishou_accounts,
)
from aima_ugc.adapters.providers.tikhub_test.operations.weibo import (
    WeiboAccountTarget,
    run_weibo,
    run_weibo_accounts,
)
from aima_ugc.adapters.providers.tikhub_test.operations.xiaohongshu import run_xiaohongshu
from aima_ugc.adapters.providers.tikhub_test.operations.xiaohongshu_accounts import (
    XiaohongshuAccountTarget,
    run_xiaohongshu_accounts,
)

__all__ = [
    "DebugState",
    "BilibiliAccountTarget",
    "DouyinAccountTarget",
    "KuaishouAccountTarget",
    "RunOutputStore",
    "TikHubTestConfig",
    "WeiboAccountTarget",
    "XiaohongshuAccountTarget",
    "run_bilibili",
    "run_bilibili_accounts",
    "run_douyin",
    "run_douyin_accounts",
    "run_kuaishou",
    "run_kuaishou_accounts",
    "run_weibo",
    "run_weibo_accounts",
    "run_xiaohongshu",
    "run_xiaohongshu_accounts",
    "runner",
]
