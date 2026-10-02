"""Content 多选升级不改变历史 Analysis Query 的同义请求身份。"""

import pytest
from aima_ugc.bootstrap.content_http import (
    _analysis_configuration_hash,
    _assert_same_analysis_run_request,
)
from aima_ugc.contracts.http import ContentFilterSnapshot
from aima_ugc.modules.content.http import ContentAnalysisRunConflict


def test_historical_analysis_query_retry_survives_new_plural_defaults() -> None:
    """旧持久快照缺新增键时仍接受同义重试，真正不同的筛选继续冲突。"""
    configuration = {
        "prompt_version": "test",
        "prompt_sha256": "1" * 64,
        "taxonomy_sha256": "2" * 64,
        "model_provider": "fake",
        "model": "fake",
        "generation_config_hash": "3" * 64,
        "runtime_config_snapshot": {},
    }
    current = ContentFilterSnapshot(voice_types=("真实用户发声",), sentiments=("负面",)).model_dump(
        mode="json"
    )
    historical = ContentFilterSnapshot(voice_type="真实用户发声", sentiment="负面").model_dump(
        mode="json"
    )
    historical.pop("voice_types")
    historical.pop("sentiments")
    row = {
        **configuration,
        "scope": "query",
        "target_count": 2,
        "run_intent": "initial_analysis",
        "filter_snapshot": historical,
    }
    arguments = {
        "expected_target_count": 2,
        "expected_configuration_hash": _analysis_configuration_hash(**configuration),
        "run_intent": "initial_analysis",
        "scope": "query",
    }
    _assert_same_analysis_run_request(row, filter_snapshot=current, **arguments)
    current["sentiments"] = ["正面"]
    with pytest.raises(ContentAnalysisRunConflict):
        _assert_same_analysis_run_request(row, filter_snapshot=current, **arguments)
