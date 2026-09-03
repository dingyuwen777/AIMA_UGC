from __future__ import annotations

from aima_ugc.bootstrap.content_http import _analysis_configuration_hash


def _configuration_hash(runtime_config_snapshot: dict[str, object] | None) -> str:
    """使用稳定基础身份计算测试 hash。"""

    return _analysis_configuration_hash(
        prompt_version="scheme-v1",
        prompt_sha256="a" * 64,
        taxonomy_sha256="b" * 64,
        model_provider="api.deepseek.com",
        model="deepseek-v4-pro",
        generation_config_hash="c" * 64,
        runtime_config_snapshot=runtime_config_snapshot,
    )


def test_runtime_provider_revision_changes_analysis_configuration_hash() -> None:
    first = {
        "provider_config_id": "11111111-1111-4111-8111-111111111111",
        "provider_kind": "llm",
        "provider": "api.deepseek.com",
        "base_url": "https://api.deepseek.com/v1",
        "secret_ref": "providers/llm/key-1.key",
        "model": "deepseek-v4-pro",
        "timeout_seconds": 45,
        "max_retries": 1,
        "max_concurrency": 5,
        "max_rps": None,
        "extra_config": {},
        "revision": 1,
    }
    second = {**first, "secret_ref": "providers/llm/key-2.key", "revision": 2}

    assert _configuration_hash(first) != _configuration_hash(second)


def test_empty_runtime_snapshot_preserves_legacy_analysis_configuration_hash() -> None:
    assert _configuration_hash(None) == _configuration_hash({})
