---
schema: coding-change/v1
id: CHG-20260926-104500-compose-script-priority
title: 统一文档 Compose 启停脚本优先级
level: L2
status: ready_for_review
owner: yuwen.ding
branch: docs/609-compose-script-priority
created: 2026-09-26T10:45:00+08:00
updated: 2026-09-26
completion_gate: required
depends_on:
  - CHG-20260926-100600-doc-navigation-quickstart
affected_areas:
  - docs
  - governance
affected_paths:
  - docs/02_环境运行与部署.md
  - docs/guides/03_Windows_Docker_Desktop_Compose运行.md
  - docs/operations/01_生产部署与离线Release方案.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：#609 第一轮已经把启停速查前置，但 Linux/WSL 与 Windows 仍把 `docker compose up/down` 放在首选位置；用户明确希望优先使用 `start_compose.py / stop_compose.py`，且所有操作入口必须成对给出启动和停止。
- **拟议修改**：把完整 Compose/Release 场景统一为脚本优先，Compose CLI 降为首次镜像准备、底层备用或调试方式；源码热更新继续使用 backend.py/frontend.py。
- **预期结果**：读者在 docs/02、Windows Guide、Production Operations 中看到一致的日常启停入口，不再需要自行判断该用脚本还是底层 Compose 命令。

# 背景、现状与问题

## 背景

Issue #609 在 Implementation PR #612 合并后收到用户新增明确要求：完整 Compose/Release 场景优先使用 start/stop 脚本，并且文档不能只展示启动命令，必须同时展示停止命令。

## 当前现状

- docs/02 第一屏已包含四类环境启停，但 Linux/WSL 和 Windows 仍先展示 docker compose；
- Windows Guide Section 4 先展示 Compose CLI，再把 start_compose.py 写成可选入口；
- Production Operations 的“服务器离线部署”运行原则仍以 docker compose up 表达，没有在该运行入口同时给出 stop_compose.py；
- Release Bundle 当前真实包含 start_compose.py 和 stop_compose.py。

## 问题、根因或约束

当前文档对同一完整 Compose Runtime 暴露了两个“看起来都像主入口”的方式。虽然都合法，但日常推荐不一致，增加操作选择成本，也弱化了脚本自动资源规划和同一 compose.auto.yaml 的价值。

## 不修改的后果

- Linux/Windows/服务器文档继续呈现不同默认入口；
- 用户可能绕过 start_compose.py 的自动资源规划；
- 只看到启动、不看到对应停止的局部文档会增加停机操作查找成本。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 | 决策 |
| --- | --- | --- | --- |
| E1 | start_compose.py 自动读取 Docker Engine CPU/内存、生成 compose.auto.yaml，并启动 no-build/no-pull Runtime | scripts/deploy/start_compose.py | 日常 Compose 启动优先脚本 |
| E2 | stop_compose.py 复用 env + compose.auto.yaml，调用 Compose stop 并保留容器/网络/数据 | scripts/deploy/stop_compose.py | 日常停止必须与启动脚本成对 |
| E3 | Windows 下 start/stop 脚本自动叠加 compose.windows.yaml | start/stop scripts | Windows 无需手写 overlay 作为首选入口 |
| E4 | Release Bundle 包含 start_compose.py/stop_compose.py | scripts/release/release_bundle.py | 服务器正式运行优先 Bundle 脚本 |
| E5 | 脚本不负责 build/pull | start_compose.py | 首次镜像准备仍保留 Compose CLI 说明 |

## 推断与待确认

无。

# 目标、成功标准与非目标

## 目标

完整 Compose/Release 场景统一“脚本优先、启停成对、Compose CLI 备用”。

## 成功标准

- [ ] Issue #609 AC9 满足，同时重新完成 AC8 的 current-head CI/Review/Delivery。
- [ ] docs/02 Linux/WSL、Windows、服务器均把 start/stop 脚本作为主入口。
- [ ] Windows Guide 的推荐日常入口同时展示启动和停止脚本。
- [ ] Production Operations 的服务器运行入口同时展示启动和停止脚本。
- [ ] Compose CLI 保留为镜像准备、底层备用或 down/remove 场景，不再与脚本争夺“推荐日常入口”。

## 范围

仅上述三篇当前运行文档与本 Change。

## 非目标

- 不修改任何脚本、Compose、Runtime、Release Bundle；
- 不改变源码开发 backend.py/frontend.py 入口；
- 不删除 Compose CLI 说明；
- 不执行真实启动、停止、Release 或部署。

## 必须保持不变

