"""检查 AIMA_UGC 项目治理入口、generated projection 与永久 CI 接线。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANAGED_START = "<!-- agent-skills:managed:start -->"
MANAGED_END = "<!-- agent-skills:managed:end -->"
PROJECT_GOVERNANCE_MARKER = "<!-- agent-skills:project-governance:v1 -->"
READY_CHECK = Path(".agents/skills/coding/scripts/ready_check.py")
CANONICAL_GOVERNANCE_CONTRACT = Path(".agents/skills/coding/scripts/governance_contract.py")
CANONICAL_ISSUE_FORM_DIR = Path(".agents/skills/coding/assets/issue-templates")
PROJECT_CHANGE_CHECK = Path("scripts/quality/check_change_completion.py")
PR_REQUIREMENT_SOURCE_CHECK = Path("scripts/quality/check_pr_requirement_source.py")
WORKFLOW_DIR = Path(".github/workflows")
ISSUE_TEMPLATE_DIR = Path(".github/ISSUE_TEMPLATE")
PR_TEMPLATE = Path(".github/PULL_REQUEST_TEMPLATE.md")
COMPLETION_OWNER = Path(".github/workflows/ci.yml")
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


def _read_text(path: Path) -> str:
    """以 UTF-8 读取项目治理接线需要的文本文件。"""
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
    return text[start:end], text[:start] + text[end:]


def _check_issue_form_projection(root: Path) -> list[str]:
    """确认 AIMA 根 Issue Forms 是受管 canonical assets 的原字节投影。"""
    source_dir = root / CANONICAL_ISSUE_FORM_DIR
    target_dir = root / ISSUE_TEMPLATE_DIR
    if not source_dir.is_dir():
        return [
            f"GOV018 {CANONICAL_ISSUE_FORM_DIR.as_posix()}: 受管 canonical Issue Form assets 不存在"
        ]

    sources = tuple(sorted(source_dir.glob("*.yml")))
    if not sources:
        return [
            f"GOV018 {CANONICAL_ISSUE_FORM_DIR.as_posix()}: 受管 canonical Issue Form assets 为空"
        ]

    errors: list[str] = []
    source_names = {path.name for path in sources}
    target_names = {
        path.name
        for pattern in ("*.yml", "*.yaml")
        for path in target_dir.glob(pattern)
        if path.is_file()
    }
    for source in sources:
        target = target_dir / source.name
        code = "GOV013" if source.name == "config.yml" else "GOV012"
        if not target.is_file():
            errors.append(
                f"{code} {target.relative_to(root).as_posix()}: 受管 Issue Form 投影不存在"
            )
            continue
        if target.read_bytes() != source.read_bytes():
            errors.append(
                f"{code} {target.relative_to(root).as_posix()}: "
                "Issue Form 投影已漂移，必须由 Agent_Skills canonical asset 生成"
            )

    for extra in sorted(target_names - source_names):
        errors.append(
            f"GOV012 {(ISSUE_TEMPLATE_DIR / extra).as_posix()}: "
            "AIMA 当前未声明额外 Issue Profile；根 Issue Form 必须保持 generated projection"
        )
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

    if not (root / READY_CHECK).is_file():
        errors.append(f"GOV004 {READY_CHECK.as_posix()}: 项目适配所需 installed validator 不存在")
    if not (root / CANONICAL_GOVERNANCE_CONTRACT).is_file():
        errors.append(
            f"GOV018 {CANONICAL_GOVERNANCE_CONTRACT.as_posix()}: "
            "受管 canonical governance validator 不存在"
        )
    if not (root / PROJECT_CHANGE_CHECK).is_file():
        errors.append(f"GOV007 {PROJECT_CHANGE_CHECK.as_posix()}: AIMA 顶层 Change 门禁入口不存在")
    if not (root / PR_REQUIREMENT_SOURCE_CHECK).is_file():
        errors.append(
            f"GOV015 {PR_REQUIREMENT_SOURCE_CHECK.as_posix()}: PR Requirement Source 机器门禁不存在"
        )
    else:
        requirement_checker = _read_text(root / PR_REQUIREMENT_SOURCE_CHECK)
        if (
            '".agents"' not in requirement_checker
            or "governance_contract.py" not in requirement_checker
        ):
            errors.append(
                f"GOV018 {PR_REQUIREMENT_SOURCE_CHECK.as_posix()}: "
                "PR gate 未直接消费受管 canonical governance validator"
            )

    errors.extend(_check_issue_form_projection(root))

    for workflow in _workflow_paths(root):
        text = _read_text(workflow)
        relative = workflow.relative_to(root).as_posix()
        for fragment in FORBIDDEN_WORKFLOW_FRAGMENTS:
            if fragment in text:
                errors.append(
                    f"GOV005 {relative}: 永久 CI 不得依赖 Agent_Skills canonical "
                    f"内部路径 {fragment}"
                )

    completion_owner = root / COMPLETION_OWNER
    if not completion_owner.is_file():
        errors.append(
            f"GOV006 {COMPLETION_OWNER.as_posix()}: Change Completion / Requirement CI Owner 不存在"
        )
    else:
        gate_text = _read_text(completion_owner)
        project_check_commands = (
            f"python {PROJECT_CHANGE_CHECK.as_posix()}",
            f"python3 {PROJECT_CHANGE_CHECK.as_posix()}",
        )
        if not any(command in gate_text for command in project_check_commands):
            errors.append(f"GOV007 {COMPLETION_OWNER.as_posix()}: 必须执行 AIMA 顶层 Change 门禁")
        if f"python {READY_CHECK.as_posix()}" in gate_text:
            errors.append(
                f"GOV016 {COMPLETION_OWNER.as_posix()}: "
                "Workflow 不得绕过项目 carrier 直接调用 generic ready-check"
            )
        if "--changed-since" not in gate_text or "--require-active-ready" not in gate_text:
            errors.append(
                f"GOV016 {COMPLETION_OWNER.as_posix()}: "
                "PR changed-since 与 main active-ready 模式必须同时保留"
            )
        if "check_agent_governance.py" not in gate_text:
            errors.append(f"GOV008 {COMPLETION_OWNER.as_posix()}: 必须先执行 AIMA 项目治理接线检查")
        if "check_pr_requirement_source.py" not in gate_text:
            errors.append(
                f"GOV015 {COMPLETION_OWNER.as_posix()}: 必须继续执行真实 PR Requirement Source 校验"
            )
        if "issues: read" not in gate_text:
            errors.append(
                f"GOV015 {COMPLETION_OWNER.as_posix()}: "
                "PR Requirement Source 校验需要最小 issues: read 权限"
            )
        if "types:" not in gate_text or "- edited" not in gate_text:
            errors.append(
                f"GOV015 {COMPLETION_OWNER.as_posix()}: "
                "PR 正文 edited 后必须重新执行 Requirement Source 校验"
            )

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
    print("AIMA 项目治理入口、generated projection 与 CI 接线检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
