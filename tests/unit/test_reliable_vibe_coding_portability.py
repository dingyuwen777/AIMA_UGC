import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / ".agents" / "skills" / "reliable-vibe-coding"


def _read(relative_path: str) -> str:
    return (SKILL_ROOT / relative_path).read_text(encoding="utf-8")


def _read_repo(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_skill_routes_by_project_stage_stack_and_risk() -> None:
    skill = _read("SKILL.md")

    assert "项目形态" in skill
    assert "研发阶段" in skill
    assert "编程语言 / 工具链" in skill
    assert "风险等级" in skill
    assert "task-routing.md" in skill
    assert "language-and-toolchain-profiles.md" in skill
    assert "validation-strategy.md" in skill


def test_agent_default_prompt_enforces_four_dimensional_routing() -> None:
    agent = _read("agents/openai.yaml")

    assert "project shape" in agent
    assert "development stage" in agent
    assert "language/toolchain" in agent
    assert "L1-L3 risk" in agent
    assert "read every triggered reference" in agent
    assert "fresh-evidence gate" in agent


def test_language_profiles_cover_major_ecosystems_without_fixed_versions() -> None:
    profiles = _read("references/language-and-toolchain-profiles.md")

    for marker in (
        "Python",
        "JavaScript / TypeScript",
        "Go",
        "Rust",
        "Java / Kotlin",
        ".NET",
        "C / C++",
        "Swift",
        "Dart / Flutter",
        "PHP",
        "Ruby",
        "Elixir",
        "Monorepo",
        "Container / IaC",
    ):
        assert marker in profiles

    assert "先读取" in profiles
    assert "锁文件" in profiles
    assert "不得擅自升级" in profiles
    assert "仓库实际命令" in profiles


def test_project_discovery_recognizes_representative_polyglot_manifests() -> None:
    namespace = runpy.run_path(str(SKILL_ROOT / "scripts" / "rvc.py"))
    classify_path = namespace["_classify_path"]

    manifest_paths = (
        "CMakeLists.txt",
        "CMakePresets.json",
        "meson.build",
        "conanfile.py",
        "vcpkg.json",
        "global.json",
        "Directory.Build.props",
        "src/App.csproj",
        "src/App.fsproj",
        "App.sln",
        "Package.swift",
        "Package.resolved",
        "pubspec.yaml",
        "pubspec.lock",
        "melos.yaml",
    )

    for relative_path in manifest_paths:
        assert classify_path(relative_path) == "manifest", relative_path


def test_generic_validation_strategy_is_not_bound_to_one_stack() -> None:
    strategy = _read("references/validation-strategy.md")

    for marker in (
        "行为 / Unit / Component",
        "接口 / Contract",
        "集成 / Persistence / Runtime Dependency",
        "用户 / Workflow Acceptance",
        "跨组件 Golden Path",
        "外部依赖 Probe",
        "Build / Package / Runtime",
        "Docs / Governance / Other",
    ):
        assert marker in strategy

    assert "testing-strategy.md" in strategy
    assert "Browser Mock Acceptance" in strategy
    assert "Backend/API/PostgreSQL Integration" in strategy
    assert "Real Provider Probe" in strategy


def test_existing_web_database_provider_profile_remains_available() -> None:
    strategy = _read("references/testing-strategy.md")

    assert "Browser Mock Acceptance" in strategy
    assert "Backend / API / PostgreSQL Integration" in strategy
    assert "Real Full-stack Golden Path" in strategy
    assert "Real Provider Probe" in strategy
    assert "为了测试方便关闭真实 PostgreSQL 约束" in strategy
    assert "不进普通 CI" in strategy


def test_preservation_map_keeps_critical_existing_rules_reachable() -> None:
    preservation = _read("references/rule-preservation-map.md")

    for marker in (
        "project-discovery.md",
        "change-management.md",
        "completion-gate.md",
        "development-workflows.md",
        "repository-constraints.md",
        "testing-strategy.md",
        "collaboration.md",
        "verification-review.md",
        "Requirement Traceability",
        "Completion Audit",
        "Red → Green → Refactor",
        "连续三次",
        "用户未提交修改",
        "新鲜证据",
        "文档同步",
        "可观测性",
        "两位数字下划线前缀",
    ):
        assert marker in preservation


def test_legacy_hard_gates_remain_in_normative_runtime_rules() -> None:
    skill = _read("SKILL.md")
    workflows = _read("references/development-workflows.md")
    change_management = _read("references/change-management.md")
    completion = _read("references/completion-gate.md")
    review = _read("references/verification-review.md")
    collaboration = _read("references/collaboration.md")
    corpus = "\n".join(
        (skill, workflows, change_management, completion, review, collaboration)
    )

    for marker in (
        ".reliable-vibe-coding/project-context.json",
        "cache_hit",
        "rvc.py status --root <repo> --json",
        "Requirement Traceability",
        "explicitly_deferred",
        "not_satisfied",
        "Completion Audit",
        "ready_check.py --root . --require-active-ready",
        "Verify Red",
        "连续三次",
        "git reset --hard",
        "git clean -fd",
        "强制推送",
        "Secret",
        "Requirement Completeness Review",
        "用户未提交修改",
        "新鲜证据",
    ):
        assert marker in corpus


def test_aima_specific_rules_remain_project_overlay_instead_of_becoming_global() -> None:
    agents = _read_repo("AGENTS.md")
    blueprint = _read_repo("docs/blueprint/06_开发约束与分阶段实施.md")
    preservation = _read("references/rule-preservation-map.md")
    workflows = _read("references/development-workflows.md")

    assert "提交信息使用中文" in agents
    assert "docs/blueprint/01—08" in blueprint
    assert "AIMA 文档编号细节" in preservation
    assert "两位数字下划线前缀" in preservation
    assert "通用 Skill 本身不把中文强加给其他仓库" in workflows


def test_change_template_uses_portable_validation_dimensions() -> None:
    template = _read("assets/CHANGE.template.md")

    assert "行为 / Unit / Component" in template
    assert "接口 / Contract" in template
    assert "Build / Package / Runtime" in template
    assert "External Dependency / Provider Probe" in template
    assert "validation-strategy.md" in template


def test_portable_core_does_not_delete_specialized_references() -> None:
    required_files = {
        "references/project-discovery.md",
        "references/change-management.md",
        "references/completion-gate.md",
        "references/development-workflows.md",
        "references/repository-constraints.md",
        "references/testing-strategy.md",
        "references/collaboration.md",
        "references/verification-review.md",
    }

    for relative_path in required_files:
        assert (SKILL_ROOT / relative_path).is_file(), relative_path
