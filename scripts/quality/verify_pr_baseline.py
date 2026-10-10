"""只读核验 metadata 编辑可复用的同 HEAD/base/merge 正式 CI 结果。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
from collections.abc import Callable
from typing import Any


def verify_checkout(head: str, base: str, merge: str) -> None:
    """把 run-name 中的组合与本次实际 checkout 绑定，拒绝非预期 merge ref。"""
    current = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    parents = subprocess.check_output(
        ["git", "rev-list", "--parents", "-n", "1", current], text=True
    ).split()
    if current != merge or parents[1:] != [base, head]:
        raise ValueError("PR checkout 与事件的 HEAD/base/merge 组合不一致")


def resolve_workflow_ids(catalog: dict[str, Any], required: set[str]) -> dict[str, int]:
    """从完整正式目录取得唯一身份；Run 标题会随 run-name 展开，不能当作身份。"""
    workflows = catalog.get("workflows")
    total = catalog.get("total_count")
    if (
        not isinstance(workflows, list)
        or type(total) is not int
        or total != len(workflows)
        or any(not isinstance(workflow, dict) for workflow in workflows)
    ):
        raise ValueError("Workflow 目录不完整或格式无效，不能证明唯一身份")
    resolved: dict[str, int] = {}
    for name in required:
        matching = [workflow for workflow in workflows if workflow.get("name") == name]
        if len(matching) != 1:
            raise ValueError(f"{name}: Workflow 目录身份缺失或不唯一")
        workflow_id = matching[0].get("id")
        if type(workflow_id) is not int or workflow_id <= 0:
            raise ValueError(f"{name}: Workflow ID 无效")
        resolved[name] = workflow_id
    return resolved


def verify_baseline(
    runs: list[dict[str, Any]],
    *,
    head: str,
    base: str,
    merge: str,
    current_run: int,
    required: dict[str, set[str]],
    workflow_ids: dict[str, int],
    jobs: Callable[[int], list[dict[str, Any]]],
) -> int:
    """仅接受正式 full run 的最新成功 jobs；未知/失败拒绝，执行中返回 75。"""
    marker = f"head={head} base={base} merge={merge} lane=full"
    waiting = False
    for workflow, identities in required.items():
        candidates = [
            run
            for run in runs
            if type(run.get("workflow_id")) is int
            and run["workflow_id"] == workflow_ids[workflow]
            and run.get("event") == "pull_request"
            and run.get("head_sha") == head
            and int(run.get("id", 0)) != current_run
            and str(run.get("display_title", "")).endswith(marker)
            and any(
                pr.get("head", {}).get("sha") == head and pr.get("base", {}).get("sha") == base
                for pr in run.get("pull_requests", [])
            )
        ]
        if not candidates:
            raise ValueError(f"{workflow}: 没有可证明同 HEAD/base/merge 的 full baseline")
        source = max(candidates, key=lambda run: int(run["id"]))
        if source.get("status") != "completed":
            waiting = True
            continue
        if source.get("conclusion") != "success":
            raise ValueError(f"{workflow}: 最新同组合 full run 未成功")
        source_jobs = jobs(int(source["id"]))
        for identity in identities:
            matching = [job for job in source_jobs if job.get("name") == identity]
            if (
                len(matching) != 1
                or matching[0].get("conclusion") != "success"
                or matching[0].get("status") != "completed"
            ):
                raise ValueError(f"{workflow}: required job {identity} 未唯一成功")
    return 75 if waiting else 0


def main() -> int:
    """只调用 GitHub 只读 API，不写 check、不修改 Run、不接受旧基线。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--merge", required=True)
    parser.add_argument("--verify-checkout", action="store_true")
    parser.add_argument("--require", action="append", default=[], metavar="WORKFLOW:JOB")
    args = parser.parse_args()
    try:
        verify_checkout(args.head, args.base, args.merge)
        if args.verify_checkout:
            return 0
        if not args.require:
            raise ValueError("必须指定正式 required job identity")
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        repository = os.environ["GITHUB_REPOSITORY"]
        if not token:
            raise ValueError("GitHub 只读凭据不可用")

        def get(path: str) -> dict[str, Any]:
            request = urllib.request.Request(
                f"https://api.github.com/repos/{repository}/{path}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)

        required: dict[str, set[str]] = {}
        for value in args.require:
            workflow, identity = value.split(":", 1)
            required.setdefault(workflow, set()).add(identity)
        workflow_ids = resolve_workflow_ids(get("actions/workflows?per_page=100"), set(required))
        runs = get(f"actions/runs?head_sha={args.head}&event=pull_request&per_page=100")[
            "workflow_runs"
        ]
        result = verify_baseline(
            runs,
            head=args.head,
            base=args.base,
            merge=args.merge,
            current_run=int(os.environ["GITHUB_RUN_ID"]),
            required=required,
            workflow_ids=workflow_ids,
            jobs=lambda run: get(f"actions/runs/{run}/jobs?per_page=100")["jobs"],
        )
        print(
            "同 HEAD/base/merge 正式 baseline 已成功。"
            if result == 0
            else "同组合 full run 仍在运行。"
        )
        return result
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as _error:
        print("metadata baseline 核验失败；必须取得当前 HEAD/base/merge 的正式 required evidence。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
