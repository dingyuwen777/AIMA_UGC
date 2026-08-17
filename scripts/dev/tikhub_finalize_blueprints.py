"""一次性 TikHub Blueprint 最终化；执行后删除。"""
from pathlib import Path
from textwrap import dedent


def replace_required(path: str, pairs: tuple[tuple[str, str], ...]) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"{path}: missing {old!r}")
        text = text.replace(old, new)
    target.write_text(text, encoding="utf-8")


replace_required(
    "docs/blueprint/13-统一数据Excel导出与调试复用.md",
    (
        ("阶段性人工审阅 Excel 实现", "阶段性原始数据 Excel 实现"),
        (
            "tikhub_test 临时 ReviewContent / ReviewCommentRow",
            "tikhub_test 临时 RawDataContent / RawDataCommentRow",
        ),
        ("内容与评论.xlsx", "<platform>_raw_data.xlsx"),
        (
            "人工审阅格式不能反向成为 Canonical Schema",
            "原始数据 Excel 展示格式不能反向成为 Canonical Schema",
        ),
        ("唯一共享 Excel Exporter/Renderer", "唯一共享原始数据 Excel Exporter"),
        (
            "`ReviewContent` / `ReviewCommentRow` / `ReviewBlock`",
            "`RawDataContent` / `RawDataCommentRow` / `RawDataBlock`",
        ),
    ),
)
replace_required(
    "docs/blueprint/README.md",
    (
        (
            "帖子/评论基础数据 Excel 导出、`.xlsx` 人工审阅",
            "帖子/评论原始数据 Excel 导出、`.xlsx` 原始数据查看",
        ),
        (
            "采集基础数据 Excel、Canonical/Aggregate 导出边界、`tikhub_test` 阶段性 Excel",
            "采集原始数据 Excel、Canonical/Aggregate 导出边界、`tikhub_test` 阶段性 Excel",
        ),
        (
            "基础数据导出、Excel、`.xlsx`、`openpyxl`、调试审阅文件",
            "原始数据导出、Excel、`.xlsx`、`openpyxl`、调试原始数据文件",
        ),
    ),
)

p07 = Path("docs/blueprint/07-技术决策与实施门禁.md")
text07 = p07.read_text(encoding="utf-8")
if "> 蓝图版本：1.17" not in text07:
    raise SystemExit("07 version anchor missing")
text07 = text07.replace("> 蓝图版本：1.17", "> 蓝图版本：1.18")
anchor07 = "| 数据库中间层 | 写入固定 Canonical → Ingestion Service → Owner Repository；读取固定 PostgreSQL → Query Repository/Read Model → Query Service；Aggregate 不作为数据库大 JSON 持久化 |\n"
if anchor07 not in text07:
    raise SystemExit("07 decision table anchor missing")
row07 = "| 原始数据 Excel | 系统级原始数据 Excel 只消费 Canonical/Aggregate 或经批准的 Provider-neutral Export Read Model；它不是分析报告。正式共享 Exporter 落地时，`tikhub_test` 必须删除平行 Excel 生成实现并复用共享导出，不能长期维护两套字段、样式和安全规则。 |\n"
p07.write_text(text07.replace(anchor07, anchor07 + row07), encoding="utf-8")

p08 = Path("docs/blueprint/08-采集策略与平台能力.md")
text08 = p08.read_text(encoding="utf-8")
old_incremental = "如果 Provider 没有稳定时间排序或 Fixture 不能证明该停止条件可靠，则 Capability 不声明增量能力，改为受控部分刷新。\n\n`comment_count` 下降只表示平台总量发生变化，可能是删除、审核或统计校正。如果以前或当前 coverage 不是完整集合，不得把“这次没看到某条旧评论”解释成具体删除。"
new_incremental = dedent(
    '''
    如果 Provider 没有稳定时间排序或 Fixture/真实 Probe 不能证明该停止条件可靠，则 Capability 不声明增量能力，改为受控部分刷新。已付费返回的当前页必须完整保存、映射和摄取；历史边界只决定“是否继续付费请求下一页”。

    当前五平台正式 Capability：

    | 平台 | 评论排序事实 | `supports_incremental_comment_sort` | 原因 |
    | --- | --- | --- | --- |
    | 小红书 | App V2 固定 `latest_v2` | `true` | 官方最新优先语义 + 当前真实页时间严格非增 |
    | B站 | App `mode=2`，首屏显式 `next_offset=0` | `true` | 官方时间排序语义 + 当前真实首屏 20/20 唯一 ID、20 个时间戳严格非增 |
    | 抖音 | App V3 评论无已批准的最新评论排序参数 | `false` | 无法证明 comment ID 可作为安全时间边界 |
    | 微博 | App `sort_type=1` | `false` | 当前真实 20 条有效评论时间顺序并非严格非增 |
    | 快手 | App `pcursor`，无已批准的最新评论排序参数 | `false` | 当前真实 94 条一级评论时间顺序并非严格非增 |

    增量安全停止使用生产共享规则：某页出现已知历史评论后，只有从**第一个已知评论到该页末尾全部都是已知评论**，才记录 `known_comment_reached` 并停止下一页；如果旧评论后又出现新评论，则继续翻页，避免置顶/混排导致误停。

    `comment_count` 下降只表示平台总量发生变化，可能是删除、审核或统计校正。如果以前或当前 coverage 不是完整集合，不得把“这次没看到某条旧评论”解释成具体删除。
    '''
).strip()
if old_incremental not in text08:
    raise SystemExit("08 incremental anchor missing")
