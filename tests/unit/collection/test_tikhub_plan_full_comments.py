"""全量策略不能沿用采样上限，且完整度必须参与再次采集决策。"""

from aima_ugc.adapters.providers.tikhub.capabilities import XIAOHONGSHU_TIKHUB_CAPABILITY
from aima_ugc.contracts.collection import (
    CollectionDecisionPolicyV1,
    CollectionDecisionRequestV1,
    ContentObservationV1,
    ReplyDecisionRequestV1,
)
from aima_ugc.modules.collection import CollectionDecisionService


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

