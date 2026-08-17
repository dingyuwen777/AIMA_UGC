# AIMA_UGC AI / Coding Agent 开发规范

本文件是新爱玛舆情监控系统所有 AI Coding Agent 和人工开发者的统一入口。详细事实由代码、Pydantic Contract、生成 OpenAPI/JSON Schema、Alembic Migration、测试、锁文件和 `docs/blueprint/` 维护。

## 1. 开始前

处理分析、设计、编码、Review、PR、CI 或交付前：

1. 先读本文件；
2. 读取 `.agents/skills/reliable-vibe-coding/SKILL.md` 并按其任务路由执行；该 Skill 不存在或无法读取时明确报告，不能假装已应用；
3. 再读 `docs/blueprint/README.md` 和 `docs/blueprint/07-技术决策与实施门禁.md`；
4. 按任务读取对应 Blueprint、模块 README、Contract、Migration、依赖、实现和测试；
5. 只读取与任务直接相关的内容；
6. 能从仓库确认的事实先自行确认；
7. 文档与机器事实冲突时，以代码、Schema、Migration、锁文件、生成物和测试为准，并同步修正文档；
8. 不从旧系统、历史聊天或单个文件猜测当前实现。

任务开始时按 Skill 判定 L1–L3 任务等级。L2/L3 先写计划并完成要求的评审。仓库存在 `openspec/` 后，涉及新能力、行为变化、数据/接口/架构/安全变更的任务必须先更新对应 OpenSpec change 并通过校验；纯机械文档或格式任务按 Skill 的例外处理。不得自行创建与 OpenSpec 命令产物冲突的目录结构。

## 2. 系统基线

默认方案不得静默改变：

- 模块化单体；
- API、Worker、Scheduler、Migration 分进程；
- PostgreSQL 18；
- Python 3.14；
- FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、psycopg 3；
- uv + `pyproject.toml + uv.lock`；
- Vue 3 + TypeScript + Vite + Pinia；
- OpenAPI 生成前端 Client；
- Provider Adapter（TikHub、官方 API、Apify、自建采集器、文件/历史导入等）→ 不可变 Raw → Mapper → Canonical → Ingestion Service → Owner Repository → PostgreSQL；
- PostgreSQL 持久化 Job；
- Local ArtifactStore 默认实现，可替换 S3；
- 应用 `.log` 文件为主要排障日志，Docker 日志为辅助；
- Docker Compose 离线 Release。

采用方案 A：仓库根目录是唯一 Python/uv 工程根，保存 `pyproject.toml`、`uv.lock`、`.python-version`、`tests/`、`scripts/` 和 `migrations/`；源码在 `backend/src/aima_ugc/`。禁止创建 `backend/pyproject.toml`、`backend/uv.lock`、`backend/tests/` 或用 `uv --project backend` 形成第二套命令。

唯一 `Dockerfile` 与 Docker build context 都在仓库根；使用 target 构建后端/前端镜像，不把 `backend/` 或 `frontend/` 当独立 context。

阶段 1 必须在根 `pyproject.toml` 明确 build backend 和 `backend/src` package discovery，并用锁定环境验证直接 `import aima_ugc` 与 Wheel 安装；未完成 PoC 前不得凭习惯选型，禁止用临时 `PYTHONPATH`、改变工作目录或修改 `sys.path` 掩盖打包配置缺失。

版本政策：初始化时在已批准技术系列内选择核验日的官方 Stable/LTS，或 Registry 最新非预发布且满足兼容约束的版本，并精确锁定；之后以 `.python-version`、Node 版本声明、`uv.lock`、`package-lock.json` 和镜像 digest 为事实。禁止运行时或构建时解析 `latest`，禁止因发现新版本自动升级；任何升级都是独立任务，必须核验官方发布说明、兼容/安全影响并执行完整门禁。

重大改变前必须说明问题证据、新旧方案、影响、迁移、回滚和验证。没有实际问题证据不得主动引入微服务、Redis、Kafka、RabbitMQ、MongoDB、OpenSearch、Kubernetes或多数据库兼容层。

## 3. 编码前

复杂任务至少明确：

```text
背景与现状
目标
范围
非目标
成功标准
输入和输出
模块 Owner
必须保持不变
预计文件
兼容性
数据迁移
测试
验收
部署
回滚
```

步骤格式：

```text
[步骤]
→ 修改范围：[文件 / 模块]
→ 预期结果：[可观察行为]
→ 验证方式：[命令 / 检查]
```

能从仓库确认的事实不反问。发现错误前提先指出。

### 用户决策门禁

如果某个未决事项会实质影响业务语义、页面/验收、公共 Contract、Schema、权限/安全、隐私与保留/删除、外部 Provider/Operation、费用/预算、调度策略、SLO/RPO/RTO、兼容性或不可逆数据行为，并且仓库没有已经批准的事实：

