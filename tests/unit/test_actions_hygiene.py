from __future__ import annotations

import runpy
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/quality/actions_hygiene.py"
MODULE = runpy.run_path(str(SCRIPT))
BUILD_PLAN = MODULE["build_cleanup_plan"]
PATH_IN_HISTORY = MODULE["path_existed_in_head_history"]
CLASSIFIER_PATH = ROOT / "scripts/quality/classify_ci_scope.py"
CLASSIFIER = runpy.run_path(str(CLASSIFIER_PATH))
CLASSIFY_PATHS = CLASSIFIER["classify_paths"]


def test_current_workflow_is_always_protected() -> None:
    """当前 main 仍存在的 Workflow 必须无条件排除在删除计划外。"""
    path = ".github/workflows/ci.yml"
    plan = BUILD_PLAN(
        {path},
        {path},
        [{"id": 1, "path": path, "name": "CI", "status": "completed"}],
    )
    assert plan["eligible_runs"] == []
    assert plan["protected_current_workflows"] == [path]


def test_pr_only_workflow_is_not_cleanup_candidate() -> None:
    """从未进入 main 历史的 PR-only Workflow 不得自动删除历史。"""
    path = ".github/workflows/pr-only.yml"
    plan = BUILD_PLAN(
        {".github/workflows/ci.yml"},
        set(),
        [{"id": 2, "path": path, "name": "PR only", "status": "completed"}],
    )
    assert plan["eligible_runs"] == []
    assert plan["skipped_not_main_history"] == [path]


def test_active_run_skips_entire_obsolete_workflow() -> None:
    """候选 Workflow 存在未完成 run 时必须整条跳过，等待后续 main push 重试。"""
    path = ".github/workflows/old.yml"
    plan = BUILD_PLAN(
        {".github/workflows/ci.yml"},
        {path},
        [
            {"id": 3, "path": path, "name": "Old", "status": "completed"},
            {"id": 4, "path": path, "name": "Old", "status": "queued"},
        ],
    )
    assert plan["eligible_runs"] == []
    assert plan["skipped_active_workflows"] == {path: ["queued"]}


def test_completed_obsolete_workflow_has_deterministic_delete_plan() -> None:
    """只剩 completed runs 的失效 Workflow 应按 id 稳定形成删除计划。"""
    path = ".github/workflows/old.yml"
    plan = BUILD_PLAN(
        {".github/workflows/ci.yml"},
        {path},
        [
            {"id": 9, "path": path, "name": "Old", "status": "completed"},
            {"id": 8, "path": path, "name": "Old", "status": "completed"},
        ],
    )
    assert [item["id"] for item in plan["eligible_runs"]] == [8, 9]
    assert plan["candidate_workflows"] == [path]


def test_git_history_distinguishes_merged_deleted_from_pr_only_path() -> None:
    """真实 Git HEAD 祖先历史必须证明 path 曾进入默认分支后才允许清理。"""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "ci@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "CI"], cwd=root, check=True)
        workflow = root / ".github/workflows/old.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: Old\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "add old workflow"], cwd=root, check=True)
        workflow.unlink()
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "remove old workflow"], cwd=root, check=True)

        assert PATH_IN_HISTORY(root, ".github/workflows/old.yml") is True
        assert PATH_IN_HISTORY(root, ".github/workflows/pr-only.yml") is False


def test_actions_hygiene_script_uses_repository_quality_profile() -> None:
    """只修改 Hygiene 脚本和专属测试时应走 repository_quality，不启动产品全栈。"""
    assert CLASSIFY_PATHS(
        [
            "scripts/quality/actions_hygiene.py",
            "tests/unit/test_actions_hygiene.py",
        ]
    ) == "repository_quality"


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
        "::warning::Actions Hygiene failed",
    ):
        assert fragment in hygiene
