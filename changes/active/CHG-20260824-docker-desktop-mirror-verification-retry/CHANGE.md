---
schema: rvc-change/v1
id: CHG-20260824-docker-desktop-mirror-verification-retry
title: 统一 Docker Hub mirror 配置并修复 Docker Desktop 验证时序
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
  - scripts/config/docker_hub_mirrors.txt
  - scripts/dev/configure_docker_desktop_mirrors.ps1
  - scripts/setup_dev_environment.sh
  - tests/unit/test_docker_build_sources.py
  - .github/workflows/compose-windows-desktop.yml
  - docs/guides/03_Windows Docker Desktop Compose运行.md
  - docs/guides/04_Docker国内构建源与本地重置.md
contracts: []
data_changes: []
---

# 目标

把 Docker Hub mirror 列表收敛为仓库内唯一配置源，并修复 Windows 首次运行 `scripts/setup_dev_environment.cmd` 时 Docker Desktop 重启后的 mirror 验证假阴性。

Windows 与 Linux 初始化脚本必须读取同一个 mirror 配置文件；以后增删或调整 mirror 顺序只修改这一处。Docker Desktop restart 后，脚本在有界时间内持续检查 `docker info` 的 `RegistryConfig.Mirrors`，直到配置真正生效或超时失败。

# 可观察成功标准

- [ ] `scripts/config/docker_hub_mirrors.txt` 是 Docker Hub mirrors 的唯一仓库配置源；非空、非注释行按文件顺序形成 mirror 列表。
- [ ] Windows `configure_docker_desktop_mirrors.ps1` 从该文件读取 mirrors，不再硬编码地址。
- [ ] Linux `setup_dev_environment.sh` 从同一文件读取 mirrors，不再维护第二份地址列表。
- [ ] Docker Desktop restart 后持续等待 `docker info` 报告预期 mirrors，而不是 Engine 首次可访问后只检查一次。
- [ ] 验证重试有明确上限和固定间隔；真正超时仍 fail closed，并输出 daemon.json 备份/恢复提示。
- [ ] 三个既有 mirror 的当前顺序、`max-download-attempts=5`、daemon.json 备份和其他配置合并逻辑保持不变。
- [ ] 已经正确应用 mirrors 时直接返回，不触发无意义重启。
- [ ] 文档只描述统一配置文件和运行行为，不再复制维护 mirror URL 列表。
- [ ] Windows PowerShell 语法、目标 unit 与永久 CI 全部通过。

# 范围

- Docker Hub mirror 唯一配置文件。
- Windows Docker Desktop mirror helper 的配置读取、重启后验证等待逻辑。
- Linux 宿主初始化脚本读取统一 mirror 列表。
- 对应静态回归测试、Windows CI 语法门禁和运行文档。

# 非目标

- 不更换当前三个 Docker Hub mirror，也不改变优先顺序。
- 不改变 Dockerfile、Compose、Docker image identity、npm/PyPI/Debian 下载源。
- 不改变 Docker Desktop/Engine 的其他配置项。
- 不把公共 mirror 可用性探测加入日常运行或普通 CI。

# 必须保持不变

1. 当前 mirror 顺序仍为 `docker.1panel.live`、`hub.1panel.dev`、`docker.m.daocloud.io`；只是从脚本硬编码迁移到唯一配置文件。
2. `max-download-attempts` 仍为 5。
3. 修改既有 daemon.json 前继续创建时间戳备份，并保留其他已有 Docker Engine 配置。
4. Docker Desktop CLI 不可用时继续显式 warning/skip，不伪装成功。
5. 最终超时或实际未应用时仍 fail closed。
6. Linux 继续保留 `/data/docker`、日志 driver/rotation 和 daemon 配置校验等原有行为。

# 已确认关键决策

