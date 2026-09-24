"""使用同一份外部 env 有序停止当前 Release 的 Compose 服务。"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def stop(*, compose_file: Path, env_file: Path, timeout_seconds: int = 60) -> None:
    """停止服务但保留容器、网络、数据库 volume 和业务文件。"""

    if timeout_seconds < 1:
        raise ValueError("停止超时必须大于 0 秒")
    compose_file = compose_file.resolve(strict=True)
    env_file = env_file.resolve(strict=True)
    override = env_file.with_name("compose.auto.yaml")
    command = ["docker", "compose", "--env-file", str(env_file), "-f", str(compose_file)]
    windows_overlay = compose_file.with_name("compose.windows.yaml")
    if os.name == "nt" and windows_overlay.is_file():
        command.extend(("-f", str(windows_overlay)))
    if override.is_file():
        command.extend(("-f", str(override)))
    subprocess.run(
        [*command, "stop", "--timeout", str(timeout_seconds)],
        check=True,
        cwd=compose_file.parent,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="停止离线 Compose；保留全部持久数据")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--compose-file", type=Path, default=_default_compose_file())
    parser.add_argument("--timeout", type=int, default=60)
    arguments = parser.parse_args()
    stop(
        compose_file=arguments.compose_file,
        env_file=arguments.env_file,
        timeout_seconds=arguments.timeout,
    )
    return 0


def _default_compose_file() -> Path:
    script = Path(__file__).resolve()
    bundled = script.parent / "compose.yaml"
    return bundled if bundled.is_file() else script.parents[2] / "compose.yaml"


if __name__ == "__main__":
    raise SystemExit(main())
