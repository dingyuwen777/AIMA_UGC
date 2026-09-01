"""一次性审计当前文档中看起来像仓库路径、但当前仓库并不存在的候选。"""

from __future__ import annotations

import os
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = runpy.run_path(str(ROOT / "scripts" / "quality" / "check_docs.py"))
_iter_current_docs = CHECKER["_iter_current_docs"]
_repository_files = CHECKER["_repository_files"]
FENCE_RE = CHECKER["FENCE_RE"]
INLINE_CODE_RE = CHECKER["INLINE_CODE_RE"]

ROOT_PREFIXES = (
    ".agents/",
    ".github/",
    "backend/",
    "changes/",
    "contracts/",
    "docs/",
    "frontend/",
    "migrations/",
    "scripts/",
    "tests/",
)
ROOT_FILES = {
    ".dockerignore",
    ".node-version",
    ".python-version",
    ".uv-version",
    "AGENTS.md",
    "Dockerfile",
    "README.md",
    "compose.windows.yaml",
    "compose.yaml",
    "env.local.example",
    "env.production.example",
    "pyproject.toml",
    "uv.lock",
}
META = frozenset("*?[]{}<>|$\"'")
PATH_LINE_RE = re.compile(r"^[A-Za-z0-9_.\-/\\\u4e00-\u9fff ]+$")


def _clean(value: str) -> str:
    return value.strip().rstrip(".,;:，。；：").replace("\\", "/")


def _candidate(value: str) -> bool:
    value = _clean(value)
    if not value or any(ch in META for ch in value):
        return False
    if any(ch.isspace() for ch in value):
        return False
    if value in ROOT_FILES:
        return True
    return value.startswith(ROOT_PREFIXES)


def _exists(root: Path, doc: Path, value: str, files: tuple[Path, ...]) -> bool:
    value = _clean(value)
    attempts: set[Path] = set()
    if value.startswith(("./", "../")):
        attempts.add((doc.parent / value).resolve())
    else:
        attempts.add((root / value).resolve())
        attempts.add((doc.parent / value).resolve())
    if any(path.exists() for path in attempts):
        return True

    suffix = value.removeprefix("./")
    if suffix.startswith("../"):
        return False
    marker = f"/{suffix.rstrip('/')}"
    matches = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        if rel == suffix.rstrip("/") or rel.endswith(marker):
            matches.append(path)
    if len(matches) == 1:
        return True
    return False


def main() -> int:
    files = _repository_files(ROOT)
    docs = _iter_current_docs(ROOT, files)
    findings: set[tuple[str, int, str]] = set()

    for doc in docs:
        relative = doc.relative_to(ROOT).as_posix()
        in_fence = False
        for line_number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue

            values: list[str] = []
            if in_fence:
                stripped = line.strip()
                if PATH_LINE_RE.match(stripped):
                    values.append(stripped)
            else:
                values.extend(match.group(1) for match in INLINE_CODE_RE.finditer(line))

            for value in values:
                if not _candidate(value):
                    continue
                if not _exists(ROOT, doc, value, files):
                    findings.add((relative, line_number, _clean(value)))

    for relative, line_number, value in sorted(findings):
        print(f"PATH_MISSING {relative}:{line_number}: {value}")
    print(f"PATH_MISSING_COUNT {len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
