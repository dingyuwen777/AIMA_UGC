"""检查固定文档入口和本地 Markdown 链接。"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
ENTRY_DOCS = [ROOT / "README.md", ROOT / "docs" / "blueprint" / "README.md"]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
STANDALONE_MANIFEST_RE = re.compile(r"(?<![\w-])manifest\.json\b")


def main() -> int:
    errors: list[str] = []
    for doc in ENTRY_DOCS:
        if not doc.exists():
            errors.append(f"DOC001 {doc.relative_to(ROOT)}: 固定文档入口不存在")
            continue

        text = doc.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target_path = target.split("#", 1)[0]
            resolved = (doc.parent / unquote(target_path)).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"DOC002 {doc.relative_to(ROOT)}: 链接逃出仓库 {target}")
                continue
            if not resolved.exists():
                errors.append(f"DOC003 {doc.relative_to(ROOT)}: 本地链接不存在 {target}")

    for doc in ROOT.rglob("*.md"):
        if ".git" in doc.parts:
            continue
        text = doc.read_text(encoding="utf-8")
        if STANDALONE_MANIFEST_RE.search(text):
            errors.append(f"DOC004 {doc.relative_to(ROOT)}: 禁止恢复已删除的独立 manifest.json 引用")
        if "R0–R3" in text or "R0-R3" in text:
            errors.append(f"DOC005 {doc.relative_to(ROOT)}: 任务等级必须使用 L1–L3")

    if errors:
        print("\n".join(errors))
        return 1

    print("文档入口与本地链接检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
