#!/usr/bin/env python3
"""安全识别并按 Workflow ID 定向清理失效 GitHub Actions 历史运行。"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TRANSIENT_HTTP_STATUS = {429, 500, 502, 503, 504}


class TransientGitHubApiError(RuntimeError):
    """表示可以等待下一次 main push 自动重试的 GitHub 临时错误。"""


def _normalise_workflow_path(value: Any) -> str | None:
    """只接受 GitHub 官方 Workflow 目录中的直接 YAML 文件路径。"""
    if not isinstance(value, str):
        return None
    raw = value.strip().replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    path = PurePosixPath(raw)
    if len(path.parts) != 3 or path.parts[:2] != (".github", "workflows"):
        return None
    if path.suffix not in {".yml", ".yaml"}:
        return None
    return path.as_posix()


def current_workflow_paths(root: Path) -> set[str]:
    """读取当前工作树真实存在的 Workflow path，作为绝对保护集合。"""
    directory = root / ".github" / "workflows"
    if not directory.is_dir():
        raise RuntimeError(f"Workflow 目录不存在：{directory}")
    return {
        path.relative_to(root).as_posix()
        for path in directory.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    }


def path_existed_in_head_history(root: Path, workflow_path: str) -> bool:
    """确认 Workflow 曾进入 HEAD first-parent 主线，而不是只存在于 PR 支线。"""
    completed = subprocess.run(
        [
            "git",
            "log",
            "--first-parent",
            "--format=%H",
            "--max-count=1",
            "HEAD",
            "--",
            workflow_path,
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"无法读取默认分支 Git 历史：{workflow_path}: {detail}")
    return bool(completed.stdout.strip())


def main_history_workflow_paths(root: Path, observed_paths: Iterable[str]) -> set[str]:
    """只把 first-parent 主线真实拥有过的 observed Workflow path 标记为 main history。"""
    return {
        path for path in sorted(set(observed_paths)) if path_existed_in_head_history(root, path)
    }


def _api_request(
    token: str,
    method: str,
    path: str,
    *,
    allow_not_found: bool = False,
) -> Any:
    """调用 GitHub Actions REST；临时错误与硬失败使用不同异常语义。"""
    request = Request(
        f"{API_ROOT}{path}",
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "repository-actions-hygiene",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read()
    except HTTPError as error:
        if error.code == 404 and (method == "DELETE" or allow_not_found):
            return None
        detail = error.read().decode("utf-8", errors="replace")
        if error.code in TRANSIENT_HTTP_STATUS:
            raise TransientGitHubApiError(
                f"GitHub API {method} {path} 临时失败：HTTP {error.code} {detail}"
            ) from error
        raise RuntimeError(
            f"GitHub API {method} {path} 失败：HTTP {error.code} {detail}"
        ) from error
    except (URLError, TimeoutError) as error:
        raise TransientGitHubApiError(
            f"GitHub API {method} {path} 临时网络失败：{error}"
        ) from error

    if not payload:
        return None
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"GitHub API {method} {path} 返回非法 JSON") from error


def _page_items(
    repository: str,
    token: str,
    endpoint: str,
    list_key: str,
    *,
    allow_not_found: bool = False,
) -> list[dict[str, Any]]:
    """完整分页一个定向 Actions endpoint；404 可按已退休 Workflow 空集合处理。"""
    result: list[dict[str, Any]] = []
    separator = "&" if "?" in endpoint else "?"
    for page in range(1, 1001):
        payload = _api_request(
            token,
            "GET",
            f"{endpoint}{separator}per_page=100&page={page}",
            allow_not_found=allow_not_found,
        )
        if payload is None and allow_not_found:
            return []
        if not isinstance(payload, dict):
            raise RuntimeError(f"GitHub Actions API 顶层返回格式非法：{endpoint}")
        items = payload.get(list_key)
        if not isinstance(items, list):
            raise RuntimeError(f"GitHub Actions API 缺少 {list_key} 列表：{endpoint}")
        if not items:
            return result
        if any(not isinstance(item, dict) for item in items):
            raise RuntimeError(f"GitHub Actions API {list_key} 包含非 object 记录")
        result.extend(items)
    raise RuntimeError(f"GitHub Actions API 分页超过安全上限：{endpoint}")


def list_repository_workflows(repository: str, token: str) -> list[dict[str, Any]]:
    """枚举仓库 Workflow records；数量通常远小于全量 workflow runs。"""
    return _page_items(
        repository,
        token,
        f"/repos/{repository}/actions/workflows",
        "workflows",
    )


def list_workflow_runs(
    repository: str,
    token: str,
    workflow_id: int,
) -> list[dict[str, Any]]:
    """只分页某一个 stale Workflow ID 的 runs，避免扫描整个仓库历史。"""
    return _page_items(
        repository,
        token,
        f"/repos/{repository}/actions/workflows/{workflow_id}/runs",
        "workflow_runs",
        allow_not_found=True,
    )


def workflow_run_count(repository: str, token: str, workflow_id: int) -> int:
    """删除后读取 stale Workflow 剩余 run 数；Workflow 已退休的 404 视为 0。"""
    payload = _api_request(
        token,
        "GET",
        f"/repos/{repository}/actions/workflows/{workflow_id}/runs?per_page=1",
        allow_not_found=True,
    )
    if payload is None:
        return 0
    if not isinstance(payload, dict):
        raise RuntimeError(f"Workflow {workflow_id} run count 返回格式非法")
    value = payload.get("total_count")
    if not isinstance(value, int) or value < 0:
        raise RuntimeError(f"Workflow {workflow_id} total_count 非法：{value!r}")
    return value


def select_stale_workflows(
    current_paths: set[str],
    main_history_paths: set[str],
    workflow_records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """按 current path 与 main history 从 repository workflow records 选出 stale IDs。"""
    stale: list[dict[str, Any]] = []
    protected_current: list[str] = []
    skipped_not_main_history: list[str] = []

    for raw in workflow_records:
        workflow_id = raw.get("id")
        path = _normalise_workflow_path(raw.get("path"))
        if not isinstance(workflow_id, int) or workflow_id <= 0:
            raise ValueError(f"Workflow record 缺少合法 id：{raw!r}")
        if path is None:
            raise ValueError(f"Workflow record 缺少合法 path：id={workflow_id}")

        record = {
            "id": workflow_id,
            "path": path,
            "name": str(raw.get("name") or ""),
            "state": str(raw.get("state") or ""),
        }
        if path in current_paths:
            protected_current.append(path)
            continue
        if path not in main_history_paths:
            skipped_not_main_history.append(path)
            continue
        stale.append(record)

    stale.sort(key=lambda item: (item["path"], item["id"]))
    return {
        "stale_workflows": stale,
        "protected_current_workflows": sorted(set(protected_current)),
        "skipped_not_main_history": sorted(set(skipped_not_main_history)),
    }


def build_cleanup_plan(
    current_paths: set[str],
    stale_workflows: Iterable[dict[str, Any]],
    runs_by_workflow: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    """对 stale Workflow ID 的定向 run 快照做 active preflight 与删除计划。"""
    skipped_active: dict[str, list[str]] = {}
    eligible_runs: list[dict[str, Any]] = []
    targeted_run_count = 0

    for workflow in stale_workflows:
        workflow_id = int(workflow["id"])
        workflow_path = str(workflow["path"])
        path_runs = runs_by_workflow.get(workflow_id, [])
        normalised_runs: list[dict[str, Any]] = []

        for raw_run in path_runs:
            run_id = raw_run.get("id")
            status = raw_run.get("status")
            run_path = _normalise_workflow_path(raw_run.get("path"))
            if not isinstance(run_id, int) or run_id <= 0:
                raise ValueError(f"Workflow run 缺少合法 id：workflow_id={workflow_id}")
            if not isinstance(status, str) or not status.strip():
                raise ValueError(f"Workflow run 缺少合法 status：id={run_id}")
            if run_path is None:
                raise ValueError(f"Workflow run 缺少合法 path：id={run_id}")
            if run_path in current_paths:
                raise RuntimeError(
                    f"拒绝清理当前 Workflow run：id={run_id}, path={run_path}"
                )
            normalised_runs.append(
                {
                    "id": run_id,
                    "workflow_id": workflow_id,
                    "workflow_path": workflow_path,
                    "path": run_path,
                    "name": str(raw_run.get("name") or ""),
                    "status": status.strip(),
                }
            )

        targeted_run_count += len(normalised_runs)
        active_statuses = sorted(
            {item["status"] for item in normalised_runs if item["status"] != "completed"}
        )
        if active_statuses:
            skipped_active[workflow_path] = active_statuses
            continue
        eligible_runs.extend(sorted(normalised_runs, key=lambda item: item["id"]))

    return {
        "eligible_runs": eligible_runs,
        "skipped_active_workflows": skipped_active,
        "targeted_run_count": targeted_run_count,
    }


def _repository(value: str | None) -> str:
    """解析 owner/name 仓库身份，避免任意 URL 拼入 API。"""
    repository = (value or os.environ.get("GITHUB_REPOSITORY") or "").strip()
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise ValueError(f"repository 必须是 owner/name：{repository!r}")
    return repository


def _token() -> str:
    """读取 GitHub Actions 自动 token；不打印、不持久化该值。"""
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("缺少 GITHUB_TOKEN/GH_TOKEN，无法读取 Actions")
    return token


def run_hygiene(
    root: Path,
    repository: str,
    token: str,
    *,
    execute: bool,
) -> dict[str, Any]:
    """定向枚举 stale Workflow IDs；显式 execute 时删除并逐 ID fresh readback。"""
    root = root.resolve()
    current_paths = current_workflow_paths(root)
    workflow_records = list_repository_workflows(repository, token)
    observed_paths = {
        path
        for record in workflow_records
        if (path := _normalise_workflow_path(record.get("path"))) is not None
    }
    history_paths = main_history_workflow_paths(root, observed_paths)
    selection = select_stale_workflows(current_paths, history_paths, workflow_records)
    stale_workflows = selection["stale_workflows"]

    runs_by_workflow: dict[int, list[dict[str, Any]]] = {}
    for workflow in stale_workflows:
        workflow_id = int(workflow["id"])
        runs_by_workflow[workflow_id] = list_workflow_runs(
            repository,
            token,
            workflow_id,
        )

    plan = build_cleanup_plan(current_paths, stale_workflows, runs_by_workflow)
    deleted_runs = 0
    if execute:
        for run in plan["eligible_runs"]:
            _api_request(
                token,
                "DELETE",
                f"/repos/{repository}/actions/runs/{run['id']}",
            )
            deleted_runs += 1

    remaining = 0
    if execute:
        skipped_paths = set(plan["skipped_active_workflows"])
        for workflow in stale_workflows:
            if workflow["path"] in skipped_paths:
                continue
            remaining += workflow_run_count(repository, token, int(workflow["id"]))
        if remaining:
            raise RuntimeError(
                f"Actions Hygiene fresh readback 仍有 {remaining} 个 eligible obsolete runs"
            )

    return {
        "schema": "repository-actions-hygiene/v2",
        "execute": execute,
        "repository": repository,
        "current_workflow_count": len(current_paths),
        "workflow_record_count": len(workflow_records),
        "candidate_workflow_count": len(stale_workflows),
        "targeted_run_count": plan["targeted_run_count"],
        "eligible_run_count": len(plan["eligible_runs"]),
        "deleted_run_count": deleted_runs,
        "skipped_active_workflows": plan["skipped_active_workflows"],
        "skipped_not_main_history": selection["skipped_not_main_history"],
        "remaining_eligible_run_count": remaining if execute else len(plan["eligible_runs"]),
    }


def _print_human(payload: dict[str, Any]) -> None:
    """输出紧凑人工摘要，不泄露 token 或完整历史记录。"""
    print(
        "Actions Hygiene: "
        f"current={payload['current_workflow_count']} "
        f"records={payload['workflow_record_count']} "
        f"candidates={payload['candidate_workflow_count']} "
        f"targeted_runs={payload['targeted_run_count']} "
        f"eligible={payload['eligible_run_count']} "
        f"deleted={payload['deleted_run_count']} "
        f"remaining={payload['remaining_eligible_run_count']}"
    )
    if payload["skipped_active_workflows"]:
        print(
            "Skipped active workflows: "
            + json.dumps(payload["skipped_active_workflows"], ensure_ascii=False, sort_keys=True)
        )
    if payload["skipped_not_main_history"]:
        print(
            "Skipped non-main-history workflows: "
            + json.dumps(payload["skipped_not_main_history"], ensure_ascii=False)
        )


def main() -> int:
    """执行命令行入口；默认 dry-run，只有 --execute 才产生删除副作用。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."), help="仓库根目录")
    parser.add_argument("--repository", help="GitHub owner/name，默认读取 GITHUB_REPOSITORY")
    parser.add_argument("--execute", action="store_true", help="真实删除 eligible workflow runs")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    try:
        payload = run_hygiene(
            args.root,
            _repository(args.repository),
            _token(),
            execute=args.execute,
        )
    except TransientGitHubApiError as error:
        print(f"temporary-error: {error}", file=sys.stderr)
        return 75
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        _print_human(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
