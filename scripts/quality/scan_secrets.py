"""对源码、Provider 证据、Change 与文档执行最小凭据泄漏扫描。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = [
    ROOT / "backend",
    ROOT / "frontend" / "src",
    ROOT / "scripts",
    ROOT / ".github",
    ROOT / "tests" / "fixtures" / "providers",
    ROOT / "changes",
    ROOT / "docs",
]
ROOT_FILES = [ROOT / "pyproject.toml", ROOT / "README.md", ROOT / "AGENTS.md"]
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".vue",
    ".mjs",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".md",
    ".txt",
}
PATTERNS = [
    (
        "SEC001",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "禁止提交私钥",
    ),
    (
        "SEC002",
        re.compile(
            r"""(?ix)
            \b(api[_-]?key|access[_-]?token|password|secret)\b
            \s*[:=]\s*
            ["'][A-Za-z0-9_./+=-]{12,}["']
            """
        ),
        "疑似硬编码凭据",
    ),
    (
        "SEC003",
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_./+=-]{20,}\b"),
        "疑似硬编码 Bearer Token",
    ),
]


def iter_files() -> list[Path]:
    files = [path for path in ROOT_FILES if path.exists()]
    for scan_root in SCAN_ROOTS:
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                if "generated" in path.parts:
                    continue
                files.append(path)
    return files


def main() -> int:
    errors: list[str] = []
    for path in iter_files():
        text = path.read_text(encoding="utf-8")
        for rule_id, pattern, message in PATTERNS:
            if pattern.search(text):
                errors.append(f"{rule_id} {path.relative_to(ROOT)}: {message}")

    if errors:
        print("\n".join(errors))
        return 1

    print("源码、Provider 证据、Change 与文档 Secret 扫描通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