- start/stop_compose.py 当前行为；
- env.local / env.production 边界；
- Windows storage override；
- Production Release no-build/no-pull 语义。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| Owner | docs/02 做总入口，Windows/Operations 做专项细节 | #609 + docs governance | 不复制完整专项说明 |
| 接口 | 不改脚本 CLI | E1-E4 | 只改说明 |
| 数据 | 不适用 | 文档任务 | 无迁移 |
| 兼容性 | Compose CLI 保留 | E5 | 老操作仍可找到 |
| 部署 | 不执行 | 用户只要求文档一致性 | 无运行副作用 |

# 修改方案与决策依据

1. docs/02：Linux/WSL 与 Windows quick-start 改为 start/stop scripts 第一位；Compose CLI 放“首次镜像准备/备用”。
2. docs/02 Section 10：同样脚本优先，避免顶部和后文推荐冲突。
3. Windows Guide：Section 4 改为“推荐日常启停”，成对展示 start/stop；Section 5 只解释 Compose CLI 的 stop/down 备用语义。
4. Production Operations：服务器离线部署把 start/stop scripts 加为正式日常运行命令，并把底层 docker compose 过程改为脚本内部语义说明。
5. 验证 current-head docs/CI/Review，合并后归档和关闭 #609。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 前一轮路径/编号/速查基础保持成立 | #609 / AC1-AC7 | satisfied | 当前 main 0ff0359 已包含 PR #612 + Archive |
| R2 | 重新完成 current-head CI/Review/Delivery | #609 / AC8 | explicitly_deferred | Ready 后由后续 PR current-head CI、独立 Review、merge/main-fresh/archive/closure 实际完成 |
| R3 | 脚本优先且启停成对，三篇运行入口一致 | #609 / AC9 | satisfied | docs/02、Windows Guide、Production Operations 已统一脚本优先；start/stop 成对；Compose CLI 仅保留镜像准备、down/调试或脚本内部语义 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | not_applicable | 不改运行行为 |
| 接口 / 契约 | not_applicable | 不改脚本 CLI |
| 集成 / 持久化 / 运行依赖 | not_applicable | 不执行 Runtime |
| 用户 / 工作流验收 | required | 三篇文档日常启停入口一致且成对 |
| 跨组件关键路径 | not_applicable | 无代码接线变化 |
| 外部依赖 / 供应方探测 | not_applicable | 无外部事实 |
| 构建 / 打包 / 运行 | not_applicable | 不改产物 |
| 文档 / 治理 / 其他 | required | 链接、docs gates、Change Ready、CI/Review |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 主要风险 | 脚本优先描述与“首次无镜像”前提冲突 | 明确脚本不 build/pull，首次准备保留 CLI |
| 兼容性 | 兼容 | Compose CLI 不删除 |
| 数据 | 不适用 | 无数据变化 |
| 部署 | 不适用 | 不执行部署 |
| 回滚 | Git 回滚 | 无运行副作用 |

# 完成审计

- [x] upstream_re_read：已重新读取 #609 AC1-AC9、三篇最终文档、start/stop/release bundle。
- [x] change_coverage：AC9 已实现；AC8 明确绑定 Ready 后新 PR 的 current-head CI/Review/Delivery。
- [x] reverse_audit：三篇文档推荐一致；日常入口不复制完整专项内容；start/stop 成对；清库场景明确说明 reset 脚本已先停止，因此只需后续启动。
- [x] unresolved_cleared：Requirement Traceability 无 not_satisfied；AC8 使用 explicitly_deferred 绑定真实后置门禁。

# 完成证据与状态

## 新鲜证据

| 证据 | 版本 | 检查 | 结果 | 证明 |
| --- | --- | --- | --- | --- |
| V1 | main 0ff0359 | 文档/脚本读取 | confirmed | E1-E5 |
| V2 | branch 11926a2 | 三篇运行文档脚本配对审计 | pass | docs/02=7/7、Windows Guide=7/7、Operations=6/6 个 start/stop_compose.py 引用；日常推荐均脚本优先 |
| V3 | branch 11926a2 | direct Compose 启动审计 | pass | docs/02 与 Windows Guide 不再把 docker compose up 作为日常推荐；Operations 仅在脚本内部流程说明保留 no-build up |
| V4 | branch 11926a2 | reset 语义审计 | pass | 清库段明确 reset_keep_vehicle_catalog.sh 自身先停止服务，因此不需要额外 stop_compose.py |

## 未验证内容与剩余风险

- 实现与静态一致性审计已完成；PR current-head CI/Review、merge/main-fresh/archive/closure 待执行。

## 交付状态

- 提交：三篇运行文档脚本优先启停已提交到任务分支
- PR：Ready 后建立
- CI：由 PR current-head required checks 执行
- 合并：仅在 current-head CI/Review Green 后 guarded merge
- Change 归档：merge 后由 repository-native Archivist 执行
- Release/Deploy：不适用
