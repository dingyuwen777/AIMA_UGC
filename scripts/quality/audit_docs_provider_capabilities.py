"""一次性反查五平台当前 TikHub Capability 是否被对应平台文档覆盖。"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py"
DOCS = {
    "xiaohongshu": ROOT / "docs/collection/01_xiaohongshu.md",
    "douyin": ROOT / "docs/collection/02_douyin.md",
    "weibo": ROOT / "docs/collection/03_weibo.md",
    "bilibili": ROOT / "docs/collection/04_bilibili.md",
    "kuaishou": ROOT / "docs/collection/05_kuaishou.md",
}


def _literal(keyword: ast.keyword) -> object:
    return ast.literal_eval(keyword.value)


def _kw(call: ast.Call, name: str) -> ast.keyword | None:
    return next((keyword for keyword in call.keywords if keyword.arg == name), None)


def _capabilities() -> dict[str, dict[str, set[str]]]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    result: dict[str, dict[str, set[str]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id.endswith("_TIKHUB_CAPABILITY")
            for target in node.targets
        ):
            continue
        platform_keyword = _kw(node.value, "platform")
        operations_keyword = _kw(node.value, "operations")
        if platform_keyword is None or operations_keyword is None:
            continue
        platform = str(_literal(platform_keyword))
        buckets = {
            "business_operations": set(),
            "provider_operations": set(),
            "sort_modes": set(),
            "time_filters": set(),
            "duration_filters": set(),
            "content_types": set(),
            "comment_sort_modes": set(),
        }
        if not isinstance(operations_keyword.value, (ast.Tuple, ast.List)):
            continue
        for operation in operations_keyword.value.elts:
            if not isinstance(operation, ast.Call):
                continue
            mapping = {
                "business_operation": "business_operations",
                "provider_operations": "provider_operations",
                "supported_sort_modes": "sort_modes",
                "supported_time_filters": "time_filters",
                "supported_duration_filters": "duration_filters",
                "supported_content_types": "content_types",
                "comment_sort_modes": "comment_sort_modes",
            }
            for keyword_name, bucket_name in mapping.items():
                keyword = _kw(operation, keyword_name)
                if keyword is None:
                    continue
                value = _literal(keyword)
                if isinstance(value, str):
                    buckets[bucket_name].add(value)
                elif isinstance(value, tuple):
                    buckets[bucket_name].update(str(item) for item in value)
        result[platform] = buckets
    return result


def main() -> int:
    capabilities = _capabilities()
    findings = 0
    for platform, doc in DOCS.items():
        text = doc.read_text(encoding="utf-8")
        current = capabilities[platform]
        for operation in sorted(current["provider_operations"]):
            if operation not in text:
                findings += 1
                print(f"PROVIDER_OPERATION_MISSING {doc.relative_to(ROOT)}: {operation}")
        print(
            f"PROVIDER_COVERAGE {platform}: "
            f"provider_operations={len(current['provider_operations'])} "
            f"missing={sum(operation not in text for operation in current['provider_operations'])}"
        )
        for bucket in (
            "business_operations",
            "sort_modes",
            "time_filters",
            "duration_filters",
            "content_types",
            "comment_sort_modes",
        ):
            missing = sorted(value for value in current[bucket] if value not in text)
            if missing:
                print(
                    f"PROVIDER_DETAIL_CANDIDATE {doc.relative_to(ROOT)} {bucket}: "
                    + ",".join(missing)
                )
    print(f"PROVIDER_OPERATION_MISSING_COUNT {findings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
