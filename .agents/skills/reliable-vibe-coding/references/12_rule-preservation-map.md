# Reliable Vibe Coding 规则保留映射

这份文件用于防止 Skill 重组、通用化或后续拆分时发生“为了简洁把规则删掉”的知识损失。

它**不是**主 Skill 的缩写版，也不能作为跳过其他 reference 的理由。执行任务仍按 [SKILL.md](../SKILL.md) 和 [02_task-routing.md](02_task-routing.md) 的触发条件读取对应原文。

本文件的职责是审计：

```text
旧规则 / 旧细节
→ 当前规范位置
→ 是通用核心、条件式专项还是项目本地 Overlay
→ 是否允许删除
```

当前 `references/` 使用两位数字前缀表达研发流程阅读顺序。**编号是导航，不是固定文档配额**：以后新增、拆分或合并 reference 时，按真实依赖关系和阅读顺序调整，不能把“当前有多少份文件”写成所有项目或未来版本的硬约束。

## 1. 保留原则

1. 原规则只允许：
   - 原文保留；
   - 移到更明确的 reference；
   - 在核心入口保留硬门禁、把展开细节放 reference；
   - 对完全等价重复做一次规范化表达。
2. 不允许因为“通用化”删除安全、兼容、测试、根因调试、文档同步、Git 或验证证据约束。
3. 不允许因为“这个项目没有该技术”删除专项知识；应改为**条件式加载**。
4. 不允许把某个项目自己的 PostgreSQL、文档编号、提交语言、框架版本等规则冒充通用规则；这类内容保留在项目本地 `AGENTS.md`/设计文档中。
5. 现有文件被其他 Change、CI、文档作为 Requirement Source 时，除非完成引用迁移，不得改名或删除。
6. 任何后续“精简 Skill”Change 都应重新检查本表和 portability tests。
7. **内容守恒优先于篇幅精简。** 文件更短、层级更少、术语更统一都不能作为删除规则细节的依据；重组只改变组织，不降低原规则的可执行性。
8. **不能用一条抽象原则替代多条带条件、例外或失败处理的可执行规则。** 触发条件、例外、失败行为、验证责任、安全边界、兼容要求、操作顺序和停止条件都属于规则语义，不能在“总结”时丢失。
9. 对被移动、合并、条件化、改名或归入项目 Overlay 的规则，必须能逐项回答“原规则在哪里、现在由什么规范承载、哪些触发/例外/失败/验证语义保持不变”；不能只证明新文件里出现了相似关键词。
10. 只有逐项证明语义完全等价时才允许消除重复。**无法证明完全等价时，保留原细节**；宁可保留少量重复，也不能用推测性的“等价总结”制造知识损失。

## 2. 原主 SKILL：目标与事实观

| 原内容 | 当前规范位置 | 类型 | 保留要求 |
| --- | --- | --- | --- |
| 自然语言请求 → 仓库事实 → 最小实现 → 真实测试 → 新鲜证据闭环 | `SKILL.md` | 通用核心 | 必须保留 |
| 可失效 project context 只作导航，不复制需求正文 | `SKILL.md` + `01_project-discovery.md` | 通用核心 | 必须保留 |
| Git 可见单文件 Change 协议用于重要变更/并行协作 | `SKILL.md` + `04_change-management.md` + `09_collaboration.md` | 通用核心 | 必须保留 |
| 当前仓库文件、运行结果、用户确认是事实；区分事实/推断/建议/未验证 | `SKILL.md` + `01_project-discovery.md` | 通用核心 | 必须保留 |

## 3. 原主 SKILL 的 13 条不变量逐项保留

