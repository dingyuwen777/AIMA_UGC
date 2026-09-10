# 内容品牌车型重分类与 Legacy Cleanup 运行手册

这份手册用于两个已经具备代码支持、但不会由系统自动执行的运维动作：

1. 按一个冻结的 Brand/Vehicle Catalog Snapshot，对既有 Current Content 补齐 Brand/Vehicle Evidence；
2. 在确认旧过滤链没有任何数据或执行事实后，通过 Migration 删除旧关系表和 Global Keyword Relevance 表。

它不授权生产部署、生产 Migration 或生产数据写入。执行者仍须先取得目标环境授权、备份/恢复能力和维护窗口；当前完整协调 Backup/Restore 仍未实现。

## 1. 当前能力和边界

重分类使用 `vehicles.content-reclassification.v1` 持久 Job。创建 Run 时冻结全部 active Brand、Vehicle、Alias 和目录版本；Worker 随后按 UUID keyset、稳定 hash shard 和持久 checkpoint 分批处理。每批 Evidence 与 checkpoint 在同一事务提交，进程重启或 Job 接管会从最后一个已提交 checkpoint 继续。

数据流是：

```text
已有非 alias Vehicle Evidence
→ 冻结目录中的 Vehicle.brand_id
→ Brand Evidence(source=vehicle_match)

Current Content title + text
→ 冻结 Brand/Vehicle Catalog Snapshot
→ BrandVehicleResolver
→ 替换该 Content Version 的自动 alias Evidence
→ 保留 import/manual/AI Vehicle Evidence 和所有人工锁
```

重分类不调用 TikHub 或 LLM，不修改 `contents` Current 字段，也不改变 AI/人工 Relevance。车型合并身份按最终 active 车型解释；人工 Brand/Vehicle Review Lock 始终优先，自动 Evidence 不得覆盖。

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
