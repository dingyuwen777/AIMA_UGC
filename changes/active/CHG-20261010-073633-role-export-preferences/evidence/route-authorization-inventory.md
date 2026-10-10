# 最终应用 Route 授权清单

本表由最终生产 assembly 的注册事实生成，用于逐接口语义 Review；不代表请求测试已经执行。基线 main `6f9779c56fdb3b4d3a83d8fb0cdd02e4cb9dd79d`，新能力包含个人默认字段与共享数据修订。后续以实际路由、显式 policy 和 CI 回归为准。

| Method | Path | Permission | Backend Owner | Frontend Consumer |
| --- | --- | --- | --- | --- |
| GET | `/openapi.json` | administrator | Platform / FastAPI | 管理员 API 文档 |
| HEAD | `/openapi.json` | administrator | Platform / FastAPI | 管理员 API 文档 |
| GET | `/docs` | administrator | Platform / FastAPI | 管理员 API 文档 |
| HEAD | `/docs` | administrator | Platform / FastAPI | 管理员 API 文档 |
| GET | `/docs/oauth2-redirect` | administrator | Platform / FastAPI | 管理员 API 文档 |
| HEAD | `/docs/oauth2-redirect` | administrator | Platform / FastAPI | 管理员 API 文档 |
| GET | `/redoc` | administrator | Platform / FastAPI | 管理员 API 文档 |
| HEAD | `/redoc` | administrator | Platform / FastAPI | 管理员 API 文档 |
| GET | `/health/live` | public | Platform | 运行探针 |
| GET | `/health/ready` | public | Platform | 运行探针 |
| GET | `/api/v1/collection-capabilities` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/import-batches/{batch_id}/supplement-eligibility` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/data-import-campaigns/{campaign_id}/supplement-eligibility` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/collection-supplements/preview` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/collection-runs` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/collection-runs/{run_id}` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/collection-runs/{run_id}/retry-failed` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/collection-runs/{run_id}/cancel` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/collection-runtime/runs` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/collection-runtime/summary` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/contents` | authenticated | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| POST | `/api/v1/contents/count` | authenticated | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/contents/{content_id}` | authenticated | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/contents/{content_id}/comments` | authenticated | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| PUT | `/api/v1/contents/{content_id}/analysis-review` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| PUT | `/api/v1/contents/{content_id}/vehicles` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| POST | `/api/v1/content-availability-observations` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/export-columns` | authenticated | Reporting | 声音广场导出 / Task Center |
| GET | `/api/v1/me/export-column-default` | authenticated | Reporting | 声音广场导出 / Task Center |
| PUT | `/api/v1/me/export-column-default` | authenticated | Reporting | 声音广场导出 / Task Center |
| GET | `/api/v1/notifications` | authenticated | Identity / Notification | 登录 / AppShell / 个人通知 |
| PUT | `/api/v1/notifications/read` | authenticated | Identity / Notification | 登录 / AppShell / 个人通知 |
| POST | `/api/v1/content-relevance-reviews` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| POST | `/api/v1/content-analysis-requests` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| POST | `/api/v1/analysis/content-runs/preview` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| POST | `/api/v1/analysis/content-runs` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/analysis/content-runs` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/analysis/content-runs/{run_id}` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| POST | `/api/v1/analysis/content-runs/{run_id}/cancel` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/content-analysis-jobs/{job_id}` | administrator | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| POST | `/api/v1/data-exports` | authenticated | Reporting | 声音广场导出 / Task Center |
| GET | `/api/v1/data-exports` | owner_or_administrator | Reporting | 声音广场导出 / Task Center |
| GET | `/api/v1/data-exports/{export_id}` | owner_or_administrator | Reporting | 声音广场导出 / Task Center |
| GET | `/api/v1/data-exports/{export_id}/download` | owner_or_administrator | Reporting | 声音广场导出 / Task Center |
| GET | `/api/v1/historical-import/directories` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/data-import-sources/server/directories` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/historical-import-campaigns` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/data-import-campaigns/server` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/data-import-campaigns/local` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| PUT | `/api/v1/data-import-campaigns/{campaign_id}/items/{item_id}/content` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/data-import-campaigns/{campaign_id}/finalize` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/historical-import-campaigns` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/data-import-campaigns` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/historical-import-campaigns/{campaign_id}` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/data-import-campaigns/{campaign_id}` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/historical-import-campaigns/{campaign_id}/items` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/data-import-campaigns/{campaign_id}/items` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/historical-import-campaigns/{campaign_id}/conflicts` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/data-import-campaigns/{campaign_id}/conflicts` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/historical-import-campaigns/{campaign_id}/start` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/data-import-campaigns/{campaign_id}/start` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/historical-import-campaigns/{campaign_id}/cancel` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/data-import-campaigns/{campaign_id}/cancel` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/historical-import-campaigns/{campaign_id}/retry-failed` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/data-import-campaigns/{campaign_id}/retry-failed` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/canonical-replays` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/canonical-replays/all` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/canonical-replays/{run_id}` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/canonical-replays/{run_id}/cancel` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/canonical-replays/all/{replay_request_id}/cancel-and-revoke` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/canonical-replays/all/{replay_request_id}/revoke` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/import-batches` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/import-batches` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/import-batches/summary` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/import-batches/{batch_id}` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/jobs/{job_id}` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/admin/feishu-report-publications` | administrator | Reporting / Feishu | 管理员报告 |
| POST | `/api/v1/admin/feishu-representative-selections` | administrator | Reporting / Feishu | 管理员报告 |
| GET | `/api/v1/admin/feishu-publication-jobs/{job_id}` | administrator | Reporting / Feishu | 管理员报告 |
| GET | `/api/v1/content-analysis-taxonomy` | authenticated | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/content-filter-options` | authenticated | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/content-data-revision` | authenticated | Workbench | 工作台 / 声音广场只读刷新 |
| GET | `/api/v1/workbench/stream` | authenticated | Workbench | 工作台 / 声音广场只读刷新 |
| GET | `/api/v1/workbench/trend` | authenticated | Workbench | 工作台 / 声音广场只读刷新 |
| GET | `/api/v1/workbench/mind` | authenticated | Workbench | 工作台 / 声音广场只读刷新 |
| GET | `/api/v1/workbench/layout` | authenticated | Workbench | 工作台 / 声音广场只读刷新 |
| PUT | `/api/v1/workbench/layout` | authenticated | Workbench | 工作台 / 声音广场只读刷新 |
| GET | `/api/v1/principal` | authenticated | Identity / Notification | 登录 / AppShell / 个人通知 |
| GET | `/api/v1/provider-configs` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/provider-configs` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| PUT | `/api/v1/provider-configs/{provider_config_id}` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/vehicle-models` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| GET | `/api/v1/vehicle-models` | authenticated | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| GET | `/api/v1/vehicle-models/{vehicle_model_id}` | authenticated | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| PUT | `/api/v1/vehicle-models/{vehicle_model_id}` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| DELETE | `/api/v1/vehicle-models/{vehicle_model_id}` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| POST | `/api/v1/vehicle-models/{vehicle_model_id}/merge` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| POST | `/api/v1/analysis-schemes` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| GET | `/api/v1/analysis-schemes` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| PUT | `/api/v1/analysis-scheme-versions/{version_id}` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/analysis-scheme-versions/{version_id}/publish` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/analysis-scheme-versions/{version_id}/rollback` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| GET | `/api/v1/audit-events` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/keyword-packs` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| GET | `/api/v1/keyword-packs` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/keyword-packs/{pack_id}/keywords` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| GET | `/api/v1/keyword-packs/{pack_id}` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| PUT | `/api/v1/keyword-packs/{pack_id}/enabled` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/collection-plans` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/collection-plans` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/collection-plans/{plan_id}` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| PUT | `/api/v1/collection-plans/{plan_id}/enabled` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/reports/preflight` | administrator | Reporting / Feishu | 管理员报告 |
| POST | `/api/v1/reports` | administrator | Reporting / Feishu | 管理员报告 |
| GET | `/api/v1/reports` | administrator | Reporting / Feishu | 管理员报告 |
| GET | `/api/v1/reports/{report_id}` | administrator | Reporting / Feishu | 管理员报告 |
| POST | `/api/v1/reports/{report_id}/retry` | administrator | Reporting / Feishu | 管理员报告 |
| POST | `/api/v1/reports/{report_id}/publish` | administrator | Reporting / Feishu | 管理员报告 |
| POST | `/api/v1/reports/{report_id}/cancel` | administrator | Reporting / Feishu | 管理员报告 |
| GET | `/api/v1/reports/{report_id}/artifacts/{artifact_id}/download` | administrator | Reporting / Feishu | 管理员报告 |
| POST | `/api/v1/wisersone-downloads` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/wisersone-downloads` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/wisersone-downloads/{download_id}` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/wisersone-downloads/{download_id}/cancel` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/wisersone-downloads/{download_id}/retry` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/content-analysis-capabilities` | authenticated | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/contents/{content_id}/media/{position}` | authenticated | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| POST | `/api/v1/contents/{content_id}/media/{position}/playback/prepare` | authenticated | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/contents/{content_id}/media/{position}/playback/stream` | authenticated | Content / Analysis | 声音广场 / 管理员分析与人工复核 |
| GET | `/api/v1/auth/feishu/login` | public | Identity / Notification | 登录 / AppShell / 个人通知 |
| GET | `/api/v1/auth/feishu/callback` | public | Identity / Notification | 登录 / AppShell / 个人通知 |
| GET | `/api/v1/auth/feishu/{connector_code}/login` | public | Identity / Notification | 登录 / AppShell / 个人通知 |
| GET | `/api/v1/auth/feishu/{connector_code}/callback` | public | Identity / Notification | 登录 / AppShell / 个人通知 |
| GET | `/api/v1/auth/connectors` | public | Identity / Notification | 登录 / AppShell / 个人通知 |
| POST | `/api/v1/auth/logout` | authenticated | Identity / Notification | 登录 / AppShell / 个人通知 |
| GET | `/api/v1/data-import-campaigns/{campaign_id}/revocation-preview` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/data-import-campaigns/{campaign_id}/revoke` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| PUT | `/api/v1/keyword-packs/{pack_id}` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| PUT | `/api/v1/keyword-packs/{pack_id}/keywords/{keyword_id}` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/keyword-packs/{pack_id}/keywords/{keyword_id}/remove` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/keyword-packs/{pack_id}/copy` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/keyword-packs/{pack_id}/archive` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/keyword-packs/{pack_id}/restore` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| GET | `/api/v1/resource-lifecycle/keyword-packs/archived` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| GET | `/api/v1/keyword-packs/{pack_id}/delete-eligibility` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| DELETE | `/api/v1/keyword-packs/{pack_id}` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| PUT | `/api/v1/collection-plans/{plan_id}` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/collection-plans/{plan_id}/copy` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/collection-plans/{plan_id}/archive` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/collection-plans/{plan_id}/restore` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/resource-lifecycle/collection-plans/archived` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| GET | `/api/v1/collection-plans/{plan_id}/delete-eligibility` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| DELETE | `/api/v1/collection-plans/{plan_id}` | administrator | Collection / Processing | 管理员采集运行 / 导入 / 策略 |
| POST | `/api/v1/provider-configs/{provider_config_id}/test-connection` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/provider-configs/{provider_config_id}/archive` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/provider-configs/{provider_config_id}/restore` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| GET | `/api/v1/provider-configs/lifecycle/archived` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| GET | `/api/v1/provider-configs/{provider_config_id}/delete-eligibility` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| DELETE | `/api/v1/provider-configs/{provider_config_id}` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/analysis-schemes/{scheme_id}/copy` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/analysis-schemes/{scheme_id}/archive` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/analysis-schemes/{scheme_id}/restore` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| GET | `/api/v1/analysis-schemes/lifecycle/archived` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| GET | `/api/v1/analysis-schemes/{scheme_id}/delete-eligibility` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| DELETE | `/api/v1/analysis-schemes/{scheme_id}` | administrator | System / Analysis | 管理员配置 / 采集策略 |
| POST | `/api/v1/vehicle-brands` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| GET | `/api/v1/vehicle-brands` | authenticated | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| GET | `/api/v1/vehicle-brands/{brand_id}` | authenticated | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| PUT | `/api/v1/vehicle-brands/{brand_id}` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| DELETE | `/api/v1/vehicle-brands/{brand_id}` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| POST | `/api/v1/vehicle-brands/{brand_id}/aliases` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| DELETE | `/api/v1/vehicle-brands/{brand_id}/aliases/{alias_id}` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| PUT | `/api/v1/vehicle-models/{vehicle_model_id}/brand` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| GET | `/api/v1/vehicle-catalog/readiness` | administrator | Brand / Vehicle | 业务选择目录 / 管理员配置 |
| GET | `/api/v1/vehicle-catalog/snapshot` | authenticated | Brand / Vehicle | 业务选择目录 / 管理员配置 |

实际 Method + Path 共 175 项，包含 include_in_schema=False 媒体路由与框架文档 GET/HEAD。可选注入 Resolver 的装配不安装 OAuth 路由，仍必须逐实际路由归类。对象级权限继续由各 Service 执行；owner_or_administrator 角色检查不能代替 Export SQL 归属过滤。
