# 内容品牌车型重分类与 Legacy Cleanup 运行手册

这份手册用于已经具备代码支持、需要显式限定范围和执行的运维动作：

1. 按一个冻结的 Brand/Vehicle Catalog Snapshot，对既有 Current Content 补齐 Brand/Vehicle Evidence；
2. 在确认旧过滤链没有任何数据或执行事实后，通过 Migration 删除旧关系表和 Global Keyword Relevance 表。
3. 对明确指定的历史帖子修复当前品牌/车型缺证，以及可以证明输入等价的 Analysis 引用和人工继承来源。

它不授权生产部署、生产 Migration 或生产数据写入。执行者仍须先取得目标环境授权、备份/恢复能力和维护窗口；当前完整协调 Backup/Restore 仍未实现。

## 1. 当前能力和边界

重分类使用 `vehicles.content-reclassification.v1` 持久 Job。创建 Run 时冻结全部 active Brand、Vehicle、Alias 和目录版本；Worker 随后按 UUID keyset、稳定 hash shard 和持久 checkpoint 分批处理。每批 Evidence 与 checkpoint 在同一事务提交，进程重启或 Job 接管会从最后一个已提交 checkpoint 继续。

数据流是：

```text
已有明确车型列、AI 或人工等非自动 Vehicle Evidence
→ 冻结目录中的 Vehicle.brand_id
→ Brand Evidence(source=vehicle_match)

Current Content title + text
→ 冻结 Brand/Vehicle Catalog Snapshot
→ BrandVehicleResolver
→ 收敛该 Content Version 的自动 alias 与旧文本 import Evidence
→ 保留明确车型导入事实、manual/AI Vehicle Evidence 和所有人工锁
```

重分类不调用 TikHub 或 LLM，不修改 `contents` Current 字段，也不改变 AI/人工 Relevance。车型合并身份按最终 active 车型解释；人工 Brand/Vehicle Review Lock 始终优先，自动 Evidence 不得覆盖。

新建 Run 的冻结目录显式持有 `brand_scoped_vehicle_v2`，先完整命中品牌，再在确认品牌内匹配车型；单字车型需同字段、同片段和原文 12 字符内唯一品牌关联。旧快照缺字段仍按 `field_priority_v1` 执行。新版将 `import` 中 `title/raw_text/transcript_text/title_text` 文本来源视为自动匹配，明确 `vehicle_model` 列及 NULL 字段继续保留；不能将所有 import 行一律清除。Current 和两类人工锁在每批读取、解析与提交期间保持稳定，人工品牌限制自动车型，明确空锁也有效。

生产实现入口：

- [`backend/src/aima_ugc/modules/vehicles/content_reclassification.py`](../../backend/src/aima_ugc/modules/vehicles/content_reclassification.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/content_reclassification.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/content_reclassification.py)
- [`backend/src/aima_ugc/bootstrap/content_reclassification_worker.py`](../../backend/src/aima_ugc/bootstrap/content_reclassification_worker.py)
- [`scripts/operations/content_reclassification.py`](../../scripts/operations/content_reclassification.py)

## 2. Cleanup 的 fail-closed 前置条件

Migration `20260910_0047` 只允许在下列数据库事实同时成立时执行：

- `keyword_pack_vehicle_models`、`collection_plan_vehicle_models`、`global_relevance_config` 都为空；
- 不存在 `ingestion.import-excel.v1` Job；
- 不存在仍携带 `keyword_selection` 的旧 Import Batch Snapshot；
- 所有 Collection Run 都是 `collection-run-config.v2`；
- 所有 Data Import Campaign 都冻结 `brand-vehicle-filter.v1` Snapshot；
- 每个 active Vehicle 都归属一个 active Brand。

任一条件不满足，Upgrade 会在 Drop 前报错并回滚，不会选择默认归属、改写旧任务或删除非空表。精确检查和 DDL 以 [`migrations/versions/20260910_0047_remove_legacy_filtering.py`](../../migrations/versions/20260910_0047_remove_legacy_filtering.py) 为机器事实。

代码和消费者还必须在部署前确认：

```powershell
rg -n "global_relevance_config|collection_plan_vehicle_models|keyword_pack_vehicle_models|collection-run-config.v1|ingestion.import-excel.v1|/api/v1/relevance-config" backend/src frontend/src contracts/openapi/openapi.json
```

当前生产代码和生成 Contract 应无命中。测试与 Migration 文件会保留拒绝旧输入、验证 downgrade 或重建旧空表的文字，不应据此误判为生产消费者。

## 3. 生产 Migration 顺序

