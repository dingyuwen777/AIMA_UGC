"""应用日志 Handler 配置。"""

from __future__ import annotations

import gzip
import logging
import os
import shutil
import sys
from collections.abc import Mapping

from aima_ugc.platform.config import PlatformSettings

from .formatter import AimaLogFormatter

_LOG_FILES: Mapping[str, str] = {
    "api": "api.log",
    "worker": "worker.log",
    "scheduler": "scheduler.log",
}


def _gzip_namer(default_name: str) -> str:
    return default_name + ".gz"


def _gzip_rotator(source: str, destination: str) -> None:
    with open(source, "rb") as source_file, gzip.open(destination, "wb") as destination_file:
        shutil.copyfileobj(source_file, destination_file)
    os.remove(source)


def _mark_managed(handler: logging.Handler) -> logging.Handler:
    handler.__dict__["_aima_managed"] = True
    return handler


def shutdown_service_logging(logger: logging.Logger) -> None:
    """移除并关闭本模块创建的 Handler，便于测试和进程退出。"""
    for handler in list(logger.handlers):
        if getattr(handler, "_aima_managed", False):
            logger.removeHandler(handler)
            handler.close()


def configure_service_logging(
    *,
    service: str,
    settings: PlatformSettings,
    logger_name: str = "aima_ugc",
) -> logging.Logger:
    """配置单进程应用文件日志和 stdout。"""
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(logger_name)
    shutdown_service_logging(logger)

    configured_level = logging.getLevelNamesMapping()[settings.log_level]
    logger.setLevel(configured_level)
    logger.propagate = False
    formatter = AimaLogFormatter(service=service)

    log_file = _LOG_FILES.get(service)
    if log_file is not None:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            settings.log_dir / log_file,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        if settings.log_compress:
            file_handler.namer = _gzip_namer
            file_handler.rotator = _gzip_rotator
        file_handler.setLevel(configured_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(_mark_managed(file_handler))

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(max(configured_level, logging.INFO))
    stream_handler.setFormatter(formatter)
    logger.addHandler(_mark_managed(stream_handler))
    return logger


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str,
    **fields: object,
) -> None:
    """记录稳定事件；stacklevel 跳过统一 helper，使前缀指向实际调用代码。"""
    logger.log(
        level,
        message,
        extra={"event": event, **fields},
        stacklevel=2,
    )
