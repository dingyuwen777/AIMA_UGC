---
schema: coding-change/v1
id: CHG-20260929-122246-production-cjk-font
title: 修复生产容器中文报告字体缺失并补齐失败诊断
level: L3
status: in_progress
owner: codex
branch: fix/production-cjk-font
created: 2026-09-29
updated: 2026-09-29
completion_gate: required
depends_on: []
affected_areas:
  - runtime
  - reporting
  - observability
  - tests
  - documentation
affected_paths:
  - Dockerfile
  - backend/src/aima_ugc/bootstrap/feishu_publication_worker.py
  - tests/unit/test_docker_build_sources.py
  - tests/unit/platform/test_feishu_publication_worker.py
  - docs/operations/01_生产部署与离线Release方案.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：生产 `v3.1.0.8` Worker 容器没有报告 Renderer 必需的 CJK 字体，飞书报告在生成中文词云时失败；Worker 又把内部异常压缩成同一个错误码，缺少可诊断日志。
- **拟议修改**：在唯一 Backend runtime 镜像安装 Debian trixie 的 `fonts-noto-cjk`；为报告发布内部 `ValueError` / `RuntimeError` 记录脱敏异常事件；补充回归、镜像真实 smoke 和服务器自检文档。公共错误码、API、Schema、数据与飞书重试语义保持不变。
- **预期结果**：新 Release 的 Worker 能解析 Regular/Bold CJK 字体并生成中文词云；其他内部失败仍返回兼容错误码，但日志能定位异常类型和调用栈。

# 背景、现状与问题

## 背景

Issue #657 记录了生产飞书报告两次失败及容器内最小复现。用户要求解决并合并主分支；Release/Deploy 与生产数据操作不在本次授权范围。

## 当前现状

- `platform/reporting/README.md` 明确 Linux 运行环境必须有 Noto Sans CJK 或 Source Han Sans。
- `resolve_cjk_font()` 和 `resolve_cjk_bold_font()` 已包含 Debian `fonts-noto-cjk` 的标准安装路径。
- 根 Dockerfile 的 Backend runtime 基于 `python:3.14.7-slim-trixie`，当前只安装 `libpq5`。
- 生产容器实际调用 `resolve_cjk_font()` 稳定抛出“未找到可用中文字体”的 `RuntimeError`。
- `execute_report()` 当前捕获 `ValueError` / `RuntimeError` 后只返回 `feishu_report_publication_failed`，不记录对应内部异常事件。

## 问题、根因或约束

根因已由真实生产容器复现闭合：构建产物没有携带代码运行所需的 CJK 字体。开发 Windows 依赖宿主微软雅黑，CI 单独安装字体，但正式 Backend 镜像没有把同一前置条件纳入 Runtime。诊断缺口不是原始失败原因，但会掩盖字体、输入校验或 Renderer 的后续内部错误。

## 不修改的后果

任何使用当前镜像生成中文报告视觉资产的生产 Worker 都会在调用飞书 API 前失败；即使未来出现不同的 `ValueError` / `RuntimeError`，运维仍只能看到通用 Job 错误码，无法从日志定位失败阶段。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 / 命令 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | 生产 Worker 缺少 CJK 字体，resolver 抛出 `RuntimeError` | 用户在 `v3.1.0.8` release 目录执行容器命令的 Traceback / #657 | 镜像必须携带 resolver 支持的字体，而不是只改宿主或临时容器 |
| E2 | Renderer 在 Linux 优先检查 Noto/Source Han 标准路径 | `wordcloud.py`、reporting README | 安装与现有 resolver 路径一致的发行版字体包即可，不需要改业务算法 |
| E3 | Backend runtime 只安装 `libpq5` | `Dockerfile` | 正式构建缺少必要运行依赖 |
| E4 | Debian trixie `fonts-noto-cjk` 同时提供 resolver 已识别的 Regular/Bold TTC | Debian 官方 package file list | 选择发行版包可以覆盖普通与粗体图表字体 |
| E5 | 报告内部异常被统一转换且未写日志 | `feishu_publication_worker.py` | 保持错误码兼容，并在转换前记录安全异常事件 |
| E6 | 统一日志已有不复制异常消息/源码行并脱敏的 `log_exception_event()` | `platform/logging/setup.py` 与 formatter tests | 复用现有日志能力，不新建日志体系 |

