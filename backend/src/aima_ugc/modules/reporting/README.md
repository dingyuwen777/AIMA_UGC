# Reporting 模块

Stage 8D 的 Reporting Owner 负责声音广场正式 Excel 导出记录，不负责重新定义 Content、Analysis 或
Excel 字段语义。

```text
HTTP 冻结 Content ID + Version
→ reporting_data_exports / reporting_data_export_items
→ reporting.content-export-excel.v1 durable Job
→ PostgreSQL Read Projection
→ UnifiedDataExcelV1
→ platform/export/excel.py 共享 Exporter
→ ArtifactService / ArtifactStore
→ 受控 HTTP 下载
```

Export 表引用 Job 与 Artifact，不复制 Job 状态。Worker 分页读取冻结版本，只有匹配当前
Prompt/Taxonomy/Provider/Model 的 Analysis 才投影为 AI 字段；未分析或 stale 内容仍导出，AI 字段为空并
计入统计。Artifact 关联事务必须验证当前 Fencing Token。当前没有已批准的自动保留/删除期限，也没有
公网认证；下载仅适用于受信部署边界。
