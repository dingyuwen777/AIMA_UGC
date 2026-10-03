---
schema: coding-change/v1
id: CHG-20261003-111428-wisersone-import
title: WisersOne 下载与统一导入接入
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/700-wisersone-import
created: 2026-10-03
updated: 2026-10-03
completion_gate: required
depends_on: []
affected_areas: [backend, frontend, deployment, docs]
affected_paths: [backend/src/aima_ugc, frontend/src, migrations, tests, Dockerfile, compose.yaml, compose.windows.yaml, scripts/deploy, docs]
contracts: [WisersOne HTTP/Job, generated HTTP clients]
data_changes: [WisersOne download lifecycle migration]
---

# 变更摘要

把已有独立 WisersOne 过去 24 小时下载能力接入系统，持久保存刷新登录态，并复用统一 Data Import Pipeline。上游要求见 #700。

# 背景、现状与问题

## 背景

用户要求本地及 Linux 无 UI 运行成功后直接合并。初始两份 JSON 随代码公开打包是用户获告知后的明确例外。

## 当前现状

根工程已有 Playwright 1.62.0；正式容器尚无浏览器。现有 server_path 默认 historical_fill_only，统一导入已有 Source 与 Canonical Artifact。

## 问题、根因或约束

独立脚本没有 PG 任务/租约/恢复/导入接线；刷新状态随代码替换会失效。慢网站导出不能占用一个无限 attempt。

## 不修改的后果

持续依赖人工拷贝文件，容器和升级后的登录态不可验证。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 独立脚本显式选择过去24小时并无限轮询网站任务 | 原脚本 download_wisersone_xlsx、_wait_download_task | 复用已验证行为，拆为有界任务阶段 |
| E2 | 既有 Campaign 有服务端目录、冻结过滤与不可变 Artifact | historical_import_http/worker、platform/storage/canonical.py | 不复制导入链路 |
| E3 | root uv 项目和非 root Docker 已建立 | pyproject.toml、Dockerfile、compose.yaml | 根构建 context 不变 |

## 推断与待确认

网站当前会话有效性和正式非 root Chromium 兼容需本轮真实验证。

# 目标、成功标准与非目标

## 目标

人工脚本可指定目录；系统可追踪下载、取消、恢复、导入和结果。

## 成功标准

以 #700 的 AC1–AC13 和用户追加的定时计划、共用弹窗、品牌过滤要求为完整完成定义，所有适用项必须取得直接证据。

## 范围

Provider/人工入口、auth、PG Job/下载事实、API/UI、Docker/Compose、七天清理和文档。

## 非目标

不检查数据内容业务正确性，不执行 Release/部署/生产迁移或导入。

## 必须保持不变

现有输入→Artifact→Canonical→过滤→Owner 链路，Job fencing/deadline，根 uv，既有用户数据库和原桌面文件。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 负责人 | Ingestion 持有下载事实，Provider 不写业务表 | #700 / AC6 | bootstrap 与 PG adapter |
| 认证 | bundle 仅首次播种，刷新使用 host bind | #700 / AC3、AC4 | 镜像升级不覆盖 |
| 长等待 | 有界阶段与 continuation，无30分钟总上限 | #700 / AC5 | 同一 Job Runtime |
| 数据 | 新导入 standard_observation，冻结文件重试 | #700 / AC6 | 现有 Campaign |
| 交付 | 用户授权 Agent 验证通过后直接交付；项目早期 PR 规则适用 | 用户当前指令、AGENTS.md | 不另等待重复授权 |

# 修改方案与决策依据

## 最小充分方案

1. 认证与 Provider → 正式与人工目录 → 过去24小时原子导出 → 本地单元和真实下载。
2. PG/API/Job → 下载生命周期、恢复与 Campaign 接线 → 隔离 PG 集成。
3. 计划和 UI → 采集策略共用新建计划弹窗、默认 WisersOne、名称/执行频率/品牌 → Scheduler 到时自动下载导入，任务状态可见 → 组件及跨组件验收。
4. Docker/Compose → 非 root 浏览器及 bind → 构建和真实 Linux 下载。
5. 文档/清理/交付 → 七天保留与 Canonical 不变 → 受影响检查、Review、CI 与 merge 收尾。

## 证据到决策

