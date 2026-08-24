---
schema: rvc-change/v1
id: CHG-20260824-docker-desktop-mirror-effective-validation
title: 修复 Docker Desktop mirror 有效验证与无界等待
level: L2
status: in_progress
owner: chatgpt
branch: fix/docker-desktop-mirror-effective-validation
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - local-development
  - developer-experience
  - ci
affected_paths:
  - scripts/dev/configure_docker_desktop_mirrors.ps1
  - tests/unit/test_docker_build_sources.py
  - .github/workflows/compose-windows-desktop.yml
  - docs/guides/03_Windows Docker Desktop Compose运行.md
  - docs/guides/04_Docker国内构建源与本地重置.md
contracts: []
data_changes: []
---

# 目标

修复 Windows Docker Desktop mirror 初始化的错误成功条件和等待体验。AIMA 只管理 `scripts/config/docker_hub_mirrors.txt` 中的 mirrors；Docker Engine 可以同时报告其他来源配置的额外 mirrors。验证必须确认 AIMA mirrors 全部生效且保持 AIMA 自身相对顺序，不能要求 Docker Engine 的有效 mirror 列表与 AIMA 列表数量完全相等。

同时封闭 Docker Desktop restart 与 `docker info` 探测的无界等待，并在等待期间输出可观察进度和实际有效 mirrors。

# 可观察成功标准

- [ ] 当前用户机器这种“Docker Engine 报告额外 mirrors，但 AIMA 三个 mirrors 全部存在”的状态立即判定为已生效，不进入无意义的长重试。
- [ ] AIMA mirror 判断允许额外 mirrors，但要求 AIMA mirrors 全部存在且保持配置文件中的相对顺序。
- [ ] daemon.json 仍必须保存 AIMA 管理的精确 mirror 列表和 `max-download-attempts=5`；只有磁盘配置和有效 Engine 状态都满足时才幂等跳过 restart。
- [ ] `docker desktop restart` 使用官方 `--timeout`，避免默认无超时。
- [ ] 每次 `docker info` mirror probe 有独立短超时；整体 post-restart 验证有总 deadline，不再用“固定次数 × sleep”冒充总超时。
- [ ] 等待期间输出 elapsed/deadline 和最近 probe 状态；成功时输出 AIMA mirrors 与额外有效 mirrors；最终失败输出实际观测和备份恢复提示。
- [ ] `scripts/config/docker_hub_mirrors.txt` 继续是 AIMA mirror 地址唯一仓库事实源，不修改 mirror 列表和顺序。
- [ ] Windows PowerShell 行为测试直接覆盖“存在额外 mirrors 仍成功”和“缺失/乱序 AIMA mirror 失败”。
- [ ] 文档只描述最新事实，不记录修复过程。

# 非目标

- 不删除或接管 Docker Desktop 其他来源配置的额外 mirrors。
- 不更换 AIMA 当前 mirror 列表。
- 不修改 Linux mirror 初始化、Dockerfile、Compose、npm/PyPI/Debian 源。
- 不引入 Pester 或新依赖。

# 必须保持不变

1. AIMA mirror 唯一配置仍为 `scripts/config/docker_hub_mirrors.txt`。
2. `max-download-attempts=5`。
3. daemon.json 写入前继续备份并保留非 AIMA Docker Engine 配置。
4. Docker Desktop CLI 不可用时继续显式 skip/warning。
5. 真正未应用 AIMA mirrors 时继续 fail closed。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 修复当前等待卡住问题 | user:2026-08-24-current-runtime-output | not_satisfied | 用户 `docker info` 秒级成功且报告 6 个 mirrors，其中包含全部 3 个 AIMA mirrors；当前代码要求 `actual.Count == Mirrors.Count`，因此永远 false |
| R2 | 不再无意义等待固定 60 次 | user:2026-08-24-current-request | not_satisfied | 当前 `60 × 2s` 且单次 `docker info` 无独立超时 |
| R3 | 完整修复而非只改日志 | user:2026-08-24-current-request | not_satisfied | 待 probe timeout、整体 deadline、restart timeout、进度与行为测试 |
| R4 | 保持单一 mirror 配置源 | user:centralize-docker-hub-mirrors | not_satisfied | 待回归确认 |
| R5 | 完成 L2 Audit/Review/CI 并正常合并 main | AGENTS.md | not_satisfied | 待门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不涉及浏览器 |
| Backend/API/PostgreSQL Integration | not_applicable | 不涉及后端/数据库 |
| Contract / Generated Client | not_applicable | 无 Contract 变化 |
| Real Full-stack Golden Path | not_applicable | 不改变业务运行栈 |
| Real Provider Probe | not_applicable | 不涉及 Provider |
| Docs / Governance / Other | required | Python static regression + Windows PowerShell direct behavior checks + permanent CI |

# Completion Audit

- [ ] upstream_re_read: Ready 前重新读取用户实际输出、AGENTS、Skill、Blueprint 07、最终 PowerShell/helper/test/workflow/Guide。
- [ ] change_coverage: R1-R5 全覆盖。
- [ ] reverse_audit: 确认 Linux、Dockerfile、Compose、包源、mirror 配置文件未被无关修改；额外 mirrors 只作为外部有效状态报告。
- [ ] unresolved_cleared: Ready 前清零 not_satisfied。

# Git / 交付

- PR：待创建 Draft
- 用户已要求完整修改本问题；沿用本轮前序“修改并合并主分支”的交付授权，最终门禁通过后正常合并并独立归档。
