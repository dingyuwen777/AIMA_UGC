"""Worker 进程正式装配入口。

业务 Job Handler 在对应模块注册；本入口只暴露 Stage 4 的 Platform Runtime、Job Worker
和 Reaper 组装能力，不复制业务处理循环。
"""

from aima_ugc.bootstrap.worker import create_job_reaper, create_job_worker, create_worker_runtime

__all__ = ["create_job_reaper", "create_job_worker", "create_worker_runtime"]
