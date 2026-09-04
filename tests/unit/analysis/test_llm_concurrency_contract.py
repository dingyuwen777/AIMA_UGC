from __future__ import annotations

import importlib.util
import inspect

from aima_ugc.adapters.llm.openai_compatible import OpenAICompatibleContentLabelingLLM
from aima_ugc.adapters.providers.imports_test import test as imports_test
from aima_ugc.modules.analysis import label_unified_content_jsonl


def test_imports_test_defaults_to_250_single_item_concurrency() -> None:
    assert imports_test.LLM_CONCURRENCY == 250
    assert imports_test.MAX_TRANSPORT_RETRIES == 4
    assert not hasattr(imports_test, "LLM_BATCH_SIZE")


def test_offline_labeling_exposes_concurrency_not_model_batch_size() -> None:
    parameters = inspect.signature(label_unified_content_jsonl).parameters
    assert "max_concurrency" in parameters
    assert parameters["max_concurrency"].default == 250
    assert "batch_size" not in parameters


def test_openai_compatible_adapter_can_size_connection_pool_for_concurrency() -> None:
    parameters = inspect.signature(OpenAICompatibleContentLabelingLLM).parameters
    assert "max_connections" in parameters


def test_explicit_transport_retry_wrapper_exists_outside_base_adapter() -> None:
    spec = importlib.util.find_spec("aima_ugc.adapters.llm.retrying")
    assert spec is not None
