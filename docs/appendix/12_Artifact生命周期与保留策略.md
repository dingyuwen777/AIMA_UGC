# Artifact 生命周期与保留策略

本文说明 AIMA_UGC 当前对服务器 Artifact **文件字节**的保留、过期和自动清理规则。

长期边界仍由以下文档控制：

- [`docs/blueprint/03_数据库与文件存储.md`](../blueprint/03_数据库与文件存储.md)
- [`docs/blueprint/05_日志安全部署与运维.md`](../blueprint/05_日志安全部署与运维.md)

本文只解释当前 Artifact Lifecycle 的实现细节。

---

## 1. 清理文件字节，不删除业务事实

当前边界保持不变：

```text
PostgreSQL
→ Content / Comment / Version / Metric
→ Job / Run / Import Batch / Export 父事实
→ Provider Request / Attempt
→ Artifact metadata / 来源关系

ArtifactStore
→ Provider Raw
→ Excel 上传源文件
→ Excel 导出文件
→ 其他大文件字节
```

Artifact 到期时只删除 ArtifactStore 中的字节，不因为文件过期删除 Content、Comment、Analysis、Import Batch、Export 请求、Provider Request/Attempt 或 Artifact metadata。

所以：

```text
文件已过期
≠ 导入/导出/采集历史被删除
```

---

## 2. 当前正式保留期限

| Artifact | `kind` | 保留起点 | 字节保留期限 | 过期后 |
| --- | --- | --- | ---: | --- |
| TikHub Provider Raw | `provider-raw` | Artifact 创建时 | 30 天 | 删除 Raw 字节，保留来源和元数据 |
| Excel 上传源文件 | `file-import.raw` | Import 任务进入终态时 | 7 天 | 删除原始 Excel 字节，保留 Batch、入库数据和来源事实 |
| Excel 正式导出文件 | `content-export.xlsx` | Export `completed_at` | 7 天 | 下载失效并删除 Excel 字节，保留 Export 请求和统计 |
| 未建立业务引用的 Excel Import/Export Artifact | 上述两种 Excel kind | Artifact 创建后 | 1 天 | 作为孤儿字节清理 |

这里的 Import 终态包括：

```text
succeeded
failed
cancelled
```

Import 仍处于 queued/running/retry 时不启动 7 天倒计时，因为 Worker 仍可能依赖源 Artifact 重试。

当前 1 天孤儿规则只覆盖能够通过现有业务父事实明确判断“未建立引用”的 Excel Import/Export Artifact。其他未来 Artifact kind 不能只因为长期处于 `stored` 就自动当作孤儿，必须先有可验证的引用关系和恢复语义。

---

## 3. 为什么 Provider Raw 不套用 1 天孤儿规则

Provider Dispatch 有真实崩溃恢复窗口：

```text
HTTP 已返回
→ Raw bytes 已写 ArtifactStore
→ Artifact metadata = stored
→ 进程在 Attempt + Artifact 联动提交前崩溃
```

Recovery 会按确定性 `storage_key` 找回尚未 linked 的 Raw。因此不能把：

```text
stored 超过 1 天
```

机械等同于“孤儿”。当前 `provider-raw` 只按 30 天正式保留期清理，不进入 Excel Import/Export 的 1 天孤儿规则。

---

## 4. Artifact 删除状态机

当前状态机继续复用已有字段：

```text
pending
→ stored
→ linked
→ delete_pending
→ deleted

pending
→ error
```

文件系统和 PostgreSQL 不能组成真正的原子事务，所以清理分三步：

```text
1. PostgreSQL 短事务
   stored / linked → delete_pending

2. 事务外
   ArtifactStore.delete(storage_key)

3. 删除成功后 PostgreSQL 短事务
   delete_pending → deleted
   + deleted_at
```

实体删除失败时保留 `delete_pending`，后续 housekeeping 重试；不能在文件删除失败时先伪造 `deleted`。

Local ArtifactStore 的 `delete()` 是幂等的。如果实例已经删掉文件、但在写 `deleted` 前崩溃，下次重复删除不存在的文件仍视为成功，然后继续收敛元数据。

### 4.1 候选扫描不能直接授权删除

