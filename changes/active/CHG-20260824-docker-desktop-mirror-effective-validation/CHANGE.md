---
schema: rvc-change/v1
id: CHG-20260824-docker-desktop-mirror-effective-validation
title: 修复 Docker Desktop mirror 有效验证与无界等待
level: L2
status: ready_for_review
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

修复 Windows Docker Desktop mirror 初始化的错误成功条件和等待边界。AIMA 只管理 `scripts/config/docker_hub_mirrors.txt` 中的 mirrors；Docker Engine 可以同时报告由 Docker Desktop、管理员策略或其他来源配置的额外 mirrors。有效状态验证只要求 AIMA mirrors 全部出现并保持 AIMA 自身相对顺序，不要求 Docker Engine 的有效 mirror 列表与 AIMA 列表数量完全相等。

Docker Desktop restart、单次 `docker info` probe 和 restart 后整体验证均具有明确硬上限；等待期间持续输出实际状态，条件满足后立即继续。

# 可观察成功标准

- [x] Docker Engine 报告额外 mirrors、但 AIMA mirrors 全部存在且相对顺序正确时立即判定为已生效，不进入无意义长重试。
- [x] AIMA mirror 判断允许额外 mirrors；缺失任一 AIMA mirror 或 AIMA 自身相对顺序错误时判定失败。
- [x] `daemon.json` 继续保存 AIMA 管理的精确 mirror 列表和 `max-download-attempts=5`；只有磁盘配置和有效 Engine 状态都满足时才幂等跳过 restart。
- [x] `docker desktop restart` 使用官方 `--timeout`，避免默认无超时。
- [x] 每次 `docker info` mirror probe 有独立 3 秒超时，probe kill 后清理等待最多 1 秒；restart 后有效状态验证有 20 秒总 deadline。
- [x] 等待期间输出 elapsed/deadline 和最近 probe 状态；成功时输出 AIMA mirrors 与额外有效 mirrors；最终失败输出最后实际观测和备份恢复提示。
- [x] `scripts/config/docker_hub_mirrors.txt` 继续是 AIMA mirror 地址唯一仓库事实源，当前列表和顺序未修改。
- [x] Windows PowerShell 行为测试直接覆盖“存在额外 mirrors 仍成功”“缺失 AIMA mirror 失败”“AIMA 相对顺序错误失败”和 daemon 精确配置语义。
- [x] 两份运行 Guide 只描述最新事实，不记录修复过程。

# 非目标

- 不删除、覆盖或接管 Docker Desktop 其他来源配置的额外 mirrors。
- 不更换 AIMA 当前 mirror 列表。
- 不修改 Linux mirror 初始化、Dockerfile、Compose、npm/PyPI/Debian 源。
- 不引入 Pester 或新依赖。

# 必须保持不变

1. AIMA mirror 唯一配置仍为 `scripts/config/docker_hub_mirrors.txt`。
2. `max-download-attempts=5`。
3. `daemon.json` 写入前继续备份并保留 registry-mirrors 之外的其他 Docker Engine 配置。
4. Docker Desktop CLI 不可用时继续显式 skip/warning。
5. 真正未应用全部 AIMA mirrors 时继续 fail closed。
6. 日常 Dockerfile/Compose 继续只使用官方 image reference。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 修复当前“docker info 很快且 AIMA mirrors 已存在，但脚本一直等待”的问题 | user:2026-08-24-current-runtime-output | satisfied | 用户实际 `docker info` 秒级返回 6 个有效 mirrors，其中包含全部 3 个 AIMA mirrors；旧实现要求有效数量等于 3。新 `Test-ExpectedMirrorsPresent()` 允许额外项并保持 AIMA 相对顺序；Windows workflow `32686784812` 直接行为测试 success |
| R2 | 正常状态不应固定等待几十秒；等待只应是异常保护上限 | user:2026-08-24-current-request | satisfied | 磁盘配置和有效状态都匹配时直接 `restart skipped`；只有需要 restart 才进入验证；整体 20 秒、单 probe 3 秒、间隔 1 秒均为上限，满足条件立即返回 |
| R3 | 完整解决等待边界，不只改日志 | user:2026-08-24-current-request | satisfied | `docker desktop restart --timeout 60`；`ProcessStartInfo` probe 3 秒；probe kill 后 `WaitForExit(1000)`；Stopwatch 20 秒 deadline；`[WAIT]` 进度、最后观测状态和恢复提示；Docker 官方 `docker desktop restart` reference 确认 `--timeout` 且默认 0/-1 为无超时 |
| R4 | 保持 Docker Hub mirror 单一配置源和已有镜像身份/包源方案 | user:centralize-docker-hub-mirrors | satisfied | PR #192 changed files 仅 helper、测试、Windows workflow、Guide 03/04 和本 Change；`scripts/config/docker_hub_mirrors.txt`、Linux setup、Dockerfile、Compose、npm/PyPI/Debian 配置均未修改 |
| R5 | 完成 L2 Audit/Review/Ready Check/永久 CI 并正常合并 main | AGENTS.md + user:merge-authorization | explicitly_deferred | Ready 前 A1/A2、Code Quality、Completion Audit 已完成；功能审计 HEAD `e977089901db60f4ff2924a19f215ecdc239139a` 除 `in_progress` 状态下预期失败的 Completion Gate 外，其余 10 个永久 workflow 全部 success。按仓库门禁，合并刻意延期到本 `ready_for_review` 提交的 11 个永久 workflow 全绿后执行；用户已授权正常合并 main |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不涉及浏览器 |
| Backend/API/PostgreSQL Integration | not_applicable | 不涉及后端/数据库行为 |
| Contract / Generated Client | not_applicable | 无公共 Contract 变化 |
| Real Full-stack Golden Path | not_applicable | 不改变业务运行栈；Internal V1-A、Stage 8F、Windows named-volume Runtime 作为回归门禁均通过 |
| Real Provider Probe | not_applicable | 不涉及 Provider |
| Docs / Governance / Other | required | 有效 Red、Python static regression、Windows PowerShell direct behavior、Windows Runtime、Completion Gate 和永久 CI |

