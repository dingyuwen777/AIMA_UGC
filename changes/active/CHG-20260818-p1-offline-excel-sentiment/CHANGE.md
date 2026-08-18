---
id: CHG-20260818-p1-offline-excel-sentiment
title: 临时 P1 Excel 离线导入、去重与舆情 AI 打标
level: L3
status: in_progress
owner: AI coding agent
branch: feature/p1-offline-excel-sentiment
base_branch: main
created_at: 2026-08-18
updated_at: 2026-08-19
affected_paths:
  - docs/blueprint/
  - backend/src/aima_ugc/adapters/llm/
  - backend/src/aima_ugc/adapters/providers/imports/
  - backend/src/aima_ugc/adapters/providers/imports_test/
  - backend/src/aima_ugc/adapters/providers/tikhub_test/
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/contracts/analysis/
  - backend/src/aima_ugc/contracts/export/
  - backend/src/aima_ugc/platform/export/
  - contracts/analysis/
  - contracts/export/
  - scripts/performance/
  - tests/unit/analysis/
  - tests/unit/collection/
  - tests/unit/platform/
  - .github/workflows/stage5a-provider-raw.yml
rollback:
  strategy: revert
  note: P1 未归档前统一回退本 Change 对应提交；不得修改数据库 Schema，不得覆盖其他 Active Change。
---

# 临时 P1 Excel 离线导入、去重与舆情 AI 打标

## 1. 目标与不变量

P1 是 Stage 7 与 Stage 8 之间的临时最高优先级阶段，不改变正式 Stage 编号。第一版不接数据库，业务主链固定为：

```text
source.xlsx
→ canonical/contents.jsonl
→ filtered/contents.jsonl
→ deduplicated/contents.jsonl
→ AI 打标
→ 本地结构/Taxonomy 校验
→ Validation Retry
→ analysis/checkpoints.jsonl
→ 原子回写同一个 deduplicated/contents.jsonl
→ <source>_<run-id>_labeled_data.xlsx
```

`analysis/checkpoints.jsonl` 只用于恢复、费用安全和审计，不是第二业务事实源；`raw_data.xlsx` 只是可选人工审阅旁路，不进入默认 `run_all()`。

```text
CanonicalContentV1 = Provider/平台可观察事实
UnifiedContentRecordV1 = content + matched_keywords + analysis
analysis = ContentLabelAnalysisV1 | null
```

Canonical 禁止增加 AI 标签。未来数据库中 `record.content` 归 Content Owner，`record.analysis` 归 Analysis Owner；不得把整条统一记录作为一坨 JSONB 写入 contents 表。

## 2. Prompt / Taxonomy / LLM 固定决策

唯一具体标签事实源：

```text
backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v1.md
```

程序只精确提取其中 `AIMA_TAXONOMY_START/END` 机器 JSON，执行 `json.loads`、Taxonomy 校验、`taxonomy_sha256`、完整 `prompt_sha256` 和运行时 membership/父子关系校验。不得解析自然语言表格猜闭集，也不得在 Python/Pydantic 复制具体标签 Enum、Literal、父子映射或第二份 taxonomy JSON。首版保持 Blueprint 15 的 9 个一级标签、39 个二级标签。

每条模型业务输入只允许 `title`、`text`、`author.display_name`，缺失填空字符串；临时 `item_no` 只做批次配对。内容 ID、平台、URL、指标、粉丝数、Provider、`matched_keywords`、源 Excel 情感和 Raw locator 等不得发送。

模型每条固定返回 `item_no/sentiment/primary_label/secondary_label`。三个业务标签字段使用 `str`，具体允许值由当前 PromptTaxonomy 动态校验。本地 Validator 必须检查 JSON、固定/额外字段、item 数量/顺序/唯一性/配对、sentiment、primary 和 secondary→primary；非法输出不得模糊匹配、近义替换或程序猜值。

`max_validation_retries >= 0` 表示额外 Validation Retry 次数：0/1/2 分别对应总模型请求最多 1/2/3 次。Validation Retry 与 Transport Retry 分离；同批已经成功的 item 不得因其他 item 失败重复调用。

## 3. 子阶段检查点

