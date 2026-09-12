---
schema: coding-change/v1
id: CHG-20260912-browser-security-headers
title: 公网浏览器安全响应头与 IP 端口兼容整改
level: L3
status: ready_for_review
owner: dingyuwen777
branch: fix/browser-security-headers
created: 2026-09-12
updated: 2026-09-12
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - security
  - deployment
  - release
  - tests
  - docs
affected_paths:
  - frontend/nginx.conf
  - frontend/tests/nginx-security.spec.ts
  - Dockerfile
  - docs/blueprint/05_日志安全部署与运维.md
  - docs/operations/01_生产部署与离线Release方案.md
  - docs/roadmap/02_生产上线实施路线.md
  - changes/active/CHG-20260912-browser-security-headers/CHANGE.md
contracts:
  - Frontend HTTP security response headers
  - Direct host IP and port HTTP diagnostic access
  - Public HTTPS ingress ownership boundary
data_changes:
  - none
---

# 变更摘要

- **问题**：Acunetix 对 `https://ugctest.aimatech.com` 的扫描发现 HSTS、CSP 和 Permissions-Policy 缺失；`/clientaccesspolicy.xml` 与 `/crossdomain.xml` 还会落入 SPA fallback。
- **目标**：不改变业务、API、数据库、Compose 端口绑定和固定本地管理员边界，由 Frontend Nginx 补齐应用侧浏览器安全策略，同时保留服务器 IP+端口 HTTP 诊断入口。
- **生产边界**：本 Change 不部署真实服务器，不修改 DNS、证书、443 或企业外层网关；真实公网 TLS/浏览器兼容与安全扫描复验继续属于 Production 候选环境证据。

# 已确认事实与设计决定

| 编号 | 事实 / 决定 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | Frontend Nginx 当前监听 8080、`server_name _;`，同源代理 `/api/` 与 `/health/`，其余使用 SPA fallback | `frontend/nginx.conf` | 不改变路由、代理与域名无关能力 |
| E2 | Compose 由 `AIMA_HTTP_BIND_IP:AIMA_HTTP_PORT` 发布 Frontend 8080，API 只在 Compose 网络内 expose 8090 | `compose.yaml` | 不修改 Compose 端口契约；IP+端口能力由 bind/firewall 决定 |
| E3 | 当前前端为 Vue + Element Plus + ECharts，API 使用同源路径 | `frontend/package.json` 与当前实现 | CSP 初始策略允许 inline style、HTTPS/data/blob 图片，但脚本保持 self-only |
| E4 | Release PR dry-run 会构建 linux/amd64 Frontend 镜像、离线重放 Compose，并 curl Frontend/Readiness | `.github/workflows/release.yml` | 通过 Dockerfile 真实变更触发现有 Release 验证，不新增平行 Workflow |
| E5 | 用户确认继续接受当前固定“本地管理员”身份，并要求整改验证通过后合并 main | #466 与本轮授权 | 不扩大到企业认证改造或真实部署 |

# 方案比较与选择

| 方案 | 优点 | 风险 / 缺点 | 结论 |
| --- | --- | --- | --- |
| A. 所有 Header 都由企业外层网关维护 | 集中治理 | CSP/Permissions 与应用资源行为耦合，代码与部署事实分离；不同环境容易漂移 | 不选 |
| B. 所有 TLS/跳转/Header 都塞进应用 Nginx | 单点配置 | 需要把证书/443/域名写入应用，破坏当前域名无关和 IP+端口诊断边界 | 不选 |
| C. 应用 Nginx 负责浏览器策略；外层入口负责 TLS/证书/HTTP→HTTPS | 保持同一镜像跨域名部署，CSP 与应用同版本；外层基础设施职责清晰 | HSTS 可能被外层重复注入，生产必须检查最终响应 | **采用** |

具体决定：

