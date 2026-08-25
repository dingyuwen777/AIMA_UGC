from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / ".agents" / "skills" / "reliable-vibe-coding"


def _read(relative_path: str) -> str:
    return (SKILL_ROOT / relative_path).read_text(encoding="utf-8")


def test_global_skill_requires_chinese_git_commit_messages() -> None:
    skill = _read("SKILL.md")
    workflows = _read("references/05_development-workflows.md")
    review = _read("references/11_verification-review.md")

    assert "所有 Git 提交信息使用中文" in skill
    assert "Git 提交信息统一使用中文" in workflows
    assert "Commit message 必须使用中文" in review


def test_global_skill_requires_chinese_comments_for_public_and_internal_functions() -> None:
    skill = _read("SKILL.md")
    workflows = _read("references/05_development-workflows.md")
    review = _read("references/11_verification-review.md")

    assert "代码注释统一使用中文" in skill
    assert "内部/private/helper 函数也必须写函数级中文注释或文档注释" in skill
    assert "除专有名词、标识符、协议、库和标准名外，代码注释统一使用中文" in workflows
    assert "内部/private/helper 函数不能因为不是 public 就省略函数级说明" in workflows
    assert (
        "新增或修改的 public/exported 与内部/private/helper 函数是否都有必要的中文函数级说明"
        in review
    )


def test_global_language_rules_are_not_delegated_to_project_overlay() -> None:
    preservation = _read("references/12_rule-preservation-map.md")
    agent = _read("agents/openai.yaml")

    assert "Git 提交信息使用中文" in preservation
    assert "代码注释使用中文" in preservation
    assert "内部/private/helper 函数也必须纳入函数级注释要求" in preservation
    assert "write Git commit messages in Chinese" in agent
    assert "write code comments in Chinese" in agent
    assert "document internal/private/helper functions" in agent

    overlay_section = preservation.split("### 应由项目 Overlay 决定", maxsplit=1)[1]
    assert "commit message 语言" not in overlay_section
    assert "代码注释与 docstring/comment language" not in overlay_section
