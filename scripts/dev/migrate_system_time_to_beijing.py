"""一次性补齐 AIMA 北京时间边界修复、回归与长期文档。"""

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
    """按预期次数替换精确文本，避免一次性迁移静默改错仓库事实。"""
    path = ROOT / relative_path
    content = path.read_text(encoding="utf-8")
    actual_count = content.count(old)
    if actual_count != expected_count:
        raise RuntimeError(
            f"{relative_path} 预期命中 {expected_count} 次，实际 {actual_count} 次：{old!r}"
        )
    path.write_text(content.replace(old, new), encoding="utf-8")
    print(relative_path)


def _write_new(relative_path: str, content: str) -> None:
    """创建预期不存在的新回归文件，存在时立即失败避免覆盖。"""
    path = ROOT / relative_path
    if path.exists():
        raise RuntimeError(f"一次性迁移预期新文件不存在：{relative_path}")
    path.write_text(content, encoding="utf-8")
    print(relative_path)


def _write_existing(relative_path: str, content: str) -> None:
    """完整重写已确认的小文件，缺失时立即失败。"""
    path = ROOT / relative_path
    if not path.is_file():
        raise RuntimeError(f"一次性迁移预期文件存在：{relative_path}")
    path.write_text(content, encoding="utf-8")
    print(relative_path)


def _fix_docx_external_protocol_boundary() -> None:
    """OOXML W3CDTF 需要 UTC Z；系统时钟仍从北京时间能力取得后再转换。"""
    path = "backend/src/aima_ugc/platform/reporting/docx_package.py"
    _replace_exact(
        path,
        "from dataclasses import dataclass\nfrom io import BytesIO",
        "from dataclasses import dataclass\nfrom datetime import UTC\nfrom io import BytesIO",
    )
    _replace_exact(
        path,
        '    now = beijing_now().strftime("%Y-%m-%dT%H:%M:%SZ")',
        '    now = beijing_now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")',
    )


def _fix_llm_pricing_calendar_semantics() -> None:
    """LLM 价格生效日属于 AIMA 自有配置语义，按北京时间日历判断。"""
    path = "backend/src/aima_ugc/adapters/llm/pricing.py"
    _replace_exact(path, "from datetime import UTC, date, datetime", "from datetime import date, datetime")
    _replace_exact(
        path,
        "from aima_ugc.platform.time import beijing_now",
        "from aima_ugc.platform.time import beijing_now, to_beijing",
    )
    _replace_exact(
        path,
        "    request_date = at.astimezone(UTC).date()",
        "    request_date = to_beijing(at).date()",
    )

    test_path = "tests/unit/analysis/test_llm_pricing_effective_date.py"
    _replace_exact(
        test_path,
        "datetime(2026, 8, 23, 23, 59, 59, tzinfo=UTC)",
        "datetime(2026, 8, 23, 15, 59, 59, tzinfo=UTC)",
        expected_count=3,
    )
    _replace_exact(
        test_path,
        "    class BeforeEffectiveDateTime(datetime):\n"
        "        @classmethod\n"
        "        def now(cls, tz: object = None) -> datetime:\n"
        "            return datetime(2026, 8, 23, 15, 59, 59, tzinfo=UTC)\n\n"
        '    monkeypatch.setattr(openai_compatible_module, "datetime", BeforeEffectiveDateTime)',
        '    monkeypatch.setattr(\n'
        '        openai_compatible_module,\n'
        '        "beijing_now",\n'
        '        lambda: datetime(2026, 8, 23, 15, 59, 59, tzinfo=UTC),\n'
        '    )',
    )

    _write_new(
        "tests/unit/analysis/test_llm_pricing_beijing_date.py",
        '''"""LLM Pricing 北京时间日历边界回归。"""\n\nfrom datetime import UTC, datetime\n\nfrom aima_ugc.adapters.llm.pricing import load_llm_pricing\n\n\ndef test_effective_date_uses_beijing_calendar_day() -> None:\n    """北京时间进入生效日后，即使 UTC 仍是前一天也应启用当日价格。"""\n    price = load_llm_pricing().price_for(\n        provider="api.deepseek.com",\n        model="deepseek-v4-pro",\n        at=datetime(2026, 8, 23, 16, 0, 0, tzinfo=UTC),\n    )\n\n    assert price.effective_date is not None\n    assert price.effective_date.isoformat() == "2026-08-24"\n''',
    )


