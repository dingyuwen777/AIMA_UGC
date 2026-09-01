"""一次性审计当前文档中的仓库脚本命令与 npm script 是否仍存在。"""

from __future__ import annotations

import json
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = runpy.run_path(str(ROOT / "scripts" / "quality" / "check_docs.py"))
_iter_current_docs = CHECKER["_iter_current_docs"]
_repository_files = CHECKER["_repository_files"]
FENCE_RE = CHECKER["FENCE_RE"]

PYTHON_SCRIPT_RE = re.compile(
    r"(?:^|\s)(?:python(?:3)?|uv\s+run\s+python)\s+((?:scripts|backend|tests)/[^\s;&|]+\.py)"
)
NPM_RUN_RE = re.compile(r"\bnpm(?:\s+--prefix\s+frontend)?\s+run\s+([A-Za-z0-9:_-]+)")
NPM_DIRECT_RE = re.compile(r"\bnpm(?:\s+--prefix\s+frontend)?\s+(test)\b")
COMPOSE_FILE_RE = re.compile(r"(?:^|\s)-f\s+([^\s;&|]+\.ya?ml)")
SHELL_SCRIPT_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])((?:\.\\|\.\/)?scripts[\\/][^\s;&|]+\.(?:cmd|ps1|sh))"
)


def _exists(value: str) -> bool:
    normalized = value.replace("\\", "/").removeprefix("./")
    return (ROOT / normalized).is_file()


def main() -> int:
    files = _repository_files(ROOT)
    docs = _iter_current_docs(ROOT, files)
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    npm_scripts = set(package.get("scripts", {}))
    findings: set[tuple[str, int, str, str]] = set()

    for doc in docs:
        relative = doc.relative_to(ROOT).as_posix()
        in_fence = False
        for line_number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if not in_fence:
                continue

            for match in PYTHON_SCRIPT_RE.finditer(line):
                value = match.group(1)
                if not _exists(value):
                    findings.add((relative, line_number, "SCRIPT_MISSING", value))

            for match in SHELL_SCRIPT_RE.finditer(line):
                value = match.group(1)
                if not _exists(value):
                    findings.add((relative, line_number, "SCRIPT_MISSING", value))

            for match in COMPOSE_FILE_RE.finditer(line):
                value = match.group(1)
                if not _exists(value):
                    findings.add((relative, line_number, "COMPOSE_FILE_MISSING", value))

            for pattern in (NPM_RUN_RE, NPM_DIRECT_RE):
                for match in pattern.finditer(line):
                    script = match.group(1)
                    if script not in npm_scripts:
                        findings.add((relative, line_number, "NPM_SCRIPT_MISSING", script))

    for relative, line_number, kind, value in sorted(findings):
        print(f"{kind} {relative}:{line_number}: {value}")
    print(f"COMMAND_FACT_MISSING_COUNT {len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
