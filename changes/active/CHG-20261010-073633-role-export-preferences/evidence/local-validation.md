# 本地验证记录

Requirement Source：[#714](https://github.com/dingyuwen777/AIMA_UGC/issues/714)，decision epoch 2。用户要求完成本地验证后先不合并远程 main；人工本地验收仍为 PENDING。

当前实现 checkpoint：`9608b2cba8a591772f7fcfebc8afe6707619db1c`，相对 `513c79804f3fe14121ba0b0422865e16a2ac8d61` 仅同步 WisersOne 管理读取的 PostgreSQL 旧断言。再次 fetch 后基线 `origin/main` 仍为 `6f9779c56fdb3b4d3a83d8fb0cdd02e4cb9dd79d`。

## 已完成的直接证据

| 验证入口 / 范围 | 实际结果 | 说明 |
| --- | --- | --- |
| `python scripts/dev/validate_changed.py --base origin/main --committed-only --execute` | PASS，退出 0 | 按唯一 CI classifier 产生 full 范围；后端阶段后仅补工作台与两个 Browser 文件，前端阶段读取当前 checkpoint，后端文件未变 |
| `uv run pytest tests/unit tests/contracts tests/api -q` | 2611 passed、16 skipped、12 subtests passed | 覆盖权限拒绝、统一错误、最终路由、身份/CSRF、配置及既有业务；跳过条件主要为 Windows 上 POSIX/Bash/符号链接等既有环境条件，不能当作 Linux 验收 |
| changed Python Ruff format/check、`uv run mypy backend/src` | PASS，479 个源码文件类型检查通过 | Windows npm.cmd 启动问题已修复，入口局部 10 项回归及真实 npm 启动通过 |
| `scripts/contracts/generate.py --check`、`scripts/contracts/check_compatibility.py` | PASS | Pydantic、OpenAPI、JSON Schema 与 Orval 生成产物一致；正式生成目录未手工维护 |
| `npm --prefix frontend run lint` | PASS，0 warning | 当前修复版本 |
| `npm --prefix frontend run test -- --run` | 361 passed / 42 files | 角色入口、身份代次、任务源、个人字段、媒体只读路径等 |
| `npm --prefix frontend run build` | PASS，含两种 Typecheck | 870 个模块；原有大 bundle 提示不阻塞构建 |
| `npm --prefix frontend run test:e2e` | 218 passed | 当前完整 Browser Mock 套件，无未声明 API 或遗留失败；覆盖原有采集/配置/报告/人工复核以及新增普通用户路径 |
| `npm --prefix frontend run test:e2e:fullstack` | 原有 20 项通过；新增角色用例修正后单独 1 项通过 | 使用隔离 PostgreSQL、生产 API/Service/Worker 和本机 Fake Provider；实际签发 AIMA Session，不能替代真实企业 OAuth |
| `role-export-preferences.spec.ts` | PASS | 两角色 UI、管理员真实复核后普通用户自动刷新、跨浏览器默认列、临时导出、Worker 成功与真实文件下载、B 查询/下载 A 文件 404、跨标签页 Cookie 换号清筛选、管理深链禁止且无管理请求 |
| 项目文档、Secret、事实、治理接线与环境模板检查 | PASS | 完整 preflight 执行，不包含本任务未跟踪临时产物 |
| `python scripts/quality/check_change_completion.py --root . --require-active-ready` | PASS，gated 164 / strict 164 / legacy 128 | 逐 AC 与反向审计完成；首次门禁指出 Change inline list 不受当前 parser 支持，改为正式 block list 后通过，没有改变需求或生产实现 |

## PostgreSQL、迁移与 XLSX

受影响范围先完成 103 个不同 PostgreSQL 用例，另有历史 Migration 兼容检查 14 项通过。新增 Reporting 集成直接打开 Worker 生成的 XLSX，断言“标题、作者”表头及顺序、两条真实导入数据、所有工作表没有普通用户受限字段；Job 创建后改个人默认，不改变已冻结文件。还覆盖 A/B/admin 真实 Session、先 owner 过滤再 LIMIT、旧未知 owner、降权/旧目录下载、并发 revision、NULL 恢复默认、失效列读取不重写。

PostgreSQL 分层回归已取得以下直接结果：platform 73（含前轮独立严格装配的 17 项）、database 125、jobs 22/1 skipped、reporting 18/1 skipped、content 315、vehicles 5，以及真实 API readiness。采集全层首次 91 passed/5 failed；独立子库尾部 167 项全部通过，node ID 并集为完整 258 项、missing 0。最后完整加载原 258 个节点并核对 inventory，按原顺序执行同样的前 96 项：96 passed/162 deselected/403.42s/退出 0。首次五项异常没有再次复现，原具体异常类型无法从已清理 fixture 和丢失额外字段的日志恢复，保留此风险，不宣称已查明根因或一次 258 项全绿。

ingestion 全层首次 155 passed/1 failed。唯一失败是旧测试仍允许普通用户 GET WisersOne 管理运行；按 #714 AC3 更新为 403，同时继续验证统一 Error Contract、管理员正常读取、Job/运行记录/取消意图/外部发送均未变化。修后整个该文件 3 passed/6.70s/退出 0，覆盖原 2 项已通过及修后 1 项，因此完整 ingestion 156 个唯一用例均有直接 PASS，不能误记为一次 156 项全绿；生产实现未改变。

| PostgreSQL 真实项目测试范围 | 结果 / 唯一覆盖 | 命令与条件 |
| --- | --- | --- |
| `tests/integration/platform` | 56 PASS；严格多 Connector 两文件另 17 PASS | 本轮普通 PG 进程显式 ignore 严格身份两文件；两文件已在专用 `aima_sync_test` 严格 fixture 装配执行，未放宽 fixture |
| `tests/integration/database` | 125 PASS | 含新增 0087 可靠回填、空库往返、有数据拒绝破坏性 downgrade；78.78s |
| `tests/integration/jobs` | 22 PASS / 1 SKIP | 10.29s；Linux 独占 session 强制回收用例按源码 Windows skip；两个 Windows 句柄/启动器用例实际 PASS |
| `tests/integration/collection` | 258 个唯一用例有 PASS，原模块/原前序 96 PASS | 原 91 PASS/5 FAIL、tail 167 PASS；最后原模块加载/原顺序前 96 项全部通过，历史未复现异常保留风险 |
| `tests/integration/content` | 315 PASS | 820.62s，含布局/统计/有效人工覆盖/Legacy 读取和当前媒体行为 |
| `tests/integration/ingestion` | 156 个唯一用例有 PASS | 原 155 PASS/1 旧预期 FAIL；修后 `test_wisersone_recovery_permissions.py` 整文件 3 PASS，原 2 个 PASS 重复，不重复计数 |
| `tests/integration/vehicles` | 5 PASS | 8.08s |
| `tests/integration/reporting` | 18 PASS / 1 SKIP | 独立报告 DB、39.10s；唯一 skip 需要 `AIMA_REPORT_BROWSER_ACCEPTANCE=1` 与专用前端，普通 PG CI 亦不启用；报告生成/发布/下载及本次 Excel 真实文件用例实际 PASS |

实际入口先设置本任务隔离 DB/data/log/temp/Secret、显式 development、TikHub disabled、Feishu dry-run，移除外部 AIMA 配置及主机 SSLKEYLOGFILE；临时 runner 仅拦截非 loopback 的真实 socket，再调用项目 `pytest`，不改生产实现、Fixture 或断言。各层独立 Python 进程持续复用任务回归 DB，与当前 `ci.yml` 分层装配一致；严格身份和 Reporting 使用自己的独立 DB。命令尾部使用 `--maxfail=5 -q --tb=short -o faulthandler_timeout=90`（Reporting 为 maxfail=3），后续增加 `-vv` 仅增强可诊断输出。

采集有界诊断保留原失败五项：根评论采集、回复父关系、接管复用搜索 Raw、回复目标 partial、空回复页纠正旧计数。初次均在 Raw 存储后进入 Scope 稳定失败终态；原 pytest 日志未渲染安全事件的额外异常字段，原 fixture 已清理，不能事后捏造数据库错误码。独立首项、相邻 22+5、前序 platform/database/jobs+5、额外前序 34+5、最早 69+5（74 PASS/590.83s）均通过。最后按原完整 258 节点加载并核对 inventory，再执行原前 91+5 的 96 项，额外捕获安全错误及失败前事实，96 项全部通过。相关 Collection/TikHub/persistence/测试代码与起点 main 相同只是静态事实，不能代替 main 实测或根因归因。原窗口 PG 日志只有故意约束拒绝场景的九条约束 ERROR，没有超时、死锁、连接、存储或 PANIC；后台 checkpoint 耗时不作为前台失败归因。

上述八层合计 972 个唯一用例有直接 PASS，另有两个明确条件 SKIP；103 项前轮定向 PG 与诊断重跑包含在相关范围内，不叠加充当新增覆盖。原 Reviewer 已独立复核最后原序/修后日志，判定足以支持本地可验收，Human PENDING，无具体 blocking 本地 Acceptance gap；历史未复现异常仍保留上述风险边界。

所有数据库均为本任务新建的本机 Docker PostgreSQL 18.4 隔离实例/数据库，不连接生产；实际外部付费 HTTP 被阻止。本任务迁移为 `20261010_0087`，空库升级、历史归属回填和保留业务数据的 downgrade 拒绝已验证。

## 修复前失败与修复后证据

首轮独立 Review 的三项修复采用定向失败用例：普通用户视频恢复与首次列表追赶修复前 2 failed/67 passed，修复后定向 72 passed；新增默认字段/Workbench Browser 6 项通过。进一步的 Workbench 慢请求重叠用例先明确失败（等待第 2 个请求时出现第 3 个），增加静默读取在途互斥后，慢请求与原定时/深链六项回归通过，最后完整 218 项 Browser 通过。

## 未执行的环境与交付边界

真实飞书企业授权、多企业真实 Connector、HTTPS/生产浏览器安全及生产候选权限尚未验收。Linux 专属运行/回收、独立报告浏览器候选装配、Release/离线回放及远程 required CI 不由 Windows 本地结果替代。本地未 push、未创建 PR、未 merge、未发布/部署或操作生产。保留根开发分支，等待人工本地验收及用户后续交付指令。
