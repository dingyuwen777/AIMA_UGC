---
schema: rvc-change/v1
id: CHG-20260824-docker-mirror-probe-output
title: 修复 Windows Docker mirror probe 输出解析
level: L2
status: ready_for_review
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

修复 Windows Docker Desktop mirror 初始化在实际 `docker info` 已经报告全部 AIMA mirrors 时仍持续等待并最终失败的问题。正式 probe 必须在 Windows PowerShell 5.1 中把 Docker 返回的多个 mirrors 保持为独立字符串，并把当前 6-mirror 状态立即识别为有效，而不是依赖 JSON 顶层数组的枚举/类型转换行为。

# 可观察成功标准

- [x] 用户当前 6-mirror 状态中，AIMA mirrors 全部存在且相对顺序正确时，正式 probe 返回 6 个独立 mirror 字符串并立即判定成功。
- [x] probe 不依赖 PowerShell 对 JSON 顶层数组的枚举/转换细节，不把多个 mirror 合并成一个空格分隔字符串。
- [x] 使用 Docker 官方支持的 Go template `range + println`，让 `docker info --format` 每行输出一个 mirror；stdout 只按非空行解析。
- [x] Windows Runner 通过真实临时 `docker.exe` 可执行文件走正式 `Get-DockerRegistryMirrorProbe()`，同时验证命令参数、stdout、数组元素、额外 mirror predicate。
- [x] 缺失 AIMA mirror 或 AIMA 相对顺序错误仍 fail closed。
- [x] 现有 restart/probe/overall timeout、daemon.json 精确配置、单一 mirror 配置源、Linux 行为全部保持不变。

# 非目标

- 不修改 `scripts/config/docker_hub_mirrors.txt` 的 mirror 列表或顺序。
- 不修改 Linux mirror 初始化。
- 不修改 Dockerfile、Compose、npm/PyPI/Debian 下载源。
- 不增加新的运行依赖。
- 不重复修改 Guide：现有 Guide 已经正确描述“允许额外有效 mirrors、AIMA 状态已满足时立即跳过 restart”，本次只修正实现与该现有事实不一致的问题。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 当前实际 6-mirror 输出必须可正确识别，不再错误重启/等待 | user:2026-08-24-real-bootstrap-output | satisfied | 用户真实日志显示 `docker info` 每次立即返回 6 个 mirrors。Red Windows run `32689316549` 的 production probe 在 Windows PowerShell 5.1 中复现 `Expected 6 independent mirrors, got 1`；最终 Windows run `32689710325` 的同一 production probe step success，6 个 mirrors 被保持为独立元素并通过 AIMA predicate |
| R2 | 必须真实可用，不能继续只靠不完整 predicate 测试 | user:2026-08-24-real-runtime-required | satisfied | 永久 Windows workflow 编译真实临时 `docker.exe` 并通过正式 `System.Diagnostics.Process` 子进程入口调用 production `Get-DockerRegistryMirrorProbe()`；中间 Green run `32689407855` 进一步真实发现未加引号时模板被拆成 `{{range`，修正 argv 分组后最终 run `32689710325` success |
| R3 | 保持现有单一 mirror 配置源与其他 Docker/包源方案 | AGENTS.md | satisfied | PR #195 changed files 仅本 Change、PowerShell helper、目标 unit test、Windows workflow；`scripts/config/docker_hub_mirrors.txt`、Linux setup、Dockerfile、Compose、Debian/PyPI/npm 配置均未修改；功能审计 HEAD `9dcb24a9b89eb95a9aa64ca752bebe6c0d931ca7` 的 10 个非 Completion 永久 workflow 全部 success |
| R4 | 完成 L2 Audit/Review/Ready Check/永久 CI 并正常合并 main | AGENTS.md | explicitly_deferred | Requirement Review A1/A2、Code Quality、Completion Audit 已完成；合并按仓库门禁刻意延期到本 `ready_for_review` 提交的 11 个永久 workflow 全绿后执行，用户已明确授权完整修复并合并 main |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 不涉及浏览器 |
| Backend/API/PostgreSQL Integration | not_applicable | 不涉及后端/数据库业务行为 |
| Contract / Generated Client | not_applicable | 无公共 Contract 变化 |
| Real Full-stack Golden Path | not_applicable | 不改变业务运行栈；Internal V1-A、Stage 8F 和 Windows named-volume Runtime 作为永久回归门禁均 success |
| Real Provider Probe | not_applicable | 不涉及外部 Provider |
| Docs / Governance / Other | required | Windows Server 2025 / Windows PowerShell 5.1 production probe + 临时 docker.exe 真实子进程行为测试、Python static regression、Windows Runtime、永久 CI |

# Completion Audit

- [x] upstream_re_read: Ready 前重新读取用户两次真实失败输出、当前分支 AGENTS、Reliable Vibe Coding、Development Workflow/Verification Review、最终 helper/test/workflow，并重新核对当前 `main`。
- [x] change_coverage: R1-R4 覆盖真实 6-mirror 失败、Windows PowerShell 5.1 production probe、现有方案兼容边界和正式交付门禁。
- [x] reverse_audit: 从 production `ProcessStartInfo` argv → fake/real docker-compatible Go template → stdout 多行 → `string[]` → `Test-ExpectedMirrorsPresent()` 反向检查完整链路；Windows Runner 直接执行同一生产 probe；PR changed files 仅 4 个预期路径，mirror 配置、Linux setup、Dockerfile、Compose、依赖、业务代码、Contract/Migration 未修改。
- [x] unresolved_cleared: R1-R3 satisfied；R4 仅按正式 Ready/CI 门禁 explicitly_deferred 到 Final Ready HEAD 全绿之后，没有范围内未决实现或设计。