1. 用户确认将 Docker Hub mirror 列表收敛成单一配置源，后续新增/删除 mirror 只修改一个文件。
2. Windows 与 Linux 必须消费同一配置文件，测试不再维护第二份 URL 常量。
3. 配置文件允许空行与 `#` 注释；有效行顺序即 Docker registry mirror 优先顺序。
4. 文档只引用配置文件位置，不复制 URL 清单，避免形成多个事实源。
5. Windows 重启后 mirror 生效允许存在短暂延迟，因此验证采用有界重试；超时仍视为失败。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 修复 mirror 已最终生效但脚本重启后过早报错的问题 | user:docker-desktop-mirror-verification-false-negative | not_satisfied | Red `6a6c375d1ea37a338c86d3a924f1833721b2ea7a`：Ruff/mypy 通过后 unit 1 failed / 603 passed，唯一失败为缺少 mirror 重试 |
| R2 | Docker Hub mirror 列表改成单一配置源，后续增删只改一处 | user:centralize-docker-hub-mirrors | not_satisfied | 待统一配置文件、Windows/Linux 消费与测试 |
| R3 | 保持既有 mirrors、下载重试、备份、Linux daemon 行为和最终失败保护 | scripts/dev/configure_docker_desktop_mirrors.ps1 | not_satisfied | 待实现与回归测试 |
| R4 | 文档只描述最新单一事实源，不复制 URL 清单 | user:centralize-docker-hub-mirrors | not_satisfied | 待同步 Windows/Docker Guide |
| R5 | 完成 L2 Completion Audit、Review、Ready Check、永久 CI 并合并 main | AGENTS.md | not_satisfied | 待最终门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不涉及浏览器行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端或数据库行为 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract |
| Real Full-stack Golden Path | not_applicable | 不修改完整运行栈业务语义 |
| Real Provider Probe | not_applicable | 不涉及外部 Provider |
| Docs / Governance / Other | required | Red/Green unit、Windows PowerShell AST 语法检查、Linux/Windows 单一配置源静态约束、Completion Gate 与永久 CI |

# Completion Audit

- [ ] upstream_re_read: Ready 前重新读取用户确认、AGENTS、Skill、Blueprint 07、当前 mirror helper、Linux setup、测试、Windows workflow 和两份 Guide。
- [ ] change_coverage: Ready 前确认 R1-R5 均由实现/测试/文档/门禁覆盖。
- [ ] reverse_audit: Ready 前确认 mirror URL 只在统一配置文件中维护；Windows/Linux 均从该文件读取；没有改变 Dockerfile/Compose 或包下载源。
- [ ] unresolved_cleared: Ready 前清零 `not_satisfied`。

# 分步计划

1. Red：要求 Windows 存在重启后有界 mirror 重试；要求 mirror URL 只存在统一配置文件、Windows/Linux 都从它读取。
2. Green：创建统一配置文件，改 Windows/Linux loader，并实现 Docker Desktop restart 后的有界 mirror 验证。
3. Docs：Windows/Docker Guide 只引用统一 mirror 配置文件和运行语义。
4. Verify：目标 unit、PowerShell 语法、永久 CI。
5. Review/Ready：Completion Audit、两阶段 Review、Ready Check 后正常合并，并单独归档 Change。

# 当前事实

用户本机已观察到：脚本写入的 `%USERPROFILE%\.docker\daemon.json` 包含三个预期 mirror，脚本重启 Docker Desktop 后立即报“docker info does not report expected registry mirrors”；随后手工执行 `docker info --format '{{json .RegistryConfig.Mirrors}}'` 已返回三个预期 mirror。当前 helper 的实现是 `Wait-DockerEngineReady()` 首次成功即返回，随后只调用一次 `Test-ExpectedMirrorsApplied`，与该假阴性一致。

当前仓库还在 Windows PowerShell 与 Linux shell 中分别硬编码同一组三个 mirror；两份 Guide 也复制了 URL 列表。用户已确认改为单一配置源。

# Git / 交付

- Branch: `fix/docker-desktop-mirror-verification-retry`
- PR: #190 Draft
- Merge: 用户已明确授权在门禁通过后合并到 `main`
