---
schema: coding-change/v1
id: CHG-20260915-112101-local-pypi-mirror-default
title: 对齐本地 Compose PyPI 默认镜像
level: L2
status: in_progress
owner: Codex
branch: fix/local-pypi-mirror-default
created: 2026-09-15
updated: 2026-09-15
completion_gate: required
depends_on: []
affected_areas:
  - config
  - build
  - docs
affected_paths:
  - env.local.example
  - changes/active/CHG-20260915-112101-local-pypi-mirror-default/CHANGE.md
contracts:
  - 本地 Compose 环境模板的 Docker 构建下载源默认值
data_changes:
  - 无 Schema、Migration、业务数据或运行数据变化
---

# 变更摘要

把 `env.local.example` 中唯一仍指向官方 PyPI 的 `AIMA_BUILD_PYPI_INDEX` 默认值，对齐到项目现有 Dockerfile、Compose、生产模板、安装脚本、构建指南和测试已经采用的清华 TUNA PyPI 镜像。

# 目标、范围与非目标

## 成功标准

- [ ] 本地环境模板默认使用 `https://pypi.tuna.tsinghua.edu.cn/simple`。
- [ ] `uv.lock` 继续保留官方 PyPI 依赖身份，依赖版本、镜像 Tag、TLS 与完整性校验不变。
- [ ] Docker 构建源专项测试、配置/文档/Secret/Change 门禁通过。
- [ ] 通过关联 #488 的 PR 合入当时最新 `main`；main-fresh CI、Change 归档、Issue 回写和分支清理作为交付收尾完成。

## 范围

- `env.local.example` 的一个 Docker 构建参数默认值。
- 本 Change、PR、CI 和合并后收尾。

## 非目标

- 不修改 `uv.lock`、依赖版本、Runtime、基础镜像或 Release workflow。
- 不实际构建或发布正式镜像，不创建 Tag、GitHub Release 或生产部署。
- 不修改小红书、评论、前端、API、Contract、Schema 或数据库代码。

## 必须保持不变

- 镜像只改变下载链路，不改变锁定包版本和供应链身份。
- HTTPS、锁文件、hash/digest 和现有完整性校验不得降低。
- `AIMA_BUILD_PYPI_INDEX` 继续允许由目标环境显式覆盖。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地 Compose 模板默认源与项目现有清华 TUNA 基线一致 | https://github.com/dingyuwen777/AIMA_UGC/issues/488 / AC1 | satisfied | 工作区 diff 只把 `env.local.example` 的 PyPI 默认值改为现有项目统一地址 |
| R2 | 不改写锁文件、依赖身份、版本或完整性校验 | https://github.com/dingyuwen777/AIMA_UGC/issues/488 / AC2 | satisfied | 预计 diff 仅含环境模板和本 Change；`uv.lock` 保持官方 PyPI registry |
| R3 | 构建源专项与治理检查通过 | https://github.com/dingyuwen777/AIMA_UGC/issues/488 / AC3 | not_satisfied | 等待目标测试、配置一致性和 Change 门禁 |
| R4 | 合入最新 main 并完成合并后验收与清理 | https://github.com/dingyuwen777/AIMA_UGC/issues/488 / AC4 | explicitly_deferred | 用户已授权端到端交付与管理员 bypass；依赖 current-head CI、合并及 main-fresh 结果，最终交付前必须完成 |

# 实施与验证计划

1. 保留用户现有一行配置修改，不改写其他构建源或锁文件。
2. 运行 Docker 构建源专项测试、Secret、Docs、Docs Facts、Agent Governance 与 Change Completion 检查。
3. 独立审查最终 diff，推送 PR 并等待 current-head required checks。
4. 合并后验证最新 `main` 与 Change Archive，回写关闭 #488 并清理任务分支。

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| Behavior / Unit | required | `test_docker_build_sources.py` 对环境模板、Compose、Dockerfile 和 Release override 的一致性检查 |
| Config / Docs | required | 环境模板解析、项目文档事实和 Secret 扫描 |
| Network source | required | 清华 TUNA 官方 PyPI 帮助与 HTTPS `simple` 地址可访问性 |
| Build / Package | not_applicable | 只对齐已由现有 Docker/Compose 路径使用并由专项测试保护的模板默认值；不改变构建实现、锁文件或镜像身份 |
| API / Contract / PostgreSQL / Frontend | not_applicable | 不修改业务接口、Schema、数据或前端 |
| External Provider / LLM | not_applicable | 不修改或调用 TikHub、LLM |
| Governance / CI | required | Change Completion、PR current-head required checks、main-fresh CI |

# 风险、兼容、部署与回滚

- 风险：清华镜像短时不可用会影响使用模板默认值的本地 Docker 构建；目标环境仍可显式覆盖回官方 PyPI。
- 兼容：变量名、覆盖方式、锁文件和依赖版本不变，只消除本地模板与其他正式配置的默认值漂移。
- 部署：无生产部署、数据迁移或服务重启；生产模板已使用相同默认值。
- 回滚：通过后续 PR 将本地模板默认值恢复为官方 PyPI；不涉及业务数据回滚。

# Completion Audit

- [ ] upstream_re_read：Ready 前重读 #488、当前配置/文档/测试和最新 `main`。
- [ ] change_coverage：逐项核对默认源、锁文件不变、验证、PR 和合并后收尾。
- [ ] reverse_audit：从 `env.local.example` 反查 Compose build args、Dockerfile、安装脚本、生产模板和构建指南的一致性。
- [ ] unresolved_cleared：Ready 前清零实现侧 `not_satisfied`，记录 current-head 证据与明确未验证项。

# 两阶段 Review

## Review A1：上游要求 → Change

待 Ready 前重读 #488 和用户授权后填写。

## Review A2：Change → 实现、测试与文档

待目标验证和独立 diff 审查后填写。
