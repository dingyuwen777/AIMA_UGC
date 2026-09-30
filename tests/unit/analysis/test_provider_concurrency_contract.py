"""管理员 LLM Provider 并发 Contract 回归。"""

import pytest
from aima_ugc.contracts.administration import ProviderConfigCreateRequest
from pydantic import ValidationError


def _request(*, max_concurrency: int) -> ProviderConfigCreateRequest:
    """构造最小 LLM Provider 创建请求。"""

    return ProviderConfigCreateRequest(
        provider_kind="llm",
        provider="openai_compatible",
        display_name="测试模型",
        base_url="https://example.invalid/v1",
        model="test-model",
        api_key="secret",
        max_concurrency=max_concurrency,
    )


def test_llm_contract_rejects_manual_concurrency() -> None:
    """LLM 容量由系统学习，隐藏字段也不能绕过后端。"""

    with pytest.raises(ValidationError, match="自动"):
        _request(max_concurrency=1_000)


def test_provider_contract_keeps_explicit_safety_ceiling() -> None:
    """异常大的线程并发仍由公共 Contract 拒绝，避免无界资源配置。"""

    with pytest.raises(ValidationError):
        _request(max_concurrency=5_000)
    with pytest.raises(ValidationError):
        _request(max_concurrency=5_001)