执行前至少完成：目标数据库备份及可恢复性确认、当前 Revision 记录、应用与 Worker 停写、Legacy 三表行数/旧 Job/旧 Run/Vehicle Ownership 对账，以及新应用镜像和回滚镜像准备。不要把开发机或 CI 的空库 Migration 结果当作目标生产数据库证据。

建议把结构扩展和破坏性 Cleanup 分开观察：

```powershell
uv run alembic current
uv run alembic upgrade 20260910_0046
uv run alembic current
uv run alembic upgrade 20260910_0047
uv run alembic current
```

`0046` 只增加重分类 Run 表；`0047` 执行 fail-closed 检查后删除三张 Legacy 表。新应用需要 `0047`；旧应用回滚需要先停掉新应用/Worker，再执行：

```powershell
uv run alembic downgrade 20260910_0046
```

该 downgrade 只恢复三张**空表结构**，不会恢复 Upgrade 前本就不允许存在的数据。`vehicle_models.brand_id` 继续 nullable；本次 Cleanup 不会创建 unknown Brand，也不会把未知归属伪造成有效数据。继续 downgrade 到 `0045` 会删除重分类 Run 表，但已经写入的 Brand/Vehicle Evidence 保留。

## 4. 创建有界重分类 Run

先确认 API/Worker 已使用同一目标数据库、Migration 已到 `0047`、Brand/Vehicle Catalog 已校准且 readiness 没有未归属 active Vehicle。然后从小范围开始：

```powershell
uv run python scripts/operations/content_reclassification.py start `
  --idempotency-key prod-20260910-shard-0 `
  --created-by operator-name `
  --shard-index 0 `
  --shard-count 1 `
  --batch-size 200 `
  --max-contents 10000
```

`max-contents` 是单 Run 的安全上限，不是数据库总量声明。需要并行时，为每个 `shard-index` 使用不同幂等键，并保持相同 `shard-count`；不要在同一批次中改变分片数。同一幂等键再次提交相同参数会返回原 Run，提交不同范围或参数会失败。

可选的 `--start-after-content-id` 和 `--end-at-content-id` 用于 UUID keyset 范围；下界为开区间，上界为闭区间。范围、分片和最大条数共同限制实际处理集合。

Worker 使用正常生产入口运行，不为重分类建立第二套执行器。创建命令只入队，不在命令进程内处理 Content。

## 5. 查询、取消和对账

```powershell
uv run python scripts/operations/content_reclassification.py status --run-id <RUN_UUID>
uv run python scripts/operations/content_reclassification.py cancel --run-id <RUN_UUID>
```

状态输出不会包含正文或完整 Alias Snapshot。重点核对：

- `job_status`、`job_progress`、`job_error_code`；
- `checkpoint_content_id` 与 `processed_count`；
- `matched_count + unmatched_count = processed_count`；
- `brand_evidence_count`、`vehicle_evidence_count`；
- `conflict_count`；
- `brand_locked_count`、`vehicle_locked_count`；
- `catalog_version`、shard/range 和 `max_contents` 是否与批准范围一致。

Cancel 是持久请求。Worker 会完成或回滚当前短事务后收敛取消；不会在半批 Evidence 已写、checkpoint 未写的状态下提交。数据库错误按 Job Runtime 策略重试；Fence 已失效时旧 Worker 不能推进 Evidence/checkpoint。

对账不应只看 Job `succeeded`。还要核对各 shard 覆盖范围、总 processed、锁定数、冲突原因和 Voice Plaza/Export 的 Brand/Vehicle 查询结果。发现 `conflict_count > 0` 时先检查目录合并/归属和 Evidence 引用，不要通过修改统计或直接 SQL 让 Run 表面成功。

## 6. 当前未验证或未自动化的生产事项

- 本仓库不包含目标生产数据库的实际空表证明、备份成功证明或恢复演练结果；
- 完整协调 Backup/Restore、企业认证和 Production Go-Live 仍由 live Roadmap 管理；
- 本手册不提供自动选择全库范围、自动调大并发或自动执行 Migration 的入口；
- CI 的 PostgreSQL 18 回归证明软件行为，不替代目标服务器容量、锁等待、I/O 和维护窗口验证。

生产执行后应把实际 Revision、Run ID、范围、统计、异常处置和恢复证据放入获批的运维记录，不写入本手册形成第二套易失事实。

## 7. 补采后历史一致性修复

这项修复适用于已受影响的有限帖子集合。新补采会在详情入库事务内自动收敛，历史数据仍需由操作者先预检、确认范围，再显式创建修复 Run。它与前面的全目录重分类使用各自的业务父事实，共用现有 Job Runtime、分类器与 Analysis 复用规则。

