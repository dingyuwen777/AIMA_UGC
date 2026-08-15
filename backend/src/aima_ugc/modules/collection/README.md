# Collection 模块

Collection 负责采集执行、Provider Adapter 调用、Raw 证据和后续 Mapper/Candidate 边界。当前已建立
Stage 5A Provider-neutral Request/Attempt、一次发送 Transport、Raw Artifact，Stage 5B
Collection Run/Scope PostgreSQL 父事实，Stage 5C Provider Request/Attempt 持久化基础，Stage 5D
不计费 Provider-neutral Dispatch、Raw 关联与崩溃恢复基础，Stage 6 小红书 TikHub App V2
Operation/Mapper、Candidate/Ingestion 追加账本和已存 Raw 回放纵切，以及 Stage 7 的
Decision/Capability 与 Provider Config/Platform Route 机器基础。

## 生产入口

- `aima_ugc.contracts.provider`：版本化 `ProviderRequestV1`、`ProviderAttemptV1`、费用、安全错误和
  `RawEnvelopeV1`；
- `aima_ugc.contracts.collection`：Stage 7 版本化 `CollectionDecisionRequestV1`、
  `CollectionDecisionV1`、`ProviderPlatformCapabilityV1`、`ProviderConfigV1` 与
  `ProviderPlatformRouteV1`；只表达规范化业务事实/能力和 Provider 配置引用，不包含 Provider 私有分页状态或
  原始 Secret；
- `aima_ugc.modules.collection.CollectionDecisionService`：根据 previous/current 规范化事实、业务策略和
  Capability 纯计算详情、一级评论与二级回复动作及稳定 reason code；不访问数据库、不发 HTTP、
  不解释 Provider Raw；
- `aima_ugc.modules.collection.provider_routing.ProviderRegistry`：把具体 Provider Config + Platform
  解析到当前已注册 Provider Capability；禁用配置、未知 Provider、Base URL 不在 Provider allowlist 或
  未实现平台时关闭失败；
- `aima_ugc.adapters.providers.registry.build_default_provider_registry`：当前只登记已有机器事实的
  `tikhub + xhs`，TikHub Base URL allowlist 为 `https://api.tikhub.io`；其余四平台只有对应
  Operation/Fixture/Capability 建立后才注册；
- `aima_ugc.adapters.providers.tikhub.capabilities.XHS_TIKHUB_CAPABILITY`：当前只登记已实现的
  小红书 TikHub 业务 Capability；其余四平台只有在对应 Operation/合法脱敏 Fixture/验证建立后才加入
  机器 registry；
- `aima_ugc.modules.collection.providers.ProviderClient`：每个 Attempt 最多调用一次注入的
  `ProviderTransport`，不隐藏网络重试；
- `aima_ugc.modules.collection.providers.RawArtifactService`：递归脱敏后通过正式
  `ArtifactService + ArtifactStore` 保存、校验和回放 gzip Raw；
- `aima_ugc.adapters.providers.fake.FakeProviderTransport`：普通测试使用的受控外部 I/O Fake；
- `aima_ugc.modules.collection.CollectionExecutionService`：校验本阶段 `manual/api/backfill` 创建语义和
  Scope 身份唯一性；
- `aima_ugc.adapters.persistence.postgres.collection.PostgresCollectionRepository`：在调用方持有的同一
  SQLAlchemy Session/事务内创建 queued Run/Scopes，并按 Job/Run 查询父事实；
- `aima_ugc.modules.collection.ProviderPersistenceService`：校验 Provider Request 与 Scope 父链，创建或
  读取幂等 Request，并准备不计费的 `reserved` Attempt；
- `aima_ugc.adapters.persistence.postgres.provider.PostgresProviderRepository`：在调用方持有的同一
  SQLAlchemy Session/事务内持久化 Request/Attempt，不提交事务、不执行外部 I/O；
- `aima_ugc.modules.collection.ProviderDispatchService`：先用 Job Fencing 在短事务中取得
  `reserved → dispatching` CAS，再于事务外最多调用一次 Provider Client，最后在短事务中提交结果；