| # | 原不变量 | 当前承载 |
| --- | --- | --- |
| 1 | 系统、开发者、用户、目标目录 `AGENTS.md`/同等规则优先，Skill 不降低上位约束 | `SKILL.md` + `02_task-routing.md`“规则优先级与项目 Overlay” |
| 2 | 当前文件/运行/用户确认是事实；缓存不是事实副本；不默认用户或 Agent 判断正确 | `SKILL.md` + `01_project-discovery.md` |
| 3 | 只在授权范围写文件/外部动作；分析/Review 不自动授权缓存、Change、分支、提交、PR、部署 | `SKILL.md` + `02_task-routing.md`执行模式 + `11_verification-review.md` |
| 4 | 保留用户未提交修改；禁止覆盖式检出、强推、破坏性清理、未授权重写历史 | `SKILL.md` + `09_collaboration.md` + `11_verification-review.md` |
| 5 | 不擅自升级依赖、改公共接口、改变数据语义、扩大范围、无关重构 | `SKILL.md` + `05_development-workflows.md` + `03_language-and-toolchain-profiles.md` |
| 6 | 没有本轮完整新鲜证据不得宣称完成/修复/通过/可发布 | `SKILL.md` + `11_verification-review.md` + `07_validation-strategy.md` |
| 7 | 从可观察目标、硬约束、根因推导最小充分机制；最佳实践只是候选证据 | `SKILL.md` + `05_development-workflows.md` |
| 8 | 只执行仓库真实存在或需求明确建立的边界/Contract/Schema/Owner/Migration/测试；不存在则有界标不适用，不补造制度 | `SKILL.md` + `06_repository-constraints.md` + `07_validation-strategy.md` |
| 9 | 有独立输入输出/价值/失败边界的能力优先建立独立验证闭环；调试/Probe/示例复用生产实现，不机械一模块一测试文件 | `SKILL.md` + `05_development-workflows.md` + `07_validation-strategy.md` |
| 10 | L2/L3 正式 Change 的当前 Change 不是自身需求全集；必须 Requirement Traceability + Completion Audit；CI 绿色不能替代需求完整性 | `SKILL.md` + `04_change-management.md` + `10_completion-gate.md` |
| 11 | 用户界面/跨前后端/DB/异步/Provider 等边界按验证矩阵分层；任一层不能声称证明未实际运行的下游 | `07_validation-strategy.md` 通用化 + `08_testing-strategy.md` 专项原文完整保留 |
| 12 | public 与非显然 private/helper 都应按需要写解释原因/约束的 docstring/定点注释；简单 helper 不机械补注释 | `SKILL.md` + `05_development-workflows.md` |
| 13 | 重要生命周期/异步/外部 I/O/失败边界在已有日志体系时补最小充分结构化可观测性；稳定事件、关联 ID、脱敏、避免 INFO 刷屏；日志不替代业务事实 | `SKILL.md` + `05_development-workflows.md` |

## 4. 原“按需读取资源”完整映射

原有专项职责全部保留；本次仅把当前规范文件改成按研发流程编号的名称。下表中的“原 reference”是迁移前名称，用于历史追溯；“当前规范位置”才是现在必须使用的路径。

| 原 reference | 当前规范位置 | 原职责 / 当前职责 |
| --- | --- | --- |
| `project-discovery.md` | `01_project-discovery.md` | 首次进入、缓存缺失/过期、仓库事实发现；职责不变 |
| `change-management.md` | `04_change-management.md` | L2/L3、需求追踪、Active Change；Validation Matrix 默认语义指向通用策略 |
| `completion-gate.md` | `10_completion-gate.md` | Requirement Traceability、Completion Audit、Ready；职责不变 |
| `development-workflows.md` | `05_development-workflows.md` | Feature/Bug/Refactor/Debug/TDD/最小实现/注释/日志/依赖/Git/文档；职责不变 |
| `repository-constraints.md` | `06_repository-constraints.md` | 只在仓库实际存在时应用 Owner/Contract/Schema/Migration/边界；继续禁止虚构架构 |
| `testing-strategy.md` | `08_testing-strategy.md` | Browser/API/PostgreSQL/Full-stack/Provider 分层专项细节；仅在这些真实边界存在时加载 |
| `collaboration.md` | `09_collaboration.md` | 多人/多 Agent/多 Change 冲突预检与分工；职责不变 |
| `verification-review.md` | `11_verification-review.md` | Requirement review、代码质量、Ready、证据、交付报告；职责不变 |

