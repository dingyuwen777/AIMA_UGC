"""一次性迁移当前项目文档中的真实仓库文件导航为相对 Markdown 链接。"""

from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = runpy.run_path(str(ROOT / "scripts" / "quality" / "check_docs.py"))
FENCE_RE = CHECKER["FENCE_RE"]
INLINE_CODE_RE = CHECKER["INLINE_CODE_RE"]
_is_inline_code_linked = CHECKER["_is_inline_code_linked"]
_iter_current_docs = CHECKER["_iter_current_docs"]
_repository_files = CHECKER["_repository_files"]
_resolve_file_reference = CHECKER["_resolve_file_reference"]
_suggest_link = CHECKER["_suggest_link"]


def _fix_inline_navigation(
    doc: Path,
    line: str,
    repository_files: tuple[Path, ...],
) -> str:
    """把普通段落中的真实仓库文件 inline-code 改为相对链接。"""
    matches = list(INLINE_CODE_RE.finditer(line))
    for match in reversed(matches):
        if _is_inline_code_linked(line, match.start(), match.end()):
            continue
        value = match.group(1)
        target = _resolve_file_reference(ROOT, doc, value, repository_files)
        if target is None:
            continue
        replacement = _suggest_link(doc, target, value)
        line = f"{line[: match.start()]}{replacement}{line[match.end() :]}"
    return line


def _pure_file_fence_links(
    doc: Path,
    entries: list[str],
    repository_files: tuple[Path, ...],
) -> list[str] | None:
    """把纯文件路径代码块转换为可点击列表；混合代码块保持原样。"""
    values = [entry.strip() for entry in entries if entry.strip()]
    if not values:
        return None

    links: list[str] = []
    for value in values:
        target = _resolve_file_reference(ROOT, doc, value, repository_files)
        if target is None:
            return None
        links.append(f"- {_suggest_link(doc, target, value)}")
    return links


def _fix_document(doc: Path, repository_files: tuple[Path, ...]) -> bool:
    """迁移单个文档并返回是否发生变化。"""
    original = doc.read_text(encoding="utf-8")
    lines = original.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not FENCE_RE.match(line):
            output.append(_fix_inline_navigation(doc, line, repository_files))
            index += 1
            continue

        opening = line
        fence_entries: list[str] = []
        index += 1
        while index < len(lines) and not FENCE_RE.match(lines[index]):
            fence_entries.append(lines[index])
            index += 1

        if index >= len(lines):
            output.append(opening)
            output.extend(fence_entries)
            break

        closing = lines[index]
        links = _pure_file_fence_links(doc, fence_entries, repository_files)
        if links is None:
            output.append(opening)
            output.extend(fence_entries)
            output.append(closing)
        else:
            output.extend(links)
        index += 1

    updated = "\n".join(output)
    if original.endswith("\n"):
        updated += "\n"
    if updated == original:
        return False
    doc.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    """批量迁移当前项目文档域并打印被修改的仓库相对路径。"""
    repository_files = _repository_files(ROOT)
    documents = _iter_current_docs(ROOT, repository_files)
    changed: list[str] = []
    for doc in documents:
        if _fix_document(doc, repository_files):
            changed.append(doc.relative_to(ROOT).as_posix())

    if changed:
        print("已迁移文档文件导航：")
        print("\n".join(changed))
    else:
        print("没有需要迁移的文档文件导航。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
