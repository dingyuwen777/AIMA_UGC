# Collection 模块

Collection 负责采集执行、Provider Adapter 调用、Raw 证据和后续 Mapper/Candidate 边界。当前已建立
Stage 5A Provider-neutral Request/Attempt、一次发送 Transport、Raw Artifact，以及 Stage 5B
Collection Run/Scope PostgreSQL 父事实。

## 生产入口

- `aima_ugc.contracts.provider`：版本化 `ProviderRequestV1`、`ProviderAttemptV1`、费用、安全错误和
  `RawEnvelopeV1`；
- `aima_ugc.modules.collection.providers.ProviderClient`：每个 Attempt 最多调用一次注入的
  `ProviderTransport`，不隐藏网络重试；
- `aima_ugc.modules.collection.providers.RawArtifactService`：递归脱敏后通过正式
  `ArtifactService + ArtifactStore` 保存、校验和回放 gzip Raw；
- `aima_ugc.adapters.providers.fake.FakeProviderTransport`：普通测试使用的受控外部 I/O Fake。
- `aima_ugc.modules.collection.CollectionExecutionService`：校验本阶段 `manual/api/backfill` 创建语义和
  Scope 身份唯一性；
- `aima_ugc.adapters.persistence.postgres.collection.PostgresCollectionRepository`：在调用方持有的同一
  SQLAlchemy Session/事务内创建 queued Run/Scopes，并按 Job/Run 查询父事实；
- `aima_ugc.modules.collection.tables`：`collection_runs/collection_scopes` 的唯一 Collection Owner
  Table 定义；第三条 Migration 建立真实 `collection_runs.job_id → jobs.id` 唯一外键。

Raw Artifact 使用以下相对 `storage_key`：

```text
raw/<provider>/<platform>/<YYYY>/<MM>/<DD>/<run_id>/<scope_id>/<attempt_id>.json.gz
```

日期按 `Asia/Shanghai` 从发送时间计算。Artifact 保持 `stored`；只有未来 Provider Attempt
Repository 在业务短事务中建立引用后，才能推进为 `linked`。

## 独立验证

```bash
uv run pytest tests/unit/collection tests/integration/collection tests/contracts/test_provider_v1.py -q
uv run python scripts/contracts/generate.py --check
```

测试从正式 Client、Raw Service、ArtifactService 和 Local ArtifactStore 进入。Fake Transport 不访问
网络、不需要 Token、不产生费用；Raw 测试目录位于 Git 忽略的 `.runtime/stage5a-tests/`。Repository
集成测试要求先准备隔离 PostgreSQL 18、Secret 文件并执行 `uv run alembic upgrade head`；独立
`Stage 5B Collection Execution` CI 固定使用 PostgreSQL 18.4。

## 当前限制

- 没有真实 HTTP/SDK/文件 Transport 或具体平台 Operation；
- 仅支持 `manual/api/backfill` Run；没有 Plan/Occurrence/Scheduler，因而不支持 `scheduled`；
- 没有 Provider Request/Attempt PostgreSQL 表、预算预留、数据库 CAS/Fencing 或 Worker 注册；
- 没有 Mapper、Candidate、Ingestion、Content/Comment 或 Scheduler；
- 没有决定 Raw 的访问、保留、删除、备份和生产容量策略；
- 真实 Provider Probe 默认不存在，不能用 Fake 结果宣称外部平台兼容。