## 推断与待确认

- 待确认：修复镜像合并后尚未执行新的正式 Release 或生产部署；因此生产环境最终复验只能在后续获授权部署新镜像后完成，不阻塞本次源码与产物级修复交付。

# 目标、成功标准与非目标

## 目标

让正式 Backend 镜像自包含报告生成需要的中文字体，并让报告 Worker 的内部生成失败在不泄露敏感内容的前提下可诊断。

## 成功标准

- [ ] 新 Backend 镜像内普通/粗体 CJK resolver 都返回真实文件。
- [ ] 新 Backend 镜像内实际生成含中文的词云 PNG 成功。
- [ ] 报告 Worker 捕获 `ValueError` / `RuntimeError` 时记录稳定 ERROR 事件，并保持原有 Job 错误码。
- [ ] 文档给出 release 根目录下的自检命令，并明确合并不等于生产部署。
- [ ] PR 最新 HEAD 的相关测试、构建、Review 与 CI 满足门禁。

## 范围

- Backend runtime 的系统字体包。
- 飞书报告发布 Worker 的内部异常诊断。
- Docker/runtime、Worker 日志、报告视觉相关测试。
- 生产 Release smoke 文档与本 Change。

## 非目标

- 不修改报告统计、词云算法、飞书 API 参数、权限、重试或发布幂等逻辑。
- 不修改公共 HTTP/Pydantic Contract、数据库 Schema/Migration 或数据。
- 不升级 Python、第三方 Python/Node 依赖或基础镜像。
- 不创建 Release、不部署生产、不重跑真实报告任务。

## 必须保持不变

- `AIMA_REPORT_CJK_FONT` 显式路径覆盖与现有字体候选顺序。
- `feishu_report_publication_failed`、飞书 API 错误码及 retry/fail 分类。
- 唯一根 Dockerfile、共享 Backend 镜像、离线 Bundle 与 `--no-build --pull never` 部署方式。
- 日志 Secret/PII 脱敏和单行长度边界。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 范围与负责人边界 | 只改 Runtime、报告 Worker 诊断、回归与 Operations | E1–E6 / #657 | 不扩到报告业务逻辑或飞书适配器 |
| 接口与契约 | 不变 | 失败位于内部运行依赖，不需要新增公共字段 | 无生成物变化 |
| 数据与迁移 | 不适用 | 无 Schema、持久数据或历史数据语义变化 | 不需要 Migration/回填 |
| 错误与失败语义 | 对外错误码不变；新增内部 ERROR 事件 | E5–E6 | 调用方兼容，运维可定位 |
| 兼容性 | 保留显式字体配置和现有候选路径 | E2 | Windows/自定义字体环境继续工作 |
| 部署与回滚 | 必须产出并部署新镜像；源码回滚后需重新发布旧镜像 | E1–E4 | 旧运行容器不会因 main 合并自动获得字体 |

# 修改方案与决策依据

## 最小充分方案

1. **建立失败回归**
   → 修改 Dockerfile Contract test 与 Worker unit test
   → 修改前分别因缺包和缺日志失败
   → 运行两个定向测试证明 Red。

2. **补齐正式 Runtime**
   → 修改根 Dockerfile Backend runtime apt 安装项
   → 安装 `fonts-noto-cjk`，继续清理 apt lists
   → 构建正式 backend target；在镜像内执行普通/粗体 resolver 与中文词云真实渲染。

3. **补齐安全诊断**
   → 修改 `feishu_publication_worker.py`
   → 捕获内部 `ValueError` / `RuntimeError` 后复用 `log_exception_event()`，记录稳定事件、Job 和发布类型，不复制异常原始 message
   → unit test 验证事件字段、安全栈和错误码兼容。

4. **同步运行文档与交付证据**
   → 修改 Production Release Operations 的 smoke 段落和本 Change
   → 给出必须在 release 根目录执行的自检命令，并标明新镜像/部署边界
   → 文档检查、Completion Audit、Deep Review、PR CI、guarded merge 和 main-fresh。

## 证据到决策

