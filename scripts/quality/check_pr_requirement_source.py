"""校验提交到 main 的 PR 是否引用合规 Requirement Source，并校验本次新增 Change。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_CONTRACT_PATH = ROOT / "scripts" / "quality" / "governance_asset_contract.py"
REQUIREMENT_SOURCE_PATTERN = re.compile(
    r"^\s*Requirement-Source\s*:\s*(.*?)\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)
ISSUE_SOURCE_PATTERN = re.compile(r"^#([1-9][0-9]*)$")
PLACEHOLDER_SOURCES = {
    "#<issue>",
    "<issue>",
    "tbd",
    "todo",
    "none",
    "null",
    "n/a",
    "na",
    "待确认",
    "待补充",
    "无",
    "-",
}


def _load_governance_contract() -> Any:
    """加载 AIMA 项目治理资产机器 Contract 适配器，避免 checker 复制 Profile 规则。"""
    spec = importlib.util.spec_from_file_location(
        "aima_governance_asset_contract",
        GOVERNANCE_CONTRACT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载项目治理资产机器 Contract：{GOVERNANCE_CONTRACT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GOVERNANCE_CONTRACT = _load_governance_contract()


class RequirementSourceError(ValueError):
    """表示 PR Requirement Source 或新增治理资产不满足机器可验证约束。"""


def extract_requirement_sources(body: str) -> tuple[str, ...]:
    """从 PR body 提取全部 Requirement-Source，并拒绝空值与占位值。"""
    sources = tuple(match.strip() for match in REQUIREMENT_SOURCE_PATTERN.findall(body))
    if not sources:
        raise RequirementSourceError("PR 缺少 Requirement-Source；请引用本仓 Issue 或正式仓库路径")

    for source in sources:
        if not source:
            raise RequirementSourceError("Requirement-Source 为空；必须填写真实需求来源")
        normalized = source.casefold()
        if normalized in PLACEHOLDER_SOURCES or "<issue>" in normalized:
            raise RequirementSourceError(
                f"Requirement-Source 使用占位值 {source!r}；请替换为真实 Issue 或仓库路径"
            )
    return sources


def _validate_issue_source(
    source: str,
    issue_loader: Callable[[int], Mapping[str, Any]],
    *,
    root: Path,
) -> None:
    """确认本仓 Issue 真实存在且 live 实例满足当前 AIMA Project Profile。"""
    match = ISSUE_SOURCE_PATTERN.fullmatch(source)
    if match is None:
        raise RequirementSourceError(f"不支持的 Issue Requirement-Source: {source}")

    number = int(match.group(1))
    issue = issue_loader(number)
    if "pull_request" in issue:
        raise RequirementSourceError(
            f"Requirement-Source {source} 指向 Pull Request；请引用定义需求的 Issue"
        )
    title = str(issue.get("title") or "").strip()
    body = str(issue.get("body") or "").strip()
    if not title or not body:
        raise RequirementSourceError(f"Requirement-Source {source} 缺少可审查的标题或正文")
    errors = GOVERNANCE_CONTRACT.validate_issue_instance(title, body, root=root)
    if errors:
        raise RequirementSourceError(
            f"Requirement-Source {source} 不满足当前 AIMA 治理资产机器 Contract：\n- "
            + "\n- ".join(errors)
        )


def _looks_like_repository_path(source: str) -> bool:
    """判断自由文本是否明确表现为仓库相对文件路径，而不是猜测外部 ID。"""
    if "://" in source or "\\" in source:
        return False
    path = PurePosixPath(source)
    return "/" in source or bool(path.suffix)


def _validate_repository_path(source: str, root: Path) -> None:
    """确认路径留在仓库根目录内且当前确实指向一个文件。"""
    if not _looks_like_repository_path(source):
        raise RequirementSourceError(
            f"不支持的 Requirement-Source {source!r}；只接受 #<Issue编号> 或仓库相对文件路径"
        )

    path = PurePosixPath(source)
    if path.is_absolute() or ".." in path.parts:
        raise RequirementSourceError(f"Requirement-Source {source!r} 必须是安全的仓库相对路径")

    root_resolved = root.resolve()
    candidate = (root_resolved / Path(*path.parts)).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise RequirementSourceError(
            f"Requirement-Source {source!r} 必须是安全的仓库相对路径"
        ) from exc

    if not candidate.is_file():
        raise RequirementSourceError(f"Requirement-Source 仓库路径不存在: {source}")


def validate_requirement_sources(
    body: str,
    *,
    root: Path,
    issue_loader: Callable[[int], Mapping[str, Any]],
) -> tuple[str, ...]:
    """验证 PR body 中每个来源都满足真实可访问与当前 Project Profile 约束。"""
    sources = extract_requirement_sources(body)
    for source in sources:
        if ISSUE_SOURCE_PATTERN.fullmatch(source):
            _validate_issue_source(source, issue_loader, root=root)
            continue
        _validate_repository_path(source, root)
    return sources


def _load_github_issue(
    number: int,
    *,
    repository: str,
    token: str,
    api_url: str,
) -> Mapping[str, Any]:
    """使用最小 GitHub Issues 读权限加载本仓 Issue，并把不可确认状态失败关闭。"""
    if not token:
        raise RequirementSourceError("GITHUB_TOKEN 为空，无法确认 Requirement-Source Issue")
    if repository.count("/") != 1:
        raise RequirementSourceError("GitHub event 缺少有效 repository.full_name")

    owner, repo = repository.split("/", maxsplit=1)
    issue_path = f"{quote(owner, safe='')}/{quote(repo, safe='')}/issues/{number}"
    url = f"{api_url.rstrip('/')}/repos/{issue_path}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AIMA-UGC-Requirement-Source-Gate",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - URL 固定来自 GitHub API 基址
            payload = json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            raise RequirementSourceError(f"Issue #{number} 不存在或不可访问") from exc
        raise RequirementSourceError(
            f"GitHub Issues API 返回 HTTP {exc.code}，无法确认 Issue #{number}"
        ) from exc
    except URLError as exc:
        raise RequirementSourceError(
            f"GitHub Issues API 访问失败，无法确认 Issue #{number}"
        ) from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise RequirementSourceError(
            f"GitHub Issues API 响应无法解析，无法确认 Issue #{number}"
        ) from exc

    if not isinstance(payload, dict):
        raise RequirementSourceError(f"GitHub Issues API 响应形状异常，无法确认 Issue #{number}")
    return payload


def _load_pull_request_event(event_path: Path) -> tuple[str, str, str, str]:
    """从 GitHub pull_request event 读取 body、仓库身份与 base/head revision。"""
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RequirementSourceError(f"无法读取 GitHub event: {event_path}") from exc

    if not isinstance(event, dict):
        raise RequirementSourceError("GitHub event 根对象不是 JSON object")
    pull_request = event.get("pull_request")
    repository = event.get("repository")
    if not isinstance(pull_request, dict) or not isinstance(repository, dict):
        raise RequirementSourceError("当前 GitHub event 不是可校验的 pull_request event")

    body = pull_request.get("body")
    repository_name = repository.get("full_name")
    base = pull_request.get("base")
    head = pull_request.get("head")
    if body is None:
        body = ""
    if not isinstance(body, str) or not isinstance(repository_name, str):
        raise RequirementSourceError("GitHub event 中 PR body 或 repository.full_name 类型异常")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise RequirementSourceError("GitHub event 中 PR base/head 结构异常")
    base_sha = str(base.get("sha") or "").strip()
    head_sha = str(head.get("sha") or "").strip()
    if not base_sha or not head_sha:
        raise RequirementSourceError("GitHub event 中 PR base/head SHA 为空")
    return body, repository_name, base_sha, head_sha


def build_parser() -> argparse.ArgumentParser:
    """构建 CI 命令行解析器，显式暴露 event 与仓库根路径。"""
    parser = argparse.ArgumentParser(description="校验 PR Requirement-Source 与新增治理资产")
    parser.add_argument("--event", type=Path, required=True, help="GitHub GITHUB_EVENT_PATH")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="当前仓库根目录")
    return parser


def main() -> int:
    """执行真实 PR Requirement Source / new Change 校验并返回适合 GitHub Actions 的退出码。"""
    args = build_parser().parse_args()
    try:
        body, repository, base_sha, head_sha = _load_pull_request_event(args.event)
        validated_changes = GOVERNANCE_CONTRACT.validate_new_changes_since(
            args.root,
            base_sha=base_sha,
            head_sha=head_sha,
        )
        token = os.environ.get("GITHUB_TOKEN", "")
        api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")

        def issue_loader(number: int) -> Mapping[str, Any]:
            """把当前 event 的仓库和 GitHub 凭据绑定为同仓 Issue 加载器。"""
            return _load_github_issue(
                number,
                repository=repository,
                token=token,
                api_url=api_url,
            )

        sources = validate_requirement_sources(body, root=args.root, issue_loader=issue_loader)
    except (RequirementSourceError, GOVERNANCE_CONTRACT.GovernanceAssetContractError) as exc:
        print(f"PR Requirement Source / Governance Asset 校验失败: {exc}")
        return 1

    print(f"PR Requirement Source 校验通过，共确认 {len(sources)} 个来源。")
    if validated_changes:
        print(f"新增 Change 机器 Contract 校验通过，共确认 {len(validated_changes)} 个实例。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
