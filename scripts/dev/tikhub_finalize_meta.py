"""一次性 TikHub README/测试说明/Change 最终化；执行后删除。"""
from pathlib import Path
from textwrap import dedent


collection = Path("docs/collection/README.md")
ctext = collection.read_text(encoding="utf-8")
anchor = "Capability 只公开当前真实响应和 Operation 已证明的能力，不因为 TikHub 文档存在某个字段/参数就自动声明支持。\n"
if anchor not in ctext:
    raise SystemExit("collection README capability anchor missing")
matrix = dedent(
    '''

    当前评论增量资格：

    | 平台 | 增量 | 当前证据/限制 |
    | --- | --- | --- |
    | 小红书 | `true` | `latest_v2` + 当前真实评论时间严格非增 |
    | B站 | `true` | `mode=2` + 首屏 `next_offset=0`，当前真实 20 条时间严格非增 |
    | 抖音 | `false` | 评论 Operation 无已批准最新评论排序参数 |
    | 微博 | `false` | `sort_type=1` 当前真实 20 条时间不是严格非增 |
    | 快手 | `false` | 当前真实 94 条评论时间不是严格非增 |

    `true` 平台在 `comment_count` 增加时走统一 `fetch_incremental`，并使用生产 `known_comment_reached` 安全边界；`false` 平台走受控刷新。任何当前页都先完整保存 Raw 并完成 Mapper/Ingestion，边界只阻止下一次付费请求。
    '''
)
ctext = ctext.replace(anchor, anchor + matrix)
old_debug = "- 调试复用生产 Service / Repository / Provider Operation，不实现第二套路径；"
if old_debug not in ctext:
    raise SystemExit("collection README debug anchor missing")
ctext = ctext.replace(
    old_debug,
    "- 长期无数据库 TikHub 调试入口为 `backend/src/aima_ugc/adapters/providers/tikhub_test/README.md`；它复用生产 Runtime/Operation/Mapper/Decision，不实现第二套路径；",
)
collection.write_text(ctext, encoding="utf-8")


testing = Path("docs/测试与调试说明.md")
ttext = testing.read_text(encoding="utf-8")
ttext = ttext.replace("→ 人工审阅导出", "→ 原始数据 Excel 导出")
ttext = ttext.replace(
    "人工审阅文件\n→ 基于 Raw/Canonical 生成的 XLSX 等派生视图，只供人工快速检查",
    "原始数据 Excel\n→ 基于 Canonical 生成的帖子/指标/评论明细视图；完整 Provider Raw 仍单独保存",
)
ttext = ttext.replace("#### XLSX 人工审阅布局", "#### 原始数据 XLSX 布局")
ttext = ttext.replace("审阅文件", "原始数据 Excel")
marker = "### 4.2 Mapper\n"
if marker not in ttext:
    raise SystemExit("testing docs Mapper marker missing")
section = dedent(
    '''
    #### 长期五平台 `tikhub_test` 调试入口

    `backend/src/aima_ugc/adapters/providers/tikhub_test/` 是五个平台长期无数据库调试入口。平台函数只准备业务参数，实际 endpoint、分页、Mapper、Capability、Decision 和增量历史边界都复用生产实现。

    ```text
    run_xiaohongshu / run_douyin / run_weibo / run_bilibili / run_kuaishou
    → 生产 TikHub Runtime / Transport → Raw → 生产 Mapper → Canonical
    → 生产 Collection Decision / known_comment_reached
    → run_summary.json + state.json + 原始数据 Excel
    ```

    真实 `.env` 只保存在调试目录本地且不提交；关键词是函数参数。支持单关键词和多关键词，多关键词共享内容 identity 去重。XHS/B站在已验证最新排序下可用已知评论历史边界停止下一页；其余平台保持受控刷新。

    当前原始数据 Excel 是系统级共享导出尚未开发前的阶段性实现。未来正式共享原始数据 Excel Exporter 落地时，必须按 Blueprint 13 删除 `tikhub_test` 平行 Excel 代码并复用共享实现。

    '''
)
testing.write_text(ttext.replace(marker, section + marker), encoding="utf-8")


root = Path("README.md")
rtext = root.read_text(encoding="utf-8")
root_anchor = "Stage 8 尚未开始。当前五平台生产实现使用同一 Collection/Content 边界，普通 CI 通过 Fake Transport + 合法脱敏 Fixture 验证，不产生付费 TikHub 请求；真实 Provider Probe 仅在明确授权和请求上限下作为外部兼容证据。当前没有请求/金额 Budget、Budget Account 或 Reservation Ledger。"
if root_anchor not in rtext:
    raise SystemExit("root README Stage8 anchor missing")
