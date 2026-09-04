"""Issue #352 的临时 CI Runner 预算测量探针；对应 Draft PR 不合并。"""


def test_ci_runner_budget_measurement_probe() -> None:
    """确认临时 backend-only 测量文件可进入常规单元测试集合。"""
    assert True
