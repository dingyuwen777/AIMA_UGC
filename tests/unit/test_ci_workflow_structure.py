from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
RUNTIME = ROOT / ".github" / "workflows" / "runtime.yml"
LEGACY_COMPLETION = ROOT / ".github" / "workflows" / "change-completion-gate.yml"


def test_ci_consolidates_ubuntu_core_without_losing_required_contexts() -> None:
    text = CI.read_text(encoding="utf-8")
    assert "name: Requirement Traceability and Completion Audit" in text
    assert "name: CI Gate" in text
    assert "name: CI Scope" not in text
    assert "name: Docs and Governance" not in text
    assert "name: Repository Quality" not in text
    assert "Verify PR Requirement Source" in text
    assert "Enforce changed PR Change readiness" in text
    assert "Secret and docs gates" in text
    assert "Unit, Contract and API tests" in text
    assert "Frontend unit, build and Browser Mock Acceptance" in text
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text


def test_completion_workflow_is_removed_after_evidence_moves_into_core() -> None:
    assert not LEGACY_COMPLETION.exists()
    text = CI.read_text(encoding="utf-8")
    assert text.count("Requirement Traceability and Completion Audit") == 1


def test_pr_body_edit_keeps_traceability_and_skips_product_layers() -> None:
    text = CI.read_text(encoding="utf-8")
    assert "- edited" in text
    assert "profile=metadata_only" in text
    for marker in (
        "repository_required=false",
        "backend_required=false",
        "frontend_required=false",
        "postgres_required=false",
        "fullstack_required=false",
    ):
        assert marker in text


def test_frontend_audit_runs_once_at_the_same_high_threshold() -> None:
    text = CI.read_text(encoding="utf-8")
    assert text.count("npm --prefix frontend audit --audit-level=high") == 1
    assert "npm --prefix frontend audit --omit=dev --audit-level=high" not in text


def test_expensive_independent_evidence_keeps_its_owner() -> None:
    text = CI.read_text(encoding="utf-8")
    assert "name: PostgreSQL Integration" in text
    assert "name: Real Full-stack Golden Path" in text
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert "name: Compose Golden Path" in runtime
    assert "Canonical Compose startup, security, persistence, and recovery" in runtime


def test_daily_code_pr_runner_budget_is_reduced_by_half() -> None:
    ci = CI.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    assert ci.count("runs-on: ubuntu-24.04") == 3
    assert runtime.count("runs-on: ubuntu-24.04") == 1
    assert "needs: quality-core" in ci
