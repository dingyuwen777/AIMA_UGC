"""检查 AIMA_UGC 项目治理入口与永久 CI 的项目级接线约束。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANAGED_START = "<!-- agent-skills:managed:start -->"
MANAGED_END = "<!-- agent-skills:managed:end -->"
PROJECT_GOVERNANCE_MARKER = "<!-- agent-skills:project-governance:v1 -->"
READY_CHECK = Path(".agents/skills/coding/scripts/ready_check.py")
WORKFLOW_DIR = Path(".github/workflows")
FORBIDDEN_WORKFLOW_FRAGMENTS = (
    ".agents/skills/coding/tests",
    ".agents/skills/coding/references/",
)
FORBIDDEN_MANAGED_INTERNALS = (
    "Runtime Mode",
    "Source Mode",
    "研发治理 MCP",
    "规则标识",
    "路由映射",
    "加载明细",
    "内部凭据",
)
FORBIDDEN_PROJECT_OVERLAY_GOVERNANCE = (
    "Runtime Mode",
    "Source Mode",
    "研发治理 MCP",
    "Project Payload",
    "Runtime Skill Projection",
    "canonical Reference",
    ".agents/skills/router/",
)
PROJECT_DOC_RULES = Path("docs/AGENTS.md")
FORBIDDEN_PROJECT_DOC_GOVERNANCE = (
    ".agents/skills/coding/",
    "Coding Skill",
    "Runtime Mode",
    "Source Mode",
    "研发治理 MCP",
)
COMPLETION_GATE = Path(".github/workflows/change-completion-gate.yml")


def _read_text(path: Path) -> str:
    """以 UTF-8 读取治理检查需要的文本文件。"""
    return path.read_text(encoding="utf-8")


def _workflow_paths(root: Path) -> tuple[Path, ...]:
    """返回项目永久 Workflow 文件，保持稳定排序便于诊断。"""
    workflow_dir = root / WORKFLOW_DIR
    paths = [*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]
    return tuple(sorted(paths))


def _managed_sections(text: str) -> tuple[str, str] | None:
    """在 marker 唯一时返回 managed block 与 marker 外项目文本。"""
    if text.count(MANAGED_START) != 1 or text.count(MANAGED_END) != 1:
        return None
    start = text.index(MANAGED_START)
    end = text.index(MANAGED_END, start) + len(MANAGED_END)
    managed = text[start:end]
    project_owned = text[:start] + text[end:]
    return managed, project_owned


def check_repository(root: Path = ROOT) -> list[str]:
    """返回 AIMA 项目治理接线错误；空列表表示当前静态约束满足。"""
    errors: list[str] = []
    agents_path = root / "AGENTS.md"
    if not agents_path.is_file():
        errors.append("GOV001 AGENTS.md: 项目统一治理入口不存在")
    else:
        agents = _read_text(agents_path)
        sections = _managed_sections(agents)
        if sections is None:
            errors.append("GOV002 AGENTS.md: Agent_Skills managed marker 必须且只能有一对")
        else:
            managed, project_owned = sections
            for fragment in FORBIDDEN_MANAGED_INTERNALS:
                if fragment in managed:
                    errors.append(
                        f"GOV009 AGENTS.md: managed block 不应展开治理实现细节 {fragment}"
                    )
            for fragment in FORBIDDEN_PROJECT_OVERLAY_GOVERNANCE:
                if fragment in project_owned:
                    errors.append(
                        f"GOV011 AGENTS.md: 项目自有 Overlay 不应保存通用治理实现说明 {fragment}"
                    )
        if agents.count(PROJECT_GOVERNANCE_MARKER) != 1:
            errors.append("GOV003 AGENTS.md: 项目治理校准区 marker 必须且只能存在一次")

    project_docs = root / PROJECT_DOC_RULES
    if project_docs.is_file():
        docs_text = _read_text(project_docs)
        for fragment in FORBIDDEN_PROJECT_DOC_GOVERNANCE:
            if fragment in docs_text:
                errors.append(
                    f"GOV010 {PROJECT_DOC_RULES.as_posix()}: 项目文档规则不得把本地通用治理安装资产当规则入口 {fragment}"
                )

    ready_check = root / READY_CHECK
    if not ready_check.is_file():
        errors.append(f"GOV004 {READY_CHECK.as_posix()}: AIMA Change Ready 机器门禁入口不存在")

    for workflow in _workflow_paths(root):
        text = _read_text(workflow)
        relative = workflow.relative_to(root).as_posix()
        for fragment in FORBIDDEN_WORKFLOW_FRAGMENTS:
            if fragment in text:
                errors.append(
                    f"GOV005 {relative}: 永久 CI 不得依赖 Agent_Skills canonical "
                    f"内部路径 {fragment}"
                )

    completion_gate = root / COMPLETION_GATE
    if not completion_gate.is_file():
        errors.append(f"GOV006 {COMPLETION_GATE.as_posix()}: Change Completion Gate 不存在")
    else:
        gate_text = _read_text(completion_gate)
        if "ready_check.py" not in gate_text:
            errors.append(
                f"GOV007 {COMPLETION_GATE.as_posix()}: 必须继续执行 AIMA Change Ready Check"
            )
        if "check_agent_governance.py" not in gate_text:
            errors.append(f"GOV008 {COMPLETION_GATE.as_posix()}: 必须先执行 AIMA 项目治理接线检查")

    return errors


def main() -> int:
    """执行项目治理静态检查并返回适合 CI 的退出码。"""
    errors = check_repository()
    if errors:
        print("\n".join(errors))
        return 1
    print("AIMA 项目治理入口与 CI 接线检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
