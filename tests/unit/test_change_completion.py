from __future__ import annotations

import runpy
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts" / "quality" / "check_change_completion.py"
READY_CHECK_PATH = ROOT / ".agents" / "skills" / "coding" / "scripts" / "ready_check.py"


def _load_checker() -> dict[str, Any]:
    """加载项目 Change 完成门禁；Red 阶段该文件尚不存在。"""
    return runpy.run_path(str(CHECKER_PATH))


def _run_git(root: Path, *args: str) -> str:
    """在隔离测试仓库执行 Git 并返回标准输出。"""
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _write(path: Path, content: str) -> None:
    """写入隔离仓库夹具。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_repository(root: Path) -> None:
    """创建具备确定身份和初始 Requirement Source 的最小 Git 仓库。"""
    _run_git(root, "init", "-b", "main")
    _run_git(root, "config", "user.name", "AIMA Test")
    _run_git(root, "config", "user.email", "aima-test@example.invalid")
    _write(root / "requirements.md", "# Test requirements\n")


def _commit(root: Path, message: str) -> str:
    """提交隔离仓库当前变化并返回提交 SHA。"""
    _run_git(root, "add", ".")
    _run_git(root, "commit", "-m", message)
    return _run_git(root, "rev-parse", "HEAD")


def _current_change(
    change_id: str,
    *,
    status: str = "ready_for_review",
    source: str = "requirements.md#AC1",
) -> str:
    """返回可通过 installed validator 的最小当前 Change。"""
    return f"""---
schema: coding-change/v1
id: {change_id}
title: Test change
level: L2
status: {status}
owner: test
branch: test/change
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: []
affected_areas:
  - governance
affected_paths:
  - requirements.md
contracts: []
data_changes: []
---

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Test requirement | {source} | satisfied | Test evidence |

# Completion Audit

- [x] upstream_re_read: Re-read requirements.
- [x] change_coverage: Requirement is covered.
- [x] reverse_audit: Consumer path is covered.
- [x] unresolved_cleared: No unresolved requirement.
"""


def _legacy_change() -> str:
    """返回只用于不可变历史归档策略的 legacy Change。"""
    return """---
schema: rvc-change/v1
id: CHG-20260801-legacy-history
status: archived
---

# Historical record
"""


def _unversioned_legacy_change() -> str:
    """返回 schema 机制引入前的不可变历史 Change。"""
    return """---
id: CHG-20260801-unversioned-history
status: done
---