- [x] P1A：设计与阶段导航
- [x] P1B：Excel imports + imports_test + convert
- [x] P1C：关键词过滤 + UnifiedContentRecordV1 去重
- [x] P1D：UnifiedDataExcelV1 + 唯一共享 Exporter + tikhub_test 迁移
- [x] P1E：PromptTaxonomyLoader + Prompt + Analysis Contract/Service/Port + Fake + README + Retry tests
- [x] P1F：真实 OpenAI-compatible LLM Adapter + 最小输入 + Validation Retry + checkpoint + JSONL 原子回写
- [x] P1G：run_all + 崩溃恢复 + 最终同源 JSONL 导出
- [ ] P1H：90k 性能 + 真实模型小样 + Review/CI + 收口
- [ ] P1 全部结束后归档 Change、删除 Blueprint 14，并恢复 README 到 Stage 8 正式导航

**当前检查点：P1H 进行中。90k Windows 性能、P1H 专项测试、两阶段 Review 与 5 条真实 DeepSeek OpenAI-compatible 模型小样均已取得新鲜证据；真实模型 5/5 首次校验成功，未触发 Validation Retry。当前唯一上层阻塞仍是 Stage 1—7/main 整仓基线完整性：已直接确认包括 Architecture 路径缺失、Collection Contract drift 以及 Content 表 `operations/platform` 不一致导致的导入/Alembic 失败。因此 P1H 尚未闭环，不归档 Change、不删除 Blueprint 14、不进入 Stage 8。**

## 4. P1A—P1F 闭环摘要

P1B 建立 `imports/` File Provider 和 `convert()`，使用 openpyxl read-only + `iter_rows(values_only=True)` 输出 Canonical JSONL，并锁定 13 列 Profile、时间转换、稳定身份优先级和错误时不发布部分业务文件。

P1C 建立平台无关关键词过滤和 `(platform, external_content_id)` 去重；冲突 fail closed，filtered/deduplicated 都使用 `UnifiedContentRecordV1`，JSONL 通过临时文件 + flush/fsync + replace 原子发布。

P1D 建立 `UnifiedDataExcelV1` 与唯一共享 Exporter，并迁移 `tikhub_test`/`imports_test`；write-only Workbook、ID 文本化、URL、公式注入防护、北京时间展示和重新打开校验均有测试。

P1E 建立 `ContentLabelAnalysisV1`、唯一 Prompt/Taxonomy、`PromptTaxonomyLoader`、严格 Runtime Validator、`ContentLabelingService`/Port/Fake 和 Validation Retry；具体标签未复制到生产 Python。

P1F 建立真实 OpenAI-compatible Adapter、Secret 边界、最小业务输入、attempts/checkpoints/failed 审计以及成功 Analysis 原子回写同一个 `deduplicated/contents.jsonl`；真实模型默认关闭，普通 CI 不产生付费调用。

P1F 最终专项验证 head `ada47610057d1aacbd0863f1df04d091cecdfd8a` 的 Stage 5A Run `32157763801` / Job `95779015906`：57 passed；Ruff/mypy、Analysis+Export Contract、Secret、Docs 成功；Architecture 仍只报告 11 个既有 `operations/...` 缺失项。

## 5. P1G 实现

P1G 在 P1F 基础上完成离线人工主链和跨进程恢复，没有新增数据库、Migration、依赖或平行 Excel 实现：

- `imports_test.run_all()` 固定串联 `convert → filter_keywords → deduplicate → label_sentiment → export_labeled_excel`；`export_raw_excel()` 不进入默认主链；
- `run_all()` 生成 `run_id`，原子写 `output/run_summary.json`，最终文件名为 `<source>_<run-id>_labeled_data.xlsx`；
- `export_labeled_excel()` 只读取已经回写 Analysis 的同一个 `deduplicated/contents.jsonl`，并继续复用唯一 Shared Exporter / `UnifiedDataExcelV1`；
- Shared Exporter 从 `UnifiedContentRecordV1.analysis` 投影 sentiment、一级、二级、model、Prompt version、Taxonomy Hash，不从 raw Excel 或 checkpoint 构造第二业务视图；
- `label_unified_content_jsonl()` 启动时加载成功 checkpoint；匹配成功的记录直接恢复到业务 JSONL 临时文件，不再次调用模型；
- 恢复身份绑定 `platform + external_content_id + input_hash + prompt_sha256 + taxonomy_sha256 + model_provider + model`；旧 Prompt、Taxonomy、Provider 或模型的 checkpoint 只保留审计，不复用为当前成功结果；
- `input_hash` 仍只由允许发送给模型的 `title + text + author.display_name` 计算；没有把 ID、URL、指标、Provider 私有字段加入模型输入；
- 成功 checkpoint 仍先 `flush/fsync`，业务 JSONL 临时文件再 `flush/fsync + os.replace`；最终替换失败时原业务 JSONL 保持不变，下一次身份一致时从 checkpoint 恢复。