| 决策 | 依据证据 | 为什么采用这个方案 |
| --- | --- | --- |
| D1 安装 Debian `fonts-noto-cjk` | E1–E4 | 直接满足当前 resolver 的 Regular/Bold 路径，且版本由 trixie 仓库与镜像构建锁定 |
| D2 不改 resolver 或增加字体下载脚本 | E2,E4 | 现有解析逻辑正确；额外下载会制造第二个供应链和版本来源 |
| D3 复用 `log_exception_event()` | E5–E6 | 保留调用栈定位且避免异常消息、Secret 或用户内容泄漏 |
| D4 保持对外错误码 | #657 / AC3 | 本次只补内部可观测性，不破坏前端/Job 消费者 |

## 备选方案与取舍

- **只在服务器宿主安装字体或临时进入容器安装**：不采用。字体不会可靠进入不可变镜像，容器重建后复发，也绕过 Release 事实源。
- **仅设置 `AIMA_REPORT_CJK_FONT` 并外挂字体文件**：保留为既有自定义能力，但不作为默认修复。它会新增生产文件装配和配置依赖，且当前官方 trixie 包已经提供匹配路径。
- **把字体文件直接提交仓库**：不采用。会引入大体积二进制、许可证与独立升级来源；发行版包更符合当前 apt 构建边界。
- **记录完整异常消息**：不采用。通用 `ValueError` / `RuntimeError` 可能携带路径、输入内容或 Secret；安全 traceback + error type 已满足根因定位的第一层需求。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Backend 镜像包含 resolver 支持的 Regular/Bold CJK 字体 | #657 / AC1 | not_satisfied | 待 Dockerfile 实现与镜像 smoke |
| R2 | 正式镜像内中文词云渲染成功 | #657 / AC2 | not_satisfied | 待真实 Docker runtime smoke |
| R3 | 内部异常写安全诊断事件且错误码兼容 | #657 / AC3 | not_satisfied | 待 Worker unit test 与实现 |
| R4 | 相关自动回归和 PR 最新 HEAD CI 通过 | #657 / AC4 | not_satisfied | 待定向/相关测试与 CI |
| R5 | 运行文档提供正确自检与部署生效边界 | #657 / AC5 | not_satisfied | 待 Operations 更新 |

# 计划改动

| 文件 / 模块 / 资产 | 计划修改 | 原因 | 对应要求 / 证据 |
| --- | --- | --- | --- |
| `Dockerfile` | Backend runtime 安装 `fonts-noto-cjk` | 修复生产镜像缺字体根因 | R1–R2 / E1–E4 |
| `feishu_publication_worker.py` | 转换内部异常前记录安全事件 | 修复诊断缺口 | R3 / E5–E6 |
| Docker/Worker unit tests | 锁定包与日志兼容行为 | 建立 Red/Regression | R1,R3–R4 |
| `docs/operations/01_生产部署与离线Release方案.md` | 新增报告字体 smoke 与生效边界 | 形成可执行生产验证 | R5 |
| 本 Change | 追溯、验证与交付状态 | L3 门禁 | R1–R5 |

执行状态：

- [x] 调查当前实现和事实源
- [x] 建立与风险相称的任务路由和验证矩阵
- [x] 行为变化建立失败证据
- [ ] 完成最小实现
- [ ] 同步受影响的长期文档
- [ ] 取得仍覆盖当前版本的验证证据
- [ ] 完成需求追溯、完成审计和适用复核

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | Worker 两类内部异常的稳定事件、字段、安全栈与错误码兼容；报告视觉相关 unit tests |
| 接口 / 契约 | not_applicable | 不修改公共 API、Pydantic、Job Payload 或生成 Contract |
| 集成 / 持久化 / 运行依赖 | required | Debian trixie 字体包在正式 Backend target 的文件路径与 Pillow/Renderer 使用 |
| 用户 / 工作流验收 | required | 镜像内中文词云 PNG 实际生成；生产最终发布待新 Release 部署后复验 |
| 跨组件关键路径 | required | Dockerfile → Backend image → resolver → wordcloud render；Worker exception → safe log → compatible Job result |
| 外部依赖 / 供应方探测 | required | Debian 官方 trixie package/file list；不调用飞书或付费 Provider |
| 构建 / 打包 / 运行 | required | 正式 Backend target 构建与容器内 smoke；Release workflow 由 PR CI 按当前路径分类执行 |
| 文档 / 治理 / 其他 | required | Operations、自检命令、Change completion、PR/Issue traceability |

