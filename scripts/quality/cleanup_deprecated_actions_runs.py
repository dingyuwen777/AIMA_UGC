#!/usr/bin/env python3
"""一次性清理当前 main 已不存在 Workflow 的 GitHub Actions 历史 runs。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.github.com"
SCHEMA = "aima-actions-history-cleanup/v1"
DEFAULT_RESERVE_REQUESTS = 150


class ApiError(RuntimeError):
    """表示 GitHub API 请求失败，并保留状态码与 rate-limit 信息。"""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        remaining: int | None = None,
        reset_epoch: int | None = None,
    ) -> None:
        """保存可用于安全降级或停止删除的 API 错误事实。"""
        super().__init__(message)
        self.status = status
        self.remaining = remaining
        self.reset_epoch = reset_epoch


@dataclass(frozen=True)
class WorkflowRun:
    """保存清理选择所需的最小 GitHub Actions run 事实。"""

    run_id: int
    path: str
    name: str
    created_at: str


@dataclass(frozen=True)
class RateLimit:
    """保存当前 token 的 core API 配额。"""

    remaining: int
    reset_epoch: int


class GitHubApi:
    """通过标准库访问当前仓库 GitHub Actions API。"""

    def __init__(self, repository: str, token: str, *, token_name: str) -> None:
        """绑定 repository、token 与仅用于日志的 token 来源名称。"""
        owner, separator, name = repository.partition("/")
        if not separator or not owner or not name:
            raise ValueError("repository 必须使用 owner/name")
        if not token:
            raise ValueError("GitHub token 不能为空")
        self.repository = repository
        self.token = token
        self.token_name = token_name

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str | int] | None = None,
    ) -> tuple[int, Mapping[str, str], bytes]:
        """发送单次 GitHub API 请求并规范化错误。"""
        url = f"{API_ROOT}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        request = Request(
            url,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "aima-actions-history-cleanup",
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                return response.status, dict(response.headers.items()), response.read()
        except HTTPError as error:
            headers = dict(error.headers.items())
            remaining = _header_int(headers, "X-RateLimit-Remaining")
            reset_epoch = _header_int(headers, "X-RateLimit-Reset")
            body = error.read().decode("utf-8", errors="replace")
            raise ApiError(
                f"GitHub API {method} {path} failed: HTTP {error.code}: {body}",
                status=error.code,
                remaining=remaining,
                reset_epoch=reset_epoch,
            ) from error

    def list_all_runs(self) -> list[WorkflowRun]:
        """分页读取仓库全部 Actions runs；读取失败时不产生删除计划。"""
        records: list[WorkflowRun] = []
        page = 1
        while True:
            _, _, body = self._request(
                "GET",
                f"/repos/{self.repository}/actions/runs",
                query={"per_page": 100, "page": page},
            )
            payload = json.loads(body.decode("utf-8"))
            raw_runs = payload.get("workflow_runs")
            if not isinstance(raw_runs, list):
                raise RuntimeError("GitHub Actions runs 响应缺少 workflow_runs list")
            if not raw_runs:
                break
            for raw in raw_runs:
                if not isinstance(raw, Mapping):
                    raise RuntimeError("GitHub Actions run 不是 object")
                run_id = raw.get("id")
                path = raw.get("path")
                name = raw.get("name")
                created_at = raw.get("created_at")
                if not isinstance(run_id, int):
                    raise RuntimeError("GitHub Actions run 缺少整数 id")
                if not isinstance(path, str) or not path.startswith(".github/workflows/"):
                    raise RuntimeError(f"GitHub Actions run path 非法：{path!r}")
                if not isinstance(name, str):
                    name = ""
                if not isinstance(created_at, str):
                    created_at = ""
                records.append(
                    WorkflowRun(
                        run_id=run_id,
                        path=path,
                        name=name,
                        created_at=created_at,
                    )
                )
            if len(raw_runs) < 100:
                break
            page += 1
        return records

    def rate_limit(self) -> RateLimit:
        """读取当前 token 的 core API 剩余额度。"""
        _, _, body = self._request("GET", "/rate_limit")
        payload = json.loads(body.decode("utf-8"))
        core = payload.get("resources", {}).get("core", {})
        remaining = core.get("remaining")
        reset_epoch = core.get("reset")
        if not isinstance(remaining, int) or not isinstance(reset_epoch, int):
            raise RuntimeError("GitHub rate_limit 响应缺少 core.remaining/reset")
        return RateLimit(remaining=remaining, reset_epoch=reset_epoch)

    def delete_run(self, run_id: int) -> tuple[str, RateLimit | None]:
        """删除一个 Workflow run；404 视为幂等已清理。"""
        path = f"/repos/{self.repository}/actions/runs/{run_id}"
        try:
            _, headers, _ = self._request("DELETE", path)
        except ApiError as error:
            if error.status == 404:
                return (
                    "missing",
                    _rate_from_values(error.remaining, error.reset_epoch),
                )
            raise
        return (
            "deleted",
            _rate_from_headers(headers),
        )


def _header_int(headers: Mapping[str, str], name: str) -> int | None:
    """大小写无关读取整数响应头。"""
    lowered = {key.lower(): value for key, value in headers.items()}
    raw = lowered.get(name.lower())
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _rate_from_values(
    remaining: int | None,
    reset_epoch: int | None,
) -> RateLimit | None:
    """只在 rate-limit 两个字段都存在时构造对象。"""
    if remaining is None or reset_epoch is None:
        return None
    return RateLimit(remaining=remaining, reset_epoch=reset_epoch)


def _rate_from_headers(headers: Mapping[str, str]) -> RateLimit | None:
    """从响应头恢复 rate-limit 事实。"""
    return _rate_from_values(
        _header_int(headers, "X-RateLimit-Remaining"),
        _header_int(headers, "X-RateLimit-Reset"),
    )


def discover_current_workflows(root: Path) -> set[str]:
    """动态发现当前 checkout 中全部正式 Workflow path。"""
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        raise FileNotFoundError(f"Workflow 目录不存在：{workflow_dir}")
    result = {
        path.relative_to(root).as_posix()
        for pattern in ("*.yml", "*.yaml")
        for path in workflow_dir.glob(pattern)
        if path.is_file() and not path.is_symlink()
    }
    if not result:
        raise RuntimeError("当前 checkout 未发现任何 Workflow，拒绝生成删除计划")
    return result


def select_deprecated_runs(
    runs: Iterable[WorkflowRun],
    current_workflows: set[str],
) -> list[WorkflowRun]:
    """只选择 exact path 已不在当前 Workflow 集合中的历史 runs。"""
    selected = [
        run
        for run in runs
        if run.path not in current_workflows
    ]
    selected.sort(key=lambda item: (item.created_at, item.run_id))
    return selected


def summarise_paths(runs: Iterable[WorkflowRun]) -> list[dict[str, Any]]:
    """按 path 汇总待清理数量，便于审计删除边界。"""
    grouped: dict[str, dict[str, Any]] = {}
    for run in runs:
        item = grouped.setdefault(
            run.path,
            {
                "path": run.path,
                "count": 0,
                "names": set(),
                "oldest": run.created_at,
                "latest": run.created_at,
            },
        )
        item["count"] += 1
        item["names"].add(run.name)
        if run.created_at and (not item["oldest"] or run.created_at < item["oldest"]):
            item["oldest"] = run.created_at
        if run.created_at and (not item["latest"] or run.created_at > item["latest"]):
            item["latest"] = run.created_at
    return [
        {
            "path": value["path"],
            "count": value["count"],
            "names": sorted(value["names"]),
            "oldest": value["oldest"],
            "latest": value["latest"],
        }
        for value in sorted(grouped.values(), key=lambda item: item["path"])
    ]


def deletion_budget(
    rate: RateLimit,
    *,
    reserve_requests: int,
    max_deletions: int,
) -> int:
    """为仓库其他 API 操作保留额度后计算本轮最大删除数。"""
    if reserve_requests < 1:
        raise ValueError("reserve_requests 必须 >= 1")
    if max_deletions < 1:
        raise ValueError("max_deletions 必须 >= 1")
    return min(max_deletions, max(0, rate.remaining - reserve_requests))


def delete_batch(
    runs: list[WorkflowRun],
    client: GitHubApi,
    *,
    reserve_requests: int,
    max_deletions: int,
) -> dict[str, Any]:
    """在当前 token 配额内幂等删除一批 runs，额度不足时安全停止。"""
    initial_rate = client.rate_limit()
    budget = deletion_budget(
        initial_rate,
        reserve_requests=reserve_requests,
        max_deletions=max_deletions,
    )
    deleted = 0
    missing = 0
    current_rate: RateLimit | None = initial_rate

    for run in runs[:budget]:
        try:
            outcome, response_rate = client.delete_run(run.run_id)
        except ApiError as error:
            if error.status == 403 and error.remaining == 0:
                current_rate = _rate_from_values(error.remaining, error.reset_epoch)
                break
            raise
        if outcome == "deleted":
            deleted += 1
        elif outcome == "missing":
            missing += 1
        else:
            raise RuntimeError(f"未知 delete outcome：{outcome}")
        if response_rate is not None:
            current_rate = response_rate
            if current_rate.remaining <= reserve_requests:
                break

    removed = deleted + missing
    return {
        "token_source": client.token_name,
        "initial_rate_remaining": initial_rate.remaining,
        "rate_remaining": current_rate.remaining if current_rate else None,
        "rate_reset_epoch": current_rate.reset_epoch if current_rate else None,
        "delete_budget": budget,
        "deleted": deleted,
        "already_missing": missing,
        "remaining": max(0, len(runs) - removed),
    }


def _scan_with_fallback(
    clients: list[GitHubApi],
) -> tuple[GitHubApi, list[WorkflowRun]]:
    """按优先级选择第一个能够读取 Actions runs 的 token。"""
    last_error: Exception | None = None
    for client in clients:
        try:
            return client, client.list_all_runs()
        except ApiError as error:
            last_error = error
            if error.status not in {401, 403}:
                raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("没有可用 GitHub API client")


def _delete_with_fallback(
    runs: list[WorkflowRun],
    clients: list[GitHubApi],
    *,
    reserve_requests: int,
    max_deletions: int,
) -> dict[str, Any]:
    """优先用 App token 删除；权限不足时退回 GITHUB_TOKEN。"""
    last_error: Exception | None = None
    for client in clients:
        try:
            return delete_batch(
                runs,
                client,
                reserve_requests=reserve_requests,
                max_deletions=max_deletions,
            )
        except ApiError as error:
            last_error = error
            if error.status == 403 and error.remaining != 0:
                continue
            if error.status == 401:
                continue
            raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("没有具备 Actions run 删除能力的 token")


def _build_parser() -> argparse.ArgumentParser:
    """构造一次性 Actions 历史清理 CLI。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="GitHub owner/name")
    parser.add_argument("--root", default=".", help="当前仓库 checkout 根目录")
    parser.add_argument(
        "--max-deletions",
        type=int,
        default=4000,
        help="单轮最多删除 run 数",
    )
    parser.add_argument(
        "--reserve-requests",
        type=int,
        default=DEFAULT_RESERVE_REQUESTS,
        help="为其他 GitHub API 操作保留的 core requests",
    )
    parser.add_argument("--dry-run", action="store_true", help="只生成选择摘要，不删除")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    """扫描当前 Actions 历史并安全清理已删除 Workflow 的 runs。"""
    args = _build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    current_workflows = discover_current_workflows(root)

    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    app_token = os.environ.get("ACTIONS_CLEANUP_APP_TOKEN", "").strip()
    clients: list[GitHubApi] = []
    if app_token:
        clients.append(
            GitHubApi(
                args.repository,
                app_token,
                token_name="change-archive-app",
            )
        )
    if github_token:
        clients.append(
            GitHubApi(
                args.repository,
                github_token,
                token_name="github-token",
            )
        )
    if not clients:
        raise SystemExit("缺少 ACTIONS_CLEANUP_APP_TOKEN / GITHUB_TOKEN")

    scan_client, all_runs = _scan_with_fallback(clients)
    deprecated = select_deprecated_runs(all_runs, current_workflows)
    summary: dict[str, Any] = {
        "schema": SCHEMA,
        "repository": args.repository,
        "scan_token_source": scan_client.token_name,
        "current_workflows": sorted(current_workflows),
        "total_runs": len(all_runs),
        "deprecated_runs": len(deprecated),
        "deprecated_paths": summarise_paths(deprecated),
        "dry_run": bool(args.dry_run),
    }

    if args.dry_run or not deprecated:
        summary.update(
            {
                "deleted": 0,
                "already_missing": 0,
                "remaining": len(deprecated),
            }
        )
    else:
        summary.update(
            _delete_with_fallback(
                deprecated,
                clients,
                reserve_requests=args.reserve_requests,
                max_deletions=args.max_deletions,
            )
        )

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"current={len(current_workflows)} total={len(all_runs)} "
            f"deprecated={len(deprecated)} deleted={summary.get('deleted', 0)} "
            f"remaining={summary.get('remaining', len(deprecated))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