本次通用化新增的 reference 也进入同一阅读序列：

| 当前 reference | 职责 |
| --- | --- |
| `02_task-routing.md` | 项目形态 × 研发阶段 × 编程语言/工具链 × 风险等级路由 |
| `03_language-and-toolchain-profiles.md` | 多语言版本/Manifest/锁文件/build/test/package 事实导航 |
| `07_validation-strategy.md` | 技术栈无关风险 → 证据职责矩阵 |
| `12_rule-preservation-map.md` | 本次及未来规则迁移的内容守恒审计 |

当前阅读导航为：

```text
01 项目事实发现
→ 02 任务路由
→ 03 语言 / 工具链
→ 04 Change 管理
→ 05 设计 / 实施 / 根因调试
→ 06 仓库边界
→ 07 通用验证
→ 08 专项测试
→ 09 协作
→ 10 Completion Gate
→ 11 Review / 交付
→ 12 规则保留审计
```

这不是“每个任务把 12 份全读一遍”的要求；仍按 `SKILL.md` / `02_task-routing.md` 的触发条件选择最少但充分的 reference。

## 5. 原统一工作流 1—11 完整映射

### 原步骤 1：建立权限和能力边界

保留内容：

- 区分只读分析、诊断、方案、实现、Review、发布、Git；
- 确认持久文件系统、终端、Python/Git/测试/多 Agent 能力；
- 无持久 FS 不承诺跨会话缓存；
- 无脚本能力用人工流程，不伪造结果；
- 未授权写项目只建会话临时导航。

当前：`SKILL.md` + `02_task-routing.md`“执行模式”。

### 原步骤 2：定位仓库并先读规则

保留内容：

- 定位真实 repo root；
- 读取 root 到目标路径所有适用规则；
- 检查 branch/worktree/未提交修改；
- 非 Git repo 明确记录。

当前：`SKILL.md` + `01_project-discovery.md`。

### 原步骤 3：复用或建立项目导航

原路径仍是：

```text
.reliable-vibe-coding/project-context.json
```

原命令仍是：

```text
python <skill>/scripts/rvc.py discover --root <repo>
```

`cache_hit / created / refreshed / failure fallback`、候选事实源失效检查、缓存不复制正文、cache hit 不代表普通源码没变化等全部由 `01_project-discovery.md` 保留。

新增语言 profile 不改变缓存 schema；不能因缓存没识别某个新生态 manifest 就跳过真实仓库调查。

### 原步骤 4：检查并行状态

原命令仍保留：

```text
python <skill>/scripts/rvc.py status --root <repo> --json
```

原冲突维度：影响路径、模块、Contract、数据、Migration、配置、共享测试资源、依赖关系；无真实交集不发明冲突，也不把预检叫锁。

当前：`04_change-management.md` + `09_collaboration.md`。

### 原步骤 5：L1/L2/L3

等级定义和“行数少不等于 L1”保持在 `SKILL.md`、`04_change-management.md`、`02_task-routing.md`。

通用化后 public CLI flag、Library API/ABI、mobile data format 等也按公共语义风险升级，不只限 HTTP/数据库。

### 原步骤 6：任务契约、Change、Requirement Traceability

保留：

- 目标；
- 可观察成功标准；
- 范围；
- 非目标；
- 必须保持不变；
- 影响区域；
- 验证；
- Git 授权；
- L2/L3 Active Change；
- `new-change` 命令；
- `completion_gate: required`；
- 当前 Change 不能引用自身当上游需求全集；
- Requirement 状态只有 `satisfied / explicitly_deferred / not_applicable / not_satisfied`；
- 未决关键问题一次只问一个最上游问题，仓库能确认的不反问。

当前：`SKILL.md` + `04_change-management.md` + `10_completion-gate.md`。

### 原步骤 7：可验证计划

保留：

- 小而完整的检查点；
- 修改范围 / 预期行为 / 依赖 / 验证命令；
- 只并行互不依赖且不修改相同文件/接口/共享状态的步骤；
- 复用现有实现；
- 预计文件；
- 兼容边界；
- public/private 注释点；
- 日志/可观测性点；
- 最小失败测试或 TDD 例外；
- 独立验证入口；
- Verification/Validation Matrix。

