"""一次性同步 CHG-314 长期文档并删除施工脚手架。

只修改文档与临时 Change 工具；完成后本文件由同一次 Runner 提交删除。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one anchor, got {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: str, marker: str, addition: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


def main() -> None:
    replace_once(
        "docs/blueprint/04_后端任务API与前端.md",
        """`POST /api/v1/content-analysis-requests` 是兼容入口，为保持既有 `request_id/job_id` Response，仍在 HTTP 短事务内冻结目标、创建首个 Shard 并建立 Analysis Run，并兼容历史 selected/query 语义。新页面只允许显式选择 1—1000 条内容：先调用 `/api/v1/analysis/content-runs/preview` 取得目标数、Shard 数和模型/Prompt/配置身份，再由用户确认创建 Run；新版 Preview/Create Contract 不接受 query scope。创建 HTTP 只保存 Run 头与 Planner Job。Planner 在 PostgreSQL 事务内用 `INSERT ... SELECT` 冻结 Content ID + `current_version`，复核 Preview 数量并维持有界 Shard Job 窗口；数量变化时整次冻结回滚，Run 返回 Planner `error_code` 供页面展示。查询范围 Run 要等真实付费模型 Gold Set、费用和容量报告后重新决策。不同 Run 结果全部保留，Current 按 Run 创建顺序选择，最新失败/取消不会抹掉旧成功结果。""",
        """`POST /api/v1/content-analysis-requests` 是兼容入口，为保持既有 `request_id/job_id` Response，仍在 HTTP 短事务内冻结目标、创建首个 Shard 并建立 Analysis Run，并兼容历史 selected/query 语义。声音广场新版 Analysis Run 正式开放两种用户范围：`selected` 接收 1—1000 个显式 Content ID；`all` 表示数据库当前全部 Content Current，不能携带 `content_ids`，也不受页面当前筛选或已加载分页影响。两种范围都先调用 `/api/v1/analysis/content-runs/preview` 取得目标数、Shard 数和模型/Prompt/配置身份，再由用户确认创建 Run。`all` 在服务层复用既有数据库 `query` Scope，并以默认空 `ContentFilterSnapshot` 作为持久快照，因此无需 Schema/Migration；历史真正带筛选条件的 `query` Run 仍保留原语义。创建 HTTP 只保存 Run 头与 Planner Job，不把全量 Content ID 放进浏览器、HTTP Payload 或单个 Job。Planner 在 PostgreSQL 事务内用 `INSERT ... SELECT` 冻结 Content ID + `current_version`，复核 Preview 数量并维持有界 Shard Job 窗口；数量变化时整次冻结回滚，Run 返回 Planner `error_code` 供页面展示。不同 Run 结果全部保留，Current 按 Run 创建顺序选择，最新失败/取消不会抹掉旧成功结果。""",
    )

    replace_once(
        "frontend/README.md",
        """当前新版 Analysis Run 只开放显式选择 1—1000 条内容；query scope Run 没有作为当前页面能力开放。页面不负责 Planner/Shard/Current 选择规则，这些由后端 Analysis Domain、PostgreSQL 和 generated Contract 决定。""",
        """当前新版 Analysis Run 正式开放 `selected` 与 `all` 两种范围。`selected` 保留显式选择 1—1000 条内容的上限；`all` 表示数据库当前全部 Content Current，即使页面没有勾选内容也可以发起，且不受当前筛选和已加载分页影响。前端对 `all` 只发送 `{ scope: 'all' }`，不会先翻页收集全部 ID。页面不负责 Planner/Shard/Current 选择规则，这些由后端 Analysis Domain、PostgreSQL 和 generated Contract 决定。""",
    )

    append_once(
        "backend/src/aima_ugc/modules/analysis/README.md",
        "## 12. Analysis Run 的 selected / all 范围",
        """
---

## 12. Analysis Run 的 selected / all 范围

声音广场正式 Run 的公共 Scope：

```text
selected
→ 1—1000 个显式 Content ID

all
→ 数据库当前全部 Content Current
→ 不受声音广场当前筛选或已加载分页影响
→ HTTP 请求不携带全量 Content ID
```

`all` 在 HTTP Contract 中是独立语义；服务端持久化时复用既有 `analysis_content_runs.scope = query`，并保存默认空 `ContentFilterSnapshot`。Planner 再使用集合式 `INSERT ... SELECT` 冻结 `content_id + current_version`，按现有 Shard 大小与在途窗口有界执行，因此不新增表或 Migration。历史真正带筛选条件的 `query` Run 继续按 `query` 返回，不会被错误改写为 `all`。
""",
    )

    append_once(
        "docs/appendix/07_AI舆情打标与分析实现.md",
        "# 20. Analysis Run 的 selected / all 范围",
        """
---

# 20. Analysis Run 的 selected / all 范围

声音广场批量 AI 打标有两个正式范围：

```text
selected
→ 显式 1—1000 个 Content ID

all
→ 当前 PostgreSQL 中全部 Content Current
→ 与声音广场当前筛选条件无关
→ 不把全量 ID 放进浏览器或 HTTP Payload
```

`AnalysisRunTargetSelection(scope="all")` 禁止提交 `content_ids`。Preview 用数据库集合式目标语句计算 `target_count`；Create 只建立 Run Header 与 `analysis.content-run-plan.v1` Planner Job。服务层把公共 `all` 规范化为既有数据库 `query` Scope + 默认空 `ContentFilterSnapshot`，所以无需 Schema/Migration；读取 Run 时只有这一默认空快照才投影回 `all`，历史存在实际筛选条件的 `query` Run 保持原语义。

Planner 在 Worker 中用 `INSERT ... SELECT` 冻结 Content ID + 当前 Version，并继续按 `analysis_run_shard_size` 和 `analysis_run_max_in_flight_jobs` 创建有界 Shard。Preview 到 Planner 之间目标数量变化时整次冻结回滚并失败关闭。禁止通过前端分页收集全部 ID，也禁止创建一个承载全部目标的超大 Job Payload。
""",
    )

    subprocess.run(
        [
            "git",
            "rm",
            "-f",
            ".github/workflows/chg314-ai-green.yml",
            ".github/workflows/chg314-ai-red.yml",
            "scripts/dev/apply_chg314_ai_all.py",
        ],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
