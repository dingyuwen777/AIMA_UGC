---
schema: rvc-change/v1
id: "CHG-20260820-llm-pricing-official-terms"
title: "LLM价格配置字段对齐供应商官方术语"
level: L3
status: done
owner: "codex"
branch: "feature/llm-pricing-official-terms"
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - "llm-adapter"
  - "documentation"
affected_paths:
  - "backend/src/aima_ugc/adapters/llm"
  - "backend/src/aima_ugc/adapters/providers/imports_test/README.md"
  - "tests/unit/analysis"
  - "docs/blueprint/15-舆情AI打标与统一分析契约.md"
contracts: []
data_changes: []
---

# 目标

在不改变 token 来源、费用公式和 `llm-http-request.v1` 历史审计格式的前提下，把共享 LLM
价格目录中的缓存命中、缓存未命中和输出单价字段改成明确包含 `tokens` 单位、并与供应商价格页
术语一致的名称；同时用模型无关的价格时段表达供应商分时单价，按每次物理 HTTP 请求开始时间
选择实际单价，并纠正远端 `main` 上已出现的不完整实现。

# 成功标准

- [x] 新价格配置使用 `input_cache_hit_per_million_tokens`、
  `input_cache_miss_per_million_tokens`、`output_per_million_tokens`，不再使用远端错误引入的
  `input_cached_per_million` / `input_uncached_per_million`。
- [x] 当前 `api.deepseek.com / deepseek-v4-pro` 的人民币单价与 2026-08-20 直接核验的 DeepSeek
  官方价格页一致：空闲时段为 0.15 / 4.5 / 13.5，高峰时段为 0.30 / 9 / 27 CNY / 百万
  tokens；北京时间 09:00–12:00、14:00–18:00 按高峰价格，其余时间按空闲价格。
- [x] 分时价格不是 DeepSeek 特例：每个 provider/model 可配置自己的 IANA 时区、默认价格时段和
  零个或多个半开区间覆盖时段；只有单一价格的其他模型继续支持全天固定价格。
- [x] 新配置必须包含合法 `effective_date`；现有旧字段 TOML 可兼容读取并产生显式 warning，
  但 `LLMModelPrice` 只暴露新属性。
- [x] 800,000 缓存命中输入 tokens、200,000 缓存未命中输入 tokens、100,000 输出 tokens
  在 DeepSeek 空闲/高峰时段分别精确计算为 `Decimal("2.37")` / `Decimal("4.74") CNY`。
- [x] 物理请求审计的 `llm-http-request.v1` 字段、价格快照 SHA-256、token 统计、rounding、
  currency 和费用计算结果与改名前兼容。
- [x] README、Blueprint、TOML、实现和测试使用一致术语；相关测试、Ruff、mypy、质量脚本和
  Wheel 构建通过。

# 范围

- `adapters/llm` 的价格 dataclass、TOML 读取、成本计算属性引用和包内价格目录。
- OpenAI-compatible Adapter 与费用复算对新价格属性的引用；审计输出键保持原格式。
- LLM 价格、请求审计相关单元测试。
- LLM Adapter README、`imports_test` 配置说明和 Blueprint 15 的长期价格目录事实。
- 当前 Change 记录和可靠工作流索引。

# 非目标

- 不修改数据库 Schema、Migration、HTTP API Contract、Analysis Contract 或报告生成逻辑。
- 不修改模型响应 token 字段映射、token 统计、费用算术公式、rounding、currency 或预算策略；
  只增加请求时间对应价格时段的选择。
- 不升级依赖，不重构 LLM Provider 架构，不增加 Provider 余额/账单 API。
- 不把配置字段改名扩大为 `llm-http-request.v1` 历史审计 JSON 字段改名。

# 必须保持不变

- `LLMTokenUsage.input_cache_hit_tokens` / `input_cache_miss_tokens` 及 DeepSeek usage 映射不变。
- `LLMHTTPRequestAudit` 和 `llm-http-request.v1` 中既有 `pricing` 键不变，历史文件仍可汇总和复算。
- 同一 provider、model、currency、实际采用单价和来源 URL 的 `pricing_snapshot_sha256` 保持不变；
  `effective_date` 是配置来源元数据，不参与费用公式和既有快照身份。
