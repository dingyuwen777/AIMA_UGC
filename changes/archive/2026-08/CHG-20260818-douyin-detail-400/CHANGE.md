---
schema: rvc-change/v1
id: "CHG-20260818-douyin-detail-400"
title: "抖音详情400不中断整批调试采集"
level: L2
status: done
owner: "dingyuwen777"
branch: "fix/tikhub-test-default-paths"
created: 2026-08-18
updated: 2026-08-19
depends_on: []
affected_areas:
  - "provider-debug"
  - "douyin"
affected_paths:
  - "backend/src/aima_ugc/adapters/providers/tikhub_test/operations/runner.py"
  - "tests/unit/collection/test_tikhub_test_douyin_http_errors.py"
  - "tests/unit/collection/test_tikhub_test_debug.py"
  - "backend/src/aima_ugc/adapters/providers/tikhub_test/README.md"
  - "docs/collection/douyin.md"
contracts: []
data_changes: []
---

# 目标

TikHub 无数据库调试运行中，单个抖音搜索结果调用 `fetch_one_video_v3` 返回 HTTP 400 时，保存完整 Raw 和请求关联信息，将该内容标记为详情不可用并继续处理其余内容，不再让一个内容级 Provider 失败中断整批关键词采集。

在该能力归档前继续收口 `tikhub_test` 目录重组后的默认路径兼容：默认 `.env` 固定来自 `tikhub_test/.env`，默认输出固定进入 `tikhub_test/output/`，不能因为 `runner.py` 移入 `operations/` 而漂移到当前工作目录的任意 `.env` 或 `operations/output/`。

# 成功标准

- [x] 抖音详情 V3 返回 HTTP 400 时 `run_douyin()` 不抛出整批异常，运行汇总状态为 `completed_with_errors`。
- [x] 失败详情响应继续保存到 Raw，请求记录保留 HTTP 状态、TikHub request ID 和 Raw 路径，`content_failures` 能定位失败内容和 Operation。
- [x] 搜索阶段已经映射的内容继续进入人工可读结果，评论覆盖标记为 `unavailable`，不继续发送该内容的评论/回复请求。
- [x] 详情失败的内容不写入跨运行去重状态；下一次显式运行仍会重新尝试详情请求。
- [x] 其他 Operation 或其他 HTTP 错误保持原有 fail-fast 行为，不引入隐藏自动重试或备用 Endpoint fallback。
- [x] `env_file=None` 时直接使用 `TikHubTestConfig.load(None)` 的固定默认 `tikhub_test/.env`，不扫描 CWD/父目录的任意 `.env`。
- [x] `output_root=None` 时固定写入 `tikhub_test/output/`，不写入 `tikhub_test/operations/output/`。
- [x] 显式 `env_file` / `output_root`、五平台入口、生产 Operation/Mapper/分页/Transport 单次发送语义保持兼容。

# 范围

- `tikhub_test` 调试运行器的抖音详情 HTTP 400 内容级容错；
- `tikhub_test` 目录重组后的默认配置/输出路径兼容；
- 无真实网络、无费用的回归测试；
- 与当前仓库事实一致的 RVC 项目导航索引刷新。

# 非目标

- 不修改五平台正式 Search/Detail/Comments/Replies Operation、参数、Mapper 或 Capability；
- 不增加自动重试，不切换 Web/V1/V2 或批量详情接口；
- 不改变生产 Worker 的 Provider Attempt、计费、重试或终态语义；
- 不重新发送真实付费请求；
- 不进入 Stage 8，不修改数据库、Migration、Analysis/Excel Contract 或依赖。

# 必须保持不变

- `run_douyin()` 及其他 `run_*()` 参数、返回类型和既有 `run_summary.json` 字段保持兼容；
- 每次 `send` 仍然恰好一次网络请求，HTTP 400 Raw 先保存后决策；
- TikHub Secret 不进入日志、汇总、测试 Fixture 或 Change；
- 非目标平台以及抖音非详情 HTTP 错误的异常行为保持不变；
- 用户确认保留的 `tikhub_test/core + operations + test.py` 目录结构与 TikHub 抓取逻辑保持不变；
- TikHub 默认 Origin 继续为 `https://api.tikhub.dev`，显式兼容既有 `https://api.tikhub.io`，其他 Origin 在发送 Secret 前拒绝。

