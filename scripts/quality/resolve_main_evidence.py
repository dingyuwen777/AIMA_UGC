"""解析 main push 是否可安全复用最终 merged PR 的既有 GitHub Check Evidence。"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ReuseEvaluation:
    """描述一次 tree/check Evidence 是否满足复用条件。"""

    reusable: bool
    reason: str


def _check_timestamp(check: dict[str, Any]) -> str:
    """为同名 check 选择最近一次结果提供稳定时间键。"""
    return str(check.get("completed_at") or check.get("started_at") or "")


def evaluate_reuse(
    *,
    current_tree: str,
    source_tree: str,
    required_checks: tuple[str, ...],
    check_runs: tuple[dict[str, Any], ...],
) -> ReuseEvaluation:
    """只在 tree 完全一致且每个 required check 最新结果成功时允许复用。"""
    if not current_tree or not source_tree:
        return ReuseEvaluation(False, "missing_tree")
    if current_tree != source_tree:
        return ReuseEvaluation(False, "tree_mismatch")

    latest: dict[str, dict[str, Any]] = {}
    required = set(required_checks)
    for check in check_runs:
        name = str(check.get("name") or "")
        if name not in required:
            continue
        previous = latest.get(name)
        if previous is None or _check_timestamp(check) > _check_timestamp(previous):
            latest[name] = check

    for name in required_checks:
        check = latest.get(name)
        if (
            check is None
            or check.get("status") != "completed"
            or check.get("conclusion") != "success"
        ):
            return ReuseEvaluation(False, "required_check_not_green")

    return ReuseEvaluation(True, "reusable")


def _api_get(url: str, *, token: str) -> Any:
    """读取 GitHub API JSON；调用方负责把访问失败降级为不可复用。"""
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AIMA-UGC-Main-Evidence-Reuse",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310 - URL 仅由 GitHub API 基址构造
        return json.load(response)


def _repo_api(api_url: str, repository: str, suffix: str) -> str:
    """构造限定在当前 GitHub 仓库的 API URL。"""
    owner, repo = repository.split("/", maxsplit=1)
    encoded = f"{quote(owner, safe='')}/{quote(repo, safe='')}"
    return f"{api_url.rstrip('/')}/repos/{encoded}/{suffix.lstrip('/')}"


def _resolve_source_pr(
    *,
    api_url: str,
    repository: str,
    commit_sha: str,
    token: str,
) -> dict[str, Any] | None:
    """从 main commit 关联 PR 中唯一选择已合并到 main 的来源 PR。"""
    payload = _api_get(
        _repo_api(
            api_url,
            repository,
            f"commits/{quote(commit_sha, safe='')}/pulls?per_page=100",
        ),
        token=token,
    )
    if not isinstance(payload, list):
        return None

    merged = [
        item
        for item in payload
        if isinstance(item, dict)
        and item.get("merged_at")
        and isinstance(item.get("base"), dict)
        and item["base"].get("ref") == "main"
    ]
    if len(merged) != 1:
        return None
    return merged[0]


def resolve_main_evidence(
    *,
    api_url: str,
    repository: str,
    commit_sha: str,
    required_checks: tuple[str, ...],
    token: str,
) -> dict[str, Any]:
    """解析来源 PR/tree/check；任何不可确认事实都返回 reusable=false。"""
    result: dict[str, Any] = {
        "reusable": False,
        "reason": "unresolved",
        "source_pr": "",
        "source_head": "",
        "current_tree": "",
        "source_tree": "",
        "required_checks": list(required_checks),
    }
    if not token:
        result["reason"] = "missing_token"
        return result
    if repository.count("/") != 1 or not commit_sha or not required_checks:
        result["reason"] = "invalid_input"
        return result

    try:
        source_pr = _resolve_source_pr(
            api_url=api_url,
            repository=repository,
            commit_sha=commit_sha,
            token=token,
        )
        if source_pr is None:
            result["reason"] = "source_pr_not_unique"
            return result

        source_head = str(
            (source_pr.get("head") or {}).get("sha")
            if isinstance(source_pr.get("head"), dict)
            else ""
        )
        source_pr_number = source_pr.get("number")
        if not source_head or not isinstance(source_pr_number, int):
            result["reason"] = "source_pr_incomplete"
            return result

        current_commit = _api_get(
            _repo_api(
                api_url,
                repository,
                f"commits/{quote(commit_sha, safe='')}",
            ),
            token=token,
        )
        source_commit = _api_get(
            _repo_api(
                api_url,
                repository,
                f"commits/{quote(source_head, safe='')}",
            ),
            token=token,
        )
        current_tree = str(((current_commit.get("commit") or {}).get("tree") or {}).get("sha") or "")
        source_tree = str(((source_commit.get("commit") or {}).get("tree") or {}).get("sha") or "")

        checks_payload = _api_get(
            _repo_api(
                api_url,
                repository,
                f"commits/{quote(source_head, safe='')}/check-runs?per_page=100",
            ),
            token=token,
        )
        check_runs = checks_payload.get("check_runs") if isinstance(checks_payload, dict) else None
        if not isinstance(check_runs, list):
            result["reason"] = "check_runs_unavailable"
            return result

        evaluation = evaluate_reuse(
            current_tree=current_tree,
            source_tree=source_tree,
            required_checks=required_checks,
            check_runs=tuple(item for item in check_runs if isinstance(item, dict)),
        )
        result.update(
            {
                "reusable": evaluation.reusable,
                "reason": evaluation.reason,
                "source_pr": str(source_pr_number),
                "source_head": source_head,
                "current_tree": current_tree,
                "source_tree": source_tree,
            }
        )
        return result
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError, KeyError, TypeError):
        result["reason"] = "github_api_unavailable"
        return result


def _write_github_output(path: Path, result: dict[str, Any]) -> None:
    """把复用判定写入 GitHub Actions 输出。"""
    values = {
        "reusable": "true" if result.get("reusable") else "false",
        "reason": str(result.get("reason") or ""),
        "source_pr": str(result.get("source_pr") or ""),
        "source_head": str(result.get("source_head") or ""),
        "current_tree": str(result.get("current_tree") or ""),
        "source_tree": str(result.get("source_tree") or ""),
    }
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def build_parser() -> argparse.ArgumentParser:
    """构建 main Evidence Reuse CLI。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--required-check", action="append", required=True)
    parser.add_argument("--github-output", type=Path)
    return parser


def main() -> int:
    """执行安全复用判定；GitHub 事实不可用时只降级为不可复用。"""
    args = build_parser().parse_args()
    result = resolve_main_evidence(
        api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        repository=args.repository,
        commit_sha=args.commit,
        required_checks=tuple(args.required_check),
        token=os.environ.get("GITHUB_TOKEN", ""),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.github_output is not None:
        _write_github_output(args.github_output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
