from __future__ import annotations

import runpy
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARCHIVER_PATH = ROOT / "scripts" / "quality" / "archive_change_after_merge.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "change-archive.yml"


def _load_archiver() -> dict[str, Any]:
    """加载归档 helper，直接验证纯确定性核心。"""
    return runpy.run_path(str(ARCHIVER_PATH))


def _write(path: Path, content: str) -> None:
    """创建测试文件及父目录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_git(root: Path, *args: str) -> str:
    """在隔离仓库执行 Git 并返回标准输出。"""
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _change(
    change_id: str, *, status: str = "ready_for_review", updated: str = "2026-09-03"
) -> str:
    """返回带可检测正文的最小 current-schema Change。"""
    return f"""---
schema: coding-change/v1
id: {change_id}
title: Archive fixture
level: L2
status: {status}
owner: test
branch: test/archive
created: 2026-09-03
updated: {updated}
completion_gate: required
depends_on: []
affected_areas: []
affected_paths: []
contracts: []
data_changes: []
---

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 保持正文不变 | external:https://github.com/example/repo/issues/1#AC1 | satisfied | evidence |

# 完成审计

- [x] upstream_re_read：已重读。
- [x] change_coverage：已覆盖。
- [x] reverse_audit：已反查。
- [x] unresolved_cleared：已清零。
"""


def test_archive_moves_one_ready_change_and_only_freezes_lifecycle(tmp_path: Path) -> None:
    """归档成功时只移动同一 ID 并修改 status/updated。"""
    module = _load_archiver()
    change_id = "CHG-20260903-archive-fixture"
    source = tmp_path / f"changes/active/{change_id}/CHANGE.md"
    original = _change(change_id)
    _write(source, original)

    result = module["archive_change"](
        tmp_path,
        changed_paths=[f"changes/active/{change_id}/CHANGE.md", "backend/src/example.py"],
        merged_at="2026-09-04T16:30:00Z",
        expected_source=original,
    )

    target = tmp_path / f"changes/archive/2026-09/{change_id}/CHANGE.md"
    assert result.changed is True
    assert result.change_id == change_id
    assert source.exists() is False
    assert target.exists() is True
    archived = target.read_text(encoding="utf-8")
    assert "status: done" in archived
    assert "updated: 2026-09-05" in archived
    assert "# 需求追溯" in archived
    assert "保持正文不变" in archived
    assert (
        archived.replace("status: done", "status: ready_for_review").replace(
            "updated: 2026-09-05", "updated: 2026-09-03"
        )
        == original
    )


def test_archive_rerun_is_idempotent_only_for_same_merged_change(tmp_path: Path) -> None:
    """同一 merged PR 重跑时，完全匹配该 revision 的已归档 Change 才能安全 no-op。"""
    module = _load_archiver()
    change_id = "CHG-20260903-archive-fixture"
    original = _change(change_id)
    target = tmp_path / f"changes/archive/2026-09/{change_id}/CHANGE.md"
    _write(target, _change(change_id, status="done", updated="2026-09-05"))

    result = module["archive_change"](
        tmp_path,
        changed_paths=[f"changes/active/{change_id}/CHANGE.md"],
        merged_at="2026-09-04T16:30:00Z",
        expected_source=original,
    )

    assert result.changed is False
    assert result.reason == "already_archived"


def test_archive_rerun_rejects_archive_from_different_merged_content(tmp_path: Path) -> None:
    """source 已移走时不能只看 ID/status；archive 必须仍可证明属于本 merged PR。"""
    module = _load_archiver()
    error = module["ArchiveChangeError"]
    change_id = "CHG-20260903-archive-fixture"
    original = _change(change_id)
    target = tmp_path / f"changes/archive/2026-09/{change_id}/CHANGE.md"
    other = _change(change_id, status="done", updated="2026-09-05").replace(
        "保持正文不变", "另一版本正文"
    )
    _write(target, other)

    with pytest.raises(error, match="本 merged PR"):
        module["archive_change"](
            tmp_path,
            changed_paths=[f"changes/active/{change_id}/CHANGE.md"],
            merged_at="2026-09-04T16:30:00Z",
            expected_source=original,
        )


def test_archive_rejects_active_change_modified_after_merged_revision(tmp_path: Path) -> None:
    """main 后续若改写同一 Active Change，旧 merged PR 的归档必须 fail closed。"""
    module = _load_archiver()
    error = module["ArchiveChangeError"]
    change_id = "CHG-20260903-archive-fixture"
    original = _change(change_id)
    source = tmp_path / f"changes/active/{change_id}/CHANGE.md"
    _write(source, original.replace("保持正文不变", "后续 main 改写"))

    with pytest.raises(error, match="偏离本 merged PR"):
        module["archive_change"](
            tmp_path,
            changed_paths=[f"changes/active/{change_id}/CHANGE.md"],
            merged_at="2026-09-04T16:30:00Z",
            expected_source=original,
        )


def test_merged_source_requires_revision_in_current_main_history(tmp_path: Path) -> None:
    """归档证据必须来自当前 main 历史中的真实 merged revision。"""
    module = _load_archiver()
    error = module["ArchiveChangeError"]
    change_id = "CHG-20260903-archive-fixture"
    relative = f"changes/active/{change_id}/CHANGE.md"
    _run_git(tmp_path, "init", "-b", "main")
    _run_git(tmp_path, "config", "user.name", "AIMA Test")
    _run_git(tmp_path, "config", "user.email", "aima-test@example.invalid")
    _write(tmp_path / relative, _change(change_id))
    _run_git(tmp_path, "add", ".")
    _run_git(tmp_path, "commit", "-m", "merged revision")
    revision = _run_git(tmp_path, "rev-parse", "HEAD")

    actual = module["merged_source_at_revision"](
        tmp_path, revision=revision, source_relative=relative
    )
    assert actual == _change(change_id)

    _run_git(tmp_path, "checkout", "--orphan", "detached-history")
    _run_git(tmp_path, "rm", "-rf", ".")
    _write(tmp_path / "other.txt", "unrelated\n")
    _run_git(tmp_path, "add", ".")
    _run_git(tmp_path, "commit", "-m", "unrelated history")

    with pytest.raises(error, match="不是当前 main HEAD 的祖先"):
        module["merged_source_at_revision"](tmp_path, revision=revision, source_relative=relative)


def test_archive_fails_when_active_and_archive_both_exist(tmp_path: Path) -> None:
    """重复身份必须 fail closed，不能猜哪一份是 Owner。"""
    module = _load_archiver()
    error = module["ArchiveChangeError"]
    change_id = "CHG-20260903-archive-fixture"
    original = _change(change_id)
    _write(tmp_path / f"changes/active/{change_id}/CHANGE.md", original)
    _write(
        tmp_path / f"changes/archive/2026-09/{change_id}/CHANGE.md",
        _change(change_id, status="done"),
    )

    with pytest.raises(error, match="同时存在"):
        module["archive_change"](
            tmp_path,
            changed_paths=[f"changes/active/{change_id}/CHANGE.md"],
            merged_at="2026-09-04T16:30:00Z",
            expected_source=original,
        )


def test_archive_fails_for_multiple_active_changes(tmp_path: Path) -> None:
    """一个 PR 出现多个 Active Change 时必须 fail closed。"""
    module = _load_archiver()
    error = module["ArchiveChangeError"]

    with pytest.raises(error, match="只能.*一个 Active Change"):
        module["select_change"](
            [
                "changes/active/CHG-20260903-a/CHANGE.md",
                "changes/active/CHG-20260903-b/CHANGE.md",
            ]
        )


def test_archive_fails_for_non_ready_change(tmp_path: Path) -> None:
    """基础设施不能把仍在开发中的 Change 伪造成 done。"""
    module = _load_archiver()
    error = module["ArchiveChangeError"]
    change_id = "CHG-20260903-archive-fixture"
    original = _change(change_id, status="in_progress")
    _write(
        tmp_path / f"changes/active/{change_id}/CHANGE.md",
        original,
    )

    with pytest.raises(error, match="ready_for_review"):
        module["archive_change"](
            tmp_path,
            changed_paths=[f"changes/active/{change_id}/CHANGE.md"],
            merged_at="2026-09-04T16:30:00Z",
            expected_source=original,
        )


def test_no_active_change_is_explicit_not_applicable(tmp_path: Path) -> None:
    """没有持久 Change 的 Implementation PR 不应为形式创建 archive。"""
    module = _load_archiver()

    result = module["archive_change"](
        tmp_path,
        changed_paths=["backend/src/example.py"],
        merged_at="2026-09-04T16:30:00Z",
    )

    assert result.changed is False
    assert result.reason == "not_applicable_no_active_change"


def test_change_archive_workflow_is_narrow_serial_and_rerunnable() -> None:
    """Workflow 只能由 merged PR/dispatch 进入，串行且使用窄权限专用 App token。"""
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    required_fragments = [
        "pull_request:",
        "types: [closed]",
        "workflow_dispatch:",
        "pr_number:",
        "permissions:\n  contents: read\n  pull-requests: read",
        "github.event.pull_request.merged == true",
        "group: change-archive-main",
        "cancel-in-progress: false",
        "environment: change-archive-main",
        "configured=false",
        "actions/create-github-app-token@v2",
        "CHANGE_ARCHIVE_APP_ID",
        "CHANGE_ARCHIVE_APP_PRIVATE_KEY",
        "merge_commit_sha",
        "--merged-revision",
        "archive_change_after_merge.py",
        "check_change_completion.py",
        "ARCHIVE_PARENT=",
        "CURRENT_MAIN=",
        "git push origin HEAD:main",
    ]
    for fragment in required_fragments:
        assert fragment in workflow
    assert "\n  push:" not in workflow
    assert "contents: write" not in workflow
