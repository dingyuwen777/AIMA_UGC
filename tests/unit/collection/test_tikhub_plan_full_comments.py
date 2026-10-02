"""全量策略不能沿用采样上限，且完整度必须参与再次采集决策。"""

import pytest
from aima_ugc.adapters.providers.tikhub.capabilities import XIAOHONGSHU_TIKHUB_CAPABILITY
from aima_ugc.contracts.collection import (
    CollectionDecisionPolicyV1,
    CollectionDecisionRequestV1,
    ContentObservationV1,
    PreviousContentStateV1,
    ReplyDecisionRequestV1,
)
from aima_ugc.modules.collection import CollectionDecisionService
from aima_ugc.modules.collection.run_policy import validate_run_decision_policy


def test_full_policy_collects_all_reported_roots_and_replies() -> None:
    policy = CollectionDecisionPolicyV1(comment_mode="full")
    decision = CollectionDecisionService().decide(
        CollectionDecisionRequestV1(
            current=ContentObservationV1(comment_count=500),
            policy=policy,
            capability=XIAOHONGSHU_TIKHUB_CAPABILITY,
        )
    )
    assert decision.comment_action == "fetch_full"
    assert decision.comment_target == 500

    reply = CollectionDecisionService().decide_reply(
        ReplyDecisionRequestV1(
            reply_count=30,
            policy=policy,
            capability=XIAOHONGSHU_TIKHUB_CAPABILITY,
        )
    )
    assert reply.target == 30


def test_full_unknown_reply_count_has_no_sampling_limit() -> None:
    decision = CollectionDecisionService().decide_reply(
        ReplyDecisionRequestV1(
            reply_count=None,
            policy=CollectionDecisionPolicyV1(comment_mode="full"),
            capability=XIAOHONGSHU_TIKHUB_CAPABILITY,
        )
    )
    assert decision.target is None


@pytest.mark.parametrize("complete,expected", [(False, "fetch_full"), (True, "skip")])
def test_full_unchanged_count_only_skips_when_roots_and_threads_were_complete(
    complete: bool,
    expected: str,
) -> None:
    decision = CollectionDecisionService().decide(
        CollectionDecisionRequestV1(
            current=ContentObservationV1(comment_count=500),
            previous=PreviousContentStateV1(
                comment_count=500,
                full_comment_capture_complete=complete,
            ),
            policy=CollectionDecisionPolicyV1(comment_mode="full"),
            capability=XIAOHONGSHU_TIKHUB_CAPABILITY,
        )
    )
    assert decision.comment_action == expected


@pytest.mark.parametrize("complete,expected", [(False, "fetch_full"), (True, "fetch_incremental")])
def test_full_increase_uses_reliable_incremental_only_after_complete_capture(
    complete: bool,
    expected: str,
) -> None:
    decision = CollectionDecisionService().decide(
        CollectionDecisionRequestV1(
            current=ContentObservationV1(comment_count=501),
            previous=PreviousContentStateV1(
                comment_count=500,
                full_comment_capture_complete=complete,
            ),
            policy=CollectionDecisionPolicyV1(comment_mode="full"),
            capability=XIAOHONGSHU_TIKHUB_CAPABILITY,
        )
    )
    assert decision.comment_action == expected
    assert decision.comment_target == 501


@pytest.mark.parametrize(
    "current,prior,complete,expected",
    [
        (30, 30, True, "skip"),
        (31, 30, True, "fetch_target"),
        (30, 30, False, "fetch_target"),
        (None, 30, True, "probe_first_page"),
    ],
)
def test_full_reply_refresh_uses_thread_evidence(
    current: int | None,
    prior: int | None,
    complete: bool,
    expected: str,
) -> None:
    result = CollectionDecisionService().decide_reply(
        ReplyDecisionRequestV1(
            reply_count=current,
            previous_reply_count=prior,
            previous_capture_complete=complete,
            policy=CollectionDecisionPolicyV1(comment_mode="full"),
            capability=XIAOHONGSHU_TIKHUB_CAPABILITY,
        )
    )
    assert result.action == expected


def test_new_snapshot_requires_type_and_consistent_comment_policy() -> None:
    snapshot = {"schema_version": "collection-run-config.v4", "comment_policy": "full"}
    with pytest.raises(ValueError, match="plan_type"):
        validate_run_decision_policy(snapshot)
    with pytest.raises(ValueError, match="不一致"):
        validate_run_decision_policy({**snapshot, "plan_type": "tikhub"})
    with pytest.raises(ValueError, match="unsupported"):
        validate_run_decision_policy({**snapshot, "plan_type": "other"})
    validate_run_decision_policy(
        {**snapshot, "plan_type": "tikhub", "decision_policy": {"comment_mode": "full"}}
    )


def test_legacy_type_interpretation_does_not_rewrite_frozen_snapshot() -> None:
    legacy = {"schema_version": "collection-run-config.v2"}
    validate_run_decision_policy(legacy)
    assert legacy == {"schema_version": "collection-run-config.v2"}
    supplement = {"schema_version": "collection-run-config.v3", "mode": "content_supplement"}
    validate_run_decision_policy(supplement)
    with pytest.raises(ValueError, match="plan_type"):
        validate_run_decision_policy({"schema_version": "collection-run-config.v3"})