当前：`SKILL.md` + `05_development-workflows.md` + `07_validation-strategy.md`。

### 原步骤 8：按任务类型实施

保留：

- Feature/Bug/Refactor 默认 Red → Green → Refactor；
- Bug/失败先复现与根因，不猜测修补；
- 用户可见行为要有调用者级 Acceptance；
- 后端/DB/运行时规则由真实依赖层证明；
- 公共 Contract 要有机器一致性；
- 跨组件只用少量 Golden Path；
- Provider/外部系统只在事实需要时有界 Probe；
- 独立能力复用生产入口；
- 非显然 helper 注释；
- 已有日志体系时补最小充分观测；
- 文档/配置/生成物说明 TDD 例外；
- 多 Agent 主 Agent 复核；
- 不给不适用项目强加架构分层。

当前：`05_development-workflows.md` + `07_validation-strategy.md`；Web/API/PostgreSQL/Provider 的原始具体规则继续在 `08_testing-strategy.md`。

### 原步骤 9：同步当前事实

保留：

- 语义检查 Blueprint/README/API/Contract/Schema/Migration/架构/配置/测试/运维是否受影响；
- 文档与实现冲突先判断哪一方是正确事实，不机械代码优先；
- 正式文档描述当前系统，Change 记录为什么变；
- 不受影响不制造文档差异；
- 未同步文档不得 Ready/完成。

当前：`SKILL.md` + `06_repository-constraints.md` + `11_verification-review.md`。

#### 原 Skill 中的 AIMA 文档编号细节

原主 Skill 曾包含这些 AIMA 项目本地细节：

```text
docs/ 子目录独立编号
README.md 不编号
两位数字下划线前缀
AIMA Blueprint 文档按项目当前稳定顺序编号
重命名同步实时路径引用
changes/archive 历史不因当前文档改名重写
```

这些规则**没有删除**，但它们属于 AIMA 项目本地 Overlay，不是所有仓库的通用要求。AIMA 当前正式承载由目标路径适用的项目规则和当前文档集合共同决定，例如：

```text
AGENTS.md
docs/AGENTS.md
docs/blueprint/README.md
当前实际 Blueprint / Roadmap / Appendix / Guide 文件集合
```

关键边界是：

- 两位数字下划线前缀是 AIMA 当前文档导航规则；
- **不预设固定文档数量、固定文件名或固定编号上限**；
- 当前稳定编号不能为了插入新主题被静默重排；需要插入/重命名/重新编号时按显式文档迁移处理；
- 通用 Skill 只规定“发现并服从项目本地文档治理、改名同步当前有效引用、历史证据不随意改写”，不把 AIMA 的当前目录数量或具体文档名强加给其他项目。

### 原步骤 10：Completion Audit、两阶段 Review、新鲜验证

完整保留：

```text
重新读取上游正式事实源
→ 不看当前 Change checklist，独立重建完成定义
→ 上游要求 → Change：查 omission
→ Change → 实现/测试/文档
→ 反向能力审计
→ Validation Matrix 证据等级复核
→ 清零 not_satisfied
→ Ready Check
→ Requirement compliance review
→ Code quality review
→ Fresh verification
```

原命令仍为：

```text
python <skill>/scripts/ready_check.py --root <repo> --require-active-ready
```

机器 Ready Check 不能证明自然语言需求完整，也不能自动证明 Validation Matrix 充分。

当前：`10_completion-gate.md` + `11_verification-review.md`。

### 原步骤 11：关闭或保留 Change

保留：

- 未合并/未发布且满足 Ready 条件：`ready_for_review`，继续 active；
- 全部成功标准、验证、文档同步且集成状态确认：`done` 后 archive；
- 需求变化：先回上游 Traceability，再更新同一 active Change；
- 已归档需求后来再变：新 Change，不改历史；
- 不先 archive 再补验证；
- 不删除 `completion_gate` 绕过 Ready Check。

