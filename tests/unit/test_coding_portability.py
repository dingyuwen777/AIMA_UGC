import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / ".agents" / "skills" / "coding"
NUMBERED_REFERENCE_FILES = (
    "01_项目发现与可失效缓存.md",
    "02_跨项目研发任务路由.md",
    "03_编程语言与工具链适配规则.md",
    "04_轻量变更管理.md",
    "05_设计实施与根因调试.md",
    "06_仓库边界数据交换与条件式约束.md",
    "07_通用验证与证据策略.md",
    "08_分层测试与验收策略.md",
    "09_多人和多智能体并行协作.md",
    "10_完成定义追溯门禁.md",
    "11_两阶段复核与完成前验证.md",
    "12_规则保留映射.md",
)


def _read(relative_path: str) -> str:
    return (SKILL_ROOT / relative_path).read_text(encoding="utf-8")


def _read_repo(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_reference_documents_follow_development_reading_order() -> None:
    reference_names = tuple(sorted(path.name for path in (SKILL_ROOT / "references").glob("*.md")))

    assert reference_names == NUMBERED_REFERENCE_FILES


def test_skill_routes_by_project_stage_stack_and_risk() -> None:
    skill = _read("SKILL.md")

    assert "项目形态" in skill
    assert "研发阶段" in skill
    assert "编程语言 / 工具链" in skill
    assert "风险等级" in skill
    assert "02_跨项目研发任务路由.md" in skill
    assert "03_编程语言与工具链适配规则.md" in skill
    assert "07_通用验证与证据策略.md" in skill


def test_agent_default_prompt_enforces_four_dimensional_routing() -> None:
    agent = _read("agents/openai.yaml")

    assert "project shape" in agent
    assert "development stage" in agent
    assert "language/toolchain" in agent
    assert "L1-L3 risk" in agent
    assert "read every triggered reference" in agent
    assert "fresh-evidence gate" in agent


def test_reorganization_preserves_executable_detail_instead_of_over_summarizing() -> None:
    skill = _read("SKILL.md")
    preservation = _read("references/12_规则保留映射.md")
    agent = _read("agents/openai.yaml")

    assert "内容守恒优先于篇幅精简" in skill
    assert "不能用一条抽象原则替代多条带条件、例外或失败处理的可执行规则" in preservation
    assert "无法证明完全等价时，保留原细节" in preservation
    assert "preserve all existing valuable details" in agent


def test_logging_fallback_severity_semantics_remain_normative() -> None:
    workflows = _read("references/05_设计实施与根因调试.md")

    assert "没有更具体规则且现有日志级别支持这些语义时，使用以下默认严重性" in workflows
    for marker in (
        "DEBUG   高频正常细节、轮询、逐批/逐页诊断信息",
        "INFO    低频重要生命周期与真实业务结果",
        "WARNING 可恢复异常、Retry、部分失败、需要关注但仍能继续",
        "ERROR   永久失败、非法配置、需要人工介入或未预期异常",
    ):
        assert marker in workflows


def test_language_profiles_cover_major_ecosystems_without_fixed_versions() -> None:
    profiles = _read("references/03_编程语言与工具链适配规则.md")

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
    namespace = runpy.run_path(str(SKILL_ROOT / "scripts" / "coding.py"))
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
    strategy = _read("references/07_通用验证与证据策略.md")

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

    assert "08_分层测试与验收策略.md" in strategy
    assert "Browser Mock Acceptance" in strategy
    assert "Backend/API/PostgreSQL Integration" in strategy
    assert "Real Provider Probe" in strategy


def test_existing_web_database_provider_profile_remains_available() -> None:
    strategy = _read("references/08_分层测试与验收策略.md")

    assert "Browser Mock Acceptance" in strategy
    assert "Backend / API / PostgreSQL Integration" in strategy
    assert "Real Full-stack Golden Path" in strategy
    assert "Real Provider Probe" in strategy
    assert "为了测试方便关闭真实 PostgreSQL 约束" in strategy
    assert "不进普通 CI" in strategy


def test_preservation_map_keeps_critical_existing_rules_reachable() -> None:
    preservation = _read("references/12_规则保留映射.md")

    for marker in (
        "01_项目发现与可失效缓存.md",
        "04_轻量变更管理.md",
        "10_完成定义追溯门禁.md",
        "05_设计实施与根因调试.md",
        "06_仓库边界数据交换与条件式约束.md",
        "08_分层测试与验收策略.md",
        "09_多人和多智能体并行协作.md",
        "11_两阶段复核与完成前验证.md",
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


def test_portable_skill_does_not_hardcode_project_document_count_or_names() -> None:
    skill = _read("SKILL.md")
    preservation = _read("references/12_规则保留映射.md")
    docs_agents = _read_repo("docs/AGENTS.md")
    blueprint_readme = _read_repo("docs/blueprint/README.md")
    portable_corpus = "\n".join((skill, preservation))

    assert "Blueprint 01—08" not in portable_corpus
    assert "固定保持当前 01—08" not in portable_corpus
    assert "不预设固定文档数量" in docs_agents
    assert "不预设固定文件名" in docs_agents
    assert "固定保持当前 01—08" not in docs_agents
    assert "当前核心 Blueprint 固定为 `01—08`" not in blueprint_readme
    assert "对应核心 Blueprint 01—08" not in blueprint_readme
    assert "不设置固定数量" in blueprint_readme
    assert "不设置固定编号上限" in blueprint_readme


def test_legacy_hard_gates_remain_in_normative_runtime_rules() -> None:
    skill = _read("SKILL.md")
    workflows = _read("references/05_设计实施与根因调试.md")
    change_management = _read("references/04_轻量变更管理.md")
    completion = _read("references/10_完成定义追溯门禁.md")
    review = _read("references/11_两阶段复核与完成前验证.md")
    collaboration = _read("references/09_多人和多智能体并行协作.md")
    corpus = "\n".join((skill, workflows, change_management, completion, review, collaboration))

    for marker in (
        ".agents/project-context.json",
        "cache_hit",
        "coding.py status --root <repo> --json",
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


def test_aima_document_governance_remains_overlay_while_language_rules_are_global() -> None:
    agents = _read_repo("AGENTS.md")
    docs_agents = _read_repo("docs/AGENTS.md")
    preservation = _read("references/12_规则保留映射.md")
    workflows = _read("references/05_设计实施与根因调试.md")

    assert "提交信息使用中文" in agents
    assert "除专有名词、标识符、协议、库和标准名外，代码注释使用中文" in agents
    assert "Python 文档字符串遵循 PEP 257" in agents
    assert "AIMA 文档编号细节" in preservation
    assert "两位数字下划线前缀" in preservation
    assert "Git 提交信息统一使用中文" in workflows
    assert "除专有名词、标识符、协议、库和标准名外，代码注释统一使用中文" in workflows

    for marker in (
        "每个 `docs/` 子目录独立编号",
        "两位数字加下划线前缀",
        "`README.md` 永远不加编号",
        "上游依赖关系排序",
        "以目标项目当前实际文档集合和项目规则为准",
        "不预设固定文档数量",
        "不预设固定文件名",
        "不得为了插入新主题静默重排已有稳定编号",
        "同一任务同步当前正式文档、README、根/嵌套 `AGENTS.md`、代码和配置中的有效路径引用",
        "历史状态、证据和结论不得因当前文档改名而改写",
        (
            "`Requirement Source` 等被 Ready Check 作为实时仓库路径校验的字段"
            "必须随目标文件移动同步到新路径"
        ),
        "`docs/assets/` 等非 Markdown 资源不适用本规则",
        "模块级 `README.md` 继续保持 README 命名",
        "文件名规范只负责导航和排序",
    ):
        assert marker in docs_agents


def test_change_template_uses_portable_validation_dimensions() -> None:
    template = _read("assets/CHANGE.template.md")

    assert "行为 / Unit / Component" in template
    assert "接口 / Contract" in template
    assert "Build / Package / Runtime" in template
    assert "External Dependency / Provider Probe" in template
    assert "07_通用验证与证据策略.md" in template


def test_portable_core_keeps_specialized_references_in_numbered_order() -> None:
    required_files = {
        "references/01_项目发现与可失效缓存.md",
        "references/04_轻量变更管理.md",
        "references/10_完成定义追溯门禁.md",
        "references/05_设计实施与根因调试.md",
        "references/06_仓库边界数据交换与条件式约束.md",
        "references/08_分层测试与验收策略.md",
        "references/09_多人和多智能体并行协作.md",
        "references/11_两阶段复核与完成前验证.md",
    }

    for relative_path in required_files:
        assert (SKILL_ROOT / relative_path).is_file(), relative_path
