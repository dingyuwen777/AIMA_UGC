"""对当前源码和配置执行最小凭据泄漏扫描。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = [
    ROOT / "backend",
    ROOT / "frontend" / "src",
    ROOT / "scripts",
    ROOT / ".github",
]
ROOT_FILES = [ROOT / "pyproject.toml"]
TEXT_SUFFIXES = {".py", ".ts", ".vue", ".mjs", ".json", ".toml", ".yml", ".yaml"}
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

    print("源码与配置 Secret 扫描通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