当前：`04_change-management.md` + `10_completion-gate.md`。

## 6. 05_development-workflows.md 细节保留清单

以下不能在未来“精简”时丢失：

### 事实调查

- README/规则/目录/入口/依赖/锁文件/build/test/配置/调用链/数据流/error handling/style/recent relevant changes；
- 只读与任务相关内容，不全仓漫游；
- 能从仓库确认的不反问。

### 需求与设计门禁

- 新行为/架构/实质歧义先解决上游决策；
- 用户负责真正业务取舍；
- Agent 不静默补齐会改变接口、数据、兼容、验收的缺口；
- L3 真实比较 2—3 个方案；
- 方案连续性：无证据不换技术路线/目录/接口/数据结构。

### 第一性原理与计划

- 可观察目标 + 硬约束 + 现有事实；
- 最简单、可逆、可验证的充分方案；
- 不为未来假设造抽象；
- 计划使用 `[步骤] → 修改范围 → 预期结果 → 验证方式`；
- 不使用 TBD/TODO/“适当补测试”式不可执行占位。

### Red → Green → Refactor

- 先写最小失败用例；
- Verify Red 必须因正确原因失败；
- Green 只写最少代码；
- Verify Green 跑目标和相关测试；
- 行为绿色后才 Refactor；
- Refactor 后再验证；
- Bug 必须有回归证据；
- 文档/配置/生成物/无法合理自动测的情况明确例外，不伪造 Red。

### 根因调试

原顺序完整保留：

```text
完整错误与调用栈
→ 稳定复现
→ 近期变更和环境差异
→ 数据流与组件边界
→ 正常参照与差异
→ 一个可证伪根因假设
→ 单变量最小实验
→ 失败用例
→ 单一修复
```

**连续三次**修复假设失败：停止叠加补丁，重新审视架构、前提和观测手段，并报告阻塞。

### 最小、精准、兼容

- 最少代码；
- 标准库/现有依赖优先；
- 不新造未要求 CLI/配置/兼容层/抽象；
- 不顺手重构/格式化/改名；
- 每处 diff 可追溯需求或验证；
- 保持 public API/import/config/default/env/data/file/persistence/startup/error compatibility；
- breaking change 先说明版本/Migration/迁移/回滚/验证。

### 函数与模块组织

- 以高内聚和现有架构为准；
- public/private/helper 有明确职责；
- 复杂规则才抽函数/对象；
- 不机械 Interface/Facade/Factory/Manager/BaseRepository。

### 独立验证能力

- 明确输入输出、独立价值、失败边界或不需全系统即可验证时建立独立闭环；
- production entry 复用；
- Fixture/Fake/隔离依赖；
- 成功判据与失败诊断清楚；
- Probe 费用/Secret/生产写入受控。

### Git / Dependency / Security

- 检查 branch/worktree；
- 保护用户未提交修改；
- 禁止 reset hard、clean fd、force push、重写共享历史；
- 未授权不 commit/push/PR/merge/delete branch；
- dependency 先版本事实和 lock；
- 新依赖说明必要性/维护/许可证/体积/替代；
- Secret 不硬编码/日志/上传；
- 不关闭 auth/cert/input validation/security；
- 避免不安全反序列化、任意命令/动态代码、字符串 SQL；
- 对 path/network/db/command/user input 做匹配风险校验。

### 注释

- 项目既有规范优先；
- public 及承载非显然规则的 private/helper 都可需要 docstring/定点注释；
- 注释解释 why/invariant/risk/compatibility，不翻译语法；
- 简单 helper 不机械注释。

### 可观测性

- 已有 logger/event 基础且功能有排障价值时主动设计；
- lifecycle、async、external I/O、retry/partial failure/state transition；
- stable event、正确 level、关联 ID；
- Secret/Token/password/sensitive Raw/PII 禁止记录；
- 高频成功细节 DEBUG 或不记录；
- 日志不替代 DB business fact/Health/Audit。

### 文档同步

- README/接口/架构/配置/运行/示例/限制与实现一致；
- 不为未实现功能提前写当前事实文档；
- 不受影响不改；
- 已批准长期决定必须落正式事实源，不只留聊天/Change。