addition = (
    root_anchor
    + "\n\n五平台无数据库 TikHub 独立调试入口见 [`backend/src/aima_ugc/adapters/providers/tikhub_test/README.md`](backend/src/aima_ugc/adapters/providers/tikhub_test/README.md)。"
    + "它复用生产 Runtime/Operation/Mapper/Decision，支持单/多关键词，输出 Raw、Canonical、`run_summary.json`、跨运行 state 和原始数据 Excel；当前评论增量只对真实排序证据充分的小红书、B站开启。"
)
root.write_text(rtext.replace(root_anchor, addition), encoding="utf-8")


change = Path("changes/active/CHG-20260817-tikhub-debug-harness/CHANGE.md")
ch = change.read_text(encoding="utf-8")
replacements = (
    (
        "title: TikHub 五平台独立调试与 XHS 增量评论一致性修复",
        "title: TikHub 五平台独立调试与评论增量一致性修复",
    ),
    (
        "# TikHub 五平台独立调试与 XHS 增量评论一致性修复",
        "# TikHub 五平台独立调试与评论增量一致性修复",
    ),
    ("Raw、Canonical、manifest、跨运行轻量 state", "Raw、Canonical、`run_summary.json`、跨运行轻量 state"),
    ("Raw、Canonical、manifest 和 XLSX", "Raw、Canonical、`run_summary.json` 和 XLSX"),
    ("manifest/Excel", "run summary/Excel"),
    ("Raw、Canonical、manifest 或 Excel", "Raw、Canonical、run summary 或 Excel"),
    ("### B. XHS 生产增量评论闭环", "### B. 五平台生产评论增量闭环"),
    (
        "9. XHS Capability 声明 `supports_incremental_comment_sort=True`；其他四个平台除非存在同等级官方/Fixture/真实证据，否则保持当前值，不顺手扩大能力。",
        "9. XHS 与 B站 Capability 声明 `supports_incremental_comment_sort=True`；抖音、微博、快手基于当前官方/真实排序证据保持 `False`，不得为统一形式强行扩大能力。",
    ),
    (
        "不把尚未验证稳定最新评论语义的抖音/微博/B站/快手强行声明为增量评论能力。",
        "不把当前没有安全最新评论边界证据的抖音/微博/快手强行声明为增量评论能力。",
    ),
    (
        "本轮只纠正 XHS 已批准 Capability/执行缺口。",
        "本轮纠正已批准评论增量设计在生产执行层的缺口，并按真实证据更新 XHS/B站 Capability；不改变五个平台主 Operation/Mapper/Canonical 语义。",
    ),
    (
        "8. XHS 官方 `latest_v2` + 当前生产 Operation 固定发送该参数，满足已批准 Blueprint 的稳定最新排序前提；本轮只为 XHS 开启生产增量评论能力。",
        "8. XHS `latest_v2` 与 B站 `mode=2 + next_offset=0` 都取得当前真实多评论顺序证据，因此两者开启生产增量；抖音无最新评论排序参数，微博/快手真实顺序不满足安全边界，保持关闭。",
    ),
)
for old, new in replacements:
    if old not in ch:
        raise SystemExit(f"Change missing source: {old!r}")
    ch = ch.replace(old, new)

evidence = dedent(
    '''

    ### 五平台真实排序与兼容证据（GitHub-hosted Runner）

    - `32045460636`：五平台首轮真实验证。XHS `latest_v2` 获得唯一一级评论且时间严格非增；快手获得 94 条唯一一级评论但时间顺序非严格非增。
    - `32047972292`：抖音 post-fix 真实兼容验证，生产 extractor 从 8 个混合业务卡片中过滤并映射 7 个稳定 `aweme_id`，Detail/Comments 主链可继续；抖音评论 Operation 仍无已批准最新评论排序参数。
    - `32048374466`：微博真实 shape 验证，Search/Detail 可映射；21 个评论候选中 20 个为有效稳定 ID，`sort_type=1` 的 20 个评论时间顺序 `time_nonincreasing=false`，因此不启用增量。
    - `32049910092`：B站最终定向验证，生产 `mode=2 + next_offset=0` 在 Provider 报告 105 条评论的样本上返回 20 条，20/20 comment ID 唯一、20 个时间戳严格非增；结合官方 `mode=2=time`，启用 B站增量。
    - 所有真实调用使用一次性 RSA-3072 OAEP-SHA256 凭据交接，Runner 接收后立即清理 PR 密文占位和临时密钥材料；明文 TikHub Key 未写入 Git、PR、日志或 Artifact。
    '''
)
if "### 五平台真实排序与兼容证据（GitHub-hosted Runner）" not in ch:
    ch += evidence
change.write_text(ch, encoding="utf-8")
