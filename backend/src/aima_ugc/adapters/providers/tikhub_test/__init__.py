"""TikHub 五平台无数据库测试/调试入口。"""

from aima_ugc.adapters.providers.tikhub_test.operations.bilibili import run_bilibili
from aima_ugc.adapters.providers.tikhub_test.operations.douyin import run_douyin
from aima_ugc.adapters.providers.tikhub_test.operations.kuaishou import run_kuaishou
from aima_ugc.adapters.providers.tikhub_test.operations.weibo import run_weibo
from aima_ugc.adapters.providers.tikhub_test.operations.xiaohongshu import run_xiaohongshu

__all__ = [
    "run_bilibili",
    "run_douyin",
    "run_kuaishou",
    "run_weibo",
    "run_xiaohongshu",
]