## 6. P1G TDD 与新鲜验证

### 6.1 已有 P1G 主链

P1G 主链已通过专项测试覆盖：

- `tests/unit/collection/test_p1g_imports_run_all.py`：锁定默认 `run_all()` 顺序、禁止 raw Excel 进入主链、`run_summary.json` 和最终文件名；
- `tests/unit/platform/test_p1g_labeled_excel.py`：锁定最终 Excel 从同一个回写后的 deduplicated JSONL 读取 Analysis；
- `tests/unit/analysis/test_p1g_checkpoint_recovery.py`：锁定 checkpoint 先落盘、崩溃后恢复和 Prompt 变化失效。

在本轮开始时，branch head `bb3cdaa2c93ba4b54253466491ba4efbe248baca` 的 Stage 5A Run `32160754603` / Job `95788804463` 已有 62 passed；Ruff/mypy、Analysis+Export Contract、Secret、Docs 成功；Architecture 仍为同一 11 个既有错误。

### 6.2 Review 发现模型身份恢复缺口：Red

需求符合性复核对照 Blueprint 15 发现：既有 checkpoint loader 只绑定 `input_hash + prompt_sha256 + taxonomy_sha256`，没有绑定 `model_provider + model`。切换 Provider 或模型时会错误恢复旧 checkpoint，跳过本应发生的当前模型调用，影响结果可追溯性和费用安全。

先建立回归测试，commit：

```text
d80a8fb674f8cd51fa4be8b33e6bd3bbd03e51aa
测试：锁定P1G模型身份恢复边界
```

Stage 5A Run `32161890146` / Job `95792468933`：

- P1 pytest：退出码 1，`2 failed, 62 passed`；
- 两个新增失败分别精确证明 Provider 从 `provider-a` 切到 `provider-b`、模型从 `model-a` 切到 `model-b` 时仍错误恢复旧 Analysis；
- Secret / Docs 同时成功；
- Red 根因与预期一致，没有用猜测式补丁制造失败。

### 6.3 Green

最小修复：

```text
f3e0981e8605a28becc8164d17308ed681498247
实现：暴露P1G当前模型恢复身份

d636cedefe324fd8620b77dc560e9755b8c916bd
修复：绑定P1G恢复模型身份
```

`ContentLabelingService` 只新增只读 `provider_name/model_name` 访问器；checkpoint loader 在既有 Prompt/Taxonomy 过滤基础上增加当前 Provider/model 精确匹配。checkpoint Schema、Analysis Contract、Prompt/Taxonomy 和业务 JSONL 结构均未改变。

`d636cedefe324fd8620b77dc560e9755b8c916bd` 的 Stage 5A Run `32162296188` / Job `95793757795`：

- P1 目标/回归 pytest：退出码 0，`64 passed in 2.89s`；
- Ruff format/check：退出码 0，39 files already formatted / All checks passed；
- mypy：退出码 0，24 source files 无问题；
- Analysis + Export Contract drift：退出码 0；
- Secret / Docs：退出码 0；
- Architecture：退出码 1，仍只报告 11 个既有 `ARCH001`，均为缺失 `backend/src/aima_ugc/operations/...` Stage 1—7 旧路径；没有新增 P1G Architecture 报错。

Architecture step 失败后，Provider/Raw tests、Provider Contract drift 和 Stage 5A 整套 quality step 按 workflow 顺序跳过。因此全仓适用 PR workflow 仍不是全绿，不把 P1 专项成功描述成整仓 CI 成功。

## 7. 两阶段 Review

需求符合性 Review：P1G 当前实现满足 `run_all()` 固定主链、raw Excel 旁路、最终 Excel 同源、checkpoint 恢复和费用安全要求。Review 中发现的 Provider/model 恢复身份缺口已通过独立 Red→Green 修复。P1H 已完成性能与真实模型小样；仍需等待 Stage 1—7/main 整仓基线恢复后取得最终全绿 CI 并收口。

代码质量 Review：从模型身份 Red 到 Green 的生产差异仅为 Service 只读身份访问器和 checkpoint 精确过滤；私有 `_load_checkpoint_index` 签名变化不构成公共 API 破坏。旧 checkpoint 文件已包含 `ContentLabelAnalysisV1.model_provider/model`，因此不需要数据格式 Migration。未新增依赖、平行 Excel 生成逻辑、隐藏 Transport Retry 或第二业务事实源。