1. 不得由 Agent 静默选一个默认值后继续实现依赖该决定的代码；
2. 先完成能够由仓库、官方资料、Fixture 或测试自行确认的事实调查，再只提出最小必要的上游问题；
3. **必须在对话中先给出明确推荐方案**；存在有意义的取舍时再给 2–3 个实质不同的备选，并说明影响，不能只把一个没有建议的开放问题丢给用户；
4. 由用户/业务 Owner 作最终决定；在得到决定前，暂停依赖该决定的 Contract、Schema、业务语义、安全策略或不可逆实现，与该决定无依赖的工作可以继续；
5. 用户明确“暂不决定/以后再做”时，把延期本身记录为正式设计边界，不得继续偷偷实现该能力；
6. 用户给出决定后，在同一任务同步到对应长期事实源：Blueprint/需求文档、OpenSpec（存在时）、Contract/Schema（形成机器事实时）以及当前 Change；聊天记录不能作为后续开发唯一事实源；
7. 后续任务再次遇到已经固化的决定时直接读取事实源执行，不重复询问；只有新需求与已批准决定冲突时才重新提请用户决策。

## 4. 简单、精准、兼容

- 只写满足当前需求的最少代码；
- 优先标准库和现有依赖；
- 不增加未要求功能、CLI、配置或兼容层；
- 不顺手重构、改名、格式化无关文件；
- 默认保持公共 API、Contract、导入路径、配置、环境变量、数据格式、数据库、启动方式、合法行为、错误类型和关键错误信息；
- 破坏性变化必须先设计版本、Migration、兼容期和回滚。

## 5. 模块边界

模块化的目的：

```text
输入明确
输出明确
变化隔离
可以独立验证
```

允许调用链：

```text
Router
→ Service
→ Model / Port
→ Repository / Adapter
```

外部数据：

```text
Provider Adapter
→ Raw Artifact
→ Mapper
→ Canonical
→ Ingestion Service
→ Owner Repository
→ PostgreSQL

数据库读取：

PostgreSQL
→ Query Repository / Read Model
→ Query/Application Service
→ Router / API
```

禁止：

- Router 直接 SQL；
- Provider 直接写业务表；
- Mapper 读数据库、发 HTTP 或做业务分类；
- 第三方 JSON 成为公共业务结构；
- 一个模块绕过 Owner 写另一个模块的表；
- 多个 Repository 写同一张表；
- 前端直接访问数据库；
- Feature 复制另一个 Feature 的 Store/API；
- 为同一能力再造平行 Client、Mapper、Repository 或 Job；
- 每个函数机械增加 Interface、Facade、Factory、Manager；
- 万能 BaseRepository；
- 运行时任意插件加载。

只有外部基础设施、跨模块或独立 Fake 明显受益时创建 Port。

## 6. 独立调试

调试入口必须复用生产实现。

- Provider Probe 调对应生产 Adapter/Operation；TikHub 只是一个 Provider 实现；
- Mapper 测试调用生产 Mapper；
- Ingestion 使用 Canonical Fixture 和隔离 PostgreSQL；
- Worker 使用生产 Job Runtime 和 Fake Handler；
- Frontend 使用生成 Client 的 Mock；
- Renderer 使用固定 Report Context；
- 不复制 endpoint、分页、字段映射和业务规则。

真实付费 Provider/模型 Probe 默认关闭，明确费用，不进普通 CI，不写生产库，不打印 Secret。

## 7. 数据

- PostgreSQL 是唯一业务事实库；
- 外部 ID 使用字符串；
- 时间数据库用 `timestamptz`；
- API 用 UTC ISO-8601；
- 日志用 `YYYY-MM-DD HH:mm:ss.SSS` 北京时间；
- 关系使用外键/关联表，不用逗号字符串；
- 稳定字段用列，低频扩展元数据才用 `jsonb`；
- 内容和评论按 Current + Version + Metric Observation 保存；
- 一张表只有一个写 Owner；
- 外部 HTTP 调用不放在数据库事务中；
- HTTP 幂等与内部 Job 幂等使用不同记录和作用域；
- 内容版本只与当前 Business Hash 比较，允许 `A → B → A` 形成新版本；
- Candidate/Ingestion 账本必须追溯到 Run、Scope、Attempt、Raw 和来源项；
- Artifact ID/元数据/权限由 `ArtifactService` 管理，`ArtifactStore` 只按 `storage_key` 存取；
- 业务事实与下游 Job 必须在同一 PostgreSQL 事务提交；
- 可重试操作必须有明确、受数据库约束的幂等键。

## 8. Contract

手写事实源：

- HTTP：Pydantic Request/Response；
- Canonical：Pydantic Canonical Model；
- Job：版本化 Pydantic Payload。

生成：

