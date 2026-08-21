# AIMA_UGC

AIMA_UGC 是爱玛舆情监控系统的新一代实现。它把多平台采集、Excel 手工导入、统一入库、AI 分析、查询展示和数据导出放在一套可追溯、可恢复的技术主链里。

如果你第一次接触这个仓库，不需要先理解所有框架名。先记住这条主线：

```text
TikHub / Excel / 其他来源
→ 保留原始证据
→ 转成系统统一数据
→ 去重、保存历史
→ PostgreSQL
→ AI 分析 / 查询 / 导出 / 报告
→ Vue 页面
```

## 1. 当前已经实现什么

### 数据采集与导入

- TikHub 五个平台：小红书、抖音、微博、B站、快手；
- 定时 Collection Plan + Scheduler；
- 手工 TikHub 调试入口 `tikhub_test`；
- Excel 文件正式导入；
- Excel 离线调试/处理入口 `imports_test`；
- Provider Raw、Request/Attempt、Candidate、来源追溯。

### 数据存储

- PostgreSQL 18；
- 账号、内容、评论 Current；
- 内容/评论版本历史；
- 点赞、评论、播放等 Metric Observation；
- Processing Import Batch；
- 持久化 Job；
- Analysis 和正式 Excel Export 业务表。

### 业务处理

- 统一 Relevance Keyword Pack；
- AI Semantic Relevance；
- 发声类型 `voice_type`；
- 情感；
- 一级/二级舆情标签；
- 正式 Excel Export；
- 离线 `report.md + report.docx` 舆情报告。

### 前端

当前已经有正式业务页面/Feature，包括：

```text
analysis
export
import-excel
jobs
keyword-planning
overview
providers
runs
settings
voice-plaza
```

所以当前前端**不是只有 health demo**。

## 2. 当前还没有完成什么

以下能力仍不能写成已实现：

- 企业登录/正式认证授权；
- 完整离线生产 Release 闭环；
- PostgreSQL + Artifact 协调 Backup/Restore 写屏障；
- Stage 9 中尚未正式开发的 Monitoring 业务，例如告警、VOC/工单等。

当前 Stage 1—7、临时 P1、Stage 8A—8F 已闭环；下一正式方向是 **Stage 9 Analysis and Monitoring**。

Stage 名称只是开发导航。某个功能是否真的存在，仍要看当前代码、Migration、Contract 和测试。

## 3. 一条数据怎样进入系统

### TikHub 正式采集

```text
Collection Plan / Run / Scope
→ Provider Request / Attempt
→ Raw Artifact
→ Candidate
→ Mapper
→ Canonical
→ Relevance
→ Ingestion
→ Content Owner
→ PostgreSQL
```

### Excel 正式导入

```text
Input Artifact
→ Processing Import Batch
→ Provider Request / Attempt
→ Excel Reader / Mapper
→ Canonical
→ Relevance
→ 同一个 Ingestion / Content Owner
→ PostgreSQL
```

两种入口在 Canonical 之后共享同一套业务去重、版本和指标历史逻辑。

更详细的白话说明见 [`docs/appendix/数据入口与统一入库.md`](docs/appendix/数据入口与统一入库.md)。

## 4. 为什么有 Raw、Canonical 和 Ingestion

### Raw

保存第三方当时真实返回的原始证据。Mapper 写错时可以重新回放，不需要重新付费调用 Provider。

### Canonical

把“小红书字段、抖音字段、Excel 列”转换成系统统一语言。

### Ingestion

负责真正写数据库：

- 同一内容身份去重；
- Current 更新；
- Version；
- Metric Observation；
- 来源关系；
- 字段 freshness。

因此 Provider 不能直接写 `contents`，Mapper 也不能自己查数据库判断重复。

## 5. 为什么耗时任务要走 Job

Excel 导入、TikHub 采集、AI、导出都可能运行很久。

当前使用 PostgreSQL 持久 Job：

```text
API 创建 Job
→ 立即返回
→ Worker 后台认领
→ Lease / Heartbeat / Deadline / Fencing
→ 更新进度和结果
```

