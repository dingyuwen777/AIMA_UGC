"""检查 AIMA_UGC 项目治理入口与永久 CI 的项目级接线约束。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANAGED_START = "<!-- agent-skills:managed:start -->"
MANAGED_END = "<!-- agent-skills:managed:end -->"
PROJECT_GOVERNANCE_MARKER = "<!-- agent-skills:project-governance:v1 -->"
READY_CHECK = Path(".agents/skills/coding/scripts/ready_check.py")
PROJECT_CHANGE_CHECK = Path("scripts/quality/check_change_completion.py")
PR_REQUIREMENT_SOURCE_CHECK = Path("scripts/quality/check_pr_requirement_source.py")
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
ISSUE_TEMPLATE_DIR = Path(".github/ISSUE_TEMPLATE")
REQUIREMENT_ISSUE_FORM = ISSUE_TEMPLATE_DIR / "01-requirement.yml"
BUG_ISSUE_FORM = ISSUE_TEMPLATE_DIR / "02-bug.yml"
TECHNICAL_CHANGE_ISSUE_FORM = ISSUE_TEMPLATE_DIR / "03-technical-change.yml"
ISSUE_TEMPLATE_CONFIG = ISSUE_TEMPLATE_DIR / "config.yml"
PR_TEMPLATE = Path(".github/PULL_REQUEST_TEMPLATE.md")
REQUIREMENT_FORM_FIELDS = (
    "id: objective",
    "id: scope",
    "id: non_goals",
    "id: acceptance_criteria",
    "id: invariants",
    "id: upstream_sources",
    "id: validation_requirements",
)
BUG_FORM_FIELDS = (
    "id: actual_behavior",
    "id: expected_behavior",
    "id: impact_scope",
    "id: reproduction_steps",
    "id: evidence",
    "id: regression_scope",
    "id: acceptance_criteria",
    "id: upstream_sources",
    "id: validation_requirements",
)
TECHNICAL_CHANGE_FORM_FIELDS = (
    "id: motivation",
    "id: current_state",
    "id: target_state",
    "id: scope",
    "id: non_goals",
    "id: compatibility_migration",
    "id: risks_rollback",
    "id: acceptance_criteria",
    "id: validation_requirements",
    "id: upstream_sources",
)
ISSUE_FORM_PROFILES = {
    "01-requirement.yml": ("需求", "[需求] "),
    "02-bug.yml": ("缺陷", "[缺陷] "),
    "03-technical-change.yml": ("技术变更", "[技术变更] "),
}


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


def _issue_field_block(text: str, field_id: str) -> str | None:
    """提取 Issue Form 字段块，避免其他字段文字误满足公共 Profile。"""
    marker = f"id: {field_id}"
    if marker not in text:
        return None
    tail = text.split(marker, 1)[1]
    next_field = tail.find("\n  - type:")
    return tail if next_field < 0 else tail[:next_field]


def _check_issue_form(path: Path, required_fields: tuple[str, ...]) -> list[str]:
    """检查项目 Issue Form 的专项字段与统一公共 Profile。"""
    if not path.is_file():
        return [f"GOV012 {path.as_posix()}: 多人协作所需 Issue Form 不存在"]

    text = _read_text(path)
    errors: list[str] = []
    for field in required_fields:
        if field not in text:
            errors.append(f"GOV012 {path.as_posix()}: 缺少必需需求字段 {field}")
    if text.count("required: true") < len(required_fields):
        errors.append(f"GOV012 {path.as_posix()}: 必需需求字段未保持 required 约束")

    profile = ISSUE_FORM_PROFILES.get(path.name)
    if profile is not None:
        chooser_name, title_prefix = profile
        first_lines = text.splitlines()[:4]
        if f"name: {chooser_name}" not in first_lines:
            errors.append(f"GOV017 {path.as_posix()}: chooser 名称必须精确为 {chooser_name}")
        if f'title: "{title_prefix}"' not in first_lines:
            errors.append(f"GOV017 {path.as_posix()}: title prefix 必须精确为 {title_prefix!r}")

    acceptance = _issue_field_block(text, "acceptance_criteria")
    if acceptance is not None and (
        "label: 验收标准" not in acceptance or "- [ ] AC1：" not in acceptance
    ):
        errors.append(
            f"GOV017 {path.as_posix()}: acceptance_criteria 必须使用统一验收标准与 AC1 task list"
        )

    validation = _issue_field_block(text, "validation_requirements")
    if validation is not None and "label: 验证要求" not in validation:
        errors.append(f"GOV017 {path.as_posix()}: validation_requirements 必须使用统一验证要求语义")
    return errors


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
                    f"GOV010 {PROJECT_DOC_RULES.as_posix()}: "
                    f"项目文档规则不得把本地通用治理安装资产当规则入口 {fragment}"
                )

    ready_check = root / READY_CHECK
    if not ready_check.is_file():
        errors.append(f"GOV004 {READY_CHECK.as_posix()}: 项目适配所需 installed validator 不存在")

    project_change_check = root / PROJECT_CHANGE_CHECK
    if not project_change_check.is_file():
        errors.append(f"GOV007 {PROJECT_CHANGE_CHECK.as_posix()}: AIMA 顶层 Change 门禁入口不存在")

    pr_requirement_source_check = root / PR_REQUIREMENT_SOURCE_CHECK
    if not pr_requirement_source_check.is_file():
        errors.append(
            f"GOV015 {PR_REQUIREMENT_SOURCE_CHECK.as_posix()}: PR Requirement Source 机器门禁不存在"
        )

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
        project_check_command = f"python {PROJECT_CHANGE_CHECK.as_posix()}"
        if project_check_command not in gate_text:
            errors.append(f"GOV007 {COMPLETION_GATE.as_posix()}: 必须执行 AIMA 顶层 Change 门禁")
        if f"python {READY_CHECK.as_posix()}" in gate_text:
            errors.append(
                f"GOV016 {COMPLETION_GATE.as_posix()}: "
                "Workflow 不得绕过项目 carrier 直接调用 generic ready-check"
            )
        if "--changed-since" not in gate_text or "--require-active-ready" not in gate_text:
            errors.append(
                f"GOV016 {COMPLETION_GATE.as_posix()}: "
                "PR changed-since 与 main active-ready 模式必须同时保留"
            )
        if "check_agent_governance.py" not in gate_text:
            errors.append(f"GOV008 {COMPLETION_GATE.as_posix()}: 必须先执行 AIMA 项目治理接线检查")
        if "check_pr_requirement_source.py" not in gate_text:
            errors.append(
                f"GOV015 {COMPLETION_GATE.as_posix()}: 必须继续执行真实 PR Requirement Source 校验"
            )
        if "issues: read" not in gate_text:
            errors.append(
                f"GOV015 {COMPLETION_GATE.as_posix()}: "
                "PR Requirement Source 校验需要最小 issues: read 权限"
            )
        if "types:" not in gate_text or "- edited" not in gate_text:
            errors.append(
                f"GOV015 {COMPLETION_GATE.as_posix()}: "
                "PR 正文 edited 后必须重新执行 Requirement Source 校验"
            )

    errors.extend(_check_issue_form(root / REQUIREMENT_ISSUE_FORM, REQUIREMENT_FORM_FIELDS))
    errors.extend(_check_issue_form(root / BUG_ISSUE_FORM, BUG_FORM_FIELDS))
    errors.extend(
        _check_issue_form(root / TECHNICAL_CHANGE_ISSUE_FORM, TECHNICAL_CHANGE_FORM_FIELDS)
    )

    issue_config = root / ISSUE_TEMPLATE_CONFIG
    if not issue_config.is_file():
        errors.append(f"GOV013 {ISSUE_TEMPLATE_CONFIG.as_posix()}: Issue chooser 配置不存在")
    elif "blank_issues_enabled: false" not in _read_text(issue_config):
        errors.append(f"GOV013 {ISSUE_TEMPLATE_CONFIG.as_posix()}: 必须关闭 blank issue 普通入口")

    pr_template = root / PR_TEMPLATE
    if not pr_template.is_file():
        errors.append(f"GOV014 {PR_TEMPLATE.as_posix()}: PR 模板不存在")
    else:
        pr_text = _read_text(pr_template)
        if "Requirement-Source:" not in pr_text:
            errors.append(f"GOV014 {PR_TEMPLATE.as_posix()}: 缺少 Requirement-Source 追溯字段")
        if "不要用关闭关键字替代" not in pr_text:
            errors.append(f"GOV014 {PR_TEMPLATE.as_posix()}: 必须区分需求追溯与 Issue 关闭语义")
        if "#123" not in pr_text or "仓库内真实存在" not in pr_text:
            errors.append(
                f"GOV014 {PR_TEMPLATE.as_posix()}: 必须公开机器可验证的 Issue / 仓库路径来源格式"
            )
        post_merge_markers = (
            "需要 post-merge evidence",
            "不得使用 `Closes` / `Fixes` / `Resolves`",
            "Closure Audit",
        )
        if any(marker not in pr_text for marker in post_merge_markers):
            errors.append(
                f"GOV014 {PR_TEMPLATE.as_posix()}: post-merge Evidence / Closure Audit 时序缺失"
            )

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
