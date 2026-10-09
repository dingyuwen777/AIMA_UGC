"""真实 HEAD90013 旧 wire 与当前 Raw 重放的严格兼容证明。"""

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu import (
    XiaohongshuMappingContext,
    map_content,
)
from aima_ugc.bootstrap.collection_scope import TikHubCollectionScopeExecutor
from aima_ugc.contracts.canonical import CanonicalContentV1
from aima_ugc.platform.jobs.models import LeaseLostError

_CASES = json.loads(
    Path("tests/fixtures/providers/tikhub/xiaohongshu/canonical_90013af0.sanitized.json").read_text(
        "utf-8"
    )
)["cases"]


@pytest.mark.parametrize("case", _CASES, ids=lambda item: item["case"])
@pytest.mark.parametrize("cross_attempt", [False, True])
def test_authentic_old_wire_is_proven_by_same_raw_and_kept_immutable(case, cross_attempt):
    old = CanonicalContentV1.model_validate(case["canonical_wire"])
    source = old.source
    current = map_content(
        case["raw"],
        XiaohongshuMappingContext(
            provider_request_id=source.provider_request_id,
            provider_attempt_id=source.provider_attempt_id,
            raw_artifact_id=source.raw_artifact_id,
            operation=source.operation,
            source_type=source.source_type,
            source_value=source.source_value,
            observed_at=source.observed_at,
        ),
        item_locator=source.item_locator,
    )
    executor = object.__new__(TikHubCollectionScopeExecutor)
    executor._legacy_canonical_by_source = {}
    executor._remember_legacy_canonical(current, case["raw"])
    assert executor._legacy_canonical_by_source[source.model_dump_json()] == old
    artifact = object()
    executor._canonical_for_attempt = lambda _: artifact
    executor._canonical_reader = SimpleNamespace(read=lambda _: [old])
    expected = (
        current.model_copy(
            update={"source": source.model_copy(update={"provider_attempt_id": str(uuid4())})}
        )
        if cross_attempt
        else current
    )
    kwargs = dict(provider_attempt_id=uuid4(), expected=(expected,))
    if cross_attempt:
        kwargs["legacy_alternatives"] = ((expected, current),)
    assert executor._persistent_filter_inputs(**kwargs) == (expected,)
    for tampered in (
        old.model_copy(update={"title": "被篡改"}),
        old.model_copy(update={"external_content_id": "other-note"}),
        old.model_copy(update={"source": source.model_copy(update={"raw_artifact_id": uuid4()})}),
        old.model_copy(update={"media": []})
        if old.media
        else old.model_copy(update={"text": "被篡改"}),
    ):
        executor._canonical_reader = SimpleNamespace(read=lambda _, row=tampered: [row])
        with pytest.raises(ValueError, match="Persistent Canonical"):
            executor._persistent_filter_inputs(**kwargs)


def test_same_executor_releases_scope_legacy_proofs_after_success_failure_and_cancel(monkeypatch):
    """长期复用 Executor 时，兼容证明只在当前 Scope 内保留正文。"""
    import aima_ugc.bootstrap.collection_scope as runtime

    executor = TikHubCollectionScopeExecutor(
        session_factory=lambda: None,
        raw_artifacts=None,
        artifacts=None,
        artifact_store=None,
        transport_factory=lambda _: None,
        secret_resolver=lambda _: None,
    )
    executor._reconciler = SimpleNamespace(recover_inherited=lambda _: None)
    executor._provider_config_for_run = lambda *_: None
    for name in (
        "_validate_decision_policy",
        "_tikhub_platform",
        "_platform_runtime_config",
        "_capability",
        "_decision_policy",
    ):
        monkeypatch.setattr(runtime, name, lambda *_: None)
    case = _CASES[0]
    canonical = CanonicalContentV1.model_validate(case["canonical_wire"])
    outcomes = ["succeeded", "failed", "cancelled", "lease_lost"] * 5
    for index, outcome in enumerate(outcomes):
        observation = canonical.model_copy(
            update={
                "source": canonical.source.model_copy(update={"provider_attempt_id": str(uuid4())})
            }
        )

        def enrichment(*, observation=observation, outcome=outcome, **_):
            assert executor._legacy_canonical_by_source == {}
            executor._remember_legacy_canonical(observation, case["raw"])
            assert len(executor._legacy_canonical_by_source) == 1
            # 同一 Scope 内仍可恢复其已经验证的 Raw/Canonical。
            assert observation.source.model_dump_json() in executor._legacy_canonical_by_source
            if outcome == "failed":
                raise ValueError("provider mapping failed")
            if outcome == "lease_lost":
                raise LeaseLostError("scope lease lost")
            return SimpleNamespace(status=outcome)

        executor._execute_content_enrichment = enrichment
        kwargs = dict(
            run=SimpleNamespace(id=uuid4()),
            scope=SimpleNamespace(
                id=uuid4(),
                source_type="content",
                operation_group="content_enrichment",
                platform="xiaohongshu",
            ),
            context=SimpleNamespace(fence=None),
        )
        # 上一次旧实例遗留的数据也须在入口清理。
        if index == 0:
            executor._legacy_canonical_by_source["previous-scope"] = canonical
        if outcome in {"failed", "lease_lost"}:
            with pytest.raises(ValueError if outcome == "failed" else LeaseLostError):
                executor.execute(**kwargs)
        else:
            assert executor.execute(**kwargs).status == outcome
        assert executor._legacy_canonical_by_source == {}
