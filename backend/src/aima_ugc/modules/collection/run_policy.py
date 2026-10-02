"""冻结Run的类型与评论执行语义，供创建和恢复入口共用。"""

from collections.abc import Mapping
from typing import Protocol

from aima_ugc.contracts.collection import CollectionDecisionPolicyV1

_SUPPLEMENT_MODES = frozenset({"batch_supplement", "content_supplement", "date_supplement"})


class _RunSnapshot(Protocol):
    @property
    def config_snapshot(self) -> dict[str, object]: ...


def validate_run_plan_type(snapshot: Mapping[str, object]) -> None:
    """未知类型在创建Scope或请求前拒绝；历史兼容只在已有版本的真实边界内。"""
    plan_type = snapshot.get("plan_type")
    version = snapshot.get("schema_version")
    if plan_type is None:
        if version == "collection-run-config.v2":
            return
        # v3是已经投产的定向补采格式，并非计划快照；必须同时具有明确补采模式。
        if version == "collection-run-config.v3" and snapshot.get("mode") == "content_supplement":
            return
        raise ValueError("Collection Run 缺少显式plan_type")
    if plan_type != "tikhub":
        raise ValueError("unsupported collection plan_type")


def requires_full_comment_capture(run: _RunSnapshot) -> bool:
    """计划full与所有既有补采复用同一个生产分页语义。"""
    snapshot = run.config_snapshot
    return snapshot.get("mode") in _SUPPLEMENT_MODES or snapshot.get("comment_policy") == "full"


def validate_run_decision_policy(snapshot: Mapping[str, object]) -> None:
    validate_run_plan_type(snapshot)
    policy = CollectionDecisionPolicyV1.model_validate(snapshot.get("decision_policy", {}))
    if snapshot.get("detail_policy", "on_change") != "on_change":
        raise ValueError("Collection Scope Runtime 当前只支持 detail_policy=on_change")
    if snapshot.get("comment_policy", "adaptive") != policy.comment_mode:
        raise ValueError("Collection Run comment_policy与decision_policy不一致")


def validate_new_run_snapshot(snapshot: Mapping[str, object]) -> None:
    """所有新Run必须写当前显式格式；历史兼容仅服务已持久化快照的恢复。"""
    if snapshot.get("schema_version") != "collection-run-config.v4":
        raise ValueError("新Collection Run必须使用collection-run-config.v4")
    if "plan_type" not in snapshot:
        raise ValueError("新Collection Run缺少显式plan_type")
    if "comment_policy" not in snapshot or "decision_policy" not in snapshot:
        raise ValueError("新Collection Run缺少冻结评论执行策略")
    validate_run_decision_policy(snapshot)
