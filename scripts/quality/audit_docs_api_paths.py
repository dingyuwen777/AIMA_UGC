"""一次性审计当前项目文档中省略 /api/v1 的本仓 API 路径。"""

from __future__ import annotations

import json
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = runpy.run_path(str(ROOT / "scripts" / "quality" / "check_docs.py"))
_iter_current_docs = CHECKER["_iter_current_docs"]
_repository_files = CHECKER["_repository_files"]

METHOD_PATH_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/(?!api/v1(?:/|$)|health(?:/|$))[A-Za-z0-9_{}<>.*:/-]+)"
)
INLINE_PATH_RE = re.compile(r"`(/(?!api/v1(?:/|$)|health(?:/|$))[^`\s?#]+)`")


def _provider_doc(relative: str) -> bool:
    return relative.startswith("docs/collection/") or relative in {
        "docs/appendix/02_TikHub五平台真实响应与字段映射.md",
        "docs/appendix/03_TikHub多接口验证与备用策略.md",
        "docs/appendix/04_TikHub接口选型与真实验证台账.md",
    }


def _match(candidate: str, openapi_paths: set[str]) -> str | None:
    matches = [path for path in openapi_paths if path.endswith(candidate)]
    if len(matches) == 1:
        return matches[0]
    return None


def main() -> int:
    repository_files = _repository_files(ROOT)
    documents = _iter_current_docs(ROOT, repository_files)
    payload = json.loads((ROOT / "contracts/openapi/openapi.json").read_text(encoding="utf-8"))
    openapi_paths = set(payload.get("paths", {}))
    findings: set[tuple[str, int, str, str]] = set()

    for doc in documents:
        relative = doc.relative_to(ROOT).as_posix()
        if _provider_doc(relative):
            continue
        for line_number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern in (METHOD_PATH_RE, INLINE_PATH_RE):
                for match in pattern.finditer(line):
                    candidate = match.group(match.lastindex or 1)
                    if pattern is METHOD_PATH_RE:
                        candidate = match.group(2)
                    if "*" in candidate or candidate.startswith("/data/"):
                        continue
                    full = _match(candidate, openapi_paths)
                    if full is not None:
                        findings.add((relative, line_number, candidate, full))

    for relative, line_number, candidate, full in sorted(findings):
        print(f"API_SHORTHAND {relative}:{line_number}: {candidate} -> {full}")
    print(f"API_SHORTHAND_COUNT {len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
