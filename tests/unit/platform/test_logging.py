import gzip
import logging
import re

from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.logging import (
    configure_service_logging,
    log_event,
    shutdown_service_logging,
)


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
    assert "password=\"***\"" in output
    assert r"line1\nline2" in output
    assert "service=api" in output
    assert "event=test.event" in output
    assert re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\] \[INFO\]", output)