- HSTS 使用 `max-age=31536000`，暂不启用 `includeSubDomains` 或 `preload`；
- CSP 使用 enforced policy：`default-src 'self'`，脚本 self-only，样式暂允许 `'unsafe-inline'`，图片允许 self/data/blob/HTTPS，连接保持 same-origin；
- Permissions-Policy 禁用当前业务未使用的 camera、microphone、geolocation、payment、usb；
- 同时补 `X-Content-Type-Options: nosniff` 与 `Referrer-Policy: strict-origin-when-cross-origin`；
- 所有 Header 使用 Nginx `always`，让错误响应也具备一致安全边界；
- 两个旧版跨域策略文件精确匹配并返回 404；
- 不增加任何 HTTP→HTTPS redirect，保持 `server_name _;` 与 8080 HTTP 监听；
- Docker frontend image 在 build 阶段执行 `nginx -t`，让无效配置在 Release 候选构建前失败。

# 成功标准

- [x] Frontend Nginx 补齐批准的五类浏览器安全响应头，HSTS 不使用 `includeSubDomains`/`preload`。
- [x] `/clientaccesspolicy.xml` 与 `/crossdomain.xml` 显式 404。
- [x] `/api/`、`/health/`、SPA fallback、`server_name _;`、8080 HTTP 监听保持不变且无强制 HTTPS redirect。
- [x] Backend、Schema/Migration、Compose 端口映射、env binding 模型和前端依赖不变。
- [x] Frontend Vitest 对 Header、404 和 IP+端口兼容不变量建立静态回归；Docker build 增加 `nginx -t`。
- [x] Blueprint、Operations、Production Roadmap 同步实现事实与仍未完成的真实公网验收边界。
- [ ] PR exact-head required CI、Release PR dry-run、独立 Review、guarded merge、main fresh CI 与原生 Change archive 由 GitHub 生命周期在本 Ready 提交后完成。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 补齐 HSTS/CSP/Permissions-Policy/nosniff/Referrer-Policy，且 HSTS 不启用 includeSubDomains/preload | #466 / AC1 | satisfied | `frontend/nginx.conf` server-level `add_header ... always`；`frontend/tests/nginx-security.spec.ts` 精确断言策略 |
| R2 | 两个旧版跨域策略文件返回 404，不进入 SPA fallback | #466 / AC2 | satisfied | 两个 exact-match Nginx location + Vitest 404 回归 |
| R3 | 保留代理、SPA、server_name、8080 和 IP+端口 HTTP 能力，不新增强制 HTTPS redirect | #466 / AC3 | satisfied | 原 `/api/`、`/health/`、`try_files` 保持；Vitest 验证 8080/server_name/无 redirect |
| R4 | 不改变 Backend、DB、Compose 端口、env binding 或前端依赖 | #466 / AC4 | satisfied | 本 Change affected diff 只涉及 Frontend Nginx/test、Docker build 校验与文档；无上述 Contract 文件变化 |
| R5 | 持久回归 + GitHub Runner 构建/回放真实 Frontend 候选并证明 IP+端口可用 | #466 / AC5 | explicitly_deferred | 静态 Vitest 与 Docker `nginx -t` 已实现；Release PR dry-run 由本 PR 的 Dockerfile 变更自动触发并在合并前核验 |
| R6 | 同步安全/部署/运维文档，不能误报完整 Production 安全已完成 | #466 / AC6 | satisfied | Blueprint 记录长期 Owner 边界；Operations 记录部署/Smoke/回滚；Roadmap 明确应用侧完成但真实 HTTPS 候选仍未闭环 |
| R7 | required CI、Release dry-run、Review 通过后再合并；合并后 main fresh 与 Change 归档闭环 | #466 / AC7 | explicitly_deferred | 该步骤必须绑定本 Ready commit/PR/merge revision，按仓库原生 GitHub Actions 与 Change Archive Automation 执行 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 行为 / Unit / Component | required | Vitest 读取真实 `nginx.conf`，验证 Header、404、代理/SPA/8080/无 redirect |
| 接口 / 契约 | required | HTTP 响应头策略和旧策略文件 404 作为浏览器入口 Contract；业务 API Contract 不变 |
| 集成 / 持久化 / 运行时依赖 | required | Release PR dry-run 构建真实 frontend image、`nginx -t`、离线 Compose replay、Readiness/Frontend curl |
| 用户 / 工作流验收 | required | Release replay 的直接 HTTP Frontend 访问证明 IP+端口入口仍成立；真实公网浏览器兼容留给生产候选 |
| 跨组件 Golden Path | required | canonical Compose frontend→health/API 接线由 Release replay 验证，既有 Frontend CI 回归业务页面 |
| 外部依赖 / Provider Probe | not_applicable | 本 Change 不调用 TikHub/LLM，也不需要付费 Provider 事实 |
| 构建 / 打包 / 运行 | required | Frontend lint/typecheck/test/build + Docker frontend build `nginx -t` + Release dry-run |
| 文档 / 治理 / 其他 | required | Change Ready、Docs/Secret/Owner gate、Blueprint/Operations/Roadmap 一致性、独立 Review |

