"""为 Stage 8F Full-stack Acceptance 持续驱动正式 PostgreSQL Job Worker。"""

from __future__ import annotations

import time

from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)


def main() -> int:
    runtime = create_worker_runtime()
    worker = create_job_worker(
        runtime=runtime,
        registry=create_collection_job_registry(runtime=runtime),
        worker_id="stage8f-fullstack-worker",
        lease_seconds=120,
        retry_delay_seconds=0,
    )
    try:
        while True:
            if not worker.run_once():
                time.sleep(0.1)
    except KeyboardInterrupt:
        return 0
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
