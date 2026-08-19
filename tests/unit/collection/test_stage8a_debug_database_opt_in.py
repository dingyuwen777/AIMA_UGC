"""Stage 8A 两个人工调试入口的数据库写入必须显式 opt-in。"""

from inspect import signature

from aima_ugc.adapters.providers.imports_test import test as imports_debug
from aima_ugc.adapters.providers.tikhub_test import (
    run_bilibili,
    run_douyin,
    run_kuaishou,
    run_weibo,
    run_xiaohongshu,
)
from aima_ugc.adapters.providers.tikhub_test.operations.runner import run_platform


def test_imports_test_database_mode_defaults_to_false() -> None:
    parameter = signature(imports_debug.run_all).parameters["write_to_database"]
    assert parameter.default is False


def test_tikhub_test_database_mode_defaults_to_false() -> None:
    entrypoints = (
        run_platform,
        run_xiaohongshu,
        run_douyin,
        run_weibo,
        run_bilibili,
        run_kuaishou,
    )
    for entrypoint in entrypoints:
        parameters = signature(entrypoint).parameters
        assert parameters["write_to_database"].default is False
        assert parameters["provider_config_id"].default is None
