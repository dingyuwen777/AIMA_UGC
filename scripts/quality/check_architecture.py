"""检查 Stage 1 仓库骨架硬约束。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = [
    ROOT / "pyproject.toml",
    ROOT / "uv.lock",
    ROOT / ".python-version",
    ROOT / ".node-version",
    ROOT / "backend" / "src" / "aima_ugc" / "__init__.py",
    ROOT / "frontend" / "package.json",
    ROOT / "frontend" / "package-lock.json",
]
FORBIDDEN = [
    ROOT / "backend" / "pyproject.toml",
    ROOT / "backend" / "uv.lock",
    ROOT / "backend" / "tests",
]


def main() -> int:
    errors: list[str] = []
    for path in REQUIRED:
        if not path.exists():
            errors.append(f"ARCH001 {path.relative_to(ROOT)}: Stage 1 必需文件不存在")
    for path in FORBIDDEN:
        if path.exists():
            errors.append(f"ARCH002 {path.relative_to(ROOT)}: 方案 A 禁止创建第二套 backend 工程")

    if errors:
        print("\n".join(errors))
        return 1

    print("Stage 1 架构骨架检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
