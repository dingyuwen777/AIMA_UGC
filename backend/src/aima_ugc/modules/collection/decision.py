"""Stage 7 采集后续动作的纯业务决策。"""

from __future__ import annotations

from aima_ugc.contracts.collection import (
    CollectionDecisionRequestV1,
    CollectionDecisionV1,
    ReplyDecisionRequestV1,
    ReplyDecisionV1,
)


class CollectionDecisionService:
    """只根据规范化当前/历史事实和 Capability 决定后续动作。"""

    def decide(self, request: CollectionDecisionRequestV1) -> CollectionDecisionV1:
        detail_action, detail_reason = self._detail_decision(request)
        comment_action, comment_reason, comment_target = self._comment_decision(
            request,
            detail_action=detail_action,
        )
        return CollectionDecisionV1(
            detail_action=detail_action,
            detail_reason=detail_reason,
            comment_action=comment_action,
            comment_reason=comment_reason,
            comment_target=comment_target,
            reply_target_per_root=(
                request.policy.reply_target_per_root
                if comment_action
                in {
                    "fetch_adaptive",
                    "fetch_incremental",
                    "refresh_controlled",
                    "probe_first_page",
                }
                else None
            ),
        )

    def decide_reply(self, request: ReplyDecisionRequestV1) -> ReplyDecisionV1:
        sub_comments = request.capability.operation("sub_comments")
        comments = request.capability.operation("comments")
        if sub_comments is None or comments is None or not comments.supports_sub_comments:
            return ReplyDecisionV1(action="skip", reason="sub_comments_unavailable")

        if request.reply_count == 0:
            return ReplyDecisionV1(action="skip", reason="reply_count_zero")
        if request.reply_count is None:
            return ReplyDecisionV1(
                action="probe_first_page",
                reason="reply_count_unknown_probe",
                target=request.policy.reply_target_per_root,
            )

        return ReplyDecisionV1(
            action="fetch_target",
            reason="reply_count_positive",
            target=min(request.reply_count, request.policy.reply_target_per_root),
        )

    @staticmethod
    def _detail_decision(
        request: CollectionDecisionRequestV1,
    ) -> tuple[str, str]:
        desired_reason: str | None = None
        if request.context.manual_deep_collection:
            desired_reason = "manual_deep_collection"
        elif request.context.scheduled_refresh_checkpoint:
            desired_reason = "scheduled_refresh_checkpoint"
        elif request.previous is None:
            desired_reason = "new_content"
        elif request.current.search_missing_required_fields:
            desired_reason = "search_missing_required_fields"
        elif request.current.business_changed:
            desired_reason = "configured_business_change"

        if desired_reason is None:
            return "skip", "unchanged"
        if request.capability.operation("content_detail") is None:
            return "skip", "detail_operation_unavailable"
        return "fetch", desired_reason

    @classmethod
    def _comment_decision(
        cls,
        request: CollectionDecisionRequestV1,
        *,
        detail_action: str,
    ) -> tuple[str, str, int | None]:
        policy = request.policy
        if not policy.comments_enabled:
            return "skip", "comments_disabled", None

        comments = request.capability.operation("comments")
        if comments is None:
            return "skip", "comments_operation_unavailable", None
        if request.current.comments_available is False:
            return "skip", "comments_unavailable", None

        current_count = request.current.comment_count
        if current_count == 0:
            return "skip", "provider_reported_zero", None

        if current_count is None:
            detail = request.capability.operation("content_detail")
            if detail_action == "fetch" and detail is not None and detail.observes_comment_count:
                return "defer_until_detail", "comment_count_unknown_detail_required", None
            return "probe_first_page", "comment_count_unknown_probe", policy.sample_target

        target = cls._comment_target(current_count, request)
        if request.previous is None:
            return "fetch_adaptive", "new_content_comments", target

        previous_count = request.previous.comment_count
        if previous_count is None:
            return "fetch_adaptive", "comment_count_became_known", target

        if current_count == previous_count:
            if policy.comment_refresh_when_count_unchanged:
                return "refresh_controlled", "comment_count_unchanged_refresh", target
            return "skip", "comment_count_unchanged", None

        if current_count > previous_count:
            if comments.supports_incremental_comment_sort:
                return "fetch_incremental", "comment_count_increased_incremental", target
            return "refresh_controlled", "comment_count_increased_refresh", target

        return "refresh_controlled", "comment_count_decreased", target

    @staticmethod
    def _comment_target(
        current_count: int,
        request: CollectionDecisionRequestV1,
    ) -> int:
        policy = request.policy
        if current_count <= policy.full_fetch_threshold:
            return current_count
        return min(current_count, policy.sample_target)