## 7. 08_testing-strategy.md 专项细节完整保留

这个文件可能被其他 Change 作为 Requirement Source，因此路径迁移必须同步所有仍被机器当作实时路径校验的 Source；不能留下旧的失效路径，也不能借改名重写历史结论。

当前专项事实源路径：

```text
.agents/skills/reliable-vibe-coding/references/08_testing-strategy.md
```

以下细节继续由该文件维护，不在本次重组中删除：

### Browser Mock Acceptance

- route/menu/button/form/drawer；
- enabled/disabled；
- method/URL/query/payload；
- loading/empty/queued/running/retry/partial success/success/failure/cancel；
- 400/404/409/422/429/500/503 与 request_id；
- polling/refresh/A→B→A/cache invalidation/cross-page/result；
- 不能证明 FastAPI/Pydantic/PostgreSQL/Worker/Provider/real full-stack。

### Backend / API / PostgreSQL Integration

- Service/Repository；
- HTTP status/error contract；
- UNIQUE/FK/CHECK/transaction/lock/idempotency/fencing/Migration；
- Job/Worker state；
- query/pagination/current/history；
- failure/retry/cancel/concurrency/takeover；
- 不能证明 Browser 交互/视觉状态。

### Contract / Generated Client

- Pydantic/Schema → OpenAPI/JSON Schema → Generated Client；
- 防 Mock 与真实接口漂移；
- Contract 绿色不等于行为/DB/Worker/Browser 已运行。

### Real Full-stack Golden Path

- 真实 Browser/Frontend/Generated Client/API/PostgreSQL/Job/Worker 等关键链；
- 少量成功链，必要时代表性失败/恢复链；
- 不用它穷举所有 UI 状态；
- 一条 Golden Path 不能证明所有组合。

### Real Provider Probe

- endpoint/参数、Sanitized Raw shape、pagination/stable ID/capability、费用/限流/错误；
- 默认关闭；
- **不进普通 CI**，除非明确批准专门机制；
- 请求/费用上限；
- 不打印 Secret；
- 不默认写生产库；
- 区分代码、网络、供应商失败；
- Fixture/Fake 不证明 Provider 此刻在线，Probe 不替代稳定回归。

### 原专项 Validation Matrix 与反模式

全部保留：required/not_applicable、有依据、不固定测试配额、Browser/Backend/Contract/Full-stack/Provider 的任务类型默认选择、Completion Audit 证据等级，以及：

- 不把所有状态都做 Full-stack；
- 不用 Browser Mock 冒充 Backend/DB/Worker；
- 不只有 Backend tests 而漏用户行为；
- 不手写第二套 Contract；
- 不为测试方便关闭真实 PostgreSQL 约束；
- 不把付费 Provider 塞普通 CI；
- 不固定 N/M 测试配额；
- 不用任一层绿色替代 Completion Audit。

## 8. 04_change-management.md / 10_completion-gate.md 保留清单

### Change 管理

- L1/L2/L3 触发条件；
- active path 与 archive path；
- metadata、affected paths/areas/contracts/data changes/dependencies；
- 真实交集才算 conflict；
- proposed → approved → in_progress → ready_for_review → done / blocked；
- Active Change 不等于锁；
- merge 后不应长期假 active；
- archive 不作为成功证据。

### Requirement Traceability

- Requirement Source 必须是用户明确决定/正式 Roadmap/Spec/Stage/适用规则；
- Change 不能引用自身；
- `satisfied / explicitly_deferred / not_applicable / not_satisfied`；
- Ready 前 `not_satisfied` 清零；
- deferred/not applicable 有正式依据。

### Completion Audit

- upstream_re_read；
- change_coverage；
- reverse_audit；
- unresolved_cleared；
- 不看当前 checklist 独立重建完成定义；
- CI/Ready Check 不能替代语义完整性；
- Agent 主动发现遗漏，不能依赖用户后续提醒。

## 9. 09_collaboration.md 保留清单

