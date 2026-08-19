---
id: CHG-20260819-stage8-ingestion-blueprint
title: 固化 Stage 8 统一数据入口与业务前端实施方案
level: L3
status: done
owner: AI coding agent
branch: main
base_branch: main
created_at: 2026-08-19
updated_at: 2026-08-19
affected_paths:
  - docs/blueprint/README.md
  - docs/blueprint/17-Stage8数据入口统一入库与业务前端实施.md
rollback:
  strategy: revert
  note: 本 Change 只固化长期设计与阶段导航；如需撤回使用普通 Git revert，不修改代码、Contract、Migration 或锁文件。
---

# 固化 Stage 8 统一数据入口与业务前端实施方案

## 1. 背景

Stage 1—7 已完成正式 TikHub Collection/Scheduler/Worker/PostgreSQL 纵切，P1 已完成不依赖数据库的 Excel 导入、关键词清洗、稳定身份去重、AI 打标、checkpoint 与统一 Excel Exporter。Stage 8 是下一正式阶段。

用户确认了 Stage 8 的产品主链：

```text
Excel 手工导入 = 第一版主要数据入口
TikHub          = 辅助补充来源
PostgreSQL      = 唯一业务事实库
```

同时确认：

- `imports_test` 和 `tikhub_test` 永久保留；
- 两个调试入口默认继续只保存文件、不要求数据库；
- 手工运行时应提供显式可选的数据库写入模式；
- 开启写库时仍保留文件，并假定开发机已经有可访问的 PostgreSQL 18 数据库实例/容器；
- 调试代码不负责启动/停止数据库容器，也不自动执行 Migration；
- Excel/TikHub 归一化成 Canonical 后必须复用同一个 ContentIngestionService/PostgresContentRepository，禁止各建数据库 Writer；
- 采用方案 B：Processing/Import Batch 作为 Excel 主入口的用户可理解父记录，最终 Content/Comment 仍归现有 Content Owner。

## 2. 仓库事实核对

本 Change 创建前核对：

- `imports_test/test.py` 当前通过正式 Excel Reader/Mapper、过滤、去重、Analysis 与 Exporter 形成离线文件链，不使用数据库；
- `tikhub_test/README.md` 当前明确为脱离数据库的五平台测试/调试入口，保存 Raw/Canonical/Excel/run summary；
- Excel Mapper 当前输出 `CanonicalContentV1`；
- `ContentIngestionService` 当前声明为 Canonical 摄取唯一生产入口；
- `PostgresContentRepository` 是 Content PostgreSQL 唯一写入口，并按内容稳定身份收敛；
- 当前持久化 Canonical 仍要求合法 `provider_attempt_id + raw_artifact_id`，因此 Stage 8 文件导入不能伪造来源 ID 或删除来源校验；
- 当前正式 OpenAPI 仍只有 health 接口，Figma 目标页的业务能力不能当成已实现 API。

## 3. 方案比较与决定

### 方案 A：Excel/TikHub 各自写数据库

拒绝。会复制去重、版本、指标、来源和事务语义，长期必然漂移。

### 方案 B：统一 Canonical → Content Ingestion，并增加 Processing/Import Batch

采用。

```text
Excel / TikHub / 未来其他来源
→ 各自 Reader/Adapter/Mapper
→ Canonical
→ ContentIngestionService
→ PostgresContentRepository
→ PostgreSQL
```

Processing/Import Batch 只负责一次文件主导处理的执行身份、阶段、统计、错误和关联 Job/Run/Artifact，不复制 Content/Comment 业务数据。

### 方案 C：前端把文件任务、TikHub Run、AI Job 自己拼成统一状态

拒绝。会让 Vue 成为业务编排层并产生第二套状态语义。

## 4. 已固化设计

新增：

```text
docs/blueprint/17-Stage8数据入口统一入库与业务前端实施.md
```

作为 Stage 8 数据入口/统一入库/手工调试可选写库/首个业务页面能力映射/8A—8F 实施顺序的唯一详细长期事实源。

更新 Blueprint README：

- 增加 Blueprint 17 导航和索引；
- Stage 8 事实恢复顺序优先读取 17；
- 当前状态明确 Stage 8 目标设计已批准但尚未实现；
- 文档修改规则增加 17 的 Owner 边界。

## 5. 兼容性与非目标

本 Change 不：

- 修改 `imports_test` / `tikhub_test` 代码；
- 删除或改变现有文件-only 默认行为；
- 创建 Processing/Import Batch 表；
- 修改现有 Migration；
- 修改 Canonical Contract；
- 修改 ContentIngestionService/PostgresContentRepository；
- 新增 `WRITE_TO_DATABASE` 实际配置；
- 修改 OpenAPI/生成 Client；
- 实现采集运行中心页面；
- 把 P1 AI 标签塞入 `contents`；
- 启动 Stage 8A 代码实现。

这些属于后续 Stage 8A 及以后正式 Change 的实现范围。

## 6. 下一正式单元

下一步固定从：

```text
Stage 8A：Unified Manual Ingestion Foundation
```

开始。

8A 必须优先解决：

1. Processing/Import Batch 最小业务边界；
2. 文件 Source Artifact / Attempt / Candidate 如何满足现有正式来源链；
3. Excel/TikHub 手工可选写库并保持默认 file-only；
4. 写库时假定本地 PostgreSQL 18 容器/实例已运行，调试入口不管理容器/Migration；
5. Excel/TikHub 跨来源同身份内容在同一 PostgreSQL Content 收敛；
6. 文件成功而 DB 失败后的幂等重试；
7. 真实 PostgreSQL Integration、Migration（若需要）与完整来源链测试。

## 7. 验证边界

本 Change 是纯设计文档固化，不伪造运行代码或 TDD 结果。

交付前应验证：

- Git 变更只涉及 Blueprint 17、Blueprint README 和本归档 Change；
- README 的 Blueprint 17 相对链接与文件名一致；
- 17 对 02/03/04/06/07/13/15/16 的相对链接存在；
- Stage 8 当前下一单元仍明确为 8A，而不是把目标设计写成已实现；
- 文档没有修改当前技术版本、OpenAPI、Schema、Migration 或运行代码事实。