def _add_protocol_and_logging_regressions() -> None:
    """固定外部 UTC 协议边界和日志不显示 timezone 文本的用户决定。"""
    _write_new(
        "tests/unit/platform/test_time_protocol_boundaries.py",
        '''"""北京时间系统与外部时间协议边界回归。"""\n\nfrom datetime import datetime\nfrom zoneinfo import ZoneInfo\n\nimport pytest\nfrom aima_ugc.platform.reporting import docx_package as docx_package_module\n\n\ndef test_docx_core_properties_convert_beijing_clock_to_utc_z(\n    monkeypatch: pytest.MonkeyPatch,\n) -> None:\n    """OOXML W3CDTF 的 Z 时间必须是同一北京时间时刻转换后的 UTC。"""\n    fixed = datetime(2026, 8, 25, 9, 44, 19, tzinfo=ZoneInfo("Asia/Shanghai"))\n    monkeypatch.setattr(docx_package_module, "beijing_now", lambda: fixed)\n\n    xml = docx_package_module._core_props_xml()\n\n    assert "2026-08-25T01:44:19Z" in xml\n    assert "2026-08-25T09:44:19Z" not in xml\n''',
    )
    _write_new(
        "tests/unit/platform/test_logging_timezone_policy.py",
        '''"""日志北京时间前缀不重复输出 timezone 文本。"""\n\nimport logging\nfrom datetime import UTC, datetime\n\nfrom aima_ugc.platform.logging import AimaLogFormatter\n\n\ndef test_log_prefix_omits_timezone_field_and_name() -> None:\n    """日志已有北京时间墙钟后，不再输出 timezone 字段或 Asia/Shanghai 文本。"""\n    record = logging.LogRecord(\n        name="aima_ugc.test.logging.timezone",\n        level=logging.INFO,\n        pathname="/tmp/runtime.py",\n        lineno=114,\n        msg="时间策略",\n        args=(),\n        exc_info=None,\n    )\n    record.created = datetime(2026, 8, 25, 1, 44, 19, 257000, tzinfo=UTC).timestamp()\n\n    line = AimaLogFormatter(service="api").format(record)\n\n    assert line.startswith("[2026-08-25 09:44:19.257 runtime.py L114] [INFO] ")\n    assert "timezone=" not in line\n    assert "Asia/Shanghai" not in line\n''',
    )
    _write_new(
        "tests/unit/platform/test_http_beijing_time_contract.py",
        '''"""AIMA 自有 HTTP 输入时间解释回归。"""\n\nfrom datetime import UTC, datetime, timedelta\n\nfrom aima_ugc.contracts.http import ImportBatchListQuery\n\n\ndef test_http_time_filters_normalize_to_beijing_time() -> None:\n    """带时区的 HTTP 时间筛选进入 AIMA Contract 后统一解释为北京时间。"""\n    query = ImportBatchListQuery(\n        created_from=datetime(2026, 8, 25, 1, 0, 0, tzinfo=UTC),\n        created_to=datetime(2026, 8, 25, 2, 0, 0, tzinfo=UTC),\n    )\n\n    assert query.created_from is not None\n    assert query.created_to is not None\n    assert query.created_from.hour == 9\n    assert query.created_to.hour == 10\n    assert query.created_from.utcoffset() == timedelta(hours=8)\n''',
    )


def _tighten_postgresql_integration() -> None:
    """用真实 PostgreSQL 同时证明版本、Session timezone 与 timestamptz 绝对时刻语义。"""
    _write_existing(
        "tests/integration/platform/test_database.py",
        '''from sqlalchemy import text\n\nfrom aima_ugc.platform.config import load_settings\nfrom aima_ugc.platform.database import DatabaseRuntime\n\n\ndef test_database_runtime_connects_to_real_postgresql_18() -> None:\n    """真实 PostgreSQL Session 使用北京时间，同时 timestamptz 保持同一绝对时刻。"""\n    settings = load_settings()\n    runtime = DatabaseRuntime(settings)\n\n    try:\n        assert runtime.ping() is True\n        with runtime.new_session() as session:\n            version_num = int(session.execute(text("SHOW server_version_num")).scalar_one())\n            session_timezone = str(session.execute(text("SHOW TimeZone")).scalar_one())\n            instant = session.execute(\n                text("SELECT TIMESTAMPTZ '2026-08-25 01:44:19+00'")\n            ).scalar_one()\n        assert version_num // 10_000 == 18\n        assert session_timezone == "Asia/Shanghai"\n        assert instant.isoformat() == "2026-08-25T09:44:19+08:00"\n    finally:\n        runtime.dispose()\n''',
    )


def _sync_blueprints() -> None:
    """把最终北京时间与外部协议边界写回长期 Blueprint，而不是只留在 Change。"""
    _replace_exact(
        "docs/blueprint/04_后端任务API与前端.md",
        "- 前端不能维护另一套平行 Request/Response Type 来“暂时对齐”。\n\n---",
        "- 前端不能维护另一套平行 Request/Response Type 来“暂时对齐”。\n\n"
        "时间 Contract 统一规则：AIMA 自有 HTTP `datetime` 以带 `+08:00` 偏移的 ISO-8601 北京时间序列化；带时区的时间筛选进入 Contract 后先归一到 `Asia/Shanghai` 再解释。第三方 Raw 或外部协议必须保持原始 timestamp/epoch/timezone 语义的事实层不改写，只有进入 AIMA 自有展示/序列化边界时才按该边界规则转换。前端 generated Client 不维护第二套 UTC 假设。\n\n---",
    )
    _replace_exact(
        "docs/blueprint/05_日志安全部署与运维.md",
        "人工日志时间显示 `Asia/Shanghai`；数据库机器时间仍用 `timestamptz`。真实调用文件和源码行号放在前缀，是为了让人工排障可以直接跳回代码。",
        "人工日志时间显示 `Asia/Shanghai`，但前缀不额外输出 `timezone` 字段或 `Asia/Shanghai` 文本；看到的墙钟即为北京时间。数据库继续用 `timestamptz` 表达绝对时间点，应用 PostgreSQL Session 默认 timezone 显式固定为 `Asia/Shanghai`。第三方 Raw 或外部协议必须保留原始时间语义时按原协议保存/传输，在 AIMA 自有展示边界再转换。真实调用文件和源码行号放在前缀，是为了让人工排障可以直接跳回代码。",
    )
    _replace_exact(
        "docs/blueprint/06_开发约束与分阶段实施.md",
        "机器 Contract 明确要求 UTC/结构化 wire format 时保留原协议语义。",
        "只有第三方 Raw 或外部协议明确要求原始 UTC/epoch/其他 wire 时间语义时才保留原协议形式；AIMA 自有 Contract 默认统一为 `Asia/Shanghai`。",
    )


def main() -> int:
    """执行一次性最终边界补丁；完成后该脚本与临时 Workflow 会从仓库删除。"""
    _fix_docx_external_protocol_boundary()
    _fix_llm_pricing_calendar_semantics()
    _add_protocol_and_logging_regressions()
    _tighten_postgresql_integration()
    _sync_blueprints()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