正式入口是 [`scripts/operations/content_consistency_repair.py`](../../scripts/operations/content_consistency_repair.py)。范围必须提供可重复的 `--content-id` 或一个 `--collection-run-id`，两者互斥；后者只选取该 Run 已有成功入库账本中的有限帖子。`--max-contents` 必填且不超过10000，超限整次拒绝，不截断后冒充完整修复；`--batch-size` 默认200，允许1–1000。没有自动全库选择入口。

先在已批准的目标环境执行只读预检：

```powershell
uv run python scripts/operations/content_consistency_repair.py dry-run `
  --content-id <CONTENT_UUID_1> `
  --content-id <CONTENT_UUID_2> `
  --max-contents 2 `
  --batch-size 200
```

也可以把两条 Content 参数替换为 `--collection-run-id <COLLECTION_RUN_UUID>`，并给出与批准范围相符的上限。输出包括目标数、候选数、品牌缺证候选数、预计等价数、目录版本及 Analysis 拒绝原因。预检在可重复读的只读事务内完成，不创建 Job、修复 Run、Evidence 或复用关系，不调用 Provider/模型；预检结果不预留后续 Current 状态。

取得**生产实际执行的单独授权、备份可恢复性和操作范围确认**后，才创建持久任务：

```powershell
uv run python scripts/operations/content_consistency_repair.py start `
  --collection-run-id <COLLECTION_RUN_UUID> `
  --max-contents 100 `
  --batch-size 200 `
  --idempotency-key <APPROVED_OPERATION_KEY> `
  --created-by <OPERATOR>

uv run python scripts/operations/content_consistency_repair.py status --run-id <REPAIR_RUN_UUID>
uv run python scripts/operations/content_consistency_repair.py cancel --run-id <REPAIR_RUN_UUID>
```

创建命令只入队，由正式 Worker 领取 `content.consistency-repair.v1`。同一幂等键和同一参数返回原 Run；改变范围、上限、批大小或操作身份会拒绝。Run 冻结当时有限目标及完整 active 目录，接管不会吸收迟到的新来源帖子或切换目录版本。执行读取每页锁定的最新 Current，按 UUID Keyset 推进已提交检查点。

每批缺证分类、合法 AI 引用、人工来源、必要的增量投影和检查点在同一事务提交。数据库异常按原 Job 策略重试，旧 Fence 不能继续写；取消阻止下一批。已提交的合法修复保留，不把取消当作撤回。第二次修复不会复制 Result、人工操作、来源账本或已有效的 Evidence；只刷新真正变化的帖子，不做全局投影重建。

对账应同时核对 `job_status/job_error_code`、`processed_count/target_count`、`checkpoint_content_id`、品牌变更数、复用新增/既有数、空匹配数和 `analysis_reasons`，以及声音广场与冻结导出/报告中的实际值。`input_mismatch`、`unknown_protocol` 和 `no_success` 不会被猜测成成功等价引用；具体算法与人工优先级由 [Analysis Owner](../../backend/src/aima_ugc/modules/analysis/README.md#6-版本身份与-stale) 维护。

## 8. 一致性结构升级和回滚边界

新应用需要 [`migrations/versions/20261009_0083_analysis_version_reuse.py`](../../migrations/versions/20261009_0083_analysis_version_reuse.py) 的 Analysis 引用、统一读取函数和增量触发器，以及 [`migrations/versions/20261009_0084_content_consistency_repair.py`](../../migrations/versions/20261009_0084_content_consistency_repair.py) 的有限修复 Run/Targets。两项 Migration 只扩展结构，不扫描 Content、不运行修复、不调用 Provider/AI。正式发布应先确认备份和当前 revision，暂停写入进程，升级结构，再启用同一版本的 API/Worker；本地空库往返通过不替代生产授权和验证。

回退应用前先停止新修复入队，取消或排空新类型 Job，并停掉新 Worker。旧 Worker 不注册该类型，不会将其误执行成旧重分类；不要留下没有对应处理器的待运行任务后就宣布回滚完成。默认保留新增结构及引用审计，原 Result/Run/人工操作始终不改写。旧应用没有新补采和引用读取能力，回退后的功能口径必须另行验证，不能承诺继续提供新功能。

删除结构的 downgrade 只用于已批准且已备份的结构回退：`0084→0083` 删除修复父事实和检查点，不撤销已提交业务修复；继续退到`0082`会删除复用关系并恢复原投影函数，已经产生的引用审计需事先保存。历史 Result/Run 不会因此复制或改写，既有有效数据也不能通过伪造新 Content Version 恢复。生产不自动执行这些 downgrade 或历史修复。