## 8. 文档同步

P1G 闭环后已同步：

- `backend/src/aima_ugc/modules/analysis/README.md`：checkpoint 恢复明确绑定 Prompt/Taxonomy/Provider/model；
- `backend/src/aima_ugc/adapters/providers/imports_test/README.md`：更新 `run_all()`、崩溃恢复、attempts/checkpoints/failed、最终 Excel 与 P1G/P1H 边界；
- `docs/blueprint/README.md`：P1A—P1G 已闭环，下一最小单元 P1H；
- `docs/blueprint/14-临时P1-Excel离线导入与舆情打标.md`：当前状态推进到 P1G 已闭环；
- Blueprint 13/15 的长期 Contract/Analysis 设计没有改变，不复制第二套标签或 Excel Schema。

P1H 本轮继续只把新鲜性能、真实模型和 CI 证据记录在同一个 Change；由于 P1H 尚未闭环，不提前删除 Blueprint 14，也不把 Stage 8 恢复为当前开发导航。

## 9. 依赖、费用、Migration、部署、回滚

- Python/Node/uv 和现有依赖版本保持不变；没有新增、升级或降级依赖；
- 无数据库写入、DDL/Migration、生产部署或持久化数据迁移；
- P1H 90k 性能使用由当前 PromptTaxonomy 动态派生合法标签的无网络 Fake，只测本地 Validator/checkpoint/JSONL 原子回写，不代表真实模型网络延迟或吞吐；
- P1H 真实模型小样使用用户明确授权的临时 OpenAI-compatible 配置，通过 Runner 一次性 RSA-OAEP 公钥加密握手注入；明文 Secret 未写入仓库、Change、PR、workflow、日志或 Artifact，密文评论消费后已清洗，Runner 在 `always()` 清理步骤删除临时私钥和解密配置；
- 真实模型小样共 5 条，生产 Adapter 发生 1 次 HTTP attempt，输入 4,535 tokens、输出 2,368 tokens，5 条均首次通过本地 Validator，Validation Retry=0；当前 Adapter 没有记录 Provider 的 cache hit/miss 拆分或金额字段，因此 `cost_amount=null`，不能把估算价冒充实际扣费；
- 实际批量启用真实 LLM 后，Validation Retry 会增加模型请求和费用；checkpoint 只在输入、Prompt/Taxonomy、Provider 和 model 全部匹配时减少重复成功调用；
- 回滚方式为 revert P1 对应提交；P1H 性能基准和真实模型小样没有数据库、部署或数据迁移回滚要求。

## 10. Active Change 协调

当前可见 Active Changes 中，`CHG-20260818-stage1-stage7-comprehensive-corrective` 的 metadata 覆盖 `contracts/`、`tests/`、`.github/workflows/` 和 `docs/blueprint/` 等广路径，与 P1 存在可见路径重叠。其 PR #65 已合并，但 Change 仍保留在 active；本轮没有越界修改其 Stage 1—7 `operations/...` Architecture、Contract 或数据库基线问题，也没有借 P1H 静默重构 platform/operations 目录。

其他已检查 Active Change（北京时间展示、抖音 detail 400、Windows bootstrap display name）没有与本次 P1H 性能基准或 Analysis Contract 形成直接 Contract/实现冲突。

## 11. Git / PR

- branch：`feature/p1-offline-excel-sentiment`；
- Draft PR：#66，保持 Open / Draft / 未合并；
- P1H 当前仍为唯一最前未完成 P1 单元；
- P1 Change 继续保持 `in_progress`；真实模型小样已完成，但整仓 CI 阻塞解除前不得归档；
- 禁止直接推 main、自动合并、强制推送或新建平行 P1 Change。

## 12. P1H 进行中证据

### 12.1 性能基准 TDD：Red → Green

先建立 `tests/unit/analysis/test_p1h_offline_performance.py`，要求性能入口必须复用生产主链、产生阶段时延/rows/s/峰值 RSS/文件大小，并最终重新打开 `labeled_data.xlsx` 验证情感、一级、二级标签非空。

Red commit：

```text
5c7448d0b6d4dd4d925dc4287cd0938d134b2cfa
测试：锁定P1H离线性能基准行为
```

Stage 5A Run `32164502249` / Job `95800818159`：pytest 在收集阶段退出码 2，原因是预期中的性能基准入口尚不存在；Secret / Docs 同时成功。

Green commit：

