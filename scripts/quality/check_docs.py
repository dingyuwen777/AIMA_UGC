"""检查当前项目文档的入口、链接、治理边界和仓库文件导航。"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
ENTRY_DOCS = (Path("README.md"), Path("docs/blueprint/README.md"))
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PATH_LINK_RE = re.compile(r"\[`([^`\n]+)`\]\(([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
STANDALONE_MANIFEST_RE = re.compile(r"(?<![\w-])manifest\.json\b")
AGENT_REFERENCE_RE = re.compile(r"\.agents/skills/[^/\s)`]+/references/")
EXCLUDED_DOC_ROOTS = {".agents", ".git", "changes"}
FALLBACK_EXCLUDED_ROOTS = EXCLUDED_DOC_ROOTS | {
    ".runtime",
    ".venv",
    "dist",
    "node_modules",
}
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


def _fallback_repository_files(root: Path) -> tuple[Path, ...]:
    """在非 Git 测试夹具中回退为受控文件系统扫描。"""
    files: list[Path] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in FALLBACK_EXCLUDED_ROOTS for part in relative.parts):
            continue
        if path.is_file():
            files.append(path)
    return tuple(sorted(files))


def _repository_files(root: Path) -> tuple[Path, ...]:
    """优先用 Git 受控文件建立索引，避免扫描运行时生成目录和外部软链。"""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=False,
        capture_output=True,
        text=False,
    )
    if result.returncode != 0:
        return _fallback_repository_files(root)

    files: list[Path] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(raw_path.decode("utf-8"))
        path = root / relative
        if path.is_file():
            files.append(path)
    return tuple(sorted(files))


def _iter_current_docs(root: Path, repository_files: tuple[Path, ...]) -> tuple[Path, ...]:
    """从受控文件索引返回当前项目文档域内所有 Markdown。"""
    return tuple(
        path
        for path in repository_files
        if path.suffix.lower() == ".md" and _is_current_project_doc(root, path)
    )


def _looks_like_file_reference(value: str) -> bool:
    """过滤命令、占位符、URL、时区标识等明显不是具体仓库文件的片段。"""
    if not value or value.startswith(("http://", "https://", "mailto:", "#", "/")):
        return False
    if any(character.isspace() for character in value):
        return False
    if any(character in PATH_META_CHARS for character in value):
        return False
    normalized = value.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    return "." in name or name in SPECIAL_FILENAMES


def _add_if_repo_file(root: Path, candidate: Path, valid: set[Path]) -> None:
    """只把解析后仍位于仓库内的真实文件加入候选集合。"""
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return
    if resolved.is_file():
        valid.add(resolved)


def _resolve_file_reference(
    root: Path,
    doc: Path,
    value: str,
    repository_files: tuple[Path, ...],
) -> Path | None:
    """把文档中的具体路径/文件名解析到唯一存在的受控仓库文件。"""
    if not _looks_like_file_reference(value):
        return None

    normalized = value.replace("\\", "/")
    valid: set[Path] = set()
    if normalized.startswith(("./", "../")):
        _add_if_repo_file(root, doc.parent / normalized, valid)
    else:
        _add_if_repo_file(root, root / normalized, valid)
        _add_if_repo_file(root, doc.parent / normalized, valid)

    suffix = normalized.removeprefix("./")
    if not suffix.startswith("../"):
        suffix_marker = f"/{suffix}"
        for candidate in repository_files:
            relative = candidate.relative_to(root).as_posix()
            if relative != suffix and not relative.endswith(suffix_marker):
                continue
            _add_if_repo_file(root, candidate, valid)

    if len(valid) != 1:
        return None
    return next(iter(valid))


def _is_inline_code_linked(line: str, start: int, end: int) -> bool:
    """判断当前 inline-code 是否已经作为 Markdown 链接 label。"""
    return start > 0 and line[start - 1] == "[" and line[end:].startswith("](")


def _suggest_link(doc: Path, target: Path, label: str) -> str:
    """生成从当前文档到目标文件的相对 Markdown 链接建议。"""
    relative = os.path.relpath(target, start=doc.parent).replace(os.sep, "/")
    normalized_label = label.replace("\\", "/")
    return f"[`{normalized_label}`]({relative})"


def _navigation_error(root: Path, doc: Path, line_number: int, value: str, target: Path) -> str:
    """生成代码块文件导航未链接的统一错误。"""
    suggestion = _suggest_link(doc, target, value)
    return (
        f"DOC008 {doc.relative_to(root)}:{line_number}: "
        f"代码块中的真实仓库文件导航不可点击 {value}；"
        f"改为代码块外链接，例如 {suggestion}"
    )


def _check_pure_file_fence(
    root: Path,
    doc: Path,
    fence_lines: list[tuple[int, str]],
    repository_files: tuple[Path, ...],
) -> list[str]:
    """只有整个代码块都是文件路径时，才把它视为不可点击的导航清单。"""
    entries = [(line_number, line.strip()) for line_number, line in fence_lines if line.strip()]
    if not entries:
        return []

    resolved: list[tuple[int, str, Path]] = []
    for line_number, value in entries:
        target = _resolve_file_reference(root, doc, value, repository_files)
        if target is None:
            return []
        resolved.append((line_number, value, target))

    return [
        _navigation_error(root, doc, line_number, value, target)
        for line_number, value, target in resolved
    ]


def _check_file_description_fence(
    root: Path,
    doc: Path,
    fence_lines: list[tuple[int, str]],
    repository_files: tuple[Path, ...],
) -> list[str]:
    """识别“文件路径 → 职责”导航块，同时避免误伤命令、目录树和流程图。"""
    entries = [(line_number, line.strip()) for line_number, line in fence_lines if line.strip()]
    if len(entries) < 2 or len(entries) % 2 != 0:
        return []

    resolved: list[tuple[int, str, Path]] = []
    for index in range(0, len(entries), 2):
        line_number, value = entries[index]
        _, description = entries[index + 1]
        target = _resolve_file_reference(root, doc, value, repository_files)
        if target is None or not description.startswith("→"):
            return []
        resolved.append((line_number, value, target))

    return [
        _navigation_error(root, doc, line_number, value, target)
        for line_number, value, target in resolved
    ]


def _check_repository_file_navigation(
    root: Path,
    doc: Path,
    text: str,
    repository_files: tuple[Path, ...],
) -> list[str]:
    """检查导航语义明确的真实仓库文件引用是否保持可点击。"""
    errors: list[str] = []
    in_fence = False
    fence_lines: list[tuple[int, str]] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            if in_fence:
                fence_errors = _check_pure_file_fence(root, doc, fence_lines, repository_files)
                if not fence_errors:
                    fence_errors = _check_file_description_fence(
                        root, doc, fence_lines, repository_files
                    )
                errors.extend(fence_errors)
                fence_lines = []
            in_fence = not in_fence
            continue

        if in_fence:
            fence_lines.append((line_number, line))
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


def _check_repository_file_link_labels(root: Path, doc: Path, text: str) -> list[str]:
    """检查路径型仓库文件链接是否显示完整仓库相对路径。"""
    errors: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, target in PATH_LINK_RE.findall(line):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (doc.parent / unquote(target_path)).resolve()
            try:
                expected = resolved.relative_to(root).as_posix()
            except ValueError:
                continue
            if not resolved.is_file():
                continue
            normalized_label = label.replace("\\", "/").removeprefix("./")
            if normalized_label != expected:
                errors.append(
                    f"DOC009 {doc.relative_to(root)}:{line_number}: "
                    f"仓库文件链接显示路径应为 {expected}，当前为 {label}"
                )
    return errors


def check_repository(root: Path = ROOT) -> list[str]:
    """返回当前项目文档错误；空列表表示文档静态约束满足。"""
    root = root.resolve()
    errors: list[str] = []
    repository_files = _repository_files(root)
    documents = _iter_current_docs(root, repository_files)

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
                resolved.relative_to(root)
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
        errors.extend(_check_repository_file_link_labels(root, doc, text))

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