- OpenAPI；
- JSON Schema；
- TypeScript Client。

生成目录禁止手工修改。Contract 删除字段、改名、改类型、改语义、可选变必填、改默认排序或错误都按破坏性变化处理。

## 9. Job

长任务必须走持久化 Job：

- 采集；
- 回补；
- 评论；
- AI；
- 报告；
- 导入导出；
- 清理。

Job 必须支持：

- Payload Version；
- 幂等；
- 租约；
- Fencing Token；
- Heartbeat；
- 超时；
- 取消；
- 分类重试；
- 进度；
- 结果和错误。

Worker 必须原子认领 `queued` 或接管 Lease 已过期的 `running` Job，并生成新 Fencing Token；完成、失败、进度、续租和业务可见提交都必须验证当前 Token。只扫描 `queued` 不合格。Scheduler 必须用唯一 `(plan_id, schedule_version, scheduled_for)` Occurrence，在同一事务创建 Run/Job 并推进 `next_run_at`。

每次 Attempt 有 Heartbeat 不可延长的 Deadline。Platform Reaper 必须用 CAS 处理 Deadline 超时、取消和次数耗尽；Heartbeat 存活不能让超时 Handler 无限运行。Scheduler 停机补跑必须有已批准的 misfire 策略和上限。

已校验 Raw 存在时禁止再次调用 Provider；网络结果未知时不能承诺零重复计费，必须按批准策略重试并记录计费未知/潜在重复费用。当前版本**不实现请求/金额预算、Budget Account 或 Reservation Ledger**，也不得为了预留扩展点保留 dormant Budget Service/Repository。Provider Request/Attempt 仍可保存 Billing/成本快照与潜在重复计费事实用于执行审计。Dispatch CAS 必须验证当前 Job Fencing，Transport 禁止在一次调用中隐藏自动网络重试；Attempt 进入 `dispatching` 后同一 Attempt 不得再次发送。未来若业务需要 Budget/Cost Guard，必须通过新的 L3 Change 明确 Contract、Schema、配置、Migration 和验证后再接入发送前边界。

所有业务写 Unit of Work、Artifact 生命周期和文件 rename/delete 必须参与统一共享 session-level advisory 写屏障，并在取得共享锁后复核维护 epoch。常规/发布 Backup Set 先启用维护，再取得同键独占锁等待在途写者排空，持有到数据库与文件捕获都完成；仅拒绝新 HTTP 请求不算一致性屏障。

正常 Heartbeat 不写 INFO。Secret 不进 Job Payload。

## 10. 日志

应用日志写：

```text
/app/logs/api.log
/app/logs/worker.log
/app/logs/scheduler.log
/app/logs/frontend-events.log
```

生产 bind mount 到 `/data/AIMA_UGC/runtime/logs`。

日志：

- UTF-8；
- 一行一个事件；
- 北京时间毫秒；
- 稳定 `event`；
- 关联 request/job/run/scope/provider/content 等 ID；
- 默认 20 MiB × 10，gzip；
- 同时输出 stdout，Docker `local` 轮转；
- 不记录完整 Payload、Raw、Token、Cookie、密码和敏感个人信息；
- 统一转义换行、引号、反斜杠和控制字符，并限制字段/整行长度；
- 健康和空闲心跳不刷 INFO；
- 高价值操作写数据库审计。

## 11. 安全

- Secret 不提交 Git、不写数据库明文、不进 Raw、日志、Job；
- 使用 Compose Secret 或只读 Secret 文件；
- 当前第一版不实现本地账号密码、登录入口、MFA、Session、CSRF 或登录限流；真实第三方身份接入需求明确后再通过独立 L3 Change 实现认证；
- 未来飞书、OIDC 或其他企业身份源必须通过可替换 Identity/Authentication Adapter 进入统一 `Principal/AuthContext`；业务模块不得直接依赖飞书 SDK、`open_id`、`union_id` 或其他 Provider 私有字段；
- Authentication 与 Authorization 解耦：后端权限判断面向统一 Principal、稳定 Permission 和对象级策略，不因更换身份 Provider 改写业务 Service；
- 如果未来选定服务端 Session，再按实际方案实现 Session 哈希、Cookie、CSRF、撤销与过期；如果采用 OAuth/OIDC/飞书授权流程，则按协议验证 `state`、`nonce`，支持时使用 PKCE；
- API 幂等必须有数据库事实源；认证/授权实现进入生产范围后同样不得使用纯进程内状态充当生产事实；
- CORS、Allowed Hosts 和 Provider 出站域名使用显式 Allowlist；
- 后端执行权限校验；
- 参数绑定 SQL；
- 防路径穿越、SSRF、命令执行、不安全反序列化、公式注入、Zip Bomb 和超大上传；
- Raw 和导出受权限和审计保护；
- Artifact 下载执行对象级授权，出站 SSRF 校验覆盖 DNS 结果和每次重定向；
- 已实现并批准的认证、证书、输入校验或安全检查不得为方便调试而关闭；第三方认证尚未接入时，敏感/写 API 不得宣称具备公网生产认证能力。

