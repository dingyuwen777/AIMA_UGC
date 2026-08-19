"""Stage 8A 两个人工调试入口的数据库写入必须显式 opt-in。"""

from inspect import signature

from aima_ugc.adapters.providers.imports_test import test as imports_debug
from aima_ugc.adapters.providers.tikhub_test.operations.runner import run_platform


def test_imports_test_database_mode_defaults_to_false() -> None:
    parameter = signature(imports_debug.run_all).parameters["write_to_database"]
    assert parameter.default is False


def test_tikhub_test_database_mode_defaults_to_false() -> None:
    parameter = signature(run_platform).parameters["write_to_database"]
    assert parameter.default is False
