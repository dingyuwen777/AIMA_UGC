from __future__ import annotations

import runpy
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE_EVIDENCE_PATH = ROOT / "scripts" / "quality" / "release_evidence.py"


def _load_release_evidence() -> dict[str, Any]:
    return runpy.run_path(str(RELEASE_EVIDENCE_PATH))


REQUIRED_CHECKS = (
    "CI Gate",
    "Compose Golden Path",
    "Requirement Traceability and Completion Audit",
)


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _change(*, status: str, updated: str, body: str = "正文保持不变。") -> str:
    return f"""---
schema: coding-change/v1
id: CHG-20260914-release-fixture
title: Release fixture
level: L3
status: {status}
owner: test
branch: test/release
created: 2026-09-14
updated: {updated}
completion_gate: required
depends_on: []
affected_areas: []
affected_paths: []
contracts: []
data_changes: []
---

# 正文

{body}
"""


def _check_payload(
    *, names: tuple[str, ...] = REQUIRED_CHECKS, conclusion: str = "success"
) -> dict[str, object]:
    return {
        "check_runs": [
            {
                "name": name,
                "status": "completed",
                "conclusion": conclusion,
                "completed_at": f"2026-09-14T00:00:0{index}Z",
            }
            for index, name in enumerate(names)
        ]
    }


def _archive_repository(
    tmp_path: Path,
    *,
    message: str | None = None,
    tamper_body: bool = False,
    extra_file: bool = False,
) -> tuple[Path, str, str]:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.com")
    source = root / "changes" / "active" / "CHG-20260914-release-fixture" / "CHANGE.md"
    source.parent.mkdir(parents=True)
    source.write_text(_change(status="ready_for_review", updated="2026-09-13"), encoding="utf-8")
    parent_sha = _commit(root, "实现提交")

    target = root / "changes" / "archive" / "2026-09" / "CHG-20260914-release-fixture" / "CHANGE.md"
    target.parent.mkdir(parents=True)
    body = "正文被篡改。" if tamper_body else "正文保持不变。"
    target.write_text(_change(status="done", updated="2026-09-14", body=body), encoding="utf-8")
    source.unlink()
    source.parent.rmdir()
    if extra_file:
        (root / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    release_sha = _commit(
        root,
        message or "归档 Change：CHG-20260914-release-fixture [skip ci]",
    )
    return root, parent_sha, release_sha


def test_current_release_sha_keeps_its_own_complete_checks(tmp_path: Path) -> None:
    module = _load_release_evidence()
    root, _, release_sha = _archive_repository(tmp_path)
    payload = _check_payload()

    assert module["resolve_evidence_sha"](root, release_sha, payload) == release_sha
    module["verify_required_checks"](payload)


def test_guarded_archive_inherits_its_unique_parent_checks(tmp_path: Path) -> None:
    module = _load_release_evidence()
    root, parent_sha, release_sha = _archive_repository(tmp_path)

    assert module["resolve_evidence_sha"](root, release_sha, {"check_runs": []}) == parent_sha


def test_partial_current_checks_do_not_inherit_parent(tmp_path: Path) -> None:
    module = _load_release_evidence()
    error = module["ReleaseEvidenceError"]
    root, _, release_sha = _archive_repository(tmp_path)

    with pytest.raises(error, match="部分存在"):
        module["resolve_evidence_sha"](
            root,
            release_sha,
            _check_payload(names=("CI Gate",)),
        )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"message": "普通提交 [skip ci]"}, "归档提交消息"),
        ({"tamper_body": True}, "确定性冻结"),
        ({"extra_file": True}, "恰好包含两个路径"),
    ],
)
def test_unguarded_archive_shape_cannot_inherit_parent(
    tmp_path: Path,
    arguments: dict[str, object],
    message: str,
) -> None:
    module = _load_release_evidence()
    error = module["ReleaseEvidenceError"]
    root, _, release_sha = _archive_repository(tmp_path, **arguments)

    with pytest.raises(error, match=message):
        module["resolve_evidence_sha"](root, release_sha, {"check_runs": []})


def test_failed_or_missing_required_checks_fail_closed() -> None:
    module = _load_release_evidence()
    error = module["ReleaseEvidenceError"]

    with pytest.raises(error, match="conclusion=failure"):
        module["verify_required_checks"](_check_payload(conclusion="failure"))

    with pytest.raises(error, match="missing"):
        module["verify_required_checks"](_check_payload(names=("CI Gate",)))


def test_failed_current_checks_cannot_fall_back_to_archive_parent(tmp_path: Path) -> None:
    module = _load_release_evidence()
    error = module["ReleaseEvidenceError"]
    root, _, release_sha = _archive_repository(tmp_path)
    payload = _check_payload(conclusion="failure")

    assert module["resolve_evidence_sha"](root, release_sha, payload) == release_sha
    with pytest.raises(error, match="conclusion=failure"):
        module["verify_required_checks"](payload)
