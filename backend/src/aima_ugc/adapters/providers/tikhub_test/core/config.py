"""TikHub 本地测试/调试配置；真实 Secret 只从 tikhub_test 根目录 .env 读取。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import SecretStr

from aima_ugc.adapters.providers.tikhub.transport import (
    DEFAULT_TIKHUB_BASE_URL,
    TikHubHttpTransport,
)

_DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


@dataclass(frozen=True, slots=True)
class TikHubTestConfig:
    """无数据库调试所需的最小 Provider 配置。"""

    base_url: str
    api_key: SecretStr = field(repr=False)
    timeout_seconds: float = 45.0

    def __post_init__(self) -> None:
        if not self.api_key.get_secret_value().strip():
            raise ValueError("TIKHUB_API_KEY 不能为空")
        if self.timeout_seconds <= 0:
            raise ValueError("TIKHUB_TIMEOUT_SECONDS 必须大于 0")
        # 复用生产 Transport 的 Origin 校验，避免调试入口绕过出站安全边界。
        transport = TikHubHttpTransport(
            base_url=self.base_url,
            timeout_seconds=self.timeout_seconds,
        )
        transport.close()

    @classmethod
    def load(cls, env_file: str | Path | None = None) -> TikHubTestConfig:
        """从显式或 tikhub_test 根目录 `.env` 文件加载，不读取进程环境。"""
        path = Path(env_file) if env_file is not None else _DEFAULT_ENV_FILE
        values = _read_env(path)
        raw_key = values.get("TIKHUB_API_KEY", "").strip()
        if not raw_key:
            raise ValueError(f"TIKHUB_API_KEY 未配置：{path}")

        base_url = values.get("TIKHUB_BASE_URL", DEFAULT_TIKHUB_BASE_URL).strip()
        raw_timeout = values.get("TIKHUB_TIMEOUT_SECONDS", "45").strip()
        try:
            timeout_seconds = float(raw_timeout)
        except ValueError as exc:
            raise ValueError("TIKHUB_TIMEOUT_SECONDS 必须为数字") from exc

        return cls(
            base_url=base_url,
            api_key=SecretStr(raw_key),
            timeout_seconds=timeout_seconds,
        )


def _read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ValueError(f"TikHub 调试配置文件不存在：{path}")

    values: dict[str, str] = {}
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"TikHub 调试 .env 第 {line_no} 行缺少 '='")
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError(f"TikHub 调试 .env 第 {line_no} 行变量名为空")
        values[normalized_key] = _strip_quotes(value.strip())
    return values


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


__all__ = ["TikHubTestConfig"]
