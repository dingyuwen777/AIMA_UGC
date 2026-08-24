---
schema: rvc-change/v1
id: CHG-20260824-docker-mirror-probe-output
title: 修复 Windows Docker mirror probe 输出解析
level: L2
status: in_progress
owner: chatgpt
branch: fix/docker-mirror-probe-output
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

修复 Windows Docker Desktop mirror 初始化在实际 `docker info` 已经报告全部 AIMA mirrors 时仍持续等待并最终失败的问题。修复必须覆盖生产 helper 的真实子进程参数传递、stdout 解析、mirror 数组构造和有效状态判断，而不是只测试 predicate 或增加等待时间。

# 可观察成功标准

- [ ] 用户当前 6-mirror 状态中，AIMA mirrors 全部存在且相对顺序正确时，正式 probe 返回 6 个独立 mirror 字符串并立即判定成功。
- [ ] probe 不依赖 PowerShell 对 JSON 顶层数组的枚举/转换细节，不把多个 mirror 合并成一个空格分隔字符串。
- [ ] 使用 Docker 官方支持的 Go template `range + println`，让 `docker info --format` 每行输出一个 mirror；stdout 只按非空行解析。
- [ ] Windows Runner 通过真实临时 `docker.exe` 可执行文件走正式 `Get-DockerRegistryMirrorProbe()`，同时验证命令参数、stdout、数组元素、额外 mirror predicate。
- [ ] 缺失 AIMA mirror 或 AIMA 相对顺序错误仍 fail closed。
- [ ] 现有 restart/probe/overall timeout、daemon.json 精确配置、单一 mirror 配置源、Linux 行为全部保持不变。

# 非目标

- 不修改 `scripts/config/docker_hub_mirrors.txt` 的 mirror 列表或顺序。
- 不修改 Linux mirror 初始化。
- 不修改 Dockerfile、Compose、npm/PyPI/Debian 下载源。
- 不增加新的运行依赖。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 当前实际 6-mirror 输出必须可正确识别，不再错误重启/等待 | user:2026-08-24-real-bootstrap-output | not_satisfied | 用户真实日志显示 `docker info` 每次立即返回全部 6 个 mirror，但正式 helper 连续 20 秒判未就绪 |
| R2 | 必须真实可用，不能继续只靠不完整测试 | user:2026-08-24-real-runtime-required | not_satisfied | 前一版 Windows CI 只直接测试 predicate，没有让 production probe 解析真实形状的 Docker 输出 |
| R3 | 保持现有单一 mirror 配置源与其他 Docker/包源方案 | AGENTS.md | not_satisfied | 待 diff/回归确认 |
| R4 | 完成 L2 Audit/Review/Ready Check/永久 CI 并正常合并 main | AGENTS.md | not_satisfied | 待门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不涉及浏览器 |
| Backend/API/PostgreSQL Integration | not_applicable | 不涉及后端/数据库业务行为 |
| Contract / Generated Client | not_applicable | 无公共 Contract 变化 |
| Real Full-stack Golden Path | not_applicable | 不改变业务运行栈，永久 CI 作为回归 |
| Real Provider Probe | not_applicable | 不涉及外部 Provider |
| Docs / Governance / Other | required | Windows PowerShell 5.1 下 production probe + fake docker.exe 真实子进程行为测试、Python static regression、永久 CI |

# Completion Audit

- [ ] upstream_re_read: Ready 前重新读取用户失败日志、AGENTS、Skill、最终 helper/test/workflow。
- [ ] change_coverage: R1-R4 全覆盖。
- [ ] reverse_audit: 确认正式 probe 从进程 argv 到 stdout 到 string[] 到 predicate 全链路有测试，且无无关 Docker/Linux/包源改动。
- [ ] unresolved_cleared: Ready 前清零 not_satisfied。

# Git / 交付

- 用户明确要求真实可用；本任务属于前序已授权“完整修复并合并 main”的连续修复。
- 实现门禁全绿后正常合并 main，并创建独立归档 PR。
