import gzip
import inspect
import logging
import re
from datetime import UTC, datetime

import pytest
from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.logging import (
    AimaLogFormatter,
    configure_service_logging,
    log_event,
    shutdown_service_logging,
)


def test_log_prefix_uses_beijing_time_filename_and_line() -> None:
    record = logging.LogRecord(
        name="aima_ugc.test.logging",
        level=logging.INFO,
        pathname="/tmp/_client.py",
        lineno=1090,
        msg="固定时刻",
        args=(),
        exc_info=None,
    )
    record.created = datetime(2026, 8, 18, 6, 10, 8, 637000, tzinfo=UTC).timestamp()

    line = AimaLogFormatter(service="api").format(record)

    assert line.startswith("[2026-08-18 14:10:08.637 _client.py L1090] [INFO] ")
    assert "service=" not in line
    assert "source=" not in line
    assert "event=log.message" in line


def test_log_event_reports_actual_caller_instead_of_logging_helper(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("aima_ugc.test.logging.caller")

    with caplog.at_level(logging.INFO, logger=logger.name):
        expected_line = _emit_from_test_caller(logger)

    record = next(record for record in caplog.records if getattr(record, "event", None) == "test.caller")
    assert record.filename == "test_logging.py"
    assert record.lineno == expected_line


def _emit_from_test_caller(logger: logging.Logger) -> int:
    frame = inspect.currentframe()
    assert frame is not None
    expected_line = frame.f_lineno + 1
    log_event(logger, logging.INFO, "test.caller", "定位真实调用点")
    return expected_line


def test_logging_redacts_escapes_and_rotates_to_gzip(tmp_path) -> None:
    settings = PlatformSettings(
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
        secret_dir=tmp_path / "secrets",
        log_max_bytes=320,
        log_backup_count=3,
        log_compress=True,
    )
    logger = configure_service_logging(
        service="api",
        settings=settings,
        logger_name="aima_ugc.test.logging",
    )

    try:
        for index in range(20):
            log_event(
                logger,
                logging.INFO,
                "test.event",
                "line1\nline2 Bearer super-secret-token",
                index=index,
                password="actual-password-value",
                email="user@example.com",
                mobile="13800138000",
            )
    finally:
        shutdown_service_logging(logger)

    rotated = sorted(settings.log_dir.glob("api.log.*.gz"))
    assert rotated

    chunks = [(settings.log_dir / "api.log").read_text(encoding="utf-8")]
    for path in rotated:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            chunks.append(handle.read())
    output = "".join(chunks)

    assert "super-secret-token" not in output
    assert "actual-password-value" not in output
    assert "user@example.com" not in output
    assert "13800138000" not in output
    assert "Bearer ***" in output
    assert 'password="***"' in output
    assert r"line1\nline2" in output
    assert "service=" not in output
    assert "source=" not in output
    assert "event=test.event" in output
    assert re.search(
        r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} test_logging\.py L\d+\] \[INFO\]",
        output,
    )