- `aima_ugc.modules.collection.ProviderAttemptReconciler`：接管遗留 `dispatching` Attempt 时优先按
  确定性路径校验并恢复已落盘 Raw；没有可用 Raw 时保守记为 `unknown`，不复发原 Attempt；
- `aima_ugc.adapters.persistence.postgres.provider_dispatch`：把 Job Fencing、Provider Attempt Owner 写入和
  Artifact `stored → linked` 组合成短事务持久化边界；
- `aima_ugc.adapters.providers.tikhub.operations.xiaohongshu`：唯一定义小红书 App V2 搜索、详情、一级/二级
  评论请求和分页状态；不访问数据库；
- `aima_ugc.adapters.providers.tikhub.mappers.xiaohongshu`：把已确认 Raw/采集上下文纯映射为
  Canonical Content/Comment；不发 HTTP、不读数据库；
- `aima_ugc.modules.collection.CandidateIngestionService` 与
  `aima_ugc.adapters.persistence.postgres.candidates.PostgresCandidateRepository`：追加逐项 Candidate 和
  Ingestion 结果；数据库约束禁止账本 UPDATE/DELETE，并拒绝没有 Canonical 身份/业务目标的成功结果；
- `aima_ugc.modules.collection.XhsRawReplayHandler` 与 `adapters.persistence.postgres.xhs_replay`：从正式
  Job Runtime 读取 completed/linked Raw，经生产 Mapper、Ingestion 和 Owner Repository 回放；Handler
  不接受 Provider Client/Transport；
- `aima_ugc.modules.collection.tables`：`collection_runs/collection_scopes` 与
  `provider_requests/provider_request_attempts` 的唯一 Collection Owner Table 定义；第三、四条
  Migration 建立真实 Job、Scope、Request 和 Artifact 外键，第五条 Migration 冻结 Request 状态白名单和
  terminal Attempt 的一次性 Raw 关联规则；`candidate_tables` 是 Stage 6 Candidate/Ingestion Owner Table，
  第六至第九条 Migration 建立业务表、来源约束、账号备用 ID 和追加账本保护。

Provider 配置实例由 System Owner 持久化在 `provider_configs`。同一种 Provider 可以有多个实例；实例不绑定平台，平台/Plan 后续选择具体 `provider_config_id`。数据库只保存 `secret_ref`，不保存 API Key/Token 明文；Secret 引用校验和解析在 `platform/security`，Provider Registry 再执行 Provider/Base URL/Capability 校验。

Raw Artifact 使用以下相对 `storage_key`：

```text
raw/<provider>/<platform>/<YYYY>/<MM>/<DD>/<run_id>/<scope_id>/<attempt_id>.json.gz
```

日期按 `Asia/Shanghai` 从数据库持久化的发送时间计算，使崩溃恢复能重建同一确定性路径。Stage 5D 在
terminal Attempt 业务短事务中一次性建立 `provider_request_attempts.raw_artifact_id` 引用，并由
Artifact Owner Repository 把元数据从 `stored` 推进为 `linked`；关联完成后来源身份不可改写。

## Stage 7 Decision 独立调试

`CollectionDecisionService` 的调试入口固定为：

```text
显式 CollectionDecisionRequestV1 JSON
→ scripts/dev/probe_collection_decision.py
→ 正式 CollectionDecisionService
→ CollectionDecisionV1 JSON
```

例如可准备一个不含 Secret 的 JSON：

```json
{
  "current": {"comment_count": 35, "comments_available": true},
  "previous": {"comment_count": 35}
}
```

然后从仓库根目录运行：

```bash
uv run python scripts/dev/probe_collection_decision.py ./decision.json
```

未显式提供 Capability 时，当前 Probe 默认使用已实现的 `XHS_TIKHUB_CAPABILITY`。该入口只验证
Decision 业务逻辑，不调用 TikHub、不读生产数据库、不产生费用，也不会把 API Key 作为输入。