text08 = text08.replace(old_incremental, new_incremental)
text08 = text08.replace("→ 人工 XLSX", "→ 原始数据 Excel")
text08 = text08.replace(
    "`decisions.jsonl` 和人工 XLSX",
    "运行摘要/决策证据和原始数据 Excel",
)

section18_start = text08.index("## 18. 五平台能力差异摘要")
section19_start = text08.index("## 19. Stage 7 当前实现与收尾门禁")
section18 = dedent(
    '''
    ## 18. 五平台能力差异摘要

    ### 18.1 小红书

    - Search App V2 支持排序、内容类型和发布时间筛选；评论 App V2 固定 `sort_strategy=latest_v2`；
    - 当前真实 Runner 观察到一级评论 ID 唯一且时间严格非增；Capability 已开启安全增量；
    - `comment_count` 增加时生产 Decision 进入 `fetch_incremental`，正式 Scope 从 PostgreSQL 读取已知一级评论 ID，并使用共享 `known_comment_reached` 边界停止下一页。

    ### 18.2 抖音

    - Search V2、App V3 Detail/Comments/Replies、Mapper、真实 Fixture、Capability/Registry 和生产纵切均已建立；
    - 真实兼容验证确认生产 extractor 会过滤不含稳定 `aweme_id` 的混合搜索卡片；
    - App V3 评论没有已批准的“最新评论排序”业务参数，因此 `supports_incremental_comment_sort=false`；评论数增加走 `refresh_controlled`。

    ### 18.3 微博

    - Web Search、App Detail/一级评论、Web V2 二级评论、Mapper、真实 Fixture、Capability/Registry 均已建立；
    - App 一级评论可发送 `sort_type=1`，但当前真实样本的 20 条有效评论时间顺序不是严格非增；生产 extractor 同时过滤没有稳定评论 ID 的展示卡片；
    - 因此 `supports_incremental_comment_sort=false`，不能因为参数名叫“latest”就提前停止分页。

    ### 18.4 B站

    - App Search/Detail/Comments/Reply、Mapper、真实 Fixture、Capability/Registry 均已建立；Search 当前没有 Provider 原生时间范围，`native_time_filter=false`；
    - 评论 `latest` 映射 `mode=2`；真实 Probe 证明首屏必须显式 `next_offset=0`，生产 Runtime 已固定该首屏语义；
    - 2026-08-18 当前真实 Runner 在 Provider 报告 105 条评论的样本上返回 20 条，20/20 ID 唯一、20 个时间戳严格非增；结合官方 `mode=2=time` 语义，Capability 开启 `supports_incremental_comment_sort=true`。

    ### 18.5 快手

    - 正式主链为 App Search V2 / Detail / 一级评论 / 二级回复；Web 评论链只保留显式 `verified_backup`，不自动 fallback；
    - 当前正式 App 评论没有已批准的最新评论排序参数；真实 Probe 的 94 条一级评论时间顺序不是严格非增；
    - 因此 `supports_incremental_comment_sort=false`，评论数增加继续受控刷新。

    详细平台规则、官方链接和当前代码路径见 [`../collection/README.md`](../collection/README.md)。

    '''
)
text08 = text08[:section18_start] + section18 + text08[section19_start:]
section19_start = text08.index("## 19. Stage 7 当前实现与收尾门禁")
section20_start = text08.index("## 20. 文档同步规则")
section19 = dedent(
    '''
    ## 19. Stage 7 当前实现状态与一致性门禁

    Stage 7 的基础采集/调度闭环已经合入 `main` 并归档；本节不再把历史 PR #55 的“待合并”步骤描述成当前工作。当前正式机器实现包括五平台 TikHub Operation/Mapper/Capability/Registry、Provider Config/Secret、Decision、Plan/Occurrence/Run Snapshot、Scheduler、`collection.run.v1` Worker、Raw/Canonical/Ingestion 与 Provider Billing 审计。

    2026-08-18 的系统一致性复核发现并修复了一个已批准 Blueprint 未完整落地的缺口：增量评论 Decision 已存在，但生产 Scope 最初没有历史 comment ID 边界，且 XHS Capability 保守关闭。当前规则已经收敛为：

    - 生产 `known_comment_reached` 规则由 Collection 模块统一拥有；
    - PostgreSQL 一次读取目标内容已有一级评论 ID，不逐评论查询；
    - XHS、B站按已验证最新排序开启增量；抖音、微博、快手保持受控刷新；
    - `tikhub_test` 只提供文件版 previous state，调用同一个生产 Decision/边界规则；
    - 当前没有请求/金额 Budget Runtime，也不以预算作为评论停止条件。

    后续任何平台若要从 `false` 改成 `true`，必须取得同等级“官方排序语义 + 当前真实多评论页顺序 + 稳定 comment ID”的证据，并同步 Capability、平台文档和回归测试；不能只依据参数名称或单条样本。

    '''
)
text08 = text08[:section19_start] + section19 + text08[section20_start:]
p08.write_text(text08, encoding="utf-8")
