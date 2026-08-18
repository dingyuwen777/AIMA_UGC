---
schema: rvc-change/v1
id: "CHG-20260814-stage5a-provider-raw-foundation"
title: "Stage 5A Provider 与 Raw 基础"
level: L3
status: done
owner: "dingyuwen777"
branch: "feature/stage5a-provider-raw-foundation"
created: 2026-08-14
updated: 2026-08-14
depends_on:
  - "CHG-20260813-stage3a-database-foundation"
  - "CHG-20260814-stage4-job-runtime"
affected_areas:
  - "collection"
  - "provider"
  - "raw"
  - "artifact"
  - "testing"
  - "ci"
  - "blueprint"
affected_paths:
  - "backend/src/aima_ugc/contracts/provider/"
  - "backend/src/aima_ugc/modules/collection/"
  - "backend/src/aima_ugc/adapters/providers/"
  - "backend/src/aima_ugc/operations/storage/"
  - "contracts/provider/"
  - "scripts/contracts/"
  - "scripts/quality/"
  - "tests/unit/collection/"
  - "tests/integration/collection/"
  - "tests/contracts/"
  - "docs/blueprint/"
  - "docs/测试与调试说明.md"
  - "README.md"
  - ".github/workflows/"
contracts:
  - "ProviderRequestV1"
  - "ProviderAttemptV1"
  - "RawEnvelopeV1"
  - "ProviderTransport"
data_changes: []
---

# 目标

建立 Stage 5A Provider 中立执行与 Raw Artifact 基础，使 HTTP、SDK、文件等未来
Provider 可以使用同一版本化 Request/Attempt/Error/Billing 语义，经不隐藏自动重试的
Transport 边界执行，并把递归脱敏后的 Raw Envelope 作为不可覆盖、可校验、可回放的
gzip Artifact 保存。该单元不依赖具体平台 Operation、真实 Fixture 或 Collection 数据库父表。

# 成功标准

- [x] `ProviderRequestV1` 使用 Operation、脱敏稳定参数和分页输入形成可复现
  fingerprint，并拒绝 Secret 字段进入逻辑请求 Contract。
- [x] `ProviderAttemptV1` 表达 `reserved/dispatching/completed/not_sent/unknown`、安全错误和费用
  事实，模型约束禁止互相矛盾的时间、Raw 和计费状态。
- [x] 正式 Provider Client 每个 Attempt 最多调用一次 `ProviderTransport`；Fake Transport 可重复
  验证成功、429、5xx、发送前失败与发送结果未知，且不保存或回显测试 Token。
- [x] `RawEnvelopeV1` 顶层语义 Provider 无关，具有固定 `provider-response.v1` Schema；Provider
  私有响应只保留在 Raw body，不进入 Canonical Contract。
- [x] Raw 写入经正式 `ArtifactService + ArtifactStore`，使用安全稳定路径、递归脱敏、确定性
  JSON、gzip、SHA-256 和 no-overwrite；回放重新验证大小、Hash、gzip 与 Pydantic Contract。
- [x] 固定 Provider JSON Schema 可确定性生成并通过漂移检查；既有 OpenAPI、Canonical、前端
  Client、Stage 1–4 门禁保持不变。
- [x] 独立 Stage 5A CI 不调用真实 Provider、不需要 Token、不产生费用。

# 范围

- `backend/src/aima_ugc/contracts/provider/`：版本化 Request、Attempt、Billing、Error、Raw Envelope。
- `backend/src/aima_ugc/modules/collection/providers/`：Transport Port、一次发送 Client、Raw Artifact
  写入与回放生产入口。
- `backend/src/aima_ugc/modules/collection/README.md`：生产入口、测试方式和阶段限制。
- `backend/src/aima_ugc/adapters/providers/fake.py`：受控 Fake Transport。
- 向 `ArtifactService.store_bytes` 增加向后兼容的显式安全 `storage_key` 能力；默认 UUID 路径不变。
- `contracts/provider/` 固定 JSON Schema，Contract 生成/漂移检查。
- Provider/Raw Unit、Contract 与使用正式 Local ArtifactStore 的集成测试。
- Stage 5A 独立 CI、README、Blueprint 和统一测试说明同步。

# 非目标

- 不创建 `provider_requests`、`provider_request_attempts` 或任何 Collection/预算数据库表；不新增
  Alembic Revision。最终表等待 `collection_runs/collection_scopes` 父事实具备后按最终外键建立。
- 不接 TikHub 或其他真实 Provider，不实现平台 Operation、分页状态机、Mapper、Candidate、
  Ingestion、Content/Comment 或 Scheduler。
