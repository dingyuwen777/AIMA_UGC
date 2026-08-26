"""按变更路径保守判断 AIMA CI 应执行的风险 profile。"""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Iterable
from pathlib import Path

DOCS_ONLY_EXACT = {"README.md"}
GOVERNANCE_ONLY_EXACT = {"AGENTS.md"}
DOCS_ONLY_PREFIXES = ("docs/",)
GOVERNANCE_ONLY_PREFIXES = ("changes/", ".agents/")


def _normalize_path(path: str) -> str:
    """把 Git 路径规范成仓库相对 POSIX 形式，不破坏 `.agents` 这类点目录。"""
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _classify_path(path: str) -> str:
    """对单一路径做白名单式分类；任何未知路径都保守回退到 full。"""
    normalized = _normalize_path(path)
    if not normalized:
        return "full"
    if (
        normalized in GOVERNANCE_ONLY_EXACT
        or normalized.endswith("/AGENTS.md")
        or normalized.startswith(GOVERNANCE_ONLY_PREFIXES)
    ):
        return "governance_only"
    if normalized in DOCS_ONLY_EXACT or normalized.endswith("/README.md"):
        return "docs_only"
    if normalized.startswith(DOCS_ONLY_PREFIXES):
        return "docs_only"
    return "full"


def classify_paths(paths: Iterable[str]) -> str:
    """汇总路径得到 CI profile；full 优先，其次 governance_only，最后 docs_only。"""
    normalized: list[str] = []
    for path in paths:
        candidate = _normalize_path(path)
        if candidate:
            normalized.append(candidate)
    if not normalized:
        return "full"

    classifications = {_classify_path(path) for path in normalized}
    if "full" in classifications:
        return "full"
    if "governance_only" in classifications:
        return "governance_only"
    return "docs_only"


def _changed_paths(base: str, head: str) -> list[str] | None:
    """读取两个提交间的全部路径；关闭 rename detection 以同时保留旧/新路径风险。"""
    if not base or not head or set(base) == {"0"}:
        return None
    try:
        completed = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", base, head],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        return None
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    ]


def _write_github_output(path: Path, profile: str, changed_count: int) -> None:
    """把分类结果写入 GitHub Actions 输出文件。"""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"profile={profile}\n")
        handle.write(f"changed_count={changed_count}\n")


def main() -> int:
    """从 Git diff 计算 CI profile，并可输出给 GitHub Actions。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="变更基线 commit SHA")
    parser.add_argument("--head", required=True, help="变更目标 commit SHA")
    parser.add_argument("--github-output", type=Path, help="可选 GITHUB_OUTPUT 文件")
    args = parser.parse_args()

    changed_paths = _changed_paths(args.base, args.head)
    if changed_paths is None:
        profile = "full"
        changed_count = 0
        print("无法可靠读取变更范围，保守使用 full CI profile。")
    else:
        profile = classify_paths(changed_paths)
        changed_count = len(changed_paths)
        print(f"CI profile={profile}; changed_count={changed_count}")
        for path in changed_paths:
            print(f"- {path}")

    if args.github_output is not None:
        _write_github_output(args.github_output, profile, changed_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
