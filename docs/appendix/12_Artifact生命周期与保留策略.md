# Artifact 生命周期与保留策略

本文说明 AIMA_UGC 当前对服务器 Artifact 字节的保留、过期和自动清理规则。

长期边界仍由：

- [`../blueprint/03_数据库与文件存储.md`](../blueprint/03_数据库与文件存储.md)
- [`../blueprint/05_日志安全部署与运维.md`](../blueprint/05_日志安全部署与运维.md)

控制。本文只解释当前已经实现的 Artifact Lifecycle 细节。

---

## 1. 先区分“业务事实”和“文件字节”

当前系统继续遵守：

```text
PostgreSQL
→ Content / Comment / Version / Metric
→ Job / Run / Import Batch / Export 父事实
→ Provider Request / Attempt
→ Artifact metadata / 业务关系

ArtifactStore
→ Provider Raw
→ Excel 上传原文件
→ Excel 导出文件
→ 其他大文件字节
```

Artifact 到期清理只删除 **ArtifactStore 中的字节**，不会因为文件过期而删除：

- Content / Comment；
- Content Version / Metric；
- Import Batch；
- Export 请求记录；
- Provider Request / Attempt；
- Analysis；
- Artifact 元数据和已有来源关系。

因此“文件已经过期”不等于“这次导入、导出或采集的历史不存在”。

---

## 2. 当前正式保留期限

| Artifact | `kind` | 保留起点 | 字节保留期限 | 过期后 |
| --- | --- | --- | ---: | --- |
| TikHub Provider Raw | `provider-raw` | Raw Artifact 创建/存储时 | 30 天 | 删除 Raw 字节，保留 Provider/Content 来源事实与 Artifact metadata |
| Excel 上传源文件 | `file-import.raw` | Import Batch 进入终态时 | 7 天 | 删除原始 Excel 字节，保留 Batch、已入库数据和来源事实 |
| Excel 正式导出文件 | `content-export.xlsx` | 导出文件生成完成时 | 7 天 | 下载失效并删除 Excel 字节，保留 Export 请求和统计；需要时重新导出 |
| 未建立业务引用的 Excel Import/Export Artifact | 上述两种 Excel kind | 创建后 | 1 天 | 作为孤儿字节清理 |

这里的“Import Batch 终态”包括：

```text
succeeded
failed
cancelled
```

Import 仍处于 queued/running/retry 期间时，源 Excel **没有 7 天倒计时**，因为 Worker 需要依赖这个 Artifact 完成重试和恢复。

---

## 3. 为什么 Provider Raw 不使用“1 天孤儿”规则

Provider Dispatch 存在崩溃恢复窗口：

```text
HTTP 已返回
→ Raw bytes 已写入 ArtifactStore
→ Artifact metadata = stored
→ 进程在 Provider Attempt + Artifact 联动提交前崩溃
```

此时 Provider Recovery 会根据确定性 `storage_key` 找回尚未 linked 的 Raw，并继续收敛 Attempt。

所以不能写成：

```text
所有 stored 且 1 天未 linked
→ 删除
```

否则会破坏 Provider Recovery。

当前规则是：

```text
provider-raw
→ 不进入 1 天 Excel 孤儿规则
→ 只按 30 天正式保留期清理
```

这比按 `storage_status=stored` 机械判定“孤儿”更安全。

---

## 4. Artifact 状态机

当前 `artifacts.storage_status` 已经支持：

```text
pending
→ stored
→ linked
→ delete_pending
→ deleted

pending
→ error
```

清理不是“数据库和文件一次事务删除”，因为文件系统 I/O 不能和 PostgreSQL 形成真正原子事务。

实际流程：

```text
1. PostgreSQL 短事务
   stored / linked
   → delete_pending

2. 事务外
   ArtifactStore.delete(storage_key)

3. 删除成功后 PostgreSQL 短事务
   delete_pending
   → deleted
   + deleted_at
```

如果第 2 步失败：

```text
delete_pending 保持不变
→ 后续 housekeeping 重试
```

绝不能出现：

```text
实体文件删除失败
但数据库先写 deleted
```

否则会制造“数据库说文件不存在、磁盘却还占空间”的假状态。

Local ArtifactStore 的 `delete()` 是幂等的：上一次实例已经删掉实体文件、但在写 `deleted` 前崩溃时，下一次重试删除同一个不存在的文件仍视为成功，然后继续收敛元数据。

---

## 5. `expires_at` 如何产生

### 5.1 新 Provider Raw

创建 Artifact 时直接写：

```text
expires_at = created_at + 30 days
```

### 5.2 新 Excel Export

导出 Artifact 生成时直接写：

```text
expires_at = created_at + 7 days
```

`created_at` 与实际导出完成阶段只相差文件持久化/关联所需的极短时间，当前不为此再增加一套第二截止时间字段。

### 5.3 Excel Import

上传时不立即写 7 天截止时间：

```text
上传
→ expires_at = null
→ Worker 允许持续重试

Batch finished_at 出现
→ expires_at = finished_at + 7 days
```

### 5.4 历史 Artifact

