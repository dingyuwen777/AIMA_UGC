"""一次性完成 AIMA 北京时间 Contract、运行边界与 live 导航迁移。"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _replace_exact(
    relative_path: str,
    old: str,
    new: str,
    *,
    expected_count: int = 1,
) -> None:
    """按预期次数替换精确文本，避免迁移脚本静默改错当前仓库事实。"""
    path = ROOT / relative_path
    content = path.read_text(encoding="utf-8")
    actual_count = content.count(old)
    if actual_count != expected_count:
        raise RuntimeError(
            f"{relative_path} 预期命中 {expected_count} 次，实际 {actual_count} 次：{old!r}"
        )
    path.write_text(content.replace(old, new), encoding="utf-8")
    print(relative_path)


def _migrate_http_contract() -> None:
    """让 AIMA 自有 HTTP datetime 统一序列化和解释为北京时间。"""
    path = "backend/src/aima_ugc/contracts/http.py"
    _replace_exact(
        path,
        "from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator",
        "from pydantic import ConfigDict, Field, field_validator, model_validator\n\n"
        "from aima_ugc.contracts.base import AimaHttpModel as BaseModel\n"
        "from aima_ugc.platform.time import to_beijing",
    )
    _replace_exact(
        path,
        "        if value is not None and (value.tzinfo is None or value.utcoffset() is None):\n"
        '            raise ValueError("时间筛选必须包含时区")\n'
        "        return value",
        "        if value is not None and (value.tzinfo is None or value.utcoffset() is None):\n"
        '            raise ValueError("时间筛选必须包含时区")\n'
        "        return to_beijing(value) if value is not None else None",
        expected_count=3,
    )


def _migrate_database_runtime() -> None:
    """把 PostgreSQL 连接 Session 默认 timezone 固定为 Asia/Shanghai。"""
    path = "backend/src/aima_ugc/platform/database/runtime.py"
    _replace_exact(
        path,
        "from aima_ugc.platform.security import read_secret_file",
        "from aima_ugc.platform.security import read_secret_file\n"
        "from aima_ugc.platform.time import BEIJING_TIMEZONE",
    )
    _replace_exact(
        path,
        '                    "connect_timeout": self._settings.db_connect_timeout_seconds,\n',
        '                    "connect_timeout": self._settings.db_connect_timeout_seconds,\n'
        '                    "options": f"-c timezone={BEIJING_TIMEZONE.key}",\n',
    )


def _migrate_live_navigation() -> None:
    """迁移当前 live 文档入口，不修改 changes/archive 历史内容。"""
    _replace_exact(
        "README.md",
        "[`.agents/skills/reliable-vibe-coding/SKILL.md`](.agents/skills/reliable-vibe-coding/SKILL.md)",
        "[`.agents/skills/coding/SKILL.md`](.agents/skills/coding/SKILL.md)",
    )
    _replace_exact(
        "AGENTS.md",
        "- 数据库时间用 `timestamptz`；\n"
        "- API 用 UTC ISO-8601；\n"
        "- 人工日志用 `YYYY-MM-DD HH:mm:ss.SSS` 北京时间；",
        "- 数据库时间继续使用 `timestamptz` 表达绝对时间点，应用 PostgreSQL Session 默认 timezone 固定为 `Asia/Shanghai`；\n"
        "- AIMA 自有 API 时间统一使用带 `+08:00` 偏移的 ISO-8601 北京时间；第三方 Raw、外部协议必须保持原始时间语义的事实层按原协议处理；\n"
        "- 人工日志使用北京时间 `[YYYY-MM-DD HH:mm:ss.SSS source.ext L<line>] [LEVEL] message`；前缀不额外输出 `timezone` 字段或 `Asia/Shanghai` 文本；",
    )


def _migrate_coding_live_paths() -> None:
    """把 Coding Skill 当前执行命令从旧 CLI/path 迁到新入口。"""
    for relative_path in (
        ".agents/skills/coding/references/04_change-management.md",
        ".agents/skills/coding/references/10_completion-gate.md",
    ):
        path = ROOT / relative_path
        content = path.read_text(encoding="utf-8")
        migrated = content.replace(
            ".agents/skills/reliable-vibe-coding/scripts/ready_check.py",
            ".agents/skills/coding/scripts/ready_check.py",
        ).replace("rvc.py", "coding.py")
        if migrated == content:
            raise RuntimeError(f"{relative_path} 没有可迁移的 live Coding 路径")
        path.write_text(migrated, encoding="utf-8")
        print(relative_path)


def main() -> int:
    """执行一次性确定性迁移；每项都要求当前文本与预期事实一致。"""
    _migrate_http_contract()
    _migrate_database_runtime()
    _migrate_live_navigation()
    _migrate_coding_live_paths()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
