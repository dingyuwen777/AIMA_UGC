"""检查当前项目文档的入口、链接、治理边界和仓库文件导航。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
ENTRY_DOCS = (Path("README.md"), Path("docs/blueprint/README.md"))
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
STANDALONE_MANIFEST_RE = re.compile(r"(?<![\w-])manifest\.json\b")
AGENT_REFERENCE_RE = re.compile(r"\.agents/skills/[^/\s)`]+/references/")
EXCLUDED_DOC_ROOTS = {".agents", ".git", "changes"}
PATH_META_CHARS = frozenset("*?[]{}<>|$\"'")
SPECIAL_FILENAMES = {"Dockerfile", "Makefile"}


def _is_current_project_doc(root: Path, path: Path) -> bool:
    """判断文件是否属于当前项目文档域，而不是历史或受管治理资产。"""
    relative = path.relative_to(root)
    if any(part in EXCLUDED_DOC_ROOTS for part in relative.parts):
        return False
    if relative in {Path("README.md"), Path("AGENTS.md")}:
        return True
    if relative.parts and relative.parts[0] == "docs":
        return True
    return path.name == "README.md"


def _iter_current_docs(root: Path) -> tuple[Path, ...]:
    """返回当前项目文档域内所有 Markdown，保持稳定排序。"""
    return tuple(
        sorted(
            path
            for path in root.rglob("*.md")
            if path.is_file() and _is_current_project_doc(root, path)
        )
    )


def _repository_files(root: Path) -> tuple[Path, ...]:
    """建立仓库文件索引，供短路径和文件名导航解析使用。"""
    return tuple(
        path.resolve()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    )


def _looks_like_file_reference(value: str) -> bool:
    """过滤命令、占位符、URL 等明显不是具体仓库文件的代码片段。"""
    if not value or value.startswith(("http://", "https://", "mailto:", "#", "/")):
        return False
    if any(character.isspace() for character in value):
        return False
    if any(character in PATH_META_CHARS for character in value):
        return False
    normalized = value.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    return "/" in normalized or "." in name or name in SPECIAL_FILENAMES


def _resolve_file_reference(
    root: Path,
    doc: Path,
    value: str,
    repository_files: tuple[Path, ...],
) -> Path | None:
    """把文档中的具体路径/文件名解析到唯一存在的仓库文件。"""
    if not _looks_like_file_reference(value):
        return None

    normalized = value.replace("\\", "/")
    direct_candidates: list[Path] = []
    if normalized.startswith(("./", "../")):
        direct_candidates.append((doc.parent / normalized).resolve())
    else:
        direct_candidates.extend(
            (
                (root / normalized).resolve(),
                (doc.parent / normalized).resolve(),
            )
        )

    valid: set[Path] = set()
    root_resolved = root.resolve()
    for candidate in direct_candidates:
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            continue
        if candidate.is_file():
            valid.add(candidate)

    suffix = normalized.removeprefix("./")
    if not suffix.startswith("../"):
        suffix_marker = f"/{suffix}"
        for candidate in repository_files:
            relative = candidate.relative_to(root_resolved).as_posix()
            if relative == suffix or relative.endswith(suffix_marker):
                valid.add(candidate)

    if len(valid) != 1:
        return None
    return next(iter(valid))


def _is_inline_code_linked(line: str, start: int, end: int) -> bool:
    """判断当前 inline-code 是否已经作为 Markdown 链接 label。"""
    return start > 0 and line[start - 1] == "[" and line[end:].startswith("](")


def _suggest_link(doc: Path, target: Path, label: str) -> str:
    """生成从当前文档到目标文件的相对 Markdown 链接建议。"""
    relative = os.path.relpath(target, start=doc.parent).replace(os.sep, "/")
    return f"[`{label.replace('\\', '/')}`]({relative})"


def _check_repository_file_navigation(
    root: Path,
    doc: Path,
    text: str,
    repository_files: tuple[Path, ...],
) -> list[str]:
    """检查导航语义明确的真实仓库文件引用是否保持可点击。"""
    errors: list[str] = []
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue

        if in_fence:
            value = line.strip()
            target = _resolve_file_reference(root, doc, value, repository_files)
            if target is not None:
                suggestion = _suggest_link(doc, target, value)
                errors.append(
                    f"DOC008 {doc.relative_to(root)}:{line_number}: "
                    f"代码块中的真实仓库文件导航不可点击 {value}；改为代码块外链接，例如 {suggestion}"
                )
            continue

        for match in INLINE_CODE_RE.finditer(line):
            value = match.group(1)
            if _is_inline_code_linked(line, match.start(), match.end()):
                continue
            target = _resolve_file_reference(root, doc, value, repository_files)
            if target is None:
                continue
            suggestion = _suggest_link(doc, target, value)
            errors.append(
                f"DOC007 {doc.relative_to(root)}:{line_number}: "
                f"真实仓库文件引用未使用 Markdown 链接 {value}；建议 {suggestion}"
            )

    return errors


def check_repository(root: Path = ROOT) -> list[str]:
    """返回当前项目文档错误；空列表表示文档静态约束满足。"""
    errors: list[str] = []
    documents = _iter_current_docs(root)
    repository_files = _repository_files(root)

    for relative in ENTRY_DOCS:
        doc = root / relative
        if not doc.exists():
            errors.append(f"DOC001 {relative}: 固定文档入口不存在")

    for doc in documents:
        text = doc.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (doc.parent / unquote(target_path)).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"DOC002 {doc.relative_to(root)}: 链接逃出仓库 {target}")
                continue
            if not resolved.exists():
                errors.append(f"DOC003 {doc.relative_to(root)}: 本地链接不存在 {target}")

        if STANDALONE_MANIFEST_RE.search(text):
            errors.append(
                f"DOC004 {doc.relative_to(root)}: 禁止恢复已删除的独立 manifest.json 引用"
            )
        if "R0–R3" in text or "R0-R3" in text:
            errors.append(f"DOC005 {doc.relative_to(root)}: 任务等级必须使用 L1–L3")
        try:
            doc.relative_to(root / "docs")
        except ValueError:
            pass
        else:
            if AGENT_REFERENCE_RE.search(text):
                errors.append(
                    f"DOC006 {doc.relative_to(root)}: "
                    "当前项目文档不得把 Agent_Skills canonical Reference 路径当作本地事实源"
                )

        errors.extend(_check_repository_file_navigation(root, doc, text, repository_files))

    return errors


def main() -> int:
    """执行项目文档静态检查并返回适合 CI 的退出码。"""
    errors = check_repository()
    if errors:
        print("\n".join(errors))
        return 1

    print("当前项目文档入口、链接、治理边界与仓库文件导航检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