# 风险、兼容、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| CSP 误拦合法前端资源 | 主要功能回归风险 | 初始策略保留 inline style 与 HTTPS/data/blob 图片；合并前跑现有 Frontend 回归，真实生产候选再做浏览器 Console 验证 |
| HSTS 撤销不是普通镜像回滚 | 浏览器会缓存策略 | 暂不使用 includeSubDomains/preload；确需撤销时在可用 HTTPS 入口返回 `max-age=0` |
| 外层网关重复注入 HSTS | 可能产生冲突策略 | Production 上线前 curl 最终 HTTPS 响应，明确单一 Owner；本 Change 不假装知道仓库外状态 |
| 直接 IP+端口访问被破坏 | 用户明确要求保持 | 不做 redirect；保留 8080/server_name/Compose binding；Release replay 继续 curl HTTP Frontend |
| 多域名部署 | 应保持无代码分叉 | CSP 使用 `'self'`、Nginx `server_name _;`，无硬编码 `ugctest`/`ugc` 域名 |
| 数据/Schema | 无变化 | 无 Migration、数据转换或数据库回滚动作 |

# 文档影响

Docs Impact 为 `targeted`：同步长期运行安全边界、生产部署/Smoke/回滚说明和 Production Roadmap 子状态；不新增第二套部署架构，不把 GitHub Runner 证据冒充真实公网生产验收。

# 完成审计

- [x] upstream_re_read：已重新读取 #466、Production Roadmap、Blueprint、Operations、当前 Nginx/Compose/Dockerfile/Release Workflow 和 Frontend 工具链事实。
- [x] change_coverage：AC1—AC7 已逐条映射到实现、测试、文档或明确的 PR/main 生命周期 deferred evidence，没有遗漏认证/数据等非目标。
- [x] reverse_audit：从外层 HTTPS→Frontend Nginx→SPA/API/health，以及 IP+端口→Frontend Nginx 两个方向复核；没有引入域名硬编码、redirect、Backend/DB/Compose Contract 变化。
- [x] unresolved_cleared：实现与文档范围内没有 not_satisfied；仅 exact-head CI/Release/merge/main-fresh/archive 因必须在 PR 生命周期发生而显式 deferred，并且是合并前/后强门禁。

# 执行清单

- [x] 读取项目治理、canonical Agent_Skills 路由、L3 Change/验证/Review/交付规则
- [x] 建立 Issue #466 作为稳定 Requirement Source
- [x] 从最新 main 创建隔离分支
- [x] 修改 Frontend Nginx、安全响应头与旧策略文件 404
- [x] 增加 Frontend Vitest 与 Docker `nginx -t`
- [x] 同步 Blueprint / Operations / Production Roadmap
- [ ] 创建 PR 并等待 exact-head CI / Release dry-run
- [ ] 独立 Review 当前 PR diff 与验证充分性
- [ ] 正常合并 main，不绕过保护规则
- [ ] 校验 main fresh CI、Issue 收口、原生 Change archive 与任务分支清理