# Historical record before schema
"""


def _check(root: Path, **kwargs: object) -> dict[str, Any]:
    """调用项目 checker，并显式复用当前安装的 validator。"""
    checker = _load_checker()
    return checker["check_repository"](
        root,
        ready_check_path=READY_CHECK_PATH,
        **kwargs,
    )


def test_changed_in_progress_current_change_fails(tmp_path: Path) -> None:
    """PR 中新增且仍为 in_progress 的顶层当前 Change 必须失败。"""
    _init_repository(tmp_path)
    base = _commit(tmp_path, "初始化")
    _write(
        tmp_path / "changes/active/CHG-20260902-current/CHANGE.md",
        _current_change("CHG-20260902-current", status="in_progress"),
    )
    _commit(tmp_path, "新增进行中变更")

    result = _check(tmp_path, changed_since=base)

    assert result["ok"] is False
    assert result["change_root"] == "changes"
    assert result["gated"] == 1
    assert any("ready_for_review" in error["message"] for error in result["errors"])


def test_ready_current_change_and_unchanged_legacy_archive_pass(tmp_path: Path) -> None:
    """Ready 当前 Change 应通过，未改动 legacy 归档不应触发迁移。"""
    _init_repository(tmp_path)
    _write(
        tmp_path / "changes/archive/2026-08/CHG-20260801-legacy-history/CHANGE.md",
        _legacy_change(),
    )
    _write(
        tmp_path / "changes/archive/2026-08/CHG-20260801-unversioned-history/CHANGE.md",
        _unversioned_legacy_change(),
    )
    base = _commit(tmp_path, "归档历史变更")
    _write(
        tmp_path / "changes/active/CHG-20260902-current/CHANGE.md",
        _current_change("CHG-20260902-current"),
    )
    _commit(tmp_path, "新增已就绪变更")

    result = _check(tmp_path, changed_since=base)

    assert result == {
        "ok": True,
        "change_root": "changes",
        "gated": 1,
        "strict_checked": 1,
        "legacy": 2,
        "errors": [],
    }


def test_ready_current_change_requires_stable_acceptance_binding(tmp_path: Path) -> None:
    """Ready Change 只引用整个需求文件而未绑定 AC 时必须失败。"""
    _init_repository(tmp_path)
    base = _commit(tmp_path, "初始化")
    _write(
        tmp_path / "changes/active/CHG-20260902-current/CHANGE.md",
        _current_change("CHG-20260902-current", source="requirements.md"),
    )
    _commit(tmp_path, "新增泛化需求来源")

    result = _check(tmp_path, changed_since=base)

    assert result["ok"] is False
    assert any("稳定 Acceptance" in error["message"] for error in result["errors"])


def test_archived_current_change_preserves_source_that_existed_at_archive_revision(
    tmp_path: Path,
) -> None:
    """归档后正常删除旧 Owner 文件时，历史 Source 必须按归档 revision 验真而不是改写历史。"""
    _init_repository(tmp_path)
    archived = tmp_path / "changes/archive/2026-09/CHG-20260902-current/CHANGE.md"
    _write(
        archived,
        _current_change("CHG-20260902-current", status="done"),
    )
    _commit(tmp_path, "归档当前变更")
    (tmp_path / "requirements.md").unlink()
    _commit(tmp_path, "后续删除旧来源文件")

    result = _check(tmp_path)

    assert result["ok"] is True
    assert result["gated"] == 1
    assert result["strict_checked"] == 1
    assert result["errors"] == []


def test_archived_current_change_rejects_source_that_never_existed_in_archive_revision(
    tmp_path: Path,
) -> None:
    """archive fast path 只接受历史 revision 的真实来源，不能让虚构路径借归档绕过。"""
    _init_repository(tmp_path)
    archived = tmp_path / "changes/archive/2026-09/CHG-20260902-current/CHANGE.md"
    _write(
        archived,
        _current_change(
            "CHG-20260902-current",
            status="done",
            source="never-existed.md",
        ),
    )
    _commit(tmp_path, "归档带无效来源的变更")

    result = _check(tmp_path)

    assert result["ok"] is False
    assert any("never-existed.md" in error["message"] for error in result["errors"])


def test_archived_current_change_rejects_directory_source_at_archive_revision(
    tmp_path: Path,
) -> None:
    """历史来源即使曾是 Git tree 也不能冒充 validator 所要求的仓库文件。"""
    _init_repository(tmp_path)
    source_dir = tmp_path / "historical-source"
    _write(source_dir / "proof.md", "# directory fixture\n")
    archived = tmp_path / "changes/archive/2026-09/CHG-20260902-current/CHANGE.md"
    _write(
        archived,
        _current_change(
            "CHG-20260902-current",
            status="done",
            source="historical-source",
        ),
    )
    _commit(tmp_path, "归档目录来源反例")
    shutil.rmtree(source_dir)
    _commit(tmp_path, "后续删除目录")

    result = _check(tmp_path)

    assert result["ok"] is False
    assert any("historical-source" in error["message"] for error in result["errors"])


def test_active_current_change_still_requires_source_in_current_head(tmp_path: Path) -> None:
    """历史兼容只属于 archive；Active Change 的 Requirement Source 仍必须当前可访问。"""
    _init_repository(tmp_path)
    active = tmp_path / "changes/active/CHG-20260902-current/CHANGE.md"
    _write(active, _current_change("CHG-20260902-current"))
    _commit(tmp_path, "新增当前变更")
    (tmp_path / "requirements.md").unlink()
    _commit(tmp_path, "删除当前来源文件")

    result = _check(tmp_path, require_active_ready=True)

    assert result["ok"] is False
    assert any("requirements.md" in error["message"] for error in result["errors"])


def test_modified_legacy_archive_fails(tmp_path: Path) -> None:
    """legacy 历史归档一旦被修改，changed-since 必须失败关闭。"""
    _init_repository(tmp_path)
    legacy = tmp_path / "changes/archive/2026-08/CHG-20260801-legacy-history/CHANGE.md"
    _write(legacy, _legacy_change())
    base = _commit(tmp_path, "归档历史变更")
    _write(legacy, _legacy_change() + "\nmodified\n")
    _commit(tmp_path, "修改历史变更")

    result = _check(tmp_path, changed_since=base)

    assert result["ok"] is False
    assert any("legacy" in error["message"] for error in result["errors"])


def test_legacy_change_in_active_fails(tmp_path: Path) -> None:
    """legacy schema 不得出现在 Active carrier。"""
    _init_repository(tmp_path)
    _write(
        tmp_path / "changes/active/CHG-20260801-legacy-history/CHANGE.md",
        _legacy_change(),
    )
    _commit(tmp_path, "错误激活历史变更")

    result = _check(tmp_path, require_active_ready=True)

    assert result["ok"] is False
    assert any(
        "legacy" in error["message"] and "active" in error["message"] for error in result["errors"]
    )


def test_unknown_schema_fails(tmp_path: Path) -> None:
    """未知 schema 不得被静默当成非 gated 文件跳过。"""
    _init_repository(tmp_path)
    _write(
        tmp_path / "changes/active/CHG-20260902-unknown/CHANGE.md",
        _current_change("CHG-20260902-unknown").replace(
            "schema: coding-change/v1",
            "schema: unknown-change/v9",
        ),
    )
    _commit(tmp_path, "新增未知变更")

    result = _check(tmp_path, require_active_ready=True)

    assert result["ok"] is False
    assert any("schema" in error["message"] for error in result["errors"])


def test_deleted_current_change_fails_changed_since(tmp_path: Path) -> None:
    """删除当前 Change 不能成为绕过 PR changed-since 的手段。"""
    _init_repository(tmp_path)
    change = tmp_path / "changes/active/CHG-20260902-current/CHANGE.md"
    _write(change, _current_change("CHG-20260902-current"))
    base = _commit(tmp_path, "新增当前变更")
    change.unlink()
    _commit(tmp_path, "删除当前变更")

    result = _check(tmp_path, changed_since=base)

    assert result["ok"] is False
    assert any("删除" in error["message"] for error in result["errors"])


def test_current_change_cannot_move_from_active_to_archive_in_pr(tmp_path: Path) -> None:
    """普通 PR 即使同一 ID/合法 done，也不能提前从 Active 归档。"""
    _init_repository(tmp_path)
    active = tmp_path / "changes/active/CHG-20260902-current/CHANGE.md"
    _write(active, _current_change("CHG-20260902-current"))
    base = _commit(tmp_path, "新增当前变更")
    archived = tmp_path / "changes/archive/2026-09/CHG-20260902-current/CHANGE.md"
    _write(
        archived,
        _current_change("CHG-20260902-current").replace(
            "status: ready_for_review",
            "status: done",
        ),
    )
    active.unlink()
    _commit(tmp_path, "尝试提前归档当前变更")

    result = _check(tmp_path, changed_since=base)

    assert result["ok"] is False
    assert any("Change Archive Automation" in error["message"] for error in result["errors"])