即使浏览器关闭或 Worker 重启，任务事实仍在数据库里。

Scheduler 只负责把到期计划变成 Occurrence/Run/Job，不直接请求 TikHub。

## 6. AI 当前怎么工作

当前 Content Labeling V3 一次模型调用完成：

```text
relevance
voice_type
sentiment
labels
```

`voice_type` 是发声类型唯一业务事实：

```text
professional_media
influencer_self_media
ordinary_user
```

不再同时保存一个重复的“是否真实用户发声”布尔字段。

完整 taxonomy / Prompt 的唯一业务事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md
```

白话说明见 [`docs/appendix/AI舆情分析与打标.md`](docs/appendix/AI舆情分析与打标.md)。

## 7. 文档应该怎么找

### 第一次进入仓库

按顺序读：

1. [`AGENTS.md`](AGENTS.md) — 所有开发和 Agent 的统一规则；
2. [`.agents/skills/reliable-vibe-coding/SKILL.md`](.agents/skills/reliable-vibe-coding/SKILL.md) — 任务分级、Change、开发和验证流程；
3. [`docs/blueprint/README.md`](docs/blueprint/README.md) — 核心架构导航；
4. [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md) — 已确认的跨模块决定；
5. 再按任务读取对应模块、Contract、Migration、实现和测试。

### 文档分层

```text
docs/blueprint/
→ 长期架构：为什么这样设计

模块 README
→ 当前代码：具体在哪里、怎么实现

docs/appendix/
→ 专题细节：SQL、Scheduler、TikHub、Excel、AI、Word 报告

docs/guides/
→ 开发工作流：例如 Figma

docs/collection/
→ 五个平台当前采集实现

代码 / Contract / Migration / generated / tests / locks
→ 精确机器事实

