from __future__ import annotations

import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts" / "quality" / "check_agent_governance.py"
CHECKER = runpy.run_path(str(CHECKER_PATH))
CHECK_REPOSITORY = CHECKER["check_repository"]
MANAGED_START = "<!-- agent-skills:managed:start -->"
MANAGED_END = "<!-- agent-skills:managed:end -->"


def _write(path: Path, content: str) -> None:
    """创建测试治理仓库中的 UTF-8 文本文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_issue_form(fields: tuple[str, ...]) -> str:
    """生成只承载 checker 契约所需字段的最小 Issue Form 夹具。"""
    return "\n".join(
        f"- type: textarea\n  {field}\n  validations:\n    required: true" for field in fields
    )


def _minimal_repository(root: Path) -> None:
    """建立满足 AIMA 项目治理接线检查的最小仓库夹具。"""
    _write(
        root / "AGENTS.md",
        "\n".join(
            (
                MANAGED_START,
                "治理能力自身的运行与实现细节不属于项目进度或交付内容。",
                MANAGED_END,
                "<!-- agent-skills:project-governance:v1 -->",
                "项目区",
            )
        ),
    )
    _write(
        root / "docs/AGENTS.md",
        "# 文档规则\n\n先遵守根 `AGENTS.md`、当前任务适用的项目事实与文档规则。\n",
    )
    _write(root / ".agents/skills/coding/scripts/ready_check.py", "# 测试夹具\n")
    _write(root / "scripts/quality/check_pr_requirement_source.py", "# 测试夹具\n")
    _write(
        root / ".github/workflows/change-completion-gate.yml",
        "on:\n"
        "  pull_request:\n"
        "    types:\n"
        "      - opened\n"
        "      - synchronize\n"
        "      - reopened\n"
        "      - edited\n"
        "permissions:\n  contents: read\n  issues: read\n"
        "python scripts/quality/check_agent_governance.py\n"
        "python scripts/quality/check_pr_requirement_source.py --event event.json --root .\n"
        "python .agents/skills/coding/scripts/ready_check.py --root .\n",
    )
    _write(
        root / ".github/ISSUE_TEMPLATE/01-requirement.yml",
        _minimal_issue_form(
            (
                "id: objective",
                "id: scope",
                "id: non_goals",
                "id: acceptance_criteria",
                "id: invariants",
                "id: upstream_sources",
            )
        ),
    )
    _write(
        root / ".github/ISSUE_TEMPLATE/02-bug.yml",
        _minimal_issue_form(
            (
                "id: actual_behavior",
                "id: expected_behavior",
                "id: impact_scope",
                "id: reproduction_steps",
                "id: evidence",
                "id: regression_scope",
                "id: acceptance_criteria",
                "id: upstream_sources",
            )
        ),
    )
    _write(
        root / ".github/ISSUE_TEMPLATE/03-technical-change.yml",
        _minimal_issue_form(
            (
                "id: motivation",
                "id: current_state",
                "id: target_state",
                "id: scope",
                "id: non_goals",
                "id: compatibility_migration",
                "id: risks_rollback",
                "id: acceptance_criteria",
                "id: validation_plan",
                "id: upstream_sources",
            )
        ),
    )
    _write(
        root / ".github/ISSUE_TEMPLATE/config.yml",
        "blank_issues_enabled: false\n",
    )
    _write(
        root / ".github/PULL_REQUEST_TEMPLATE.md",
        "Requirement-Source: #123\n"
        "仓库内真实存在的正式文件也可以作为 Requirement Source。\n"
        "不要用关闭关键字替代 Requirement-Source。\n",
    )


def _managed_block(text: str) -> str:
    """提取唯一的 Agent_Skills managed block，供项目侧披露回归检查。"""
    start = text.index(MANAGED_START)
    end = text.index(MANAGED_END, start) + len(MANAGED_END)
    return text[start:end]


def test_current_repository_governance_wiring_is_valid() -> None:
    """当前仓库必须只依赖 AIMA 自己可维护的项目治理接线。"""
    assert CHECK_REPOSITORY(ROOT) == []


def test_current_project_uses_local_branch_first_work_initialization() -> None:
    """AIMA 项目规则必须固定本地分支、首次 push 与早期 PR 的真实顺序。"""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    blueprint = (ROOT / "docs/blueprint/06_开发约束与分阶段实施.md").read_text(encoding="utf-8")
    combined = agents + blueprint

    for marker in (
        "本地任务分支",
        "首个本地提交",
        "首次 push",
        "远程跟踪分支",
        "早期 PR",
        "不得先创建远程空分支",
        "Issue ↔ Change ↔ branch ↔ PR",
    ):
        assert marker in combined


def test_current_managed_block_is_project_facing_without_runtime_internals() -> None:
    """正式安装后的根入口不得继续暴露旧 Runtime/MCP/路由加载实现。"""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    managed = _managed_block(agents)

    assert "治理能力自身的运行与实现细节不属于项目进度或交付内容" in managed
    for forbidden in (
        "Runtime Mode",
        "研发治理 MCP",
        "规则标识",
        "路由映射",
        "加载明细",
        "内部凭据",
    ):
        assert forbidden not in managed


def test_project_docs_do_not_route_generic_governance_to_local_installed_skill_core() -> None:
    """项目文档规则不得把本地 Agent_Skills 安装副本当通用治理入口。"""
    docs_agents = (ROOT / "docs/AGENTS.md").read_text(encoding="utf-8")

    assert ".agents/skills/coding/" not in docs_agents
    assert "先遵守根 `AGENTS.md`、当前任务适用的项目事实与文档规则" in docs_agents


def test_repository_no_longer_tracks_legacy_runtime_or_install_manifest() -> None:
    """正式升级后 legacy manifest 与项目内 Runtime binary 不再作为 Git 仓库资产。"""
    assert not (ROOT / ".agents/agent-skills-install.json").exists()

    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".agents/runtime/agent-skills-mcp.exe"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.returncode != 0
    assert "/.agents/runtime/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_checker_rejects_supplier_internal_workflow_paths(tmp_path: Path) -> None:
    """永久 CI 不得重新依赖 Agent_Skills canonical tests 或 References。"""
    _minimal_repository(tmp_path)
    _write(
        tmp_path / ".github/workflows/ci.yml",
        "python -m unittest discover .agents/skills/coding/tests -v\n"
        "cat .agents/skills/coding/references/08_example.md\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    assert len([error for error in errors if error.startswith("GOV005")]) == 2


def test_checker_rejects_internal_runtime_terms_in_managed_block(tmp_path: Path) -> None:
    """目标项目根 managed block 不得重新生长旧 Runtime/MCP 实现说明。"""
    _minimal_repository(tmp_path)
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    agents = agents.replace(
        MANAGED_END,
        "Runtime Mode 使用研发治理 MCP，并输出路由映射与加载明细。\n" + MANAGED_END,
    )
    _write(tmp_path / "AGENTS.md", agents)

    errors = CHECK_REPOSITORY(tmp_path)

    managed_errors = [error for error in errors if error.startswith("GOV009")]
    assert len(managed_errors) >= 4


def test_checker_rejects_local_installed_skill_as_project_docs_governance_source(
    tmp_path: Path,
) -> None:
    """项目自有 docs 规则不能把本地安装 Skill Core 当作通用规范 Owner。"""
    _minimal_repository(tmp_path)
    _write(
        tmp_path / "docs/AGENTS.md",
        "先遵守根 `AGENTS.md` 与 `.agents/skills/coding/` 的 Coding Skill。\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    docs_errors = [error for error in errors if error.startswith("GOV010")]
    assert len(docs_errors) == 2


def test_checker_rejects_generic_governance_implementation_in_project_overlay(
    tmp_path: Path,
) -> None:
    """marker 外 AIMA Overlay 只能描述项目规则和事实，不保存通用治理实现。"""
    _minimal_repository(tmp_path)
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    agents += "\nSource Mode 从 Project Payload 读取 canonical Reference。\n"
    _write(tmp_path / "AGENTS.md", agents)

    errors = CHECK_REPOSITORY(tmp_path)

    overlay_errors = [error for error in errors if error.startswith("GOV011")]
    assert len(overlay_errors) == 3


def test_checker_requires_unique_governance_markers(tmp_path: Path) -> None:
    """根治理入口的 managed 与项目校准 marker 必须保持唯一。"""
    _minimal_repository(tmp_path)
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    _write(tmp_path / "AGENTS.md", agents + "\n<!-- agent-skills:managed:start -->\n")

    errors = CHECK_REPOSITORY(tmp_path)

    assert any(error.startswith("GOV002") for error in errors)


def test_checker_requires_ready_check_and_completion_gate_wiring(tmp_path: Path) -> None:
    """AIMA Completion Gate 必须继续保留项目 Ready Check 证明责任。"""
    _minimal_repository(tmp_path)
    (tmp_path / ".agents/skills/coding/scripts/ready_check.py").unlink()
    _write(
        tmp_path / ".github/workflows/change-completion-gate.yml",
        "permissions:\n  issues: read\n"
        "python scripts/quality/check_agent_governance.py\n"
        "python scripts/quality/check_pr_requirement_source.py\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    assert any(error.startswith("GOV004") for error in errors)
    assert any(error.startswith("GOV007") for error in errors)


def test_checker_requires_pr_requirement_source_gate_wiring(tmp_path: Path) -> None:
    """真实 PR Requirement Source checker、Workflow 调用和最小 Issues 权限必须同时存在。"""
    _minimal_repository(tmp_path)
    (tmp_path / "scripts/quality/check_pr_requirement_source.py").unlink()
    _write(
        tmp_path / ".github/workflows/change-completion-gate.yml",
        "python scripts/quality/check_agent_governance.py\n"
        "python .agents/skills/coding/scripts/ready_check.py --root .\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    source_errors = [error for error in errors if error.startswith("GOV015")]
    assert len(source_errors) == 4


def test_checker_requires_pr_body_edit_revalidation(tmp_path: Path) -> None:
    """治理回归必须阻止 Requirement Source 的 `edited` 重验触发被删除。"""
    _minimal_repository(tmp_path)
    workflow_path = tmp_path / ".github/workflows/change-completion-gate.yml"
    workflow = workflow_path.read_text(encoding="utf-8").replace("      - edited\n", "")
    _write(workflow_path, workflow)

    errors = CHECK_REPOSITORY(tmp_path)

    assert any(error.startswith("GOV015") and "正文 edited" in error for error in errors)


def test_checker_requires_issue_and_pr_requirement_traceability(tmp_path: Path) -> None:
    """多人协作入口缺少 Issue/PR 需求追溯契约时必须被项目治理检查阻止。"""
    _minimal_repository(tmp_path)
    (tmp_path / ".github/ISSUE_TEMPLATE/01-requirement.yml").unlink()
    (tmp_path / ".github/ISSUE_TEMPLATE/03-technical-change.yml").unlink()
    (tmp_path / ".github/ISSUE_TEMPLATE/config.yml").unlink()
    _write(tmp_path / ".github/PULL_REQUEST_TEMPLATE.md", "# PR\n")

    errors = CHECK_REPOSITORY(tmp_path)

    assert len([error for error in errors if error.startswith("GOV012")]) >= 2
    assert any(error.startswith("GOV013") for error in errors)
    assert any(error.startswith("GOV014") for error in errors)


def test_checker_requires_local_branch_first_work_initialization(tmp_path: Path) -> None:
    """项目治理检查必须阻止本地开工顺序规则被静默删除。"""
    _minimal_repository(tmp_path)

    errors = CHECK_REPOSITORY(tmp_path)

    assert any(error.startswith("GOV016") for error in errors)
