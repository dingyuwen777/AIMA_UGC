"""Stage 7 Collection Decision 业务规则测试。"""

from __future__ import annotations

from aima_ugc.adapters.providers.tikhub.capabilities import XHS_TIKHUB_CAPABILITY
from aima_ugc.contracts.collection import (
    CollectionDecisionContextV1,
    CollectionDecisionPolicyV1,
    CollectionDecisionRequestV1,
    ContentObservationV1,
    PreviousContentStateV1,
    ReplyDecisionRequestV1,
)
from aima_ugc.modules.collection import CollectionDecisionService


def _request(
    *,
    current_comment_count: int | None,
    previous_comment_count: int | None = None,
    existing: bool = False,
    comments_available: bool | None = True,
    search_missing_required_fields: bool = False,
    business_changed: bool = False,
    manual_deep_collection: bool = False,
    scheduled_refresh_checkpoint: bool = False,
) -> CollectionDecisionRequestV1:
    return CollectionDecisionRequestV1(
        current=ContentObservationV1(
            comment_count=current_comment_count,
            comments_available=comments_available,
            search_missing_required_fields=search_missing_required_fields,
            business_changed=business_changed,
        ),
        previous=(
            PreviousContentStateV1(comment_count=previous_comment_count) if existing else None
        ),
        context=CollectionDecisionContextV1(
            manual_deep_collection=manual_deep_collection,
            scheduled_refresh_checkpoint=scheduled_refresh_checkpoint,
        ),
        policy=CollectionDecisionPolicyV1(),
        capability=XHS_TIKHUB_CAPABILITY,
    )


def test_new_content_with_zero_comments_fetches_detail_but_short_circuits_comments() -> None:
    decision = CollectionDecisionService().decide(_request(current_comment_count=0))

    assert decision.detail_action == "fetch"
    assert decision.detail_reason == "new_content"
    assert decision.comment_action == "skip"
    assert decision.comment_reason == "provider_reported_zero"
    assert decision.comment_target is None


def test_existing_unchanged_comment_count_skips_detail_and_comments() -> None:
    decision = CollectionDecisionService().decide(
        _request(current_comment_count=35, previous_comment_count=35, existing=True)
    )

    assert decision.detail_action == "skip"
    assert decision.detail_reason == "unchanged"
    assert decision.comment_action == "skip"
    assert decision.comment_reason == "comment_count_unchanged"


def test_comment_count_increase_uses_controlled_refresh_without_proven_incremental_sort() -> None:
    decision = CollectionDecisionService().decide(
        _request(current_comment_count=41, previous_comment_count=35, existing=True)
    )

    assert decision.comment_action == "refresh_controlled"
    assert decision.comment_reason == "comment_count_increased_refresh"
    assert decision.comment_target == 41


def test_comment_count_increase_uses_incremental_only_when_capability_proves_it() -> None:
    incremental_capability = XHS_TIKHUB_CAPABILITY.model_copy(
        update={
            "operations": tuple(
                operation.model_copy(update={"supports_incremental_comment_sort": True})
                if operation.business_operation == "comments"
                else operation
                for operation in XHS_TIKHUB_CAPABILITY.operations
            )
        }
    )
    request = _request(current_comment_count=80, previous_comment_count=35, existing=True)
    request = request.model_copy(update={"capability": incremental_capability})

    decision = CollectionDecisionService().decide(request)

    assert decision.comment_action == "fetch_incremental"
    assert decision.comment_reason == "comment_count_increased_incremental"
    assert decision.comment_target == 50


def test_comment_count_decrease_never_guesses_specific_deletion() -> None:
    decision = CollectionDecisionService().decide(
        _request(current_comment_count=20, previous_comment_count=35, existing=True)
    )

    assert decision.comment_action == "refresh_controlled"
    assert decision.comment_reason == "comment_count_decreased"
    assert decision.comment_target == 20


def test_unknown_comment_count_is_not_treated_as_zero() -> None:
    new_decision = CollectionDecisionService().decide(_request(current_comment_count=None))
    assert new_decision.detail_action == "fetch"
    assert new_decision.comment_action == "defer_until_detail"
    assert new_decision.comment_reason == "comment_count_unknown_detail_required"

    existing_decision = CollectionDecisionService().decide(
        _request(current_comment_count=None, previous_comment_count=None, existing=True)
    )
    assert existing_decision.detail_action == "skip"
    assert existing_decision.comment_action == "probe_first_page"
    assert existing_decision.comment_reason == "comment_count_unknown_probe"


def test_comment_unavailable_and_detail_business_triggers_are_explicit() -> None:
    unavailable = CollectionDecisionService().decide(
        _request(current_comment_count=12, comments_available=False)
    )
    assert unavailable.comment_action == "skip"
    assert unavailable.comment_reason == "comments_unavailable"

    missing = CollectionDecisionService().decide(
        _request(
            current_comment_count=12,
            previous_comment_count=12,
            existing=True,
            search_missing_required_fields=True,
        )
    )
    assert missing.detail_action == "fetch"
    assert missing.detail_reason == "search_missing_required_fields"

    changed = CollectionDecisionService().decide(
        _request(
            current_comment_count=12,
            previous_comment_count=12,
            existing=True,
            business_changed=True,
        )
    )
    assert changed.detail_action == "fetch"
    assert changed.detail_reason == "configured_business_change"

    deep = CollectionDecisionService().decide(
        _request(
            current_comment_count=12,
            previous_comment_count=12,
            existing=True,
            manual_deep_collection=True,
        )
    )
    assert deep.detail_action == "fetch"
    assert deep.detail_reason == "manual_deep_collection"

    scheduled = CollectionDecisionService().decide(
        _request(
            current_comment_count=12,
            previous_comment_count=12,
            existing=True,
            scheduled_refresh_checkpoint=True,
        )
    )
    assert scheduled.detail_action == "fetch"
    assert scheduled.detail_reason == "scheduled_refresh_checkpoint"


def test_reply_decision_uses_explicit_zero_positive_and_unknown_semantics() -> None:
    service = CollectionDecisionService()

    zero = service.decide_reply(
        ReplyDecisionRequestV1(
            reply_count=0,
            policy=CollectionDecisionPolicyV1(),
            capability=XHS_TIKHUB_CAPABILITY,
        )
    )
    assert zero.action == "skip"
    assert zero.reason == "reply_count_zero"
    assert zero.target is None

    positive = service.decide_reply(
        ReplyDecisionRequestV1(
            reply_count=9,
            policy=CollectionDecisionPolicyV1(),
            capability=XHS_TIKHUB_CAPABILITY,
        )
    )
    assert positive.action == "fetch_target"
    assert positive.reason == "reply_count_positive"
    assert positive.target == 5

    unknown = service.decide_reply(
        ReplyDecisionRequestV1(
            reply_count=None,
            policy=CollectionDecisionPolicyV1(),
            capability=XHS_TIKHUB_CAPABILITY,
        )
    )
    assert unknown.action == "probe_first_page"
    assert unknown.reason == "reply_count_unknown_probe"