changes/archive/
→ 历史为什么改过
```

## 8. 常用专题入口

| 想解决的问题 | 文档 |
| --- | --- |
| 看整体架构 | [`docs/blueprint/01-总体架构与技术选型.md`](docs/blueprint/01-总体架构与技术选型.md) |
| 理解 Raw / Mapper / Canonical / Ingestion | [`docs/blueprint/02-采集系统与数据标准化.md`](docs/blueprint/02-采集系统与数据标准化.md) |
| 理解数据库设计 | [`docs/blueprint/03-数据库与文件存储.md`](docs/blueprint/03-数据库与文件存储.md) |
| API / Job / 前端怎么协作 | [`docs/blueprint/04-后端任务API与前端.md`](docs/blueprint/04-后端任务API与前端.md) |
| 日志、安全、部署 | [`docs/blueprint/05-日志安全部署与运维.md`](docs/blueprint/05-日志安全部署与运维.md) |
| 开发、测试、CI、Git | [`docs/blueprint/06-开发约束与分阶段实施.md`](docs/blueprint/06-开发约束与分阶段实施.md) |
| 当前已确认硬决定 | [`docs/blueprint/07-技术决策与实施门禁.md`](docs/blueprint/07-技术决策与实施门禁.md) |
| 采集策略/Provider/评论 | [`docs/blueprint/08-采集策略与平台能力.md`](docs/blueprint/08-采集策略与平台能力.md) |
| PostgreSQL 查询/调试 | [`docs/appendix/PostgreSQL调试与常用SQL.md`](docs/appendix/PostgreSQL调试与常用SQL.md) |
| Scheduler 恢复 | [`docs/appendix/Scheduler运行与恢复.md`](docs/appendix/Scheduler运行与恢复.md) |
| TikHub 真实响应 | [`docs/appendix/TikHub真实响应结构.md`](docs/appendix/TikHub真实响应结构.md) |
| TikHub 接口选型 | [`docs/appendix/TikHub接口验证与选型台账.md`](docs/appendix/TikHub接口验证与选型台账.md) |
| Excel 导入/导出/离线处理 | [`docs/appendix/Excel导入导出与离线处理.md`](docs/appendix/Excel导入导出与离线处理.md) |
| AI 打标 | [`docs/appendix/AI舆情分析与打标.md`](docs/appendix/AI舆情分析与打标.md) |
| Word 舆情报告 | [`docs/appendix/Word舆情报告.md`](docs/appendix/Word舆情报告.md) |
| Figma 工作流 | [`docs/guides/前端与Figma工作流.md`](docs/guides/前端与Figma工作流.md) |
| HTTP API | [`docs/API接口说明.md`](docs/API接口说明.md) |
| 测试与调试 | [`docs/测试与调试说明.md`](docs/测试与调试说明.md) |
| 环境与部署 | [`docs/环境运行与部署.md`](docs/环境运行与部署.md) |

## 9. 仓库目录

```text
AIMA_UGC/
├─ AGENTS.md
├─ pyproject.toml
├─ uv.lock
├─ backend/src/aima_ugc/
│  ├─ entrypoints/      进程/API入口
│  ├─ bootstrap/        生产装配
│  ├─ modules/          业务模块
│  ├─ platform/         Job/Artifact/日志/数据库等基础设施
│  ├─ adapters/         Provider/PostgreSQL 等外部实现
│  └─ contracts/        手写 Pydantic 契约
├─ frontend/src/
│  ├─ app/
│  ├─ pages/
│  ├─ features/
│  ├─ shared/
│  └─ generated/api/
├─ migrations/versions/
├─ contracts/
├─ tests/
├─ scripts/
├─ docs/
│  ├─ blueprint/
│  ├─ appendix/
│  ├─ guides/
│  └─ collection/
└─ changes/
```

## 10. 本地开发

本地配置模板：

```text
env.local.example
```

其中只放非敏感配置。PostgreSQL 密码、LLM API Key、Cursor signing key 等 Secret 通过 `AIMA_SECRET_DIR` 下的只读文件提供，不提交 Git。

详细安装、Windows 一键初始化、本地 API/Vite/PostgreSQL 启动方式见：

[`docs/环境运行与部署.md`](docs/环境运行与部署.md)

不要从 README 复制旧版本号或旧命令；实际版本由：

```text
.python-version
.node-version
.uv-version
pyproject.toml
uv.lock
frontend/package.json
frontend/package-lock.json
```

维护。

## 11. 测试与质量门禁

仓库已有后端 Unit/Contract/API/Integration、PostgreSQL Migration、前端 Unit/E2E、架构检查、表 Owner 检查、Secret 扫描和文档检查。

常用入口：

```bash
uv run ruff format --check backend tests scripts
uv run ruff check backend tests scripts
uv run mypy backend/src
uv run pytest tests/unit -q
uv run pytest tests/contracts -q
uv run pytest tests/api -q
python scripts/quality/check_architecture.py
python scripts/quality/check_table_ownership.py
python scripts/quality/scan_secrets.py
python scripts/quality/check_docs.py
```

前端准确命令以 `frontend/package.json` 为准。

任何“完成、修复、可合并”的结论都必须基于当前分支最新代码的实际验证结果，不能复用旧 CI 结论。

## 12. 当前关键边界

### 数据库

- PostgreSQL 是唯一业务事实库；
- 一个表只有一个写 Owner；
- 正式结构变化用 Alembic；
- 不用文档维护第二套 DDL。

### Provider

- Provider 不直接写业务表；
- 一个 Attempt 最多一次真实发送；
- 完整 Raw 存在时优先 replay；
- 当前不自动跨 TikHub API family fallback。

### 预算

Provider 和 LLM 都可以记录费用事实，但当前没有请求次数/金额 Budget Guard。

### 认证

正式企业认证尚未完成，不能把当前业务 API 直接描述成已具备公网生产权限控制。

### 发布与恢复

完整离线 Release 和 PostgreSQL + Artifact 协调 Backup/Restore 尚未闭环。

## 13. 文档与代码冲突怎么办

不要简单“以文档为准”或“以代码为准”。

```text
先读当前代码 / Contract / Migration / 测试
→ 再看已批准决策
→ 判断是代码偏离设计，还是文档过期
→ 同一任务修正正确的一方
```

旧聊天、模型记忆和历史 Stage 文档不能替代当前仓库事实。
