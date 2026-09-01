from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts" / "quality" / "check_pr_requirement_source.py"
CHECKER = runpy.run_path(str(CHECKER_PATH))
RequirementSourceError = CHECKER["RequirementSourceError"]
EXTRACT_REQUIREMENT_SOURCES = CHECKER["extract_requirement_sources"]
VALIDATE_REQUIREMENT_SOURCES = CHECKER["validate_requirement_sources"]


def _issue_loader(number: int) -> dict[str, Any]:
    """返回单元测试使用的真实 Issue 形状，不触发网络访问。"""
    if number == 286:
        return {"number": 286, "title": "协作治理"}
    if number == 999:
        return {"number": 999, "title": "这是 PR", "pull_request": {"url": "example"}}
    raise RequirementSourceError(f"Issue #{number} 不存在或不可访问")


def test_extract_requires_at_least_one_source() -> None:
    """PR 缺少 Requirement-Source 时必须失败关闭。"""
    with pytest.raises(RequirementSourceError, match="缺少 Requirement-Source"):
        EXTRACT_REQUIREMENT_SOURCES("## 背景\n无来源\n")


@pytest.mark.parametrize(
    "value",
    (
        "",
        "#<Issue>",
        "TBD",
        "TODO",
        "待确认",
    ),
)
def test_extract_rejects_empty_or_placeholder_sources(value: str) -> None:
    """模板占位值或未决值不能冒充稳定需求来源。"""
    with pytest.raises(RequirementSourceError, match="占位|为空"):
        EXTRACT_REQUIREMENT_SOURCES(f"Requirement-Source: {value}\n")


def test_extract_preserves_multiple_sources() -> None:
    """一个 PR 确实实现多个来源时应保留全部 Requirement Source。"""
    sources = EXTRACT_REQUIREMENT_SOURCES(
        "Requirement-Source: #286\nRequirement-Source: docs/blueprint/07_技术决策与实施门禁.md\n"
    )

    assert sources == ("#286", "docs/blueprint/07_技术决策与实施门禁.md")


def test_validate_accepts_real_issue_and_repository_file(tmp_path: Path) -> None:
    """真实本仓 Issue 与安全存在的仓库相对正式路径都应通过。"""
    requirement_file = tmp_path / "docs" / "spec.md"
    requirement_file.parent.mkdir(parents=True)
    requirement_file.write_text("# Spec\n", encoding="utf-8")

    sources = VALIDATE_REQUIREMENT_SOURCES(
        "Requirement-Source: #286\nRequirement-Source: docs/spec.md\n",
        root=tmp_path,
        issue_loader=_issue_loader,
    )

    assert sources == ("#286", "docs/spec.md")


def test_validate_rejects_issue_that_is_actually_pull_request(tmp_path: Path) -> None:
    """GitHub `/issues` 同时返回 PR，机器门禁必须排除 PR 伪装的需求来源。"""
    with pytest.raises(RequirementSourceError, match="Pull Request"):
        VALIDATE_REQUIREMENT_SOURCES(
            "Requirement-Source: #999\n",
            root=tmp_path,
            issue_loader=_issue_loader,
        )


def test_validate_rejects_missing_issue(tmp_path: Path) -> None:
    """不存在或不可访问的 Issue 不能通过追溯门禁。"""
    with pytest.raises(RequirementSourceError, match="不存在或不可访问"):
        VALIDATE_REQUIREMENT_SOURCES(
            "Requirement-Source: #404\n",
            root=tmp_path,
            issue_loader=_issue_loader,
        )


@pytest.mark.parametrize("source", ("../outside.md", "/tmp/spec.md", "docs/missing.md"))
def test_validate_rejects_unsafe_or_missing_repository_paths(
    tmp_path: Path,
    source: str,
) -> None:
    """路径来源必须留在仓库内且指向当前真实文件。"""
    with pytest.raises(RequirementSourceError, match="仓库相对路径|不存在"):
        VALIDATE_REQUIREMENT_SOURCES(
            f"Requirement-Source: {source}\n",
            root=tmp_path,
            issue_loader=_issue_loader,
        )


def test_validate_rejects_unsupported_identifier(tmp_path: Path) -> None:
    """AIMA 未定义的自由文本 ID/URL 不应被机器门禁猜测解析。"""
    with pytest.raises(RequirementSourceError, match="不支持的 Requirement-Source"):
        VALIDATE_REQUIREMENT_SOURCES(
            "Requirement-Source: RFC-123\n",
            root=tmp_path,
            issue_loader=_issue_loader,
        )
