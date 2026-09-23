from __future__ import annotations

import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/quality/actions_hygiene.py"
MODULE = runpy.run_path(str(SCRIPT))
SELECT_STALE = MODULE["select_stale_workflows"]
BUILD_PLAN = MODULE["build_cleanup_plan"]
PATH_IN_HISTORY = MODULE["path_existed_in_head_history"]
LIST_WORKFLOW_RUNS = MODULE["list_workflow_runs"]
RUN_HYGIENE = MODULE["run_hygiene"]
RUNTIME_GLOBALS = RUN_HYGIENE.__globals__
MAIN = MODULE["main"]
MAIN_GLOBALS = MAIN.__globals__
TRANSIENT_ERROR = MODULE["TransientGitHubApiError"]
CLASSIFIER = runpy.run_path(str(ROOT / "scripts/quality/classify_ci_scope.py"))
CLASSIFY_PATHS = CLASSIFIER["classify_paths"]


def test_current_workflow_record_is_always_protected() -> None:
    """当前 main 仍存在的 Workflow record 必须无条件排除在 stale candidate 外。"""
    path = ".github/workflows/ci.yml"
    selection = SELECT_STALE(
        {path},
        {path},
        [{"id": 1, "path": path, "name": "CI", "state": "active"}],
    )
    assert selection["stale_workflows"] == []
    assert selection["protected_current_workflows"] == [path]


def test_pr_only_workflow_record_is_not_cleanup_candidate() -> None:
    """从未进入 main first-parent 历史的 PR-only Workflow record 不得自动删除。"""
    path = ".github/workflows/pr-only.yml"
    selection = SELECT_STALE(
        {".github/workflows/ci.yml"},
        set(),
        [{"id": 2, "path": path, "name": "PR only", "state": "disabled"}],
    )
    assert selection["stale_workflows"] == []
    assert selection["skipped_not_main_history"] == [path]


def test_active_run_skips_entire_stale_workflow() -> None:
    """stale Workflow 存在未完成 run 时整条跳过，等待后续 main push 重试。"""
    workflow = {
        "id": 3,
        "path": ".github/workflows/old.yml",
        "name": "Old",
        "state": "disabled",
    }
    plan = BUILD_PLAN(
        {".github/workflows/ci.yml"},
        [workflow],
        {
            3: [
                {"id": 30, "path": workflow["path"], "name": "Old", "status": "completed"},
                {"id": 31, "path": workflow["path"], "name": "Old", "status": "queued"},
            ]
        },
    )
    assert plan["eligible_runs"] == []
    assert plan["skipped_active_workflows"] == {workflow["path"]: ["queued"]}


def test_completed_stale_workflow_has_deterministic_delete_plan() -> None:
    """只剩 completed runs 的 stale Workflow 应按 run id 稳定进入删除计划。"""
    workflow = {
        "id": 4,
        "path": ".github/workflows/old.yml",
        "name": "Old",
        "state": "disabled",
    }
    plan = BUILD_PLAN(
        {".github/workflows/ci.yml"},
        [workflow],
        {
            4: [
                {"id": 42, "path": workflow["path"], "name": "Old", "status": "completed"},
                {"id": 41, "path": workflow["path"], "name": "Old", "status": "completed"},
            ]
        },
    )
    assert [item["id"] for item in plan["eligible_runs"]] == [41, 42]
    assert plan["targeted_run_count"] == 2


def test_first_parent_history_distinguishes_main_deleted_from_pr_only() -> None:
    """first-parent 历史必须区分 main 真删除与只存在于被 merge 支线的临时 Workflow。"""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "ci@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "CI"], cwd=root, check=True)

        old = root / ".github/workflows/old.yml"
        old.parent.mkdir(parents=True)
        old.write_text("name: Old\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "add old"], cwd=root, check=True)
        old.unlink()
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "remove old"], cwd=root, check=True)

        subprocess.run(["git", "switch", "-qc", "feature"], cwd=root, check=True)
        pr_only = root / ".github/workflows/pr-only.yml"
        pr_only.write_text("name: PR only\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "add pr-only"], cwd=root, check=True)
        pr_only.unlink()
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "remove pr-only"], cwd=root, check=True)
        subprocess.run(["git", "switch", "-q", "main"], cwd=root, check=True)
        subprocess.run(
            ["git", "merge", "--no-ff", "-qm", "merge feature", "feature"],
            cwd=root,
            check=True,
        )

        assert PATH_IN_HISTORY(root, ".github/workflows/old.yml") is True
        assert PATH_IN_HISTORY(root, ".github/workflows/pr-only.yml") is False


def test_workflow_run_listing_is_targeted_by_workflow_id() -> None:
    """定向分页只访问 workflow-id runs endpoint，禁止回退到全仓 runs 扫描。"""
    globals_ = LIST_WORKFLOW_RUNS.__globals__
    old_request = globals_["_api_request"]
    requested: list[str] = []
    pages = [
        {
            "workflow_runs": [
                {
                    "id": 51,
                    "path": ".github/workflows/old.yml",
                    "name": "Old",
                    "status": "completed",
                }
            ]
        },
        {"workflow_runs": []},
    ]
    try:
        def fake_request(token, method, path, **kwargs):
            requested.append(path)
            return pages.pop(0)

        globals_["_api_request"] = fake_request
        runs = LIST_WORKFLOW_RUNS("owner/repo", "token", 123)
    finally:
        globals_["_api_request"] = old_request

    assert [item["id"] for item in runs] == [51]
    assert requested
    assert all("/actions/workflows/123/runs?" in path for path in requested)
    assert all("/actions/runs?" not in path for path in requested)