Housekeeping 查询清理候选和真正认领删除之间存在时间窗口。例如：

```text
T1：扫描发现一个 Excel Artifact 尚无业务引用
T2：业务事务建立 Import Batch / Export 引用
T3：housekeeping 开始删除
```

如果 T3 只相信 T1 的候选结果，就可能删除已经变成正式业务输入/输出的文件。

因此当前实现固定为：

```text
候选扫描
→ 只用于批量发现

真正认领 delete_pending
→ 在同一 PostgreSQL UPDATE CAS 中重新检查
   - 当前仍已到期；或
   - 当前仍是无业务引用的 Excel Import/Export 孤儿
```

如果扫描后已经建立正式引用且文件尚未到期，CAS 不成功，本轮放弃删除。反过来，如果 cleanup 已先成功认领 `delete_pending`，后续正常 `stored → linked` 状态转换也会失败并使业务事务回滚，不会形成“业务引用已提交但文件被删除”的状态。

---

## 5. `expires_at` 如何确定

### Provider Raw

新 `provider-raw` 创建时即可写：

```text
expires_at = created_at + 30 days
```

历史 Raw 如果 `expires_at` 为空，由 housekeeping 使用 `stored_at`，必要时回退 `created_at`，补齐 30 天截止时间。

### Excel Import

上传时：

```text
expires_at = null
```

任务仍运行时保持为空。任务终态后使用：

```text
Import terminal_at + 7 days
```

`terminal_at` 优先使用 `processing_import_batches.finished_at`；如果 Batch 因取消语义没有独立结束时间，则使用对应终态 Job 的 `finished_at`。只要同一个输入 Artifact 仍有未终态 Import 引用，就不会开始清理倒计时。

### Excel Export

创建文件时先保持：

```text
expires_at = null
```

Export 成功关联 Artifact 后，由 housekeeping 使用：

```text
reporting_data_exports.completed_at + 7 days
```

前端也使用同一个公开 `completed_at + 7 天` 规则，因此界面显示的“下载有效期至”与后端实际清理/下载拒绝时间一致。

### 历史 Artifact

上线前已经存在且 `expires_at = null` 的正式 Artifact 会按上述同一规则幂等补齐。

因此部署该版本后，已经超过新保留期限的历史文件可能在首次或后续 housekeeping 中立即进入清理。回滚代码不能恢复已经删除的字节；生产部署前如需另行保留超期历史文件，应先按正式 Backup/Restore 方案处理。

---

## 6. Housekeeping 怎样运行

不新增 Cron Sidecar、Celery、Redis 或独立 Cleanup Service，复用已有 Scheduler 进程：

```text
Scheduler 主循环
→ Collection Plan tick 保持原逻辑
→ Artifact housekeeping 最多每小时一次
```

每轮：

```text
补齐历史 expires_at
→ 查询有限数量候选
→ CAS 重新核对当前删除资格并认领 delete_pending
→ 事务外删文件
→ mark_deleted
→ 失败留待后续重试
```

housekeeping 属于辅助运维任务。它自身发生未预期异常时会记录 `artifact.cleanup.failed`，但不能终止 Collection Scheduler 主循环。

主要日志事件：

```text
artifact.cleanup.completed
artifact.cleanup.failed
artifact.cleanup.delete_failed
artifact.cleanup.backend_mismatch
```

日志不得记录 Raw、Excel 内容、Secret 或未脱敏业务 Payload。

---

## 7. 写入确认失败时为什么不能直接删文件

Artifact 写入是分阶段的：

```text
metadata pending
→ Store 写字节
→ metadata mark_stored
```

`mark_stored` 报错并不一定表示数据库没有提交；可能是数据库已经提交，但调用方没有收到确认。

因此规则是：

```text
mark_stored 失败
→ 尝试 pending -> error CAS

CAS 成功
→ 能证明元数据仍是 pending
→ 可以回收刚写入字节

CAS 失败
→ 可能 stored 已经提交
→ 保守保留字节
```

不能为了“清孤儿”在事务结果未知时主动制造数据丢失。

---

## 8. 前端怎样展示

### Excel Import

位置：采集运行中心的 Excel Import Batch 详情。

