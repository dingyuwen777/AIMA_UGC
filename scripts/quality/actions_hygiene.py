#!/usr/bin/env python3
"""安全识别并按需清理已经从默认分支失效的 GitHub Actions Workflow 历史运行。"""

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
WORKFLOW_PREFIX = ".github/workflows/"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


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
    result: set[str] = set()
    for path in directory.iterdir():
        if path.is_file() and path.suffix in {".yml", ".yaml"}:
            result.add(path.relative_to(root).as_posix())
    return result


def path_existed_in_head_history(root: Path, workflow_path: str) -> bool:
    """确认 Workflow 曾进入 HEAD 的 first-parent 主线，而不是只存在于被合并的支线提交。"""
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
    """从 HEAD first-parent 主线确认本轮观察到的 Workflow path 是否曾被默认分支持有。"""
    return {
        path
        for path in sorted(set(observed_paths))
        if path_existed_in_head_history(root, path)
    }


def build_cleanup_plan(
    current_paths: set[str],
    main_history_paths: set[str],
    runs: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """根据 current/main-history/run-status 三层事实形成确定性的安全删除计划。"""
    grouped: dict[str, list[dict[str, Any]]] = {}
    ignored_non_workflow = 0

    for raw_run in runs:
        path = _normalise_workflow_path(raw_run.get("path"))
        if path is None:
            ignored_non_workflow += 1
            continue

        run_id = raw_run.get("id")
        status = raw_run.get("status")
        if not isinstance(run_id, int) or run_id <= 0:
            raise ValueError(f"Workflow run 缺少合法 id：path={path}")
        if not isinstance(status, str) or not status.strip():
            raise ValueError(f"Workflow run 缺少合法 status：id={run_id}, path={path}")

        grouped.setdefault(path, []).append(
            {
                "id": run_id,
                "path": path,
                "name": str(raw_run.get("name") or ""),
                "status": status.strip(),
            }
        )

    protected_current = sorted(path for path in grouped if path in current_paths)
    skipped_not_main_history = sorted(
        path
        for path in grouped
        if path not in current_paths and path not in main_history_paths
    )
    candidate_paths = sorted(
        path
        for path in grouped
        if path not in current_paths and path in main_history_paths
    )

    skipped_active: dict[str, list[str]] = {}
    eligible_runs: list[dict[str, Any]] = []
    for path in candidate_paths:
        path_runs = sorted(grouped[path], key=lambda item: item["id"])
        active_statuses = sorted(
            {item["status"] for item in path_runs if item["status"] != "completed"}
        )
        if active_statuses:
            skipped_active[path] = active_statuses
            continue
        eligible_runs.extend(path_runs)

    return {
        "current_workflows": sorted(current_paths),
        "observed_workflow_paths": sorted(grouped),
        "protected_current_workflows": protected_current,
        "skipped_not_main_history": skipped_not_main_history,
        "candidate_workflows": candidate_paths,
        "skipped_active_workflows": skipped_active,
        "eligible_runs": eligible_runs,
        "ignored_non_workflow_runs": ignored_non_workflow,
    }


def _api_request(
    token: str,
    method: str,
    path: str,
) -> Any:
    """使用当前 GitHub Actions token 调用仓库 REST API，任何异常都失败关闭。"""
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
        if method == "DELETE" and error.code == 404:
            return None
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API {method} {path} 失败：HTTP {error.code} {detail}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"GitHub API {method} {path} 网络失败：{error}") from error

    if not payload:
        return None
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"GitHub API {method} {path} 返回非法 JSON") from error


def list_workflow_runs(repository: str, token: str) -> list[dict[str, Any]]:
    """完整分页读取仓库 Workflow runs，删除前后都使用同一读取逻辑。"""
    result: list[dict[str, Any]] = []
    for page in range(1, 1001):
        payload = _api_request(
            token,
            "GET",
            f"/repos/{repository}/actions/runs?per_page=100&page={page}",
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Actions runs API 顶层返回格式非法")
        runs = payload.get("workflow_runs")
        if not isinstance(runs, list):
            raise RuntimeError("Actions runs API 缺少 workflow_runs 列表")
        if not runs:
            return result
        if any(not isinstance(item, dict) for item in runs):
            raise RuntimeError("Actions runs API 包含非 object 记录")
        result.extend(runs)
    raise RuntimeError("Actions runs 分页超过安全上限 1000 页，拒绝继续")


def _repository(value: str | None) -> str:
    """解析 owner/name 仓库身份，避免把任意 URL 拼入 GitHub API。"""
    repository = (value or os.environ.get("GITHUB_REPOSITORY") or "").strip()
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise ValueError(f"repository 必须是 owner/name：{repository!r}")
    return repository


def _token() -> str:
    """读取 GitHub Actions 自动 token；不打印、不持久化该值。"""
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("缺少 GITHUB_TOKEN/GH_TOKEN，无法读取 Actions runs")
    return token


def run_hygiene(
    root: Path,
    repository: str,
    token: str,
    *,
    execute: bool,
) -> dict[str, Any]:
    """生成清理计划；显式 execute 时删除 eligible completed runs 并 fresh readback。"""
    root = root.resolve()
    current_paths = current_workflow_paths(root)
    snapshot = list_workflow_runs(repository, token)
    observed_paths = {
        path
        for run in snapshot
        if (path := _normalise_workflow_path(run.get("path"))) is not None
    }
    history_paths = main_history_workflow_paths(root, observed_paths)
    plan = build_cleanup_plan(current_paths, history_paths, snapshot)

    deleted_runs = 0
    if execute:
        for run in plan["eligible_runs"]:
            _api_request(
                token,
                "DELETE",
                f"/repos/{repository}/actions/runs/{run['id']}",
            )
            deleted_runs += 1

    fresh_snapshot = list_workflow_runs(repository, token) if execute else snapshot
    fresh_observed_paths = {
        path
        for run in fresh_snapshot
        if (path := _normalise_workflow_path(run.get("path"))) is not None
    }
    fresh_history_paths = main_history_workflow_paths(root, fresh_observed_paths)
    fresh_plan = build_cleanup_plan(current_paths, fresh_history_paths, fresh_snapshot)
    remaining_eligible = len(fresh_plan["eligible_runs"])

    if execute and remaining_eligible:
        raise RuntimeError(
            f"Actions Hygiene fresh readback 仍有 {remaining_eligible} 个 eligible obsolete runs"
        )

    return {
        "schema": "repository-actions-hygiene/v1",
        "execute": execute,
        "repository": repository,
        "current_workflow_count": len(current_paths),
        "observed_run_count": len(snapshot),
        "candidate_workflow_count": len(plan["candidate_workflows"]),
        "eligible_run_count": len(plan["eligible_runs"]),
        "deleted_run_count": deleted_runs,
        "skipped_active_workflows": fresh_plan["skipped_active_workflows"],
        "skipped_not_main_history": fresh_plan["skipped_not_main_history"],
        "remaining_eligible_run_count": remaining_eligible,
    }


def _print_human(payload: dict[str, Any]) -> None:
    """输出紧凑人工摘要，不泄露 token 或完整历史记录。"""
    print(
        "Actions Hygiene: "
        f"current={payload['current_workflow_count']} "
        f"observed={payload['observed_run_count']} "
        f"candidates={payload['candidate_workflow_count']} "
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