- 普通输入/输出文本模型的 `input_per_million` 能力保持，不扩展本次明确列出的字段改名范围。
- 没有匹配价格或 usage 分类不足时仍明确不可计算，不新增默认单价或跨模型 fallback。

# 关键决策

## 方案比较

1. **采用：新配置名 + 旧 TOML 别名 warning + 审计格式冻结。** 能让新配置清楚表达官方术语，
   又不破坏已经存在的自定义 TOML 和历史审计，改动集中且可回滚。
2. 立即删除所有旧配置名。实现更少，但既有部署或外部 `LLMPricingCatalog.from_toml()` 调用会
   在升级后直接失败，不符合用户给出的生产兼容门禁。
3. 连同 `llm-http-request.v1` 审计字段一起改名。表面术语最统一，但会改变历史审计数据格式和
   复算消费者，违反本次非目标，因此不采用。

分时价格另比较：

1. **采用：每模型通用价格时段 + 请求开始时间自动选价。** 每个模型可有一个无时间范围的默认
   时段，以及多个显式覆盖时段；时段使用模型自己的 IANA 时区，区间按 `[start, end)` 解释。
   它能准确表达 DeepSeek 当前双时段价格，也可复用于其他供应商/模型。
2. 始终采用高峰价。实现最少且不会低估，但空闲时段费用会被系统性高估，不符合准确计费目标。
3. 每次 run 人工选择空闲/高峰价。无需时间匹配代码，但容易配置错误，历史复算也缺乏可靠依据。

## 已确认决策与依据

- 用户已明确指定三个新字段、`effective_date`、Decimal 计算、文档测试和完整 Git/PR 流程。
- 用户在 2026-08-20 指出首次核验使用了搜索引擎缓存旧值。重新直接核验 DeepSeek 官方“模型 &
  价格”页后确认：`deepseek-v4-pro` 当前采用北京时间分时价格，空闲 0.15 / 4.5 / 13.5，高峰
  0.30 / 9 / 27 CNY 每百万 tokens；高峰为 09:00–12:00、14:00–18:00。旧值
  0.025 / 3 / 6 不再作为当前官方价格使用。
- 用户已确认方案 A：按物理 HTTP 请求实际开始时间自动选择价格；配置机制必须同时适用于其他模型。
- 每个模型使用一个无 `time_ranges` 的默认价格时段覆盖全天，显式时段优先匹配；显式区间采用
  `[start, end)`，因此 09:00 和 14:00 进入高峰，12:00 和 18:00 回到空闲。费用复算从既有
  `llm-http-request.v1.started_at` 读取同一时间依据，不增加审计字段。
- 远端 `main` 的 `fd170ec` / `745ffc1` 已直接引入 `input_cached_per_million`、
  `input_uncached_per_million` 并删除原校验，导致当前相关基线测试 14 项失败。本 Change 使用后续
  修复提交恢复验证，不回写或重写共享历史。
- 仓库没有外置生产价格文件的明确事实，但 `LLMPricingCatalog.from_toml()` 是可复用加载入口，
  且包内价格目录会随 Wheel 部署；采用兼容读取比假设“只有开发配置”更安全。旧字段只在解析层
  作为别名存在并发出 `FutureWarning`，新 dataclass 和所有新示例只使用官方术语字段。
- `effective_date` 表示该价格条目在 AIMA 价格目录中的生效日期；它被严格校验，但不改变公式、
  历史审计 Schema 或同价快照 Hash。

## 迁移、部署、回滚与风险

- 数据库/API/Contract/Migration：无变化。
- 配置迁移：DeepSeek 新配置改为模型级 `timezone` 加 `[[models.price_periods]]`；每个时段仍使用
  三个官方术语单价字段。其他模型可使用同一分时结构，也可继续使用模型级全天固定单价。旧 TOML
  在兼容期仍可加载并告警，不静默改变含义。远端错误字段不作为正式兼容面，因为该提交无法通过
  既有生产调用链测试。
- 部署：随正常 Wheel 发布包内 `pricing.toml`，无新服务、Secret、环境变量或依赖。
- 回滚：可回滚本 Change 的单一 squash merge；旧审计文件和数据库不需要恢复动作。
- 风险：供应商价格和时段会变化；维护者必须以 `source_url` 一手价格页为准同时更新数值、时区、
  时段和日期，并运行 Decimal 费用与边界测试。本地计算仍不等于供应商最终账单。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立分时价格选择失败测试并确认 Red