```text
155f0f76a7f67fc349ff2ea0522d74bb1cbee52c
实现：增加P1H离线性能基准
```

`script/performance` 实际路径为 `scripts/performance/benchmark_p1_offline.py`。该脚本只编排现有生产函数：`convert_excel_to_canonical_jsonl → filter_canonical_content_jsonl → deduplicate_content_jsonl → label_unified_content_jsonl → Shared Excel Exporter`。90k AI 阶段使用 `_TaxonomyBenchmarkLLM`，具体标签从当前 `PromptTaxonomy` 动态取得，不在 Python 复制情感或一级/二级标签闭集。

Green 的 Stage 5A Run `32164885340` / Job `95802045888`：P1 目标/回归 pytest 退出码 0，`65 passed in 3.25s`；mypy、Analysis+Export Contract、Secret/Docs 成功；Architecture 仍为同一 11 个既有 `ARCH001`。

### 12.2 Review 发现 Windows 门禁退出码缺口并修复

第一次 90k Run `32165048185` 的性能命令确实跑完，但日志同时暴露 Ruff `I001`。PowerShell 当时没有显式传播 native process 的 `$LASTEXITCODE`，后续 pytest 成功导致 step 被误标为 success。因此该 Run 不作为门禁全绿证据，只保留其性能数值为辅助参考。

修复 commit：

```text
b04670233fcf8b9b8bf1ab7d63db5c04a564a8b8
修复：严格传播P1H性能门禁失败
```

修复内容仅为 Ruff import 顺序与 Windows workflow 的 native process 退出码传播；没有修改生产数据主链、Contract、Prompt/Taxonomy 或依赖。

### 12.3 90,000 × 13 Windows 新鲜性能证据

修正后的 P1H Windows Run `32165652105` / Job `95804494417`，环境为 Windows Server 2025、Python 3.14.7、仓库锁定依赖：

```text
uv run ruff format --check scripts/performance/benchmark_p1_offline.py tests/unit/analysis/test_p1h_offline_performance.py
→ 退出码 0，2 files already formatted

uv run ruff check scripts/performance/benchmark_p1_offline.py tests/unit/analysis/test_p1h_offline_performance.py
→ 退出码 0，All checks passed

uv run pytest tests/unit/analysis/test_p1h_offline_performance.py -q
→ 退出码 0，1 passed in 1.66s

uv run python scripts/performance/benchmark_p1_offline.py --work-dir <runner-temp> --rows 90000 --label-batch-size 100
→ 退出码 0
```

性能结果：

| 阶段 | 90k 用时 | rows/s | 阶段记录时的进程峰值 RSS |
| --- | ---: | ---: | ---: |
| convert | 22.480 s | 4,003.59 | 53,231,616 B |
| filter_keywords | 4.131 s | 21,787.50 | 53,231,616 B |
| deduplicate | 8.010 s | 11,236.49 | 85,499,904 B |
| analysis_writeback（无网络 Fake） | 13.182 s | 6,827.34 | 220,123,136 B |
| export_labeled_excel | 101.117 s | 890.06 | 234,762,240 B |

主链合计 `148.919 s`，`604.35 rows/s`；进程峰值 RSS `234,762,240 B`（约 223.9 MiB）。Fixture 生成另耗时 `13.884 s`，不计入真实 source.xlsx 已存在时的主链耗时。最终 Excel 导出占主链主要时间，但当前没有正确性、OOM 或依赖层面的失败证据，因此没有引入 pandas。

文件大小：

```text
source_xlsx             5,826,550 B
canonical/contents      134,268,574 B
filtered/contents       142,818,574 B
deduplicated/contents   193,398,574 B
analysis/attempts       16,628,886 B
analysis/checkpoints    70,962,894 B
labeled_data.xlsx       12,894,069 B
```

当前 Prompt/Taxonomy 哈希：

```text
prompt_sha256   473af4b34e507ec086e9b8f4c177a2ffef8080319c619cb328599212438ca0e1
taxonomy_sha256 d5f118a1a8b002670439858b5dfb1d70f85ee324c1df360733f7caa33aa59c02
```

### 12.4 真实模型小样：从配置门禁阻塞到生产 Adapter 成功

早期 P1H Real LLM Probe Run `32165397317` / Job `95803681128` 以及本轮重跑 Job `95906190689` 都在任何模型请求前确认 GitHub Actions 没有配置 `AIMA_LLM_API_KEY` 与 `AIMA_LLM_MODEL`，配置门禁退出码 2，真实调用步骤被跳过；这两次均为 0 请求、0 token、0 模型费用。

