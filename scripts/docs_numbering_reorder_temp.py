"""一次性同步 Appendix 02—05 的最终功能开发顺序编号；运行后删除自身。"""

from __future__ import annotations

from pathlib import Path

PLACEHOLDERS = {
    "02_Scheduler调度执行与停机恢复.md": "__AIMA_APPENDIX_SCHEDULER__",
    "03_TikHub五平台真实响应与字段映射.md": "__AIMA_APPENDIX_TIKHUB_FIELDS__",
    "04_TikHub多接口验证与备用策略.md": "__AIMA_APPENDIX_TIKHUB_FAMILIES__",
    "05_TikHub接口选型与真实验证台账.md": "__AIMA_APPENDIX_TIKHUB_LEDGER__",
}

FINAL_NAMES = {
    "__AIMA_APPENDIX_SCHEDULER__": "05_Scheduler调度执行与停机恢复.md",
    "__AIMA_APPENDIX_TIKHUB_FIELDS__": "02_TikHub五平台真实响应与字段映射.md",
    "__AIMA_APPENDIX_TIKHUB_FAMILIES__": "03_TikHub多接口验证与备用策略.md",
    "__AIMA_APPENDIX_TIKHUB_LEDGER__": "04_TikHub接口选型与真实验证台账.md",
}

SELF = Path("scripts/docs_numbering_reorder_temp.py")
VALIDATOR = Path("scripts/docs_numbering_validate_temp.py")
CONTEXT = Path(".reliable-vibe-coding/project-context.json")


def should_skip(path: Path) -> bool:
    return (
        path in {SELF, VALIDATOR, CONTEXT}
        or Path("changes/archive") == path
        or Path("changes/archive") in path.parents
        or Path(".github/workflows") == path
        or Path(".github/workflows") in path.parents
        or Path(".git") in path.parents
    )


def main() -> None:
    changed: list[str] = []
    for path in Path(".").rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(Path("."))
        if should_skip(rel):
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        updated = text
        for old, placeholder in PLACEHOLDERS.items():
            updated = updated.replace(old, placeholder)
        for placeholder, new in FINAL_NAMES.items():
            updated = updated.replace(placeholder, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="")
            changed.append(str(rel))

    SELF.unlink()
    print("Appendix 编号引用同步完成：")
    for item in changed:
        print(item)


if __name__ == "__main__":
    main()