E1 要求提交/轮询/下载阶段拆分；E2 要求复用生产导入；E3 要求在正式镜像验证。

## 备选方案与取舍

单一无限长 Job 会破坏 attempt deadline；复制 imports_test 会复制业务规则；刷新写回源码会导致升级丢失。采用分阶段 Job 与 host auth。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 正式 Provider 和人工入口 | #700 / AC1 | not_satisfied | 实施中 |
| R2 | 过去24小时、五平台和原子 Excel | #700 / AC2 | not_satisfied | 实施中 |
| R3 | 两份初始 JSON 正式打包 | #700 / AC3 | not_satisfied | 实施中 |
| R4 | host auth 首次播种、刷新与升级 | #700 / AC4 | not_satisfied | 实施中 |
| R5 | 无总等待上限、持久恢复与取消 | #700 / AC5 | not_satisfied | 实施中 |
| R6 | 受管文件接入标准统一导入 | #700 / AC6 | not_satisfied | 实施中 |
| R7 | 现有页面入口与完整结果 | #700 / AC7 | not_satisfied | 实施中 |
| R8 | 正式非 root Docker 与 Compose | #700 / AC8 | not_satisfied | 实施中 |
| R9 | 七天原文件清理、Canonical 保留 | #700 / AC9 | not_satisfied | 实施中 |
| R10 | Windows 实际免密码下载 | #700 / AC10 | not_satisfied | 实施中 |
| R11 | 正式 Linux 实际下载和隔离导入 | #700 / AC11 | not_satisfied | 实施中 |
| R12 | 文档、验证与完整交付收尾 | #700 / AC12 | not_satisfied | 实施中 |
| R13 | 共用计划弹窗、名称/频率/品牌及自动下载导入 | 用户追加决定、#700 / AC13 | not_satisfied | 实施中 |

# 计划改动

Provider/wisersone 与 wisersone_test、Ingestion 下载模型与 Contract、PG repository/schema/migration、bootstrap API/worker、frontend import 页面/生成 client、Dockerfile/Compose/host preparation、tests、相关正式文档和安全例外。

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | auth/原子发布/任务恢复/UI |
| 接口 / 契约 | required | HTTP/Job/OpenAPI/生成 client |
| 集成 / 持久化 / 运行依赖 | required | 隔离真实 PG、Job、Campaign、Owner |
| 用户 / 工作流验收 | required | 下载→导入结果与取消/重试 |
| 跨组件关键路径 | required | API/worker/import/frontend |
| 外部依赖 / 供应方探测 | required | Windows 与 Linux 各实际下载 |
| 构建 / 打包 / 运行 | required | wheel 与非 root Docker |
| 文档 / 治理 / 其他 | required | Completion、秘密扫描例外、Review、CI |

## 验证计划

按 scripts/dev/validate_changed.py --base origin/main 的唯一 scope classifier 执行。真实 Provider 验证不进入普通 CI、不写生产库。独立审查和 Completion 后同步 main 并获得 current head CI。

# 风险、兼容性、迁移与回滚

网站会话仍可失效，需要人工重新登录。新增下载生命周期表，不改旧导入 Contract 默认。保留既有历史数据与 Canonical。失败时停止新下载，旧导入流程保持可用；回滚代码前保留 host auth 和已完成输入。

# 文档、依赖、部署与发布影响

同步采集、存储、运行、统一导入和模块 README。依赖版本不升级。新增浏览器构建内容、host mount、auth 配置。只批准初始两份 JSON 例外，其余 Secret 规则不变。Release/部署未授权。

# 完成审计

- [ ] upstream_re_read：重新读取用户决定和 live Issue。
- [ ] change_coverage：覆盖全部 AC。
- [ ] reverse_audit：API↔UI、Job↔结果、源码↔wheel/镜像。
- [ ] unresolved_cleared：未满足项清零。

# 完成证据与状态

## 新鲜证据

已验证 live Issue canonical create Contract 通过，分支从同步 main 建立。实现证据待本轮获取。

## 未验证内容与剩余风险

全部实现仍在进行；不声称功能完成。

## 交付状态

Issue #700；本地 feature/700-wisersone-import。PR/CI/merge/archive/closure 尚未执行。Release/Deploy 不适用：用户只授权合并。

## 备注

清理仅限本任务 scratch、测试容器、镜像和可证明归属的构建缓存。
