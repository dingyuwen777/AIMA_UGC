from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"target block not found: {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        ".agents/skills/reliable-vibe-coding/SKILL.md",
        "11. 对存在用户界面、跨前后端、数据库、异步任务或外部 Provider 的 L2/L3 工作，按 [testing-strategy.md](references/testing-strategy.md) 建立 Validation Matrix。Browser Mock 用于广覆盖用户可见状态，Backend/DB Integration 验证服务器规则，Contract 保证机器接口一致，Real Full-stack 只用少量关键 Golden Path 证明真实接线，Real Provider Probe 仅在必要时有界执行；任一层都不能声称证明自己没有实际运行的下游边界。\n",
        "11. 对存在用户界面、跨前后端、数据库、异步任务或外部 Provider 的 L2/L3 工作，按 [testing-strategy.md](references/testing-strategy.md) 建立 Validation Matrix。Browser Mock 用于广覆盖用户可见状态，Backend/DB Integration 验证服务器规则，Contract 保证机器接口一致，Real Full-stack 只用少量关键 Golden Path 证明真实接线，Real Provider Probe 仅在必要时有界执行；任一层都不能声称证明自己没有实际运行的下游边界。\n"
        "12. 代码注释不只面向 public/exported 接口。对内部/private/helper 函数，只要包含非显然业务规则、关键不变量、状态转换、算法取舍、兼容原因或重要副作用边界，也应提供简短 docstring 或定点注释，优先解释“为什么/约束是什么”，而不是逐行复述代码；简单自解释 helper 不机械补注释。\n"
        "13. 实现重要功能时，如果仓库已经有日志/事件基础设施，并且该功能涉及关键生命周期、异步任务、外部 I/O、重试/部分失败、状态转换或后期排障价值，应主动设计并补最小充分的结构化日志。复用现有 logger/event/脱敏机制，使用稳定事件名、正确级别和已有 request/job/run/batch 等关联 ID；禁止打印 Secret/Token/密码/敏感 Raw/PII，禁止 INFO 级逐条高频刷屏，也不能用日志替代数据库业务事实或 Health。\n",
    )
    replace_once(
        ".agents/skills/reliable-vibe-coding/SKILL.md",
        "- 预计修改文件；\n- 需要保持兼容的接口、配置和数据；\n",
        "- 预计修改文件；\n"
        "- 需要保持兼容的接口、配置和数据；\n"
        "- 新增或修改的 public 与内部/private/helper 函数中，哪些非显然规则、关键约束或副作用需要 docstring/定点注释；\n"
        "- 如果仓库已有日志能力，本次重要业务阶段、外部 I/O、异步状态和失败边界中哪些需要新增/调整日志，以及哪些高频细节应保持 DEBUG 或不记录；\n",
    )
    replace_once(
        ".agents/skills/reliable-vibe-coding/SKILL.md",
        "- 独立可验证能力：优先提供不依赖完整系统启动的最小验证入口，使用真实生产入口与可控边界；测试粒度由行为边界、风险、依赖和失败模式决定，而不是目录或文件数量。\n- 文档、纯配置、生成文件或无法自动测试的环境：说明 TDD 例外，采用解析、内容检查、构建或人工运行等替代验证。\n",
        "- 独立可验证能力：优先提供不依赖完整系统启动的最小验证入口，使用真实生产入口与可控边界；测试粒度由行为边界、风险、依赖和失败模式决定，而不是目录或文件数量。\n"
        "- 代码可读性：public/exported 接口与非显然内部/private/helper 逻辑都按 `development-workflows.md` 补必要 docstring/注释；注释解释意图、约束和原因，不翻译语法。\n"
        "- 重要功能可观测性：仓库已有日志体系且观测点对调试/运维有价值时，按 `development-workflows.md` 增加最小充分日志；没有现有日志基础设施或没有独立排障价值时，不为满足清单新造日志框架。\n"
        "- 文档、纯配置、生成文件或无法自动测试的环境：说明 TDD 例外，采用解析、内容检查、构建或人工运行等替代验证。\n",
    )

    replace_once(
        ".agents/skills/reliable-vibe-coding/references/development-workflows.md",
        "## 代码注释\n\n注释解释原因、约束、风险和非直观规则，不复述代码。沿用项目语言和风格；公共接口和复杂逻辑添加必要文档注释。\n默认使用中文编写注释。\n\n## 文档同步\n",
        "## 代码注释\n\n注释的目标是降低维护者恢复上下文的成本，不是提高注释覆盖率。默认使用项目既有语言和风格；仓库没有其他约定时使用中文。\n\n以下位置优先提供简短 docstring 或定点 inline comment：\n\n- public/exported 接口需要解释稳定 Contract、重要前置条件、副作用或非显然返回/异常语义时；\n- 内部/private/helper 函数包含非显然业务规则、关键不变量、状态机/状态转换、算法取舍、兼容原因、重试/幂等边界或重要 I/O/事务副作用时；\n- 一段代码之所以“必须这样写”来自外部协议、历史兼容、安全约束、性能测量或容易被未来维护者误删的原因时。\n\n注释优先回答：\n\n```text\n为什么这样做？\n必须保持什么约束？\n失败/状态转换边界是什么？\n为什么不能采用看起来更简单的写法？\n```\n\n不要：\n\n- 给简单 getter/setter、单行 wrapper、名称已经完整表达行为的 helper 机械补 docstring；\n- 逐行翻译 `if`、循环、赋值或调用；\n- 在注释复制会漂移的 Schema、配置默认值或业务事实，应该引用其正式事实源；\n- 用长注释掩盖糟糕命名、过深嵌套或错误函数边界。\n\n## 可观测性与日志\n\n实现功能时先确认仓库是否已经存在正式 logging/event 体系。只有存在可复用基础设施，并且日志对理解运行过程、调试或后期排障有实际价值时，才增加日志；不要为了通用“最佳实践”给没有日志体系的项目新造框架。\n\n优先考虑这些观测点：\n\n- 低频但重要的业务生命周期开始/完成/终止；\n- API/Worker/Scheduler/Job 等异步阶段和关键状态转换；\n- 外部网络、数据库、文件、Provider、模型等 I/O 的安全摘要与结果；\n- Retry、backoff、降级、部分失败、跳过、取消、接管和永久失败；\n- 会显著缩短“问题发生在哪一步”定位时间的关键分支。\n\n日志内容应尽量使用仓库已有稳定 event 名和关联字段，例如 `request_id`、`job_id`、`run_id`、`batch_id`、`content_id`、stage/status/error_code 等真实存在的标识；不要为了日志凭空设计第二套业务 ID。\n\n级别遵循仓库现有约定；没有更具体规则时：\n\n```text\nDEBUG   高频正常细节、轮询、逐批/逐页诊断信息\nINFO    低频重要生命周期与真实业务结果\nWARNING 可恢复异常、Retry、部分失败、需要关注但仍能继续\nERROR   永久失败、非法配置、需要人工介入或未预期异常\n```\n\n控制噪声和重复：\n\n- 不在 INFO 为每条记录、每次循环或每个正常轮询刷屏；批量处理优先记录批次/阶段摘要，必要的逐条细节放 DEBUG；\n- 同一异常优先在真正拥有处理/终止责任的边界记录一次，避免 Router/Service/Repository 每层重复打印相同 traceback；\n- 日志是解释执行过程的辅助证据，不替代 PostgreSQL/业务父事实、Artifact、Health、指标或审计表。\n\n安全边界：\n\n- 复用仓库现有 logger、结构化 event、Formatter、脱敏和轮转；不创建第二套 FileHandler/日志目录；\n- 禁止记录 Secret、Token、密码、Cookie、Authorization、完整连接串、未脱敏 PII、原始敏感 Payload/Raw；\n- 错误上下文只记录定位所需的最小安全字段；已有脱敏机制也不能成为主动打印 Secret 的理由。\n\n如果一个重要功能故障时现有日志无法回答“执行到了哪一步、使用了哪个已有业务标识、为什么失败/重试/跳过”，应把缺失观测点作为实现质量问题修正；反之，如果数据库状态、已有事件或现有日志已经足够，就不要重复增加消息。\n\n## 文档同步\n",
    )

    replace_once(
        ".agents/skills/reliable-vibe-coding/references/verification-review.md",
        "- 命名、注释和维护成本；\n- 无关改动、重复实现和失效内容；\n",
        "- 命名、注释和维护成本；\n"
        "- public/exported 接口以及非显然内部/private/helper 逻辑是否有足以解释意图、约束、状态转换或副作用边界的注释；是否存在逐行翻译代码的冗余注释；\n"
        "- 仓库已有日志体系且本次功能重要/难排障时，关键生命周期、异步阶段、外部 I/O、Retry/部分失败/终态是否具备最小充分可观测性；反之是否存在 INFO 高频刷屏、重复异常日志或无排障价值消息；\n"
        "- 新增日志是否复用现有 logger/event/级别/关联 ID 与脱敏机制，且没有 Secret/Token/密码/敏感 Raw/PII 泄露，也没有用日志替代持久业务事实；\n"
        "- 无关改动、重复实现和失效内容；\n",
    )

    replace_once(
        "docs/blueprint/05-日志安全部署与运维.md",
        "不要用 INFO 日志证明进程存活；健康由 Health 和实际 Job/Run 事实判断。\n\n---\n\n# 6. 日志轮转\n",
        "不要用 INFO 日志证明进程存活；健康由 Health 和实际 Job/Run 事实判断。\n\n## 5.1 功能开发时怎样选择日志观测点\n\n仓库已经具备正式应用日志体系，因此实现重要功能时不能只考虑返回值和数据库结果，也要判断后期排障是否需要补充**最小充分**的运行过程日志。\n\n优先记录：低频重要生命周期、Job/Run/Batch 等关键状态变化、外部 I/O 的安全结果摘要、Retry/部分失败/跳过/取消/永久失败，以及能显著帮助定位“执行到哪一步”的关键分支。优先复用已有 `request_id/job_id/run_id/batch_id/content_id` 等真实关联 ID 和稳定 event，不为日志新造业务身份。\n\n同时控制日志噪声：逐条记录、正常轮询、循环内部高频成功细节使用 DEBUG 或不记录；INFO 保留给真正重要且低频的生命周期/业务结果。同一异常原则上在拥有处理或终止责任的边界记录一次，避免多层重复 traceback。\n\n新增日志必须继续经过现有 Formatter/脱敏/轮转边界，禁止主动记录 Secret、Token、密码、Authorization、敏感 Raw/Payload 或未脱敏 PII。日志只辅助解释“为什么/在哪一步”，不能替代 PostgreSQL 业务事实、Artifact、Health 或正式审计表。\n\n---\n\n# 6. 日志轮转\n",
    )

    replace_once(
        "docs/blueprint/06-开发约束与分阶段实施.md",
        "不能先把代码改好，再写一个永远不会失败的“装饰测试”。\n\n---\n\n# 10. 哪些任务不强行 TDD\n",
        "不能先把代码改好，再写一个永远不会失败的“装饰测试”。\n\n## 9.1 代码注释与关键日志也属于实现质量\n\n开发时不要只给正式对外函数写注释。对内部/private/helper 函数，如果它承载非显然业务规则、关键不变量、状态转换、兼容原因、算法取舍或重要 I/O/事务副作用，应提供简短 docstring 或定点注释，解释“为什么/必须保持什么”，而不是逐行复述代码。简单自解释 helper 不要求机械注释。\n\n如果目标功能重要、后期故障定位依赖运行过程，并且仓库已经有正式日志基础设施，应在实现时同步评估关键观测点。复用既有 logger/event、日志级别、关联 ID、Formatter 与脱敏机制；重点覆盖低频生命周期、异步阶段、外部 I/O、Retry/部分失败/终态。不要在 INFO 逐条刷屏，不记录 Secret/敏感 Raw/PII，也不要用日志替代数据库业务事实。\n\n这两项在完成前的代码质量 Review 中都要复核；不是要求每个函数都有注释、每个步骤都有日志。\n\n---\n\n# 10. 哪些任务不强行 TDD\n",
    )

    test_path = ROOT / ".agents/skills/reliable-vibe-coding/tests/test_development_guidance.py"
    test_path.write_text(
        '''from __future__ import annotations\n\nimport unittest\nfrom pathlib import Path\n\n\nROOT = Path(__file__).resolve().parents[4]\n\n\nclass DevelopmentGuidanceTest(unittest.TestCase):\n    def _read(self, path: str) -> str:\n        return (ROOT / path).read_text(encoding="utf-8")\n\n    def test_skill_exposes_internal_comment_and_observability_rules(self) -> None:\n        skill = self._read(".agents/skills/reliable-vibe-coding/SKILL.md")\n        self.assertIn("内部/private/helper 函数", skill)\n        self.assertIn("重要功能可观测性", skill)\n        self.assertIn("禁止打印 Secret/Token/密码", skill)\n\n    def test_development_workflow_contains_actionable_guidance(self) -> None:\n        workflow = self._read(\n            ".agents/skills/reliable-vibe-coding/references/development-workflows.md"\n        )\n        self.assertIn("## 代码注释", workflow)\n        self.assertIn("内部/private/helper 函数包含非显然业务规则", workflow)\n        self.assertIn("## 可观测性与日志", workflow)\n        self.assertIn("同一异常优先在真正拥有处理/终止责任的边界记录一次", workflow)\n\n    def test_review_and_aima_blueprints_consume_the_rules(self) -> None:\n        review = self._read(\n            ".agents/skills/reliable-vibe-coding/references/verification-review.md"\n        )\n        blueprint05 = self._read("docs/blueprint/05-日志安全部署与运维.md")\n        blueprint06 = self._read("docs/blueprint/06-开发约束与分阶段实施.md")\n        self.assertIn("非显然内部/private/helper", review)\n        self.assertIn("最小充分可观测性", review)\n        self.assertIn("功能开发时怎样选择日志观测点", blueprint05)\n        self.assertIn("代码注释与关键日志也属于实现质量", blueprint06)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''',
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
