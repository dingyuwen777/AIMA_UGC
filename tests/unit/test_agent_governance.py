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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_issue_form(fields: tuple[str, ...]) -> str:
    return "\n".join(f"- type: textarea\n  {field}\n  validations:\n    required: true" for field in fields)


def _minimal_repository(root: Path) -> None:
    _write(root / "AGENTS.md", "\n".join((MANAGED_START, "治理能力自身的运行与实现细节不属于项目进度或交付内容。", MANAGED_END, "<!-- agent-skills:project-governance:v1 -->", "项目区")))
    _write(root / "docs/AGENTS.md", "# 文档规则\n\n先遵守根 `AGENTS.md`、当前任务适用的项目事实与文档规则。\n")
    _write(root / ".agents/skills/coding/scripts/ready_check.py", "# 测试夹具\n")
    _write(root / "scripts/quality/check_change_completion.py", "# 测试夹具\n")
    _write(root / "scripts/quality/check_pr_requirement_source.py", "# 测试夹具\n")
    _write(
        root / ".github/workflows/ci.yml",
        "on:\n  pull_request:\n    types:\n      - opened\n      - synchronize\n      - reopened\n      - edited\n"
        "permissions:\n  contents: read\n  issues: read\n"
        "python scripts/quality/check_agent_governance.py\n"
        "python scripts/quality/check_pr_requirement_source.py --event event.json --root .\n"
        "python scripts/quality/check_change_completion.py --root . --changed-since base\n"
        "python scripts/quality/check_change_completion.py --root . --require-active-ready\n",
    )
    _write(root / ".github/ISSUE_TEMPLATE/01-requirement.yml", _minimal_issue_form(("id: objective", "id: scope", "id: non_goals", "id: acceptance_criteria", "id: invariants", "id: upstream_sources")))
    _write(root / ".github/ISSUE_TEMPLATE/02-bug.yml", _minimal_issue_form(("id: actual_behavior", "id: expected_behavior", "id: impact_scope", "id: reproduction_steps", "id: evidence", "id: regression_scope", "id: acceptance_criteria", "id: upstream_sources")))
    _write(root / ".github/ISSUE_TEMPLATE/03-technical-change.yml", _minimal_issue_form(("id: motivation", "id: current_state", "id: target_state", "id: scope", "id: non_goals", "id: compatibility_migration", "id: risks_rollback", "id: acceptance_criteria", "id: validation_plan", "id: upstream_sources")))
    _write(root / ".github/ISSUE_TEMPLATE/config.yml", "blank_issues_enabled: false\n")
    _write(root / ".github/PULL_REQUEST_TEMPLATE.md", "Requirement-Source: #123\n仓库内真实存在的正式文件也可以作为 Requirement Source。\n不要用关闭关键字替代 Requirement-Source。\n")


def _managed_block(text: str) -> str:
    start = text.index(MANAGED_START)
    end = text.index(MANAGED_END, start) + len(MANAGED_END)
    return text[start:end]


def test_current_repository_governance_wiring_is_valid() -> None:
    assert CHECK_REPOSITORY(ROOT) == []


def test_current_managed_block_is_project_facing_without_runtime_internals() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    managed = _managed_block(agents)
    assert "治理能力自身的运行与实现细节不属于项目进度或交付内容" in managed
    for forbidden in ("Runtime Mode", "研发治理 MCP", "规则标识", "路由映射", "加载明细", "内部凭据"):
        assert forbidden not in managed


def test_project_docs_do_not_route_generic_governance_to_local_installed_skill_core() -> None:
    docs_agents = (ROOT / "docs/AGENTS.md").read_text(encoding="utf-8")
    assert ".agents/skills/coding/" not in docs_agents
    assert "先遵守根 `AGENTS.md`、当前任务适用的项目事实与文档规则" in docs_agents


