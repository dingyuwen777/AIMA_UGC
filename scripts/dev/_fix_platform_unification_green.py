"""一次性修复平台标识统一首轮 Green 暴露的机械问题。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_if_present(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old in text:
        target.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    replace_if_present(
        "tests/integration/database/test_migration_data_lifecycle.py",
        "from sqlalchemy.engine import Engine\n",
        "from sqlalchemy.engine import Engine\nfrom sqlalchemy.exc import IntegrityError\n",
    )
    replace_if_present(
        "tests/integration/database/test_migration_data_lifecycle.py",
        "with pytest.raises(Exception):",
        "with pytest.raises(IntegrityError):",
    )
    replace_if_present(
        "backend/src/aima_ugc/adapters/providers/imports/excel_profile.py",
        '    "b站": "bilibili",\n',
        '    "B站": "bilibili",\n',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
