"""FastAPI 进程入口。"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """创建 API 应用。"""
    return FastAPI(title="AIMA_UGC API", version="0.1.0")


app = create_app()