随后用户明确授权一组仅用于本次验证的 OpenAI-compatible DeepSeek 配置。为了不把 Secret 落入仓库或 GitHub 日志，本轮使用一次性 GitHub Runner 生成 RSA-3072 公私钥：公钥通过短期 Artifact 暴露，配置只以 RSA-OAEP SHA-256 密文通过 PR 评论传递；Runner 解密后调用现有生产 Adapter，密文评论立即清洗，私钥与解密配置在 `always()` 清理步骤删除。临时 workflow 代码在取得证据后已恢复/删除，最终分支不保留第二套模型 Probe。

真实模型 Run `32199031852` / Job `95908742768`：

```text
模型 provider = deepseek
模型 = deepseek-v4-pro
样本数 = 5
rows_succeeded = 5
rows_failed = 0
llm_http_attempts = 1
initial_valid_rate = 1.0
retried_item_count = 0
final_failure_rate = 0.0
average_attempts_per_item = 1.0
input_tokens = 4535
output_tokens = 2368
cost_amount = null
prompt_sha256 = 473af4b34e507ec086e9b8f4c177a2ffef8080319c619cb328599212438ca0e1
taxonomy_sha256 = d5f118a1a8b002670439858b5dfb1d70f85ee324c1df360733f7caa33aa59c02
```

`Run production adapter real LLM small sample`、临时配置清理和整个真实模型 Job 均为 success。5 条样本在第一次响应即全部通过 JSON、固定字段、item 映射、Taxonomy membership 与一级/二级父子关系校验，所以 Validation Retry 没有发生；这证明当前真实 OpenAI-compatible Adapter + 完整 Prompt + Runtime Validator 至少在本次小样上形成可运行闭环，但不把 5 条样本外推为长期模型质量或稳定性承诺。

### 12.5 清理后的 P1 专项回归与整仓 CI 阻塞

真实模型验证结束后，`.github/workflows/stage5a-provider-raw.yml` 已恢复到验证前原始 blob，独立临时 `p1h-ephemeral-real-llm.yml` 已删除。代码等价清理 commit `cb96380734111bfb02cce62589479301848a9f8b` 的 Stage 5A Run `32199303267` / Job `95909508553` 提供最新 P1 专项证据：

- P1 目标/回归 pytest：退出码 0，`65 passed in 4.15s`；
- Ruff：退出码 0，`40 files already formatted` / `All checks passed`；
- mypy：退出码 0，24 source files 无问题；
- Analysis + Export Contract drift：退出码 0；
- Secret / Docs：退出码 0；
- Architecture：退出码 1，仍报告同一 11 个 `ARCH001`，均为缺失 `backend/src/aima_ugc/operations/...` Stage 1—7 必需路径；
- Architecture 之后的 Provider/Raw tests、Provider Contract drift、整套 Stage 5A quality 按 workflow 顺序跳过。

同一清理 commit 触发的 PR workflows 仍为失败/未全绿，已直接核实的整仓基线失败至少包括以下三类：

1. **Architecture 路径基线不一致**：`scripts/quality/check_architecture.py` 要求 11 个 `backend/src/aima_ugc/operations/...` 文件，当前仓库实际未满足，Stage 5A 以退出码 1 失败。
2. **Collection Contract drift**：顶层 CI 在 Stage 1 Contract 生成检查中仍发现已提交 Schema 与当前源码生成值不一致；`ProviderPlatformCapabilityV1.schema_version` 的已提交值与当前生成值分别为 `provider-platform-capability.v1` / `provider-operations-capability.v1`。
3. **Content 表 `operations/platform` 不一致**：Stage 2 Platform 与 Stage 3A Database 仍会在导入 `modules/content/tables.py` 时因索引访问不存在的 `contents_table.c.platform` 触发 `AttributeError: platform`，并连带阻塞 Alembic/数据库验证。

上述 Stage 1—7 问题与 `CHG-20260818-stage1-stage7-comprehensive-corrective` 的既有范围真实重叠；本轮 P1 不越界修改数据库 Schema、Collection Contract 或 platform/operations 架构，也不绕过 CI。

因此 P1H 当前只剩一个上层阻塞：**Stage 1—7/main 整仓基线完整性尚未恢复。** 真实模型小样已完成，不再是阻塞项。P1H 保持未勾选；下一次仍只继续 P1H 的整仓基线阻塞解除、最终 Review/CI 与收口。