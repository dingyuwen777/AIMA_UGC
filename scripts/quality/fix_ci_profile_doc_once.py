"""一次性校准 Blueprint 中 repository-quality 白名单语义。"""

from pathlib import Path

path = Path("docs/blueprint/06_开发约束与分阶段实施.md")
text = path.read_text(encoding="utf-8")
old = "→ `scripts/quality/**` 与明确归属的治理/文档质量测试"
new = (
    "→ 明确白名单的治理/文档质量脚本（位于 `scripts/quality/`）与其专属测试；"
    "未列入白名单的质量脚本按未知机器路径 fail-closed 到 `full`"
)
if new in text:
    raise SystemExit(0)
if old not in text:
    raise SystemExit("repository-quality documentation baseline missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
