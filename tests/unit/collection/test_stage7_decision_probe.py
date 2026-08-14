"""Stage 7 Business Decision Probe 只负责准备输入并调用正式决策。"""

from scripts.dev.probe_collection_decision import evaluate_payload


def test_probe_defaults_to_current_xhs_capability_and_returns_explainable_decision() -> None:
    decision = evaluate_payload(
        {
            "current": {"comment_count": 35, "comments_available": True},
            "previous": {"comment_count": 35},
        }
    )

    assert decision["detail_action"] == "skip"
    assert decision["detail_reason"] == "unchanged"
    assert decision["comment_action"] == "skip"
    assert decision["comment_reason"] == "comment_count_unchanged"


def test_probe_zero_comment_keeps_zero_semantics() -> None:
    decision = evaluate_payload({"current": {"comment_count": 0}})

    assert decision["detail_action"] == "fetch"
    assert decision["comment_action"] == "skip"
    assert decision["comment_reason"] == "provider_reported_zero"