## 12. 测试

新功能、修复和行为变化默认：

```text
Red
→ Green
→ Refactor
```

缺陷修复必须有回归测试。测试验证真实行为，不只验证 Mock 被调用。

验证顺序：

```text
目标测试
→ 模块测试
→ Contract/DB/Provider 专项
→ 前后端集成
→ 完整 CI
```

涉及公共边界时还必须运行架构依赖、表写入 Owner、Secret 扫描和文档入口检查：

```bash
uv run python scripts/quality/check_architecture.py
uv run python scripts/quality/check_table_ownership.py
uv run python scripts/quality/scan_secrets.py
uv run python scripts/quality/check_docs.py
```

门禁失败要修根因，不能修改门禁放行违规实现。失败输出必须包含规则 ID、文件或位置、原因和修复方向。

可靠性/安全专项必须使用真实 PostgreSQL 和生产调用链：

- Worker 在 claim、HTTP、Raw、业务提交和终态边界崩溃后恢复，旧/新 Lease 并发受 Fencing；
- Attempt Deadline、Reaper 超时/取消/次数耗尽 CAS 和 Heartbeat 不续 Deadline；
- 多 Scheduler 对同一 Occurrence 不重复、不丢失；
- 多级预算账户并发预留、结算、释放和计费未知；
- API Idempotency-Key 覆盖同/异 Payload、跨用户和过期；
- 认证接入阶段按实际协议验证身份边界与授权；采用 Session 时覆盖 fixation、CSRF、撤销/过期，采用 OAuth/OIDC/飞书授权流程时覆盖 state/nonce/PKCE/回调绑定；通用授权覆盖 Permission/对象级权限/IDOR，其他安全专项继续覆盖 SSRF 重定向/DNS、路径/Zip/日志注入；
- 中文搜索质量/性能基准、容量 Soak、数据库+Artifact 协调恢复和孤儿对账。

禁止：

- 删除或跳过失败测试；
- 降低断言和门禁；
- 吞异常；
- 针对测试硬编码；
- 盲目更新 Snapshot；
- 用旧结果冒充本轮验证；
- 局部测试冒充完整回归。

## 13. 依赖

- 初始化直接依赖版本以 `docs/blueprint/07-技术决策与实施门禁.md` 的编制日快照为目标；实际安装后以锁文件为准；
- Python 依赖只改 `pyproject.toml`，同步 `uv.lock`；
- CI 使用 `uv sync --locked`；
- Frontend 提交 `package-lock.json`，CI 使用 `npm ci`；
- 不同时使用多个包管理器；
- 普通功能不升级依赖；
- 新增依赖说明必要性、许可证、维护、体积和替代方案；
- 镜像和 Release 固定 digest；
- 不得因有新版本擅自升级；升级必须是独立任务并完整回归；
- OpenAPI SDK 生成器与前端 Lint 组合在阶段 1 PoC 验证前不得凭习惯选型或宣称兼容。

## 14. 文档

代码完成前检查系统事实是否变化：

- 模块职责；
- 调用链；
- 输入输出；
- API/Canonical/Job；
- 数据库；
- 配置；
- 日志；
- 启动部署；
- 调试测试；
- 用户行为。

受影响就同任务更新，不受影响不制造文档差异。长期文档描述合并后的当前系统，不写成变更日志。文档用普通中文、真实路径、真实命令和明确例子。用户确认的长期业务/技术决定或明确延期决定必须在同一任务落到正式事实源，不能只存在于聊天或 Change 历史中。

## 15. Git

任务从最新 `main` 创建：

```text
feature/
fix/
hotfix/
refactor/
perf/
docs/
test/
build/
chore/
migration/
revert/
```

名称使用小写英文、数字和连字符，只表达任务内容。禁止工具/模型/人员身份前缀。

禁止：

- `git reset --hard`；
- `git clean -fd`；
- 强制推送；
- 覆盖用户修改；
- 重写共享历史；
- 未授权提交、推送、PR、合并或删分支；
- CI 失败、冲突或结果未确认时强行推进。

提交信息使用中文。

## 16. Review 和交付

复杂任务先检查需求符合性，再检查代码质量。严重和重要问题未解决不得合并。

完成结论必须有本轮实际证据。交付至少报告：

- 变更摘要；
- 逐文件目的；
- Contract/数据库变化；
- 文档同步及依据；
- 实际验证命令、退出码和结果；
- 未验证内容及风险；
- 兼容、依赖、Migration、部署、回滚；
- 分支、提交、PR、CI、合并和清理状态。

禁止只说“已完成”“测试通过”。