- 不提交真实 Fixture、Token、Cookie、Authorization、API Key 或未授权个人信息。
- 不实现真实 Probe、真实 HTTP Transport、内部网络重试、预算预留、Attempt 数据库 CAS/Fencing。
- 不决定 Raw 保留期限、删除策略、权限或生产部署。
- 不新增公开 HTTP API、前端页面、依赖或配置。

# 必须保持不变

- 模块化单体及 Provider → Raw → Mapper → Canonical → Ingestion 方向不变。
- `ArtifactStore` 只理解 `storage_key` 和字节；Artifact ID、元数据与生命周期继续由
  `ArtifactService/ArtifactMetadataPort` 管理。
- `ArtifactService.store_bytes` 现有调用方继续得到 `kind/<uuid>` 路径和相同错误语义。
- 既有 Canonical、OpenAPI、Job Payload、数据库 Schema、Migration、配置、依赖和锁文件不变。
- Secret 不进 Job Payload、Provider Request、Raw、日志或生成 Contract。
- 真实外部网络调用不位于数据库事务中；Transport 不隐藏自动重试。

# 关键决策

## 方案比较与用户决定

1. **方案 A（已批准）**：先建立 Provider-neutral Contract、Fake Transport 和 Raw Artifact；
   Provider 数据库表等待 Collection 父事实。最小、可逆，不产生临时弱约束 Schema。
2. 方案 B：把 Collection Run/Scope 与 Provider 表一起提前到 Stage 5。会连带 Plan/Occurrence、
   Scheduler 和未决业务语义，范围过大。
3. 方案 C：先创建无外键 `scope_id`，Stage 7 再补约束。会产生弱约束窗口、回填和迁移风险，
   与数据库约束来源链冲突。

用户于 2026-08-14 明确批准方案 A。本 Change 是 Stage 5 的首个正式子单元 Stage 5A；完成后
Stage 5 仍为进行中，不能宣称 Provider PostgreSQL Attempt/费用账本或真实平台已完成。

## Contract 与兼容

- Provider Contract 采用 Pydantic V1 版本标识和 `extra=forbid/frozen`；Raw 文件格式固定为
  `provider-response.v1`，生成 JSON Schema 是机器事实。
- Provider Token 只存在于 Transport 调用边界并使用 `SecretStr`/排除序列化；逻辑 Request 只
  接受脱敏参数。Raw 写入仍做递归最终脱敏。
- Transport 接口由 AIMA 自身请求/响应定义，不暴露第三方 SDK 对象；Fake 只替换外部 I/O，
  测试仍从正式 Client/Raw Service 进入。

## Migration、部署与回滚

- 无数据库 Migration、回填、依赖或运行配置变化。
- 本阶段只提供库级生产入口，不接 Worker Registry 或生产 Provider，因此无部署启用步骤。
- 回滚可直接回退本 Change；现有 Artifact API 默认行为不变。若测试/开发产生 Raw 文件，可在
  对应隔离测试目录删除，不涉及生产业务数据。

## 安全、性能与运维风险

- 递归脱敏是最终防线；调用方仍不得主动把 Secret 填入业务 Contract。
- Raw body 可能较大；本单元只验证字节完整性，不宣称容量、吞吐、保留或备份目标成立。
- 网络结果未知只能记录 `unknown + potential_duplicate_charge`，不能承诺零重复费用。
- Artifact `stored → linked` 依赖未来 Provider Attempt Repository，本阶段不得伪造 linked。

# 任务

- [x] 调查当前实现、Stage 5 Blueprint、Artifact/Contract 边界和父表依赖冲突。
- [x] 用户确认方案 A 与 Stage 5A 非目标。
- [x] Red：建立 Request/Attempt/Client/Fake/Raw/Artifact/Schema 失败测试并确认因生产入口缺失失败。
- [x] Green：完成最小 Provider Contract、Client/Transport、Fake 和 Raw Artifact 实现。
- [x] Refactor：在全绿后整理重复、公共导出和错误命名，不增加行为。
- [x] 生成固定 Provider JSON Schema并同步 Contract 漂移门禁。
- [x] 同步 README、Blueprint、统一测试说明和独立 Stage 5A CI。
- [x] 执行需求符合性与代码质量两阶段本地复核，修复 Raw 直接构造脱敏和截断 gzip 错误边界。
- [x] 取得 PR/CI/合并后 main 新鲜证据并归档 Change。

# 验证

## 计划

- 目标测试：`uv run pytest tests/unit/collection tests/contracts/test_provider_v1.py -q`。
- Artifact 集成：`uv run pytest tests/integration/collection -q`，只使用正式 Local ArtifactStore 和
  可控 Metadata Fake，不访问生产数据库或网络。
- Contract：`uv run python scripts/contracts/generate.py --check`、
  `uv run python scripts/contracts/check_compatibility.py`。
