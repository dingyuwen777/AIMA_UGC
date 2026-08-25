"""一次性把 AIMA 生产源码的系统自产 UTC 当前时间迁移为北京时间。"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "backend" / "src" / "aima_ugc"
OLD_CALL = "datetime.now(UTC)"
NEW_CALL = "beijing_now()"
IMPORT_LINE = "from aima_ugc.platform.time import beijing_now"


def _insert_time_import(content: str) -> str:
    """在顶层 import 区末尾插入北京时间 helper，由 Ruff 负责最终排序。"""
    if IMPORT_LINE in content:
        return content
    module = ast.parse(content)
    import_nodes = [
        node
        for node in module.body
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node.end_lineno is not None
    ]
    if not import_nodes:
        raise ValueError("生产模块缺少顶层 import，无法安全插入北京时间 helper")
    insert_after = max(node.end_lineno or node.lineno for node in import_nodes)
    lines = content.splitlines(keepends=True)
    lines.insert(insert_after, f"{IMPORT_LINE}\n")
    return "".join(lines)


def _migrate_file(path: Path) -> bool:
    """只迁移系统当前时间调用，不改外部 timestamp 解析或显式协议时区。"""
    content = path.read_text(encoding="utf-8")
    if OLD_CALL not in content:
        return False
    migrated = content.replace(OLD_CALL, NEW_CALL)
    migrated = _insert_time_import(migrated)
    path.write_text(migrated, encoding="utf-8")
    return True


def main() -> int:
    """迁移所有命中的生产 Python 文件并输出相对路径。"""
    changed: list[Path] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if _migrate_file(path):
            changed.append(path)
    for path in changed:
        print(path.relative_to(ROOT).as_posix())
    print(f"已迁移 {len(changed)} 个生产源码文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
