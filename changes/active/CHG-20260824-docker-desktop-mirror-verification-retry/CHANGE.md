---
schema: rvc-change/v1
id: CHG-20260824-docker-desktop-mirror-verification-retry
title: 修复 Docker Desktop mirror 重启后验证时序
level: L2
status: in_progress
owner: chatgpt
branch: fix/docker-desktop-mirror-verification-retry
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
contracts: []
data_changes: []
---

# 目标

修复 Windows 首次运行 `scripts/setup_dev_environment.cmd` 时 Docker Desktop 重启后的 mirror 验证假阴性：Docker Engine 已能响应但 `RegistryConfig.Mirrors` 尚未稳定时，不应只检查一次并立即失败，而应在有界时间内继续重试，直到预期 mirror 全部按既定顺序生效或真正超时。

# 可观察成功标准

- [ ] Docker Desktop restart 成功后，脚本持续等待 `docker info` 报告预期 mirrors，而不是 Engine 首次可访问后只检查一次。
- [ ] 重试有明确上限和固定间隔；超时仍保持失败并输出备份/恢复提示。
- [ ] 三个既有 Docker Hub mirror、`max-download-attempts=5`、daemon.json 备份与原有幂等逻辑保持不变。
- [ ] 已经正确应用 mirrors 时仍直接返回，不触发无意义重启。
- [ ] Windows PowerShell 语法检查与目标回归测试通过。

# 范围

- Windows Docker Desktop mirror helper 的重启后验证等待逻辑。
- 对应静态回归测试与 Windows CI 语法门禁。

# 非目标

- 不更换现有三个 Docker Hub mirror。
- 不改变 Linux `setup_dev_environment.sh`。
- 不改变 Dockerfile、Compose、npm/PyPI/Debian 下载源。
- 不修改 Docker Desktop/Engine 的其他配置项。

# 必须保持不变

1. mirrors 仍固定为 `docker.1panel.live`、`hub.1panel.dev`、`docker.m.daocloud.io`，顺序保持不变。
2. `max-download-attempts` 仍为 5。
3. 修改既有 daemon.json 前继续创建时间戳备份。
4. Docker Desktop CLI 不可用时继续显式 warning/skip，不伪装成功。
5. 最终超时或实际未应用时仍 fail closed。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 修复 mirror 已最终生效但脚本重启后过早报错的问题 | user:docker-desktop-mirror-verification-false-negative | not_satisfied | 待 Red/Green 与 Windows CI |
| R2 | 保持既有 mirrors、下载重试、备份和最终失败保护 | scripts/dev/configure_docker_desktop_mirrors.ps1 | not_satisfied | 待实现与回归测试 |
| R3 | 完成 L2 Completion Audit、Review、Ready Check、永久 CI 并合并 main | AGENTS.md | not_satisfied | 待最终门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不涉及浏览器行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端或数据库行为 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract |
| Real Full-stack Golden Path | not_applicable | 不修改完整运行栈语义 |
| Real Provider Probe | not_applicable | 不涉及外部 Provider |
| Docs / Governance / Other | required | Red/Green unit、Windows PowerShell AST 语法检查、Completion Gate 与永久 CI |

# Completion Audit

- [ ] upstream_re_read: Ready 前重新读取用户问题、AGENTS、Skill、Blueprint 07、当前 mirror helper、测试和 Windows workflow。
- [ ] change_coverage: Ready 前确认 R1-R3 均由实现/测试/门禁覆盖。
- [ ] reverse_audit: Ready 前确认没有修改 mirror 列表、Linux setup、Dockerfile/Compose 或包下载源。
- [ ] unresolved_cleared: Ready 前清零 `not_satisfied`。

# 分步计划

1. Red：增加回归断言，要求脚本存在重启后有界 mirror 重试等待，并禁止恢复成单次验证。
2. Green：将重启后的验证改为循环等待预期 mirrors；保留原有 fail-closed 和恢复提示。
3. Verify：运行目标 unit、Windows PowerShell 语法检查和永久 CI。
4. Review/Ready：完成 Completion Audit、两阶段 Review、Ready Check 后正常合并，并单独归档 Change。

# 当前事实

用户本机已观察到：脚本写入的 `%USERPROFILE%\.docker\daemon.json` 包含三个预期 mirror，脚本重启 Docker Desktop 后立即报“docker info does not report expected registry mirrors”；随后手工执行 `docker info --format '{{json .RegistryConfig.Mirrors}}'` 已返回三个预期 mirror。当前 helper 的实现是 `Wait-DockerEngineReady()` 首次成功即返回，随后只调用一次 `Test-ExpectedMirrorsApplied`，与该假阴性一致。

# Git / 交付

- Branch: `fix/docker-desktop-mirror-verification-retry`
- PR: 待创建
- Merge: 用户已明确授权在门禁通过后合并到 `main`
