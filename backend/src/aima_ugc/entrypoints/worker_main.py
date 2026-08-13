"""Worker 进程入口模块；业务 Job Runtime 在 Stage 4 实现。"""

from aima_ugc.bootstrap.worker import create_worker_runtime

__all__ = ["create_worker_runtime"]
