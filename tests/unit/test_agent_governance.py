from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts" / "quality" / "check_agent_governance.py"
CHECKER = runpy.run_path(str(CHECKER_PATH))
CHECK_REPOSITORY = CHECKER["check_repository"]


def _write(path: Path, content: str) -> None:
    """创建测试治理仓库中的 UTF-8 文本文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_repository(root: Path) -> None:
    """建立满足 AIMA 项目治理接线检查的最小仓库夹具。"""
    _write(
        root / "AGENTS.md",
        "\n".join(
            (
                "<!-- agent-skills:managed:start -->",
                "受管区",
                "<!-- agent-skills:managed:end -->",
                "<!-- agent-skills:project-governance:v1 -->",
                "项目区",
            )
        ),
    )
    _write(root / ".agents/skills/coding/scripts/ready_check.py", "# 测试夹具\n")
    _write(
        root / ".github/workflows/change-completion-gate.yml",
        "python scripts/quality/check_agent_governance.py\n"
        "python .agents/skills/coding/scripts/ready_check.py --root .\n",
    )


def test_current_repository_governance_wiring_is_valid() -> None:
    """当前仓库必须只依赖 AIMA 自己可维护的项目治理接线。"""
    assert CHECK_REPOSITORY(ROOT) == []


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
        "python scripts/quality/check_agent_governance.py\n",
    )

    errors = CHECK_REPOSITORY(tmp_path)

    assert any(error.startswith("GOV004") for error in errors)
    assert any(error.startswith("GOV007") for error in errors)