def test_repository_tracks_current_runtime_without_legacy_assets() -> None:
    assert not (ROOT / ".agents/agent-skills-install.json").exists()
    legacy = subprocess.run(["git", "ls-files", "--error-unmatch", ".agents/runtime/agent-skills-mcp.exe"], cwd=ROOT, capture_output=True, text=True, check=False)
    current = subprocess.run(["git", "ls-files", "--error-unmatch", ".agents/runtime/agent-skills.exe"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert legacy.returncode != 0
    assert current.returncode == 0


def test_checker_rejects_supplier_internal_workflow_paths(tmp_path: Path) -> None:
    _minimal_repository(tmp_path)
    _write(tmp_path / ".github/workflows/extra.yml", "python -m unittest discover .agents/skills/coding/tests -v\ncat .agents/skills/coding/references/08_example.md\n")
    errors = CHECK_REPOSITORY(tmp_path)
    assert len([error for error in errors if error.startswith("GOV005")]) == 2


def test_checker_rejects_internal_runtime_terms_in_managed_block(tmp_path: Path) -> None:
    _minimal_repository(tmp_path)
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8").replace(MANAGED_END, "Runtime Mode 使用研发治理 MCP，并输出路由映射与加载明细。\n" + MANAGED_END)
    _write(tmp_path / "AGENTS.md", agents)
    errors = CHECK_REPOSITORY(tmp_path)
    assert len([error for error in errors if error.startswith("GOV009")]) >= 4


def test_checker_rejects_local_installed_skill_as_project_docs_governance_source(tmp_path: Path) -> None:
    _minimal_repository(tmp_path)
    _write(tmp_path / "docs/AGENTS.md", "先遵守根 `AGENTS.md` 与 `.agents/skills/coding/` 的 Coding Skill。\n")
    errors = CHECK_REPOSITORY(tmp_path)
    assert len([error for error in errors if error.startswith("GOV010")]) == 2


def test_checker_rejects_generic_governance_implementation_in_project_overlay(tmp_path: Path) -> None:
    _minimal_repository(tmp_path)
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8") + "\nSource Mode 从 Project Payload 读取 canonical Reference。\n"
    _write(tmp_path / "AGENTS.md", agents)
    errors = CHECK_REPOSITORY(tmp_path)
    assert len([error for error in errors if error.startswith("GOV011")]) == 3


def test_checker_requires_unique_governance_markers(tmp_path: Path) -> None:
    _minimal_repository(tmp_path)
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    _write(tmp_path / "AGENTS.md", agents + "\n<!-- agent-skills:managed:start -->\n")
    errors = CHECK_REPOSITORY(tmp_path)
    assert any(error.startswith("GOV002") for error in errors)


def test_checker_requires_ready_check_and_completion_gate_wiring(tmp_path: Path) -> None:
    _minimal_repository(tmp_path)
    (tmp_path / ".agents/skills/coding/scripts/ready_check.py").unlink()
    (tmp_path / "scripts/quality/check_change_completion.py").unlink()
    _write(tmp_path / ".github/workflows/ci.yml", "permissions:\n  issues: read\npython scripts/quality/check_agent_governance.py\npython scripts/quality/check_pr_requirement_source.py\n")
    errors = CHECK_REPOSITORY(tmp_path)
    assert any(error.startswith("GOV004") for error in errors)
    assert any(error.startswith("GOV007") for error in errors)


def test_checker_rejects_workflow_bypassing_project_change_carrier(tmp_path: Path) -> None:
    _minimal_repository(tmp_path)
    workflow_path = tmp_path / ".github/workflows/ci.yml"
    workflow = workflow_path.read_text(encoding="utf-8").replace("python scripts/quality/check_change_completion.py", "python .agents/skills/coding/scripts/ready_check.py")
    _write(workflow_path, workflow)
    errors = CHECK_REPOSITORY(tmp_path)
    assert any(error.startswith("GOV007") for error in errors)
    assert any(error.startswith("GOV016") and "generic" in error for error in errors)


def test_checker_requires_pr_requirement_source_gate_wiring(tmp_path: Path) -> None:
    _minimal_repository(tmp_path)
    (tmp_path / "scripts/quality/check_pr_requirement_source.py").unlink()
    _write(tmp_path / ".github/workflows/ci.yml", "python scripts/quality/check_agent_governance.py\npython scripts/quality/check_change_completion.py --root . --changed-since base\npython scripts/quality/check_change_completion.py --root . --require-active-ready\n")
    errors = CHECK_REPOSITORY(tmp_path)
    assert len([error for error in errors if error.startswith("GOV015")]) == 4


def test_checker_requires_pr_body_edit_revalidation(tmp_path: Path) -> None:
    _minimal_repository(tmp_path)
    workflow_path = tmp_path / ".github/workflows/ci.yml"
    workflow = workflow_path.read_text(encoding="utf-8").replace("      - edited\n", "")
    _write(workflow_path, workflow)
    errors = CHECK_REPOSITORY(tmp_path)
    assert any(error.startswith("GOV015") and "正文 edited" in error for error in errors)


def test_checker_requires_issue_and_pr_requirement_traceability(tmp_path: Path) -> None:
    _minimal_repository(tmp_path)
    (tmp_path / ".github/ISSUE_TEMPLATE/01-requirement.yml").unlink()
    (tmp_path / ".github/ISSUE_TEMPLATE/03-technical-change.yml").unlink()
    (tmp_path / ".github/ISSUE_TEMPLATE/config.yml").unlink()
    _write(tmp_path / ".github/PULL_REQUEST_TEMPLATE.md", "# PR\n")
    errors = CHECK_REPOSITORY(tmp_path)
    assert len([error for error in errors if error.startswith("GOV012")]) >= 2
    assert any(error.startswith("GOV013") for error in errors)
    assert any(error.startswith("GOV014") for error in errors)
