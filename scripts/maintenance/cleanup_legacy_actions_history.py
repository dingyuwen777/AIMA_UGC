#!/usr/bin/env python3
"""Safely plan and delete GitHub Actions runs for workflows removed from main.

This is a temporary maintenance tool. It discovers the current workflow whitelist
from the checkout, requires that whitelist to match the six approved long-term
workflow paths exactly, validates the complete deletion plan before the first
DELETE, and never enumerates runs for protected workflow paths.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

EXPECTED_CURRENT_WORKFLOWS = {
    ".github/workflows/change-completion-gate.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/fullstack.yml",
    ".github/workflows/release.yml",
    ".github/workflows/runtime.yml",
    ".github/workflows/tooling.yml",
}

API_VERSION = "2022-11-28"
DEFAULT_MAX_DELETES = 500
RATE_LIMIT_RESERVE = 100


class CleanupSafetyError(RuntimeError):
    """Raised when a safety invariant is violated before deletion."""


@dataclass(frozen=True)
class WorkflowRecord:
    workflow_id: int
    name: str
    path: str
    state: str


@dataclass(frozen=True)
class RunRecord:
    run_id: int
    workflow_id: int
    workflow_path: str
    status: str
    created_at: str


class GithubActionsClient:
    """Minimal GitHub REST client using the workflow-scoped GITHUB_TOKEN."""

    def __init__(self, *, api_url: str, repository: str, token: str) -> None:
        if not repository or "/" not in repository:
            raise CleanupSafetyError("GITHUB_REPOSITORY is missing or invalid")
        if not token:
            raise CleanupSafetyError("GITHUB_TOKEN is required")
        self._api_url = api_url.rstrip("/")
        self._repository = repository
        self._token = token

    def _request(self, method: str, url: str) -> tuple[int, Any | None]:
        request = urllib.request.Request(
            url,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "aima-actions-history-cleanup",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                status = response.status
                body = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise CleanupSafetyError(
                f"GitHub API {method} {url} failed with {exc.code}: {body[:1000]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise CleanupSafetyError(f"GitHub API {method} {url} failed: {exc}") from exc

        if not body:
            return status, None
        return status, json.loads(body.decode("utf-8"))

    def repo_json(self, path: str) -> Any:
        _, payload = self._request(
            "GET", f"{self._api_url}/repos/{self._repository}{path}"
        )
        return payload

    def global_json(self, path: str) -> Any:
        _, payload = self._request("GET", f"{self._api_url}{path}")
        return payload

    def delete_run(self, run_id: int) -> None:
        status, _ = self._request(
            "DELETE",
            f"{self._api_url}/repos/{self._repository}/actions/runs/{run_id}",
        )
        if status != 204:
            raise CleanupSafetyError(
                f"unexpected DELETE status for run {run_id}: {status}"
            )

    def _paginate(self, path: str, key: str) -> Iterable[dict[str, Any]]:
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            payload = self.repo_json(
                f"{path}{separator}per_page=100&page={page}"
            )
            if not isinstance(payload, dict) or key not in payload:
                raise CleanupSafetyError(
                    f"unexpected paginated payload for {path}: missing {key}"
                )
            items = payload[key]
            if not isinstance(items, list):
                raise CleanupSafetyError(
                    f"unexpected paginated payload for {path}: {key} is not a list"
                )
            for item in items:
                if not isinstance(item, dict):
                    raise CleanupSafetyError(
                        f"unexpected item type in {path}: {type(item)!r}"
                    )
                yield item
            if len(items) < 100:
                return
            page += 1

    def list_workflows(self) -> list[WorkflowRecord]:
        workflows: list[WorkflowRecord] = []
        for item in self._paginate("/actions/workflows", "workflows"):
            try:
                workflow_id = int(item["id"])
                path = str(item["path"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CleanupSafetyError(
                    f"workflow record is missing id/path: {item!r}"
                ) from exc
            if not path:
                raise CleanupSafetyError(
                    f"workflow {workflow_id} has an empty path; refusing cleanup"
                )
            workflows.append(
                WorkflowRecord(
                    workflow_id=workflow_id,
                    name=str(item.get("name") or ""),
                    path=path,
                    state=str(item.get("state") or ""),
                )
            )
        return workflows

    def list_runs(self, workflow: WorkflowRecord) -> list[RunRecord]:
        records: list[RunRecord] = []
        path = f"/actions/workflows/{workflow.workflow_id}/runs"
        for item in self._paginate(path, "workflow_runs"):
            try:
                run_id = int(item["id"])
                workflow_id = int(item["workflow_id"])
                run_path = str(item["path"])
                status = str(item["status"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CleanupSafetyError(
                    f"run record is missing required fields: {item!r}"
                ) from exc
            records.append(
                RunRecord(
                    run_id=run_id,
                    workflow_id=workflow_id,
                    workflow_path=normalize_workflow_path(run_path),
                    status=status,
                    created_at=str(item.get("created_at") or ""),
                )
            )
        return records


def normalize_workflow_path(path: str) -> str:
    """Normalize the optional @ref suffix used by some Actions path surfaces."""
    return path.split("@", 1)[0]


def discover_current_workflow_paths(repo_root: Path) -> set[str]:
    workflow_dir = repo_root / ".github" / "workflows"
    discovered = {
        path.relative_to(repo_root).as_posix()
        for path in workflow_dir.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    }
    if discovered != EXPECTED_CURRENT_WORKFLOWS:
        missing = sorted(EXPECTED_CURRENT_WORKFLOWS - discovered)
        unexpected = sorted(discovered - EXPECTED_CURRENT_WORKFLOWS)
        raise CleanupSafetyError(
            "current workflow whitelist drifted; refusing cleanup. "
            f"missing={missing}, unexpected={unexpected}"
        )
    return discovered


def validate_legacy_run(
    *, workflow: WorkflowRecord, run: RunRecord, whitelist: set[str]
) -> None:
    """Fail closed unless a run is provably completed and owned by one legacy path."""
    if workflow.path in whitelist:
        raise CleanupSafetyError(
            f"protected workflow entered legacy validation: {workflow.path}"
        )
    if run.workflow_id != workflow.workflow_id:
        raise CleanupSafetyError(
            f"run {run.run_id} workflow_id mismatch: "
            f"expected {workflow.workflow_id}, got {run.workflow_id}"
        )
    if run.workflow_path in whitelist:
        raise CleanupSafetyError(
            f"run {run.run_id} resolves to protected path {run.workflow_path}"
        )
    if run.workflow_path != workflow.path:
        raise CleanupSafetyError(
            f"run {run.run_id} path mismatch: workflow={workflow.path}, "
            f"run={run.workflow_path}"
        )
    if run.status != "completed":
        raise CleanupSafetyError(
            f"run {run.run_id} is not completed (status={run.status}); "
            "refusing any deletion in this pass"
        )


def collect_cleanup_plan(
    *, client: GithubActionsClient, whitelist: set[str]
) -> tuple[list[WorkflowRecord], dict[int, list[RunRecord]]]:
    workflows = client.list_workflows()
    registered_protected_paths = {
        workflow.path for workflow in workflows if workflow.path in whitelist
    }
    missing_protected = whitelist - registered_protected_paths
    if missing_protected:
        raise CleanupSafetyError(
            "GitHub Actions registry is missing protected workflow paths; "
            f"refusing cleanup: {sorted(missing_protected)}"
        )

    legacy_workflows = [
        workflow for workflow in workflows if workflow.path not in whitelist
    ]
    runs_by_workflow: dict[int, list[RunRecord]] = {}

    # Complete discovery and validation before the first DELETE call.
    for workflow in legacy_workflows:
        runs = client.list_runs(workflow)
        for run in runs:
            validate_legacy_run(workflow=workflow, run=run, whitelist=whitelist)
        runs_by_workflow[workflow.workflow_id] = runs

    return legacy_workflows, runs_by_workflow


def ordered_plan(
    legacy_workflows: list[WorkflowRecord],
    runs_by_workflow: dict[int, list[RunRecord]],
) -> list[tuple[WorkflowRecord, RunRecord]]:
    # Finish smaller workflows first so ghost sidebar entries disappear as early as possible.
    workflows = sorted(
        legacy_workflows,
        key=lambda item: (
            len(runs_by_workflow[item.workflow_id]),
            item.path,
            item.workflow_id,
        ),
    )
    plan: list[tuple[WorkflowRecord, RunRecord]] = []
    for workflow in workflows:
        runs = sorted(
            runs_by_workflow[workflow.workflow_id],
            key=lambda run: (run.created_at, run.run_id),
        )
        plan.extend((workflow, run) for run in runs)
    return plan


def append_step_summary(
    *,
    whitelist: set[str],
    legacy_workflows: list[WorkflowRecord],
    runs_by_workflow: dict[int, list[RunRecord]],
    deleted: int,
    remaining: int,
    apply: bool,
) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    total_runs = sum(len(items) for items in runs_by_workflow.values())
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("## Legacy Actions history cleanup\n\n")
        handle.write(f"- mode: `{'apply' if apply else 'plan'}`\n")
        handle.write(f"- protected workflows: `{len(whitelist)}`\n")
        handle.write(f"- legacy workflow records: `{len(legacy_workflows)}`\n")
        handle.write(f"- legacy completed runs discovered: `{total_runs}`\n")
        handle.write(f"- deleted this pass: `{deleted}`\n")
        handle.write(f"- estimated remaining: `{remaining}`\n\n")
        handle.write("### Protected paths\n\n")
        for path in sorted(whitelist):
            handle.write(f"- `{path}`\n")
        handle.write("\n### Legacy workflow records\n\n")
        if not legacy_workflows:
            handle.write("No legacy workflow records returned by the GitHub Actions API.\n")
        else:
            for workflow in sorted(legacy_workflows, key=lambda item: item.path):
                count = len(runs_by_workflow[workflow.workflow_id])
                handle.write(
                    f"- `{workflow.path}` — id `{workflow.workflow_id}` — "
                    f"state `{workflow.state}` — completed runs `{count}`\n"
                )


def run_self_test() -> None:
    whitelist = set(EXPECTED_CURRENT_WORKFLOWS)
    legacy = WorkflowRecord(1, "legacy", ".github/workflows/old.yml", "disabled")
    valid = RunRecord(10, 1, ".github/workflows/old.yml", "completed", "2026-01-01")
    validate_legacy_run(workflow=legacy, run=valid, whitelist=whitelist)

    cases = [
        (
            WorkflowRecord(
                2,
                "protected",
                ".github/workflows/ci.yml",
                "active",
            ),
            RunRecord(20, 2, ".github/workflows/ci.yml", "completed", ""),
        ),
        (
            legacy,
            RunRecord(11, 999, ".github/workflows/old.yml", "completed", ""),
        ),
        (
            legacy,
            RunRecord(12, 1, ".github/workflows/ci.yml", "completed", ""),
        ),
        (
            legacy,
            RunRecord(13, 1, ".github/workflows/another.yml", "completed", ""),
        ),
        (
            legacy,
            RunRecord(14, 1, ".github/workflows/old.yml", "in_progress", ""),
        ),
    ]
    for workflow, run in cases:
        try:
            validate_legacy_run(workflow=workflow, run=run, whitelist=whitelist)
        except CleanupSafetyError:
            pass
        else:
            raise AssertionError(
                f"unsafe fixture unexpectedly passed: workflow={workflow}, run={run}"
            )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        workflow_dir = root / ".github" / "workflows"
        workflow_dir.mkdir(parents=True)
        for workflow_path in EXPECTED_CURRENT_WORKFLOWS:
            path = root / workflow_path
            path.write_text("name: fixture\n", encoding="utf-8")
        assert discover_current_workflow_paths(root) == EXPECTED_CURRENT_WORKFLOWS
        (workflow_dir / "unexpected.yml").write_text("name: unexpected\n", encoding="utf-8")
        try:
            discover_current_workflow_paths(root)
        except CleanupSafetyError:
            pass
        else:
            raise AssertionError("whitelist drift fixture unexpectedly passed")

    print("cleanup safety self-test passed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--max-deletes", type=int, default=DEFAULT_MAX_DELETES)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        if not args.plan and not args.apply:
            return 0
    if args.plan == args.apply:
        raise CleanupSafetyError("choose exactly one of --plan or --apply")
    if args.max_deletes < 1:
        raise CleanupSafetyError("--max-deletes must be >= 1")

    whitelist = discover_current_workflow_paths(Path(args.repo_root).resolve())
    print("Protected workflow paths:")
    for path in sorted(whitelist):
        print(f"  KEEP {path}")

    client = GithubActionsClient(
        api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        repository=os.environ.get("GITHUB_REPOSITORY", ""),
        token=os.environ.get("GITHUB_TOKEN", ""),
    )
    legacy_workflows, runs_by_workflow = collect_cleanup_plan(
        client=client, whitelist=whitelist
    )
    plan = ordered_plan(legacy_workflows, runs_by_workflow)

    print(f"Registered legacy workflow records: {len(legacy_workflows)}")
    for workflow in sorted(legacy_workflows, key=lambda item: item.path):
        print(
            "  LEGACY "
            f"id={workflow.workflow_id} state={workflow.state} "
            f"runs={len(runs_by_workflow[workflow.workflow_id])} path={workflow.path}"
        )
    print(f"Validated legacy completed runs: {len(plan)}")

    if args.plan:
        append_step_summary(
            whitelist=whitelist,
            legacy_workflows=legacy_workflows,
            runs_by_workflow=runs_by_workflow,
            deleted=0,
            remaining=len(plan),
            apply=False,
        )
        print(
            "CLEANUP_SUMMARY "
            f"mode=plan protected={len(whitelist)} "
            f"legacy_workflows={len(legacy_workflows)} "
            f"legacy_runs={len(plan)} deleted=0 remaining={len(plan)}"
        )
        return 0

    rate = client.global_json("/rate_limit")
    try:
        remaining_rate = int(rate["resources"]["core"]["remaining"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CleanupSafetyError("unable to read GitHub core API rate limit") from exc
    safe_api_budget = max(0, remaining_rate - RATE_LIMIT_RESERVE)
    delete_budget = min(args.max_deletes, safe_api_budget, len(plan))
    print(
        f"GitHub core API remaining={remaining_rate}; "
        f"reserve={RATE_LIMIT_RESERVE}; delete_budget={delete_budget}"
    )

    deleted = 0
    for workflow, run in plan[:delete_budget]:
        # Re-assert the critical invariants immediately before each irreversible call.
        validate_legacy_run(workflow=workflow, run=run, whitelist=whitelist)
        client.delete_run(run.run_id)
        deleted += 1
        if deleted % 50 == 0 or deleted == delete_budget:
            print(f"Deleted {deleted}/{delete_budget} runs in this pass")

    remaining = len(plan) - deleted
    append_step_summary(
        whitelist=whitelist,
        legacy_workflows=legacy_workflows,
        runs_by_workflow=runs_by_workflow,
        deleted=deleted,
        remaining=remaining,
        apply=True,
    )
    print(
        "CLEANUP_SUMMARY "
        f"mode=apply protected={len(whitelist)} "
        f"legacy_workflows={len(legacy_workflows)} "
        f"legacy_runs={len(plan)} deleted={deleted} remaining={remaining}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CleanupSafetyError as exc:
        print(f"SAFETY_ABORT: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