## Provider Config / Route 独立验证

Provider Config 与平台路由不需要启动完整前后端：

```text
ProviderConfigV1 / System ProviderConfig
→ ProviderRegistry
→ ProviderPlatformRouteV1
→ 当前 ProviderPlatformCapabilityV1
```

当前默认 Registry 只允许 `tikhub + xhs`，并只接受 `https://api.tikhub.io`。同一个 TikHub Provider 类型可以建立多个稳定 UUID 的 Config；两个实例可共享同一 Capability，但历史身份、后续 Budget 和平台引用保持独立。禁用 Config、未知 Provider、不允许 Base URL、尚未实现的平台都必须失败。

## 独立验证

```bash
uv run pytest tests/unit/collection/test_stage7_decision.py tests/unit/collection/test_tikhub_capabilities.py tests/unit/collection/test_stage7_decision_probe.py tests/unit/collection/test_provider_routing.py -q
uv run pytest tests/contracts/test_collection_stage7.py tests/contracts/test_provider_config_stage7.py -q
uv run pytest tests/unit/collection tests/unit/content tests/contracts/test_provider_v1.py -q
uv run pytest tests/integration/collection tests/integration/content tests/integration/database/test_provider_config_repository.py -q
uv run python scripts/contracts/generate.py --check
```

测试从正式 Client、Raw Service、ArtifactService、Decision Service、Provider Registry 和 Local ArtifactStore 等对应生产入口进入。
Fake Transport 不访问网络、不需要 Token、不产生费用；Raw 测试目录位于 Git 忽略的
`.runtime/stage5a-tests/`。Repository 集成测试要求先准备隔离 PostgreSQL 18、Secret 文件并执行
`uv run alembic upgrade head`；独立 `Stage 5B Collection Execution`、
`Stage 5C Provider Persistence`、`Stage 5D Provider Dispatch`、`Stage 6 XHS Vertical Slice` 与
`Stage 7 Provider Config Routing` CI 固定使用 PostgreSQL 18.4。

## 当前限制

- 已有小红书 TikHub App V2 具体 Operation，但没有接入真实生产 HTTP Transport；
- Stage 7 已有通用 Decision/Capability、Provider Config/Route Contract、System `provider_configs` 父事实和
  当前 `tikhub + xhs` Registry；没有把抖音、微博、B站、快手的设计目标冒充当前机器 Capability；
- 当前 Provider Config 只保存 `secret_ref` 并复用 Stage 2 只读 Secret 文件边界；Stage 8 若提供浏览器凭据
  编辑，仍需独立建立安全可写 SecretStore/SecretService，读取接口不得回显原始 Secret；
- XHS `get_note_comments` 当前仍缺合法脱敏非空真实评论 Fixture/Real Probe，虽然正式 Operation 使用
  `latest_v2`，但机器 Capability 暂不声明 `supports_incremental_comment_sort`；评论数增加时先走受控刷新；
- 仅支持 `manual/api/backfill` Run；没有 Plan/Occurrence/Scheduler，因而不支持 `scheduled`；
- 当前 Dispatch 纵切只允许不计费 Attempt 和 Fake Transport；没有最终多级预算预留/结算、真实付费
  Provider、生产网络调用或最终多级预算；Stage 6 只有已存 Raw 回放 Job Handler；
- 只有小红书 Mapper/Candidate/Ingestion/Content/Comment 首个平台纵切，没有其余平台或 Scheduler；
- 没有决定 Raw 的访问、保留、删除、备份和生产容量策略；
- 真实 Provider Probe 默认不进入普通 CI；2026-08-14 的用户授权搜索 Probe 只确认当次 HTTP 200
  空页包装/分页字段，不能用其或 Fake 结果宣称详情、评论或生产平台兼容。本轮尝试的额外只读实调在
  HTTP 发送前即因执行宿主 DNS 无法解析 TikHub 域名而失败，因此没有新增真实接口兼容证据。