- [x] 完成模型无关的分时价格最小实现
- [x] 同步受影响文档和正确官方价格
- [x] 取得修正后的新鲜验证证据

# 验证

## 计划

- 目标测试：`uv run pytest tests/unit/analysis/test_llm_pricing.py tests/unit/analysis/test_llm_request_audit.py tests/unit/analysis/test_openai_compatible_llm.py -q`
- 相关测试：`uv run pytest tests/unit/analysis -q`，再执行全量 `uv run pytest -q` 并如实区分环境前置失败。
- 静态检查/构建：`uv run ruff check backend tests scripts`、`uv run mypy backend/src`、
  `python scripts/quality/check_docs.py`、`python scripts/quality/scan_secrets.py`、架构与表 Owner
  检查，以及 `uv build --wheel`。

## 新鲜证据

- 首次字段修复 Red：远端基线目标测试 18 项中 14 failed、4 passed；新增正式字段、日期和兼容
  测试 10 项中 9 failed、1 passed，证明远端不完整改名破坏了生产 Adapter 与既有校验。
- 分时价格 Red：价格目录测试 23 项中 18 failed、5 passed，旧实现不接受请求时间或
  `price_periods`；Adapter 回归测试实际得到空闲价 `0.000282` 而预期请求开始时的高峰价
  `0.000564`；费用复算实际按执行时刻得到 `0.0002565`，而按审计请求时间应为 `0.000513`。
- 目标 Green：价格、请求审计、OpenAI-compatible Adapter 三个文件共 35 passed。
- Analysis 模块：105 passed。
- 全量单元测试：457 passed、1 skipped；skip 原因是当前 Windows 文件系统不支持该 symlink 用例。
- 完整 `pytest`：共收集 612 项，504 passed、1 skipped、8 failed、99 errors。全部失败/错误的共同
  前置原因是隔离 worktree 不存在 `.runtime/secrets/postgres_password`，PostgreSQL 18 集成环境
  未就绪；未伪造 Secret 或把这些结果声明为通过。目标、Analysis 和全量单元测试均已实际通过。
- Ruff：全仓 `ruff check` 通过，351 个文件 `ruff format --check` 通过。
- mypy：185 个源码文件无问题。
- 质量门禁：架构、表 Owner、文档入口和 Secret 扫描四项均退出码 0。
- Wheel：`uv build --wheel` 退出码 0；实际用 `zipfile + tomllib` 重新打开
  `dist/aima_ugc-0.1.0-py3-none-any.whl`，共 246 个成员、426,102 bytes。包内价格 TOML 包含
  `Asia/Shanghai`、空闲/高峰两套正确价格和 09:00–12:00、14:00–18:00 时段，且不含
  `.uv-cache`。
- 官方核验：DeepSeek “模型 & 价格”页列出 `deepseek-v4-pro` 当前空闲价格 0.15 / 4.5 / 13.5、
  高峰价格 0.30 / 9 / 27 CNY / 百万 tokens；高峰时段为北京时间 09:00–12:00、14:00–18:00。
- PR #96 修正提交的 20 个 GitHub Actions 检查全部通过，包含 Stage 1、PostgreSQL、Provider、
  Scheduler、质量门禁和 Windows bootstrap；远端隔离环境补足了本地缺少 PostgreSQL Secret 的验证。

# 文档影响

- 更新 `backend/src/aima_ugc/adapters/llm/README.md`：字段、日期、当前 DeepSeek 分时价格、边界和
  换模型步骤。
- 更新 `backend/src/aima_ugc/adapters/providers/imports_test/README.md`：每个配置项含义、取值来源、
  费用公式字段和旧配置迁移。
- 更新 `docs/blueprint/15-舆情AI打标与统一分析契约.md`：共享价格目录保存有效日期、时区和通用
  价格时段，按物理请求开始时间选价；审计 Schema 和算术公式不变。

# 交付

- Commit：`541e8ef`（字段与兼容修复）、`0abc1c8`（项目索引）、`322d93b`（通用分时价格与
  DeepSeek 当前价格修正）；提交信息均为中文。
- PR：Draft PR #96 的修正提交已推送，归档前 20 个 GitHub Actions 检查全部通过；归档提交复验后
  转为 Ready 并 squash merge。
- 发布：不单独发布；合并后随正常发布流程生效。
