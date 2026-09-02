from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != 1:
        raise SystemExit(f"{path}: expected one match, got {actual}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "frontend/src/features/identity/store.ts",
    "  async function markRead(itemIds: string[]): Promise<void> {",
    "  /** 标记当前 Principal 的通知已读，并以服务端全量未读计数作为最终事实。 */\n  async function markRead(itemIds: string[]): Promise<void> {",
)
replace_once(
    "frontend/src/features/import-batches/store.ts",
    "  async function loadCreationOptions(selectedBatchId?: string | null): Promise<void> {",
    "  /** 加载新建补采所需能力、全部合法历史批次和完整启用词包目录。 */\n  async function loadCreationOptions(selectedBatchId?: string | null): Promise<void> {",
)
for function_name, comment in (
    ("reviewRelevance", "提交相关性人工复核，并刷新当前已加载窗口而不折叠分页。"),
    ("reviewDetailVehicles", "保存详情页车型人工结论，并保持当前列表分页窗口。"),
    ("reviewDetailAnalysis", "保存详情页分析人工纠正，并保持当前列表分页窗口。"),
):
    replace_once(
        "frontend/src/features/voice-plaza/store.ts",
        f"  async function {function_name}(\n",
        f"  /** {comment} */\n  async function {function_name}(\n",
    )
