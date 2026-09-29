"""飞书多维表双向镜像常驻进程。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from aima_ugc.bootstrap.feishu_bitable_mirror import (
    PostgresFeishuBitableMirrorService,
)
from aima_ugc.bootstrap.runtime import PlatformRuntime, create_platform_runtime
from aima_ugc.platform.logging import log_event

_POLL_SECONDS = 1.0


def run_mirror_loop(
    runtime: PlatformRuntime,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    service = PostgresFeishuBitableMirrorService(runtime)
    while True:
        service.run_once()
        sleep(_POLL_SECONDS)


def main() -> None:
    runtime = create_platform_runtime("feishu-bitable-mirror")
    log_event(
        runtime.logger,
        logging.INFO,
        "feishu.bitable_mirror.started",
        "飞书多维表双向镜像服务已启动。",
    )
    try:
        run_mirror_loop(runtime)
    except KeyboardInterrupt:
        log_event(
            runtime.logger,
            logging.INFO,
            "feishu.bitable_mirror.stopped",
            "飞书多维表双向镜像服务已停止。",
        )
    finally:
        runtime.close()


__all__ = ["main", "run_mirror_loop"]


if __name__ == "__main__":
    main()