- 相关测试：`uv run pytest tests/unit tests/contracts tests/api -q`。
- 静态检查：Ruff format/check、mypy、架构、Table Owner、Secret 和文档门禁。
- 构建/回归：Wheel、前端生成/类型/测试/Build 与仓库通用 CI；Stage 5A 独立 CI。

## 新鲜证据

- Red 1：在已同步的根工程环境运行目标测试，3 个测试模块因
  `aima_ugc.contracts.provider` / `aima_ugc.adapters.providers` 生产入口不存在而收集失败。
- Red 2：固定 Provider Schema 测试因三个 `contracts/provider/*.schema.json` 不存在而 3 项失败。
- Review Red：Raw Contract 未拒绝未脱敏路径的测试失败；截断 gzip 回放直接泄漏 `EOFError` 的
  回归测试 1 项失败。最小修复后两项进入目标回归。
- `.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/unit/collection tests/integration/collection tests/contracts/test_provider_v1.py -q`
  退出码 0，16 passed。
- `.venv\Scripts\ruff.exe format --check backend tests scripts`、
  `.venv\Scripts\ruff.exe check backend tests scripts` 退出码 0，98 files already formatted，All checks passed。
- `.venv\Scripts\mypy.exe backend/src` 退出码 0，69 source files 无问题。
- Contract 生成检查和兼容检查退出码 0：OpenAPI、Canonical 与 Provider Contract 已同步，
  OpenAPI 基线与 Canonical/Provider Schema 漂移检查通过。
- 架构、Table Owner、Secret、文档门禁退出码均为 0；现有五张表 Owner 未变化。
- `uv lock --check --python D:\python314\python.exe` 与 `uv build --wheel` 退出码 0；Wheel 包含
  Provider/Collection/Fake 生产模块。隔离 venv 以 `--no-deps` 安装成功，并从 site-packages 导入
  `aima_ugc 0.1.0`。本机 Python 为 3.14.6，锁定的 3.14.7 留给 CI 精确验证。
- `.venv\Scripts\python.exe -m pytest tests/unit tests/contracts tests/api -q` 在沙箱外运行：43 passed，
  1 failed；唯一失败是 Windows 创建目录符号链接返回 `WinError 1314`，发生在测试准备阶段，
  未删除、跳过或修改该测试，等待 Linux CI 复验。
- 前端文件、OpenAPI 和生成 Client 未变化；本机 Node/npm 版本不等于锁定版本，前端完整门禁由
  仓库通用 CI 使用精确版本验证。
- 实现 PR #19 head `ca0604a22b82ec166f507cf1cfe54fb506f7acce`：通用 CI
  `31772112193` 和 Stage 5A CI `31772112256` 均为 success。
- PR #19 以 squash 合并到 main，merge commit
  `d0d93d6bd84094d16e1b0d8f0cd2d5f455c621f5`。
- 合并后 main：通用 CI `31772268280` 和 Stage 5A CI `31772268312` 均为
  completed/success；通用 CI 覆盖精确 Python/Node/npm、Wheel、前端、Windows bootstrap、
  PostgreSQL 18 Stage 2/3A 和 Linux 路径安全回归。
- 合并后本地 main 目标测试 16 passed；Contract、架构、Table Owner、Secret、文档门禁均退出码 0。

# 文档影响

- `README.md`：Stage 5A 当前能力、测试入口和 Stage 5 仍未完成。
- `docs/blueprint/README.md`、`06`、`07`：固化经用户确认的 5A/后续持久化边界，消除
  Provider 表早于 Collection 父表的阶段冲突。
- `docs/测试与调试说明.md`：Provider/Fake/Raw 独立验证入口与未覆盖项。
- `02/03/04/05` 的长期语义不变；实现后只在事实冲突时做最小同步。

# 交付

- 基线 main：`dd53605ace65583a8f4a91baa967b35651da609d`。
- 实现分支：`feature/stage5a-provider-raw-foundation`。
- 实现 Commit：`ca0604a22b82ec166f507cf1cfe54fb506f7acce`，中文提交
  `建立 Stage 5A Provider 与 Raw 基础`。
- 实现 PR：[PR #19](https://github.com/dingyuwen777/AIMA_UGC/pull/19)。
- 合并 Commit：`d0d93d6bd84094d16e1b0d8f0cd2d5f455c621f5`。
- Change 收尾分支：`chore/archive-stage5a-provider-raw-foundation-change`。
- Change 状态：done，归档到
  `changes/archive/2026-08/CHG-20260814-stage5a-provider-raw-foundation/`。
- 发布：未部署；Stage 5A 只建立库级入口，无生产启用、Migration 或数据迁移。