# 关键决策

- 既有真实 Raw 已证明抖音详情请求只包含非空 19 位 `aweme_id`，同一运行中该详情 Endpoint 曾成功返回；原 400 属单内容 Provider/上游失败，不升级成整批调试失败。
- 不在代码中隐藏自动重试；失败内容记录并继续，下一次人工运行自然形成新的显式请求。
- 失败内容保留 Search 映射结果但不写跨运行成功状态，避免暂时性详情失败被永久跳过。
- 目录重组后默认路径相对 `tikhub_test` 包根，而不是相对移动后的 `operations/runner.py`。
- `TikHubTestConfig.load(None)` 已唯一负责默认 `.env` 路径，因此删除 `runner.py` 私有的 CWD 向上搜索 helper，避免两个互相竞争的默认规则。
- `_DEFAULT_OUTPUT_ROOT` 固定为 `Path(__file__).resolve().parent.parent / "output"`；显式 `output_root` 仍优先。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立抖音 400 失败测试
- [x] 完成抖音 400 最小实现
- [x] 同步抖音文档
- [x] 取得抖音 400 新鲜验证证据
- [x] 建立目录重组默认路径 Red 回归
- [x] 修复默认 `.env` / `output` 路径
- [x] 目标、相关与整仓新鲜验证
- [x] 刷新 RVC `project-context.json`
- [x] 两阶段复核
- [x] PR #73 合并、post-merge 验证与 Change 归档

# 验证

## 抖音 400 既有证据

- Red：`uv run pytest tests/unit/collection/test_tikhub_test_douyin_http_errors.py -q`，退出码 1；Fake Detail HTTP 400 在 `_send` 被升级为整批 `RuntimeError`。
- Green：同一目标测试退出码 0；增强为两条内容后证明第一条 400 不阻塞第二条，并证明下一运行会重新请求失败内容。
- 相关回归：`uv run pytest tests/unit/collection/test_douyin_tikhub_operation.py tests/unit/collection/test_tikhub_test_douyin_http_errors.py -q`，退出码 0，`12 passed`。

## 目录重组默认路径 Red

PR #73 Red head `214e8b84c158f4911e9221958308b6e8ea41b8aa`，Stage5A Run `32208948894` / Job `95937592263`：

```text
P1/相关 pytest: 2 failed, 66 passed in 2.22s
exit 1
```

两个失败与预期根因一一对应：

1. `_DEFAULT_OUTPUT_ROOT` 实际为 `tikhub_test/operations/output`，预期为 `tikhub_test/output`；
2. `run_platform(env_file=None)` 仍调用 `find_env_file()` 扫描 CWD/父目录。

同一 Red run 的 Secret 与 Docs 检查均成功。

## Green 与格式门禁

最小实现 commit `910183de055fe9e5450958332149628d80c752ee`：

- 默认 output 改为 `tikhub_test/output/`；
- `run_platform()` 直接 `TikHubTestConfig.load(env_file)`；
- 删除未导出的私有 `find_env_file()`；
- Operation/Mapper/分页/HTTP/400 逻辑未修改。

首次 Green 目标测试已经 `68 passed`，随后 Ruff format 正确指出 helper 删除后多余空行；使用仓库锁定 Ruff 机械格式化后，最终候选不保留临时 workflow。

## PR 合并前最终候选

代码与 RVC 索引候选 `9cf16351f219d25da41076ff97ef22d21d313695` 已取得 11/11 适用正式 workflow success；Change 状态提交 `c7404ab62c517877219058d615adb91b0f50c9f6` 再次取得 11/11 success：

