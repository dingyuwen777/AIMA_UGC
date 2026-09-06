"""一次性同步本 Change 引入的 CI/Test Impact 与 Archive 治理说明。"""

from pathlib import Path

PATH = Path("docs/blueprint/06_开发约束与分阶段实施.md")


def replace_once(text: str, old: str, new: str) -> str:
    """精确替换一个既有事实；缺失时失败关闭，避免静默写错文档。"""
    if old not in text:
        raise SystemExit(f"documentation baseline missing: {old[:120]}")
    return text.replace(old, new, 1)


def main() -> int:
    """把旧的重复 CI/Archive 语义校准为当前风险驱动规则。"""
    text = PATH.read_text(encoding="utf-8")
    if "## 19.1 风险驱动 CI / Test Impact profile" in text:
        print("CI governance documentation already synchronized.")
        return 0

    text = replace_once(
        text,
        "→ implementation main-fresh 与 archive revision governance fresh 分别按各自 revision 取证",
        "→ implementation main-fresh 与 repository-native Change Archive workflow 证据分别取证",
    )
    text = replace_once(
        text,
        "Change Archive 可以在 Implementation PR merge 后立即运行，不需要等待 implementation main-fresh 才开始；两套证据按各自 revision 独立保留，最终 Closure 再同时核验。普通开发者和 Agent 不通过第二个归档 PR、手工移动目录或 direct push main 代替仓库原生归档。没有持久 Change 的轻量任务跳过 archive 步骤，但仍按 Requirement Source、PR、main-fresh 与适用的 Closure 条件完成交付。",
        "Change Archive 可以在 Implementation PR merge 后立即运行，不需要等待 implementation main-fresh 才开始。Archivist 在提交前必须重新读取当前 main、绑定真实 merged PR revision、执行 Change completion gate，并证明 staged diff 恰好只有同一 Change 的 active→archive 两条路径；只有这些条件全部成立，机械归档 commit 才使用 `[skip ci]`，避免再次触发与产品实现无关的 CI/Runtime。最终 Closure 同时核验 Implementation merge revision 的 main-fresh 证据、成功的 Change Archive workflow、`archive/done` 状态与 Acceptance/Closure Audit。普通开发者和 Agent 不通过第二个归档 PR、手工移动目录或 direct push main 代替仓库原生归档。没有持久 Change 的轻量任务跳过 archive 步骤，但仍按 Requirement Source、PR、main-fresh 与适用的 Closure 条件完成交付。",
    )
    text = replace_once(
        text,
        "`archive/done` 只表示这次施工交付已经真实进入目标分支并被冻结，不等价于 Requirement / Issue 已最终完成。Issue Closure 仍由上游 Acceptance Criteria、implementation main-fresh、适用的 archive revision governance fresh，以及 Closure Audit 共同决定；GitHub PR、Commit 和 Actions 是 merge SHA / CI Run 等交付事实的 Owner，不把这些动态事实复制回 Change。",
        "`archive/done` 只表示这次施工交付已经真实进入目标分支并被冻结，不等价于 Requirement / Issue 已最终完成。Issue Closure 仍由上游 Acceptance Criteria、implementation main-fresh、成功的 repository-native Change Archive workflow 与 `archive/done` 结果，以及 Closure Audit 共同决定；GitHub PR、Commit 和 Actions 是 merge SHA / CI Run 等交付事实的 Owner，不把这些动态事实复制回 Change。",
    )
    text = replace_once(
        text,
        "Implementation PR merge 后如果携带持久 Change，由 repository-native Change Archive 基础设施负责归档；Agent/开发者不提交第二个 archive PR，也不手工 direct push main。归档可以和 implementation main-fresh 独立运行，但最终 Closure 必须按真实 Requirement 同时核验：Implementation merge revision 的 required main-fresh、对应 `archive/done`、archive revision 的 required governance fresh，以及 Acceptance/Closure Audit。任一必要条件失败都不得关闭 Requirement。",
        "Implementation PR merge 后如果携带持久 Change，由 repository-native Change Archive 基础设施负责归档；Agent/开发者不提交第二个 archive PR，也不手工 direct push main。归档可以和 implementation main-fresh 独立运行；Archivist 在 commit 前完成 completion gate 与 exact diff allowlist 后，机械归档 commit 使用 `[skip ci]`，不再重复触发产品 CI/Runtime。最终 Closure 必须按真实 Requirement 同时核验：Implementation merge revision 的 required main-fresh、成功的 Change Archive workflow、对应 `archive/done`，以及 Acceptance/Closure Audit。任一必要条件失败都不得关闭 Requirement。",
    )

    start = text.find("## 19.1 文档与治理变更的 CI profile")
    end = text.find("\n门禁失败：", start)
    if start < 0 or end < 0:
        raise SystemExit("CI profile section markers are missing")
    section = """## 19.1 风险驱动 CI / Test Impact profile

AIMA 主 `CI` 始终保留稳定的 `Requirement Traceability and Completion Audit` 与 `CI Gate` check 身份；[`scripts/quality/classify_ci_scope.py`](../../scripts/quality/classify_ci_scope.py) 根据 PR/push 的真实 diff 选择本次有独立证明价值的 Evidence。分类只允许明确白名单降级，CI/Workflow/selector 自身、公共基础设施与未知机器路径一律 fail-closed 到 `full`。

```text
docs_only
→ `docs/**`、根 README、模块 README 等明确不改变机器行为的说明文档
→ 只保留 Secret / Docs / Requirement / Change 等仓库治理证据

governance_only
→ `changes/**`、`AGENTS.md`、`.agents/**` 等研发治理事实
→ 保留项目治理接线、Secret / Docs / Requirement / Change 等证据

repository_quality
→ `scripts/quality/**` 与明确归属的治理/文档质量测试
→ 使用锁定 Python 环境执行质量脚本 Ruff 与专属回归，不启动产品 Backend、Frontend、PostgreSQL 或 Full-stack

backend_only / frontend_only / contract / persistence / cross_component
→ 只启用受影响技术栈和独立风险层；Contract 保留 producer/consumer 生成物一致性，跨前后端边界保留真实 Golden Path
→ Persistence 由 `postgres_suites` 选择 platform/database/jobs/collection/content/ingestion 等最小充分 suite；Migration、共享基础设施、无法唯一映射的 persistence 路径升级为全部 PostgreSQL 证据

full
→ CI/Workflow/selector 自身、Migration、依赖/lock、Compose/Docker/build/startup/deploy、共享控制面或未知机器路径
→ 保留 Backend + Frontend + Contract + PostgreSQL + Real Full-stack + startup smoke 的完整证明责任
```

报告字体同样按证据责任准备：只有 Reporting/Word/DOCX 相关 Python 证明需要 `fonts-noto-cjk`；PostgreSQL Integration 不再安装与其证明责任无关的 CJK 字体。

不能按扩展名判断“文档”。例如 [`backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md`](../../backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md) 虽然是 Markdown，但它是运行时消费的 Prompt，会改变 AI 业务行为，因此不能进入 docs-only。模板、Schema、配置或其他机器消费文本同理。

`Full-stack Acceptance` 对已确认不影响产品接线的 docs/governance 路径做 trigger-level 忽略；未知 Markdown 和 Prompt 不在忽略范围。`Runtime Acceptance` 继续保留 `Compose Golden Path` check 身份和 runtime-risk fast path，Draft PR 在 Job 分配前跳过，Ready 后取得新鲜 required evidence。Release dry-run 只由 Release Workflow、Dockerfile、Compose、生产 env 示例及其直接回归测试触发，不因部署说明或 Roadmap 文案变化重新构建候选；PR 新提交会取消同一 PR 的旧 dry-run，手工正式 Release 不自动取消。

带持久 Change 的 Implementation PR merge 后，repository-native Change Archive 在当前 main 上重新绑定 merged PR、执行 completion gate 并验证 exact two-path allowlist；通过后机械 archive commit 使用 `[skip ci]`，因此不再为同一实现重复启动业务 CI/Runtime。这个例外只属于 Archivist 的确定性归档路径，普通 commit/PR 和未知路径不能获得。

轻量 profile 的含义是“某些产品运行风险在本 diff 中有事实依据地 `not_applicable`”，不是“可以少验证”。一个 diff 同时命中多个已知风险时证明责任单调合并；只要出现 CI-self、共享控制面或未知机器路径，就整体升级到 `full`。
"""
    text = text[:start] + section + text[end:]
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
