"""TikHub 五平台无数据库测试/调试入口。"""

from .bilibili import run_bilibili
from .douyin import run_douyin
from .kuaishou import run_kuaishou
from .weibo import run_weibo
from .xiaohongshu import run_xiaohongshu

__all__ = [
    "run_bilibili",
    "run_douyin",
    "run_kuaishou",
    "run_weibo",
    "run_xiaohongshu",
]