- CI — Run `32209730314`；
- Stage 1-7 Audit Correctness — `32209730304`；
- Stage 5A Provider Raw — `32209730292`；
- Stage 5B Collection Execution — `32209730309`；
- Stage 5C Provider Persistence — `32209730301`；
- Stage 5D Provider Dispatch — `32209730329`；
- Stage 6 XHS Vertical Slice — `32209730297`；
- Stage 7 Keyword Packs — `32209730347`；
- Stage 7 Plan Occurrence Run Snapshot — `32209730295`；
- Stage 7 Provider Config Routing — `32209730316`；
- Stage 7 Scheduler Runtime — `32209730377`。

Stage5A 的目标测试、Ruff/mypy、Analysis/Export Contract、Architecture、Secret/Docs、Provider/Raw、Provider Contract 与全局 quality 全部 success。Stage6 的 Unit、Quality、PostgreSQL Integration 与全部 Migration round-trip success。总 CI 的 Stage1、Stage2、Stage3A 与 Windows bootstrap success。

RVC 索引通过 GitHub-hosted Runner 实际执行：

```text
python .agents/skills/reliable-vibe-coding/scripts/rvc.py discover --root .
```

生成后的 `.reliable-vibe-coding/project-context.json` 已提交；一次性 workflow 已删除，不进入最终 PR。

## PR #73 与 post-merge

PR #73 正常 merge 到 `main`：

```text
merge commit = 6e25fdb640e8a51a394258ee09b33e79405cda88
```

没有 rebase、force push 或 CI 绕过。合并后从该 main merge commit 建立归档验证分支，并使用 3 个无业务语义 `.txt` marker 重新触发全部正式 Stage workflow；候选 `ab29f4783972e72d105460971d21bd6ffdc39c28` 取得 **12/12 success**：

- CI — Run `32209959634`；
- Stage 1-7 Audit Correctness — `32209959680`；
- Stage 4 Job Runtime — `32209959676`；
- Stage 5A Provider Raw — `32209959592`；
- Stage 5B Collection Execution — `32209959595`；
- Stage 5C Provider Persistence — `32209959608`；
- Stage 5D Provider Dispatch — `32209959621`；
- Stage 6 XHS Vertical Slice — `32209959594`；
- Stage 7 Keyword Packs — `32209959718`；
- Stage 7 Plan Occurrence Run Snapshot — `32209959660`；
- Stage 7 Provider Config Routing — `32209959604`；
- Stage 7 Scheduler Runtime — `32209959609`。

三个 marker 在归档前均已删除，不属于产品文件，也不会进入 `main`。

# 两阶段复核

## 需求符合性

- 默认 `.env` 和默认 output 都与用户认可的 `tikhub_test` 新目录结构、README 和实际目录一致；
- 显式路径参数仍覆盖默认值；
- 抖音 400 容错保持不变；
- TikHub `.dev` 默认 Origin 和 `.io` 兼容保持不变；
- 五平台抓取继续复用生产 Runtime/Operation/Mapper/Capability，没有复制第二套抓取逻辑。

## 代码质量

- 修复集中在默认路径解析和两条回归测试，没有公共 API、Contract、Schema、Migration、依赖或数据库变化；
- 删除的 `find_env_file()` 是未导出的私有 helper，没有仓库内其他调用；
- 无真实网络、无付费请求；
- Ruff、mypy、Architecture、Ownership、Secret、Docs、Contract、PostgreSQL、Migration 门禁均由最新 CI 覆盖。

# 文档影响

- `docs/collection/douyin.md` 继续说明 400 容错只属于 `tikhub_test` 调试入口，不改变生产 Provider 重试和 fallback 语义。
- `tikhub_test/README.md` 已声明默认 `.env` 为 `tikhub_test/.env`、默认输出为 `tikhub_test/output/`；本次代码对齐既有长期说明，无需制造重复文档改动。

# 交付

- 实现 PR：#73，已合并；
- 实现 merge commit：`6e25fdb640e8a51a394258ee09b33e79405cda88`；
- post-merge 12/12 正式 workflow 已成功；
- 归档 PR：#74；
- 当前状态：`done`；
- 不涉及数据库、Migration、依赖、真实 TikHub 付费请求或 Stage 8。