运行中显示：

```text
源 Excel 会在任务进入终态后继续保留 7 天，处理和重试期间不会提前清理。
```

进入终态后显示实际截止时间；过期后明确说明文件进入自动清理，但 Batch、入库数据和来源元数据继续保留。

取消任务如果 Batch 自身没有 `finished_at`，前端使用终态 Job 的 `finished_at`，与后端保留时间语义一致。

### Excel Export

位置：声音广场的导出记录。

显示：

```text
下载有效期至 YYYY-MM-DD HH:mm
```

到期后：

```text
下载已过期
按钮禁用
需要重新创建导出
```

后端下载接口同时执行过期守卫，所以不能只通过绕过前端按钮继续下载超期文件。

### Provider Raw

不新增普通业务前端入口。Raw 属于采集恢复、审计和排障证据，按后台 30 天策略自动清理。

---

## 9. 运维与回滚边界

### Scheduler 必须运行

TTL 不是由文件系统自动执行。自动物理删除依赖 Scheduler 进程持续运行 housekeeping。

Scheduler 短暂停机不会导致业务数据损坏，只会延后文件删除；恢复后再次扫描并收敛。

### 清理是不可逆的文件操作

```text
代码回滚
≠ 已删除 Artifact 字节恢复
```

因此生产部署时需要意识到：首次启用保留策略后，历史超期 Artifact 可能被删除。

完整 PostgreSQL + Artifact 协调 Backup/Restore 仍属于生产上线后续正式能力，本功能不伪造已经完成该能力。

---

## 10. 实现入口

核心代码：

- [`backend/src/aima_ugc/platform/storage/retention.py`](../../backend/src/aima_ugc/platform/storage/retention.py)
- [`backend/src/aima_ugc/platform/storage/service.py`](../../backend/src/aima_ugc/platform/storage/service.py)
- [`backend/src/aima_ugc/platform/storage/ports.py`](../../backend/src/aima_ugc/platform/storage/ports.py)
- [`backend/src/aima_ugc/adapters/storage/local/store.py`](../../backend/src/aima_ugc/adapters/storage/local/store.py)
- [`backend/src/aima_ugc/adapters/persistence/postgres/artifact_metadata.py`](../../backend/src/aima_ugc/adapters/persistence/postgres/artifact_metadata.py)
- [`backend/src/aima_ugc/bootstrap/artifact_cleanup.py`](../../backend/src/aima_ugc/bootstrap/artifact_cleanup.py)
- [`backend/src/aima_ugc/entrypoints/scheduler_main.py`](../../backend/src/aima_ugc/entrypoints/scheduler_main.py)
- [`backend/src/aima_ugc/bootstrap/reporting_http.py`](../../backend/src/aima_ugc/bootstrap/reporting_http.py)

前端：

- [`frontend/src/shared/artifactRetention.ts`](../../frontend/src/shared/artifactRetention.ts)
- [`frontend/src/features/import-batches/pages/CollectionRuntimePage/components/ImportBatchDetailDrawer.vue`](../../frontend/src/features/import-batches/pages/CollectionRuntimePage/components/ImportBatchDetailDrawer.vue)
- [`frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/DataExportDialog.vue`](../../frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/DataExportDialog.vue)

关键验证：

- [`tests/unit/platform/test_artifact_retention.py`](../../tests/unit/platform/test_artifact_retention.py)
- [`tests/unit/platform/test_artifact_service_failure_recovery.py`](../../tests/unit/platform/test_artifact_service_failure_recovery.py)
- [`tests/unit/platform/test_artifact_cleanup_scheduler.py`](../../tests/unit/platform/test_artifact_cleanup_scheduler.py)
- [`tests/unit/platform/test_export_download_retention.py`](../../tests/unit/platform/test_export_download_retention.py)
- [`tests/integration/database/test_artifact_retention_repository.py`](../../tests/integration/database/test_artifact_retention_repository.py)
- [`frontend/tests/artifact-retention.spec.ts`](../../frontend/tests/artifact-retention.spec.ts)
- [`frontend/e2e/artifact-retention.spec.ts`](../../frontend/e2e/artifact-retention.spec.ts)
