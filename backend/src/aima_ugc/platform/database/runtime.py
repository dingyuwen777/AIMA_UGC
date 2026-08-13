"""同步 SQLAlchemy / psycopg 数据库运行时。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from aima_ugc.platform.config import PlatformSettings
from aima_ugc.platform.security import read_secret_file

SecretReader = Callable[[Path], SecretStr]


class DatabaseRuntime:
    """惰性创建 PostgreSQL Engine，禁止自动建表或自动 Migration。"""

    def __init__(
        self,
        settings: PlatformSettings,
        *,
        secret_reader: SecretReader = read_secret_file,
    ) -> None:
        self._settings = settings
        self._secret_reader = secret_reader
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def _ensure_engine(self) -> Engine:
        if self._engine is None:
            password = self._secret_reader(self._settings.postgres_password_file).get_secret_value()
            url = URL.create(
                drivername="postgresql+psycopg",
                username=self._settings.db_user,
                password=password,
                host=self._settings.db_host,
                port=self._settings.db_port,
                database=self._settings.db_name,
            )
            self._engine = create_engine(
                url,
                pool_pre_ping=True,
                connect_args={
                    "connect_timeout": self._settings.db_connect_timeout_seconds,
                },
            )
        return self._engine

    def ping(self) -> bool:
        """执行真实 `SELECT 1`，不自动重试或修改 Schema。"""
        with self._ensure_engine().connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
        return int(result) == 1

    def new_session(self) -> Session:
        """创建同步 Session，供后续 Repository/Unit of Work 使用。"""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self._ensure_engine(),
                class_=Session,
                expire_on_commit=False,
            )
        return self._session_factory()

    def dispose(self) -> None:
        """释放连接池；未创建 Engine 时为空操作。"""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