def test_execute_deletes_targeted_snapshot_then_requires_zero_readback() -> None:
    """execute 只删除 stale workflow 的定向快照，并逐 workflow ID fresh readback。"""
    names = (
        "current_workflow_paths",
        "list_repository_workflows",
        "main_history_workflow_paths",
        "list_workflow_runs",
        "workflow_run_count",
        "_api_request",
    )
    saved = {name: RUNTIME_GLOBALS[name] for name in names}
    deleted: list[str] = []
    stale_path = ".github/workflows/old.yml"
    try:
        RUNTIME_GLOBALS["current_workflow_paths"] = lambda root: {".github/workflows/ci.yml"}
        RUNTIME_GLOBALS["list_repository_workflows"] = lambda repository, token: [
            {"id": 9, "path": stale_path, "name": "Old", "state": "disabled"}
        ]
        RUNTIME_GLOBALS["main_history_workflow_paths"] = lambda root, observed: {stale_path}
        RUNTIME_GLOBALS["list_workflow_runs"] = lambda repository, token, workflow_id: [
            {"id": 90, "path": stale_path, "name": "Old", "status": "completed"}
        ]
        RUNTIME_GLOBALS["workflow_run_count"] = lambda repository, token, workflow_id: 0
        RUNTIME_GLOBALS["_api_request"] = (
            lambda token, method, path, **kwargs: deleted.append(path)
            if method == "DELETE"
            else None
        )
        payload = RUN_HYGIENE(ROOT, "owner/repo", "token", execute=True)
    finally:
        RUNTIME_GLOBALS.update(saved)

    assert deleted == ["/repos/owner/repo/actions/runs/90"]
    assert payload["targeted_run_count"] == 1
    assert payload["deleted_run_count"] == 1
    assert payload["remaining_eligible_run_count"] == 0


def test_execute_fails_when_targeted_readback_still_has_runs() -> None:
    """DELETE 后 stale workflow ID 仍有 run 时必须硬失败，不能伪造清理完成。"""
    names = (
        "current_workflow_paths",
        "list_repository_workflows",
        "main_history_workflow_paths",
        "list_workflow_runs",
        "workflow_run_count",
        "_api_request",
    )
    saved = {name: RUNTIME_GLOBALS[name] for name in names}
    stale_path = ".github/workflows/old.yml"
    try:
        RUNTIME_GLOBALS["current_workflow_paths"] = lambda root: {".github/workflows/ci.yml"}
        RUNTIME_GLOBALS["list_repository_workflows"] = lambda repository, token: [
            {"id": 10, "path": stale_path, "name": "Old", "state": "disabled"}
        ]
        RUNTIME_GLOBALS["main_history_workflow_paths"] = lambda root, observed: {stale_path}
        RUNTIME_GLOBALS["list_workflow_runs"] = lambda repository, token, workflow_id: [
            {"id": 100, "path": stale_path, "name": "Old", "status": "completed"}
        ]
        RUNTIME_GLOBALS["workflow_run_count"] = lambda repository, token, workflow_id: 1
        RUNTIME_GLOBALS["_api_request"] = lambda token, method, path, **kwargs: None
        with pytest.raises(RuntimeError, match="fresh readback"):
            RUN_HYGIENE(ROOT, "owner/repo", "token", execute=True)
    finally:
        RUNTIME_GLOBALS.update(saved)


def test_cli_distinguishes_transient_and_hard_failures() -> None:
    """CLI 只把临时 GitHub API 错误映射为 75，权限/不变量错误保持普通失败。"""
    old_run = MAIN_GLOBALS["run_hygiene"]
    old_token = MAIN_GLOBALS["_token"]
    old_argv = sys.argv[:]
    try:
        MAIN_GLOBALS["_token"] = lambda: "fixture-token"
        sys.argv = ["actions_hygiene.py", "--repository", "owner/repo"]

        def transient(*args, **kwargs):
            raise TRANSIENT_ERROR("temporary")

        MAIN_GLOBALS["run_hygiene"] = transient
        assert MAIN() == 75

        def hard(*args, **kwargs):
            raise RuntimeError("hard")

        MAIN_GLOBALS["run_hygiene"] = hard
        assert MAIN() == 1
    finally:
        MAIN_GLOBALS["run_hygiene"] = old_run
        MAIN_GLOBALS["_token"] = old_token
        sys.argv = old_argv


def test_actions_hygiene_script_uses_repository_quality_profile() -> None:
    """只修改 Hygiene 脚本和专属测试时应走 repository_quality，不启动产品全栈。"""
    assert (
        CLASSIFY_PATHS(
            [
                "scripts/quality/actions_hygiene.py",
                "tests/unit/test_actions_hygiene.py",
            ]
        )
        == "repository_quality"
    )


def test_ci_owns_hygiene_with_job_level_actions_write_only() -> None:
    """AIMA 必须复用现有 CI，并把 destructive 权限限制在 main-only hygiene job。"""
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    header, jobs = workflow.split("jobs:", 1)
    assert "actions: write" not in header
    assert "  actions-hygiene:" in jobs
    hygiene = jobs.split("  actions-hygiene:", 1)[1]
    for fragment in (
        "name: Actions Hygiene",
        "github.event_name == 'push'",
        "refs/heads/main",
        "needs: ci-gate",
        "actions: write",
        "contents: read",
        "fetch-depth: 0",
        "scripts/quality/actions_hygiene.py",
        "--execute",
        'status}" -eq 75',
        "::warning::Actions Hygiene temporary GitHub API failure",
        "Actions Hygiene invariant/permission failure",
    ):
        assert fragment in hygiene