# Completion Audit

- [x] upstream_re_read: Ready 前重新读取用户实际 `docker info` 输出、当前分支 `AGENTS.md`、Reliable Vibe Coding、Blueprint README/07、最终 helper、目标 test、Windows workflow、Guide 03/04，并核对 Docker 官方 Desktop restart timeout reference。
- [x] change_coverage: R1-R5 覆盖错误成功条件、正常状态立即返回、三个等待边界、可观察输出、单一配置源、测试/文档与交付门禁。
- [x] reverse_audit: 从用户 6-mirror 状态反查 predicate，再从 helper 反查磁盘配置、有效状态、restart、probe、deadline、输出和恢复；PR changed files 仅 6 个预期路径，Linux setup、mirror 配置文件、Dockerfile、Compose、依赖、业务代码、Contract/Migration 未修改；并行多词包 Change 路径不重叠。
- [x] unresolved_cleared: R1-R4 satisfied；R5 的 merge 仅按正式门禁 explicitly_deferred 到 Final Ready HEAD 全绿之后，没有范围内未决设计或缺失实现。

# Review

## Requirement Review A1：上游要求 → Change

通过。用户先提供实际卡住输出，随后用 `docker info` 证明 Docker Engine 响应很快且有效列表有 6 个 mirrors；由此重新确认根因是旧 predicate 的 `actual.Count == AIMA.Count`，不是机器慢。用户进一步要求完整修复，因此 Change 同时覆盖正确有效状态语义、正常状态立即返回、restart/probe/overall 三层上限和可观察日志，而不是只调整 sleep 次数。

## Requirement Review A2：Change → 实现 / 测试 / 文档

通过。`Test-ExpectedMirrorsPresent()` 以子序列方式确认 AIMA mirrors 的完整性和相对顺序，允许其他来源的额外 mirrors；`Test-AimaDaemonConfigMatches()` 继续要求 AIMA 自己写入的 `daemon.json` 精确匹配统一配置及下载重试数。当前状态先 probe，磁盘+有效状态都匹配即跳过 restart。Windows Runner 直接构造额外/缺失/乱序 mirror 状态测试 predicate；两份 Guide 描述同一最新语义。

## Code Quality Review

通过，无 Serious/Important finding。实现未引入依赖或 wrapper；单次 `docker info` 通过 `System.Diagnostics.Process` 设置硬等待，超时后 kill 的清理等待同样有界；restart 使用 Docker Desktop CLI 官方 timeout；整体使用 Stopwatch deadline，不再用固定重试次数假装总超时。额外 mirrors 只报告 warning，不被 AIMA 静默删除；真正缺少 AIMA mirrors 仍 fail closed。probe 参数使用明确的双引号格式串，避免 Windows 参数分词歧义。

# 验证证据

## Red

有效 Red commit：`d332f9110daef2b5fbe322a203d961a08d5d88ab`

总 CI `32685887856` 在 Ruff / mypy 通过后执行 unit，结果 **1 failed / 603 passed**；唯一目标失败为旧 helper 不存在新的 restart/probe/deadline 有界验证模型，证明旧实现不满足本轮完成定义。

## Green / 功能审计

功能审计 HEAD：`e977089901db60f4ff2924a19f215ecdc239139a`

- CI `32686784849`: success；Stage 1 / Stage 2 / Stage 3A / Windows bootstrap 全部 success，目标 unit 位于 Backend and repository checks 并通过。
- Windows Docker Desktop Compose Compatibility `32686784812`: success；PowerShell AST、额外 mirror predicate 直接行为测试、CMD/PowerShell Compose 和 named-volume Runtime 全部 success。
- Internal V1-A `32686784799`: success。
- Stage 8F `32686784805`: success。
- Local Dev Bootstrap `32686784850`: success。
- Stage 6 `32686784836`: success。
- Stage 7 Plan `32686784820`、Keyword Packs `32686784844`、Scheduler `32686784851`、Provider Config `32686784808`: success。
- Change Completion Gate `32686784872` 在 Change 仍为 `in_progress` 时按治理规则预期 failure；本 `ready_for_review` 提交后重新执行。

中间候选 HEAD 曾因新增 Python 测试的一行 Ruff formatter 要求失败；实际 Stage 7 Plan Unit/PostgreSQL 已 success。按 Ruff 给出的精确格式修正后，最终功能审计 HEAD 的全量 Quality/CI 已 success；未把格式失败伪装为功能失败。

# Git / 交付

- Branch: `fix/docker-desktop-mirror-effective-validation`
- PR: #192
- Merge authorization: 用户已明确要求完整修复，并沿用本轮“修改脚本、合并到主分支”的正常合并授权。
- Final gate: 本 `ready_for_review` HEAD 必须重新通过 11 个永久 workflow。
- Archive: 实现 PR 合并后创建独立归档 PR，将本 Change 标记 `done` 并移动到 `changes/archive/2026-08/`；不得触碰并行 `CHG-20260824-multi-keyword-pack-entrypoints`。