## 验证计划

- 目标测试：`tests/unit/test_docker_build_sources.py`、`tests/unit/platform/test_feishu_publication_worker.py`。
- 相关回归：`tests/unit/platform/test_reporting_visuals.py`、统一日志 tests。
- 静态检查或构建：Ruff、mypy 受影响文件、docs checks、Docker backend build。
- 专项真实边界：新 backend 镜像内 resolver + 中文词云 PNG smoke。
- 就绪检查：`python scripts/quality/check_change_completion.py --root . --require-active-ready` 与 PR required CI。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 依据 / 处理方式 |
| --- | --- | --- |
| 主要风险 | Backend 镜像体积增加；镜像未实际重建会造成假修复 | Debian 包 installed size 约 91 MB；以真实镜像构建/smoke 和部署边界文档控制 |
| 兼容性 | 公共行为兼容 | 不改 API/Schema/错误码；自定义字体配置继续优先 |
| 数据 / Migration | 不适用 | 无数据库或 Artifact 变更 |
| 部署 / 运行 | 需要新 Release 镜像并重启 Backend 服务 | 旧容器文件系统不会随源码合并变化 |
| 回滚 / 恢复 | 可回滚镜像到上一 Release；无数据恢复 | 系统包和日志代码只存在于镜像层，无持久状态变更 |

# 文档、依赖、部署与发布影响

- **长期文档**：同步 Production Release smoke，说明字体自检的执行目录、预期路径和部署生效条件。
- **依赖 / Runtime**：新增 Debian runtime 包 `fonts-noto-cjk`；不升级既有版本，不新增 Python/Node 依赖。
- **配置 / Secret**：无新配置；现有 `AIMA_REPORT_CJK_FONT` 保持可选覆盖；日志不记录异常原始 message。
- **部署 / Release**：修复只有在构建新 Backend 镜像并通过新 Release 部署、重启 `worker`/共享 Backend 服务后生效。本任务不执行 Release/Deploy。
- **兼容 / 消费方通知**：无需公共消费方改造；运维需知道旧 `v3.1.0.8` 镜像仍会失败。

# 完成审计

- [ ] upstream_re_read：实现完成后重读 #657 AC、生产 Traceback、Dockerfile、Worker、Reporting/Operations。
- [ ] change_coverage：逐条核对 AC1–AC5 与实现、测试、文档和 CI。
- [ ] reverse_audit：从正式镜像到 resolver/render、从 Worker 内部异常到日志/Job 结果双向复核；前后端、数据库反向审计因无相关边界而不适用。
- [ ] unresolved_cleared：Ready 前清零全部 `not_satisfied`，生产部署后复验作为明确剩余交付阶段记录。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 / 环境 | 命令 / 检查 | 结果 | 证明了什么 |
| --- | --- | --- | --- | --- |
| V1 | branch pre-implementation / Windows Python 3.14.7 | `python -m pytest tests/unit/test_docker_build_sources.py::test_backend_runtime_installs_report_cjk_fonts -q` | 1 failed：Dockerfile Backend stage 不包含 `fonts-noto-cjk` | 镜像运行依赖缺口已由失败测试锁定 |
| V2 | branch pre-implementation / Windows Python 3.14.7 | `python -m pytest tests/unit/platform/test_feishu_publication_worker.py::test_report_worker_logs_safe_internal_error_and_preserves_error_code -q` | 2 failed：`ValueError` / `RuntimeError` 均无目标日志事件；结果错误码仍兼容 | Worker 诊断缺口已由失败测试锁定 |

## 未验证内容与剩余风险

- Red 阶段已完成，尚未实现 Green；生产部署/真实报告重跑未获本任务授权。

## 交付状态

- 提交：待创建。
- 拉取请求：待创建。
- CI：待执行。
- 合并：用户已授权，满足门禁后 guarded merge。
- Change 归档：合并后等待仓库自动归档并验证。
- 发布 / 部署：未授权，不执行。

## 备注

- 用户已有未提交修改 `scripts/deploy/reset_keep_vehicle_catalog.sh` 与本任务无关，必须保留且不纳入提交。