- Change 是 Git 可见协作协议，不是原子锁/lease/online status；
- 看不到未推送/未同步/其他客户端私有状态；
- 冲突按真实路径、模块、Contract、数据、Migration、配置、共享测试、依赖；
- 多 Agent 只派互不依赖、无共享写边界的任务；
- 给子 Agent 最少充分上下文；
- 主 Agent 不直接相信子 Agent 成功报告，必须复核 diff 与证据；
- 分支/Owner/影响范围不能被 Skill 强制，只能由协作和 CI 门禁约束。

## 10. 11_verification-review.md 保留清单

- 先 Requirement Completeness，再当前 Change 符合性，再 Code Quality；
- Completion Audit；
- correctness/boundary/error/security/compatibility/maintainability/unrelated diff；
- public 与 private/helper 注释质量；
- observability 充足且不泄密/刷屏；
- validation evidence 必须说明实际边界；
- generated artifact 验证；
- branch/worktree/diff/CI；
- 所有完成结论要“确定命令 → 实际运行 → 读完整输出/exit/failure count → 对照成功标准 → 只陈述证据支持状态”；
- 历史日志/子 Agent/局部测试/代码阅读不能冒充新鲜证据；
- 交付报告包含变更、逐文件目的、Traceability、Validation、Audit、文档、命令/退出码、未验证/风险、兼容/依赖/Migration/部署/回滚、Git/PR/CI/合并/清理状态。

## 11. 项目本地规则与通用 Skill 的边界

通用化不是把项目规则删掉，而是把归属放正确。

### 应留在通用 Skill

- 仓库事实优先；
- 规则优先级；
- L1/L2/L3；
- Change/Traceability/Audit；
- TDD/根因调试；
- 最小/兼容；
- 依赖/Git/Secret 安全；
- generic validation；
- 文档同步；
- Review/新鲜证据。

### 应由项目 Overlay 决定

- Python/Node/JDK/Go/Rust 的精确版本；
- React/Vue/Spring/FastAPI 等具体框架；
- PostgreSQL/MySQL/SQLite 等数据库；
- npm/pnpm/uv/Maven/Gradle 等包管理/构建；
- commit message 语言；
- docs 编号方式、当前文档数量和具体文件名；
- 模块 Owner 名称；
- CI job 名称；
- release/deploy topology；
- security/auth provider；
- project-specific architecture。

在 AIMA_UGC 中，这些继续由 `AGENTS.md`、`docs/AGENTS.md`、当前 Blueprint/Roadmap/Appendix/Guide 集合、locks、Contract、Migration、tests、CI 等当前事实决定。把 Skill 复制到其他项目时，不应把 AIMA 的具体技术决定或当前文档集合一起当作全球默认。

## 12. 自动化守护

仓库级 portability 回归至少检查：

- `SKILL.md` 明确四维路由；
- `references/` 当前规范文件按研发流程使用两位数字前缀，便于人工阅读；
- 编号只表达阅读顺序，不写死未来 reference 数量；
- 多语言 profile 存在；
- generic Validation Matrix 存在；
- `08_testing-strategy.md` 关键专项内容仍存在；
- 原 8 个专项 reference 的职责都能从当前编号路径到达；
- `CHANGE.template.md` 使用通用 validation 维度；
- 本文件仍能定位 Requirement Traceability、Completion Audit、Red → Green → Refactor、根因调试“连续三次”、用户未提交修改、新鲜证据、文档同步、可观测性等关键规则；
- 通用 Skill 不硬编码任一项目的 Blueprint 数量、固定文件名或固定编号上限；
- `SKILL.md` 和本文件都明确“内容守恒优先于篇幅精简”，并禁止用抽象原则替代带条件/例外/失败处理的可执行规则；
- Agent 默认提示要求 preserve all existing valuable details，而不是只要求读取 reference。

自动检查只能防明显丢文件/关键词/结构漂移，不能证明规则语义完全等价。任何大规模 Skill 重组仍需人工逐节做内容守恒 Review；如果自动检查与人工逐项映射冲突，以更保守的内容保留结果为准。