# Review

## Requirement Review A1：上游要求 → Change

通过。用户提供的最新原始症状已经把完成定义收敛为：Docker Engine 实际 6-mirror 输出必须在 Windows PowerShell 5.1 的正式 helper 中被正确识别，且不能再用不经过 production probe 的 predicate 测试宣称修复。Change 明确包含这两项，并保留既有单一 mirror 配置源、超时和跨平台边界。

## Requirement Review A2：Change → 实现 / 测试 / 文档

通过。production probe 改为 Docker Go template `{{range .RegistryConfig.Mirrors}}{{println .}}{{end}}`，整个模板用双引号保持为单一 argv；stdout 按 CRLF/LF 非空行拆分并返回 `string[]`。Windows workflow 的临时 `docker.exe` 检查收到的实际 argv，并模拟用户同形状的 3 个额外 mirror + 3 个 AIMA mirror。旧 JSON 路径在 Red 中得到 `got 1`，未加引号的第一版 Green 又得到 `unexpected docker format: {{range`，最终实现同时消除两个真实 Windows 边界问题。现有 Guide 描述的目标行为未改变，因此无需重复改文档。

## Code Quality Review

通过，无 Serious/Important finding。实现只替换 probe 的输出协议，不改 daemon.json 写入、有效 mirror predicate、restart/overall/probe timeout、恢复提示或其他平台。使用 Docker 自带 Go template 和 .NET/PowerShell 现有能力，无新增依赖。逐行协议比 JSON 顶层数组更直接，避免 PowerShell 5.1 的枚举/强制类型歧义；模板的 Windows argv 引号已由真实子进程行为测试验证。probe/cleanup 等待仍全部有界，错误继续 fail closed。

# 验证证据

## Red：真实复现用户故障

Red HEAD：`94503369a8d47355abcc2a5015b445d798fe4f18`

Windows Docker Desktop Compose Compatibility run `32689316549`，Windows Compose CLI job `97320004643` 在 Windows Server 2025 / Windows PowerShell 5.1 中编译临时 `docker.exe`，production `Get-DockerRegistryMirrorProbe()` 实际结果：

```text
Expected 6 independent mirrors, got 1: https://legacy-one.example/ ... https://docker.m.daocloud.io
```

这与用户本机日志中“6 个 URL 在 helper 内表现成一个空格分隔值并持续等待”的症状同构，证明旧 production probe 确实有缺陷。

## Green 中间边界发现

Green candidate `20d7497670d6b1925dfe9c4872c12737d5a91777` 改为 `range + println` 后，Windows run `32689407855` 的同一 production probe 报：

```text
Production probe failed: unexpected docker format: {{range
```

说明未加引号的 Go template 在 Windows `ProcessStartInfo.Arguments` 中被空格拆成多个 argv。随后将整个 template 双引号包裹，继续沿用同一真实子进程测试，而不是降低断言。

## Green / 功能审计

功能审计 HEAD：`9dcb24a9b89eb95a9aa64ca752bebe6c0d931ca7`

- Windows Docker Desktop Compose Compatibility `32689710325`: success；production probe、predicate、PowerShell AST、CMD/PowerShell Compose、named-volume Runtime 全部 success。
- CI `32689710292`: success；Backend/repository checks、Windows bootstrap、Stage 1/2/3A 全部 success。
- Internal V1-A `32689710347`: success。
- Stage 8F `32689710273`: success。
- Local Dev Bootstrap `32689710271`: success。
- Stage 6 `32689710402`: success。
- Stage 7 Plan `32689710284`、Keyword Packs `32689710353`、Scheduler `32689710275`、Provider Config `32689710350`: success。
- Change Completion Gate `32689710293` 在 Change 仍为 `in_progress` 时按治理规则预期 failure；本 `ready_for_review` 提交后重新执行。

中间提交曾因新增 Python 静态断言的 Ruff formatter/E501 要求导致 Quality job failure；对应 Scheduler/Provider Unit 与 PostgreSQL 均 success。按 Ruff 精确要求修正测试格式后，功能审计 HEAD 的所有非 Completion 永久 workflow 全部 success，没有把格式失败伪装成功能失败。

# 文档影响

无需修改正式 Guide。当前 Guide 已正确描述：Docker Desktop 有效状态允许额外 mirrors，AIMA managed mirrors 已全部生效且 daemon 配置匹配时立即跳过 restart；本次只是让 production probe 真正实现该已有事实。

# Git / 交付

- Branch: `fix/docker-mirror-probe-output`
- PR: #195
- Functional audit HEAD: `9dcb24a9b89eb95a9aa64ca752bebe6c0d931ca7`
- Merge authorization: 用户明确要求确保真实可用，并沿用本轮“完整修复、合并到主分支”的正常合并授权。
- Final gate: 本 `ready_for_review` HEAD 必须重新通过 11 个永久 workflow。
- Archive: 实现 PR 合并后创建独立归档 PR，将本 Change 标记 `done` 并移动到 `changes/archive/2026-08/`。