上线该能力前已经存在的 Artifact 可能：

```text
expires_at = null
```

Scheduler housekeeping 会幂等补齐：

```text
历史 provider-raw
→ stored_at / created_at + 30 days

历史 content-export.xlsx
→ stored_at / created_at + 7 days

历史 file-import.raw
→ 对应 processing_import_batches.finished_at + 7 days
```

因此部署该版本后，**已经超过新保留期限的历史文件可能在第一次或后续 housekeeping 中立即进入清理**。这是用户已确认保留策略的正常结果，不是延迟 30/7 天后才从新版本部署日开始计算。

生产升级前如果仍需要保留某些超期历史字节，应先按生产 Backup/Restore 方案另行留存；不能依赖回滚代码恢复已经删除的文件。

---

## 6. Housekeeping 如何运行

当前不新增 Cron Sidecar、Celery、Redis 或独立 Cleanup Service。

复用已有 Scheduler 进程：

```text
Scheduler 主循环
→ Collection Plan tick 仍按原频率执行
→ Artifact housekeeping 最多每小时执行一次
```

Housekeeping 每次：

```text
补齐历史 expires_at
→ 查询有限数量候选
→ 逐条 CAS 认领 delete_pending
→ 事务外删文件
→ mark_deleted
→ 失败留待下次重试
```

一次候选数量有界，避免在一个 Scheduler tick 内无界扫描/删除大量历史文件。

清理日志使用现有结构化日志体系，主要事件：

```text
artifact.cleanup.completed
artifact.cleanup.delete_failed
artifact.cleanup.backend_mismatch
```

不记录 Raw 内容、Excel 内容、Secret 或用户敏感 Payload。

---

## 7. Excel Import 前端怎样显示

现有入口：

```text
采集运行中心
→ Excel Import Batch
→ 批次详情
```

当前展示规则：

```text
任务未终态
→ “源 Excel 会在任务进入终态后继续保留 7 天”

任务已终态、尚未到期
→ 显示精确“保留至 YYYY-MM-DD HH:mm”

已经超过保留期
→ 提示原文件进入自动清理
→ 同时明确 Batch、入库数据、来源元数据仍保留
```

前端截止时间来自现有公开 Contract 的 `finished_at + 7 天`，不新增第二套 API 字段。

---

## 8. Excel Export 前端怎样显示

现有入口：

```text
声音广场
→ 导出记录
```

当前展示：

```text
导出成功且未到期
→ “下载有效期至 …”
→ 下载按钮可用

超过 completed_at + 7 天
→ “下载已过期”
→ 下载按钮禁用
→ 用户可以重新创建导出
```

后端下载接口同时执行 7 天有效期判断，所以即使绕过前端直接请求过期下载 URL，也不会继续提供过期 Artifact。

当前为保持公共 Error Contract 兼容，过期的直接下载仍走既有 `DataExportNotReady` 失败边界；前端会在请求前给出更明确的“已过期”状态。

---

## 9. 关键代码位置

保留策略：

```text
backend/src/aima_ugc/platform/storage/retention.py
```

Artifact 状态/Port/Service：

```text
backend/src/aima_ugc/platform/storage/models.py
backend/src/aima_ugc/platform/storage/ports.py
backend/src/aima_ugc/platform/storage/service.py
```

Local Store：

```text
backend/src/aima_ugc/adapters/storage/local/store.py
```

PostgreSQL 元数据/清理候选：

```text
backend/src/aima_ugc/adapters/persistence/postgres/artifact_metadata.py
```

Housekeeping：

```text
backend/src/aima_ugc/bootstrap/artifact_cleanup.py
backend/src/aima_ugc/entrypoints/scheduler_main.py
```

Excel Import 前端：

```text
frontend/src/features/import-batches/pages/CollectionRuntimePage/components/ImportBatchDetailDrawer.vue
```

Excel Export 前端：

```text
frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/DataExportDialog.vue
```

共享前端期限计算：

```text
frontend/src/shared/artifactRetention.ts
```

---

## 10. 修改这些规则时的门禁

保留期限和删除语义属于不可逆数据行为。

以后如果要修改：

```text
30 天
7 天
1 天
删除对象范围
保留起点
```

必须先确认业务决定，再同步：

```text
Artifact retention policy
→ PostgreSQL cleanup query/state flow
→ Scheduler housekeeping
→ Backend download behavior
→ Frontend copy/state
→ Tests
→ 本文档
```

不得只改前端文字，也不得只改 Scheduler 常量。

---

## 11. 与 Backup/Restore 的关系

Artifact Retention 解决的是：

> 在线运行目录不要无限增长。

它不等于生产 Backup/Restore。

生产协调恢复仍要求：

```text
PostgreSQL
+ ArtifactStore
→ 协调 Backup Set
```

已经过 Retention 正常删除的在线 Artifact 不应因为数据库 metadata 仍保留，就被误认为可以从在线 Store 恢复。

完整 Production Backup/Restore 仍按：

- [`11_生产部署与离线Release方案.md`](11_生产部署与离线Release方案.md)
- [`../roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md)

推进。
