"""一个命令准备并启动 AIMA_UGC 本地后端开发栈。"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import NAMESPACE_URL, uuid5

from local_runtime import (
    LOCAL_TIKHUB_SECRET_REF,
    LocalDevConfig,
    LocalDevError,
    RuntimePaths,
    build_runtime_environment,
    ensure_env_local,
    ensure_postgres_container,
    load_local_dev_config,
    prepare_cursor_secrets,
    prepare_runtime_directories,
    repository_root,
    runtime_paths,
)

_READY_URL = "http://127.0.0.1:8090/health/ready"
_LOCAL_TIKHUB_CONFIG_ID = uuid5(NAMESPACE_URL, "https://aima.local/provider/tikhub")


class ChildProcess(NamedTuple):
    name: str
    process: subprocess.Popen[bytes]


def main() -> int:
    parser = argparse.ArgumentParser(description="启动 AIMA_UGC 本地后端开发栈")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    root = repository_root()
    try:
        env_path, created = ensure_env_local(root)
        config = load_local_dev_config(env_path)
        if args.validate_only:
            print(f"Local dev config valid: {env_path}")
            return 0
        return _run(root=root, config=config, env_created=created, prepare_only=args.prepare_only)
    except LocalDevError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def _run(
    *,
    root: Path,
    config: LocalDevConfig,
    env_created: bool,
    prepare_only: bool,
) -> int:
    print("AIMA_UGC Local Backend")
    print("=" * 56)
    if env_created:
        print("[INFO] 已从 env.local.example 自动创建 env.local。")
    for key in config.unknown_keys:
        print(f"[WARN] env.local 中的 {key} 不是本地简化配置项，将由 dev launcher 忽略。")

    paths = runtime_paths(root)
    prepare_runtime_directories(paths)
    prepare_cursor_secrets(paths)
    print(f"[OK] Runtime directories: {paths.runtime}")
    print("[OK] Cursor secrets")

    ensure_postgres_container(paths)
    print("[OK] PostgreSQL 18.4: aima-ugc-postgres-dev @ 127.0.0.1:5432")

    runtime_environment = build_runtime_environment(paths=paths, config=config)
    _run_migration(root=root, environment=runtime_environment)
    print("[OK] Database migration: head")

    tikhub_available = _provision_tikhub(
        root=root,
        paths=paths,
        environment=runtime_environment,
        config=config,
    )
    _print_feature_status(config=config, tikhub_available=tikhub_available)

    if prepare_only:
        print("[OK] Local backend preparation completed.")
        return 0

    children: list[ChildProcess] = []
    stop_requested = threading.Event()
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def request_stop(_signum: int, _frame: object) -> None:
        stop_requested.set()

    signal.signal(signal.SIGTERM, request_stop)
    try:
        children.append(
            _start_child(
                "Worker",
                [sys.executable, "-m", "aima_ugc.entrypoints.worker_main"],
                root=root,
                environment=runtime_environment,
            )
        )
        print("[OK] Worker started")

        if config.scheduler_enabled:
            children.append(
                _start_child(
                    "Scheduler",
                    [sys.executable, "-m", "aima_ugc.entrypoints.scheduler_main"],
                    root=root,
                    environment=runtime_environment,
                )
            )
            print("[OK] Scheduler started")
        else:
            print("[SKIP] Scheduler disabled for local development")

        children.append(
            _start_child(
                "API",
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "aima_ugc.entrypoints.api_main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8090",
                    "--reload",
                    "--reload-dir",
                    "backend/src",
                ],
                root=root,
                environment=runtime_environment,
            )
        )
        print("[OK] API process started")
        _wait_for_ready(children)
        print(f"[OK] /health/ready: {_READY_URL}")
        print("Backend is ready. Press Ctrl+C to stop API/Worker/Scheduler.")

        while not stop_requested.wait(0.5):
            for child in children:
                return_code = child.process.poll()
                if return_code is not None:
                    raise LocalDevError(
                        f"{child.name} 意外退出（exit={return_code}）；请查看上方输出和 .runtime/logs。"
                    )
    except KeyboardInterrupt:
        print("\n[INFO] Stopping local backend...")
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        for child in reversed(children):
            _stop_child(child)
    return 0


def _run_migration(*, root: Path, environment: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root,
        env=environment,
        check=False,
    )
    if result.returncode != 0:
        raise LocalDevError("Alembic Migration 失败；后端没有启动。")


def _provision_tikhub(
    *,
    root: Path,
    paths: RuntimePaths,
    environment: dict[str, str],
    config: LocalDevConfig,
) -> bool:
    """幂等维护仅属于本地开发的 TikHub Provider Config。"""

    from aima_ugc.adapters.persistence.postgres.system import PostgresProviderConfigRepository
    from aima_ugc.modules.system.models import ProviderConfig
    from aima_ugc.platform.config import load_settings
    from aima_ugc.platform.database import DatabaseRuntime

    runtime = DatabaseRuntime(load_settings(environment, base_dir=root))
    try:
        session = runtime.new_session()
        try:
            with session.begin():
                repository = PostgresProviderConfigRepository(session)
                current = repository.get(_LOCAL_TIKHUB_CONFIG_ID)
                enabled = config.tikhub_configured
                try:
                    desired = ProviderConfig(
                        id=_LOCAL_TIKHUB_CONFIG_ID,
                        provider="tikhub",
                        display_name="TikHub Local Dev",
                        base_url=config.tikhub_base_url,
                        secret_ref=LOCAL_TIKHUB_SECRET_REF,
                        enabled=enabled,
                    )
                except ValueError as exc:
                    if current is not None:
                        repository.update_settings(
                            current.id,
                            display_name=current.display_name,
                            base_url=current.base_url,
                            secret_ref=current.secret_ref,
                            enabled=False,
                        )
                    paths.tikhub_secret_file.unlink(missing_ok=True)
                    print(f"[WARN] TikHub 本地配置无效，已禁用：{exc}")
                    return False

                if current is None:
                    if enabled:
                        repository.create(desired)
                else:
                    repository.update_settings(
                        current.id,
                        display_name=desired.display_name,
                        base_url=desired.base_url,
                        secret_ref=desired.secret_ref,
                        enabled=desired.enabled,
                    )
                return enabled
        finally:
            session.close()
    finally:
        runtime.dispose()


def _print_feature_status(*, config: LocalDevConfig, tikhub_available: bool) -> None:
    print("\nLocal capabilities")
    print("- Excel Import: AVAILABLE")
    print("- Voice Plaza: AVAILABLE")
    print("- Excel Export: AVAILABLE")

    if tikhub_available:
        print(f"- TikHub: AVAILABLE ({config.tikhub_base_url})")
    else:
        print("- TikHub: NOT CONFIGURED")
        print("  [WARN] 如需真实采集，请在 env.local 填写 AIMA_TIKHUB_API_KEY 后重启后端。")

    if config.llm_configured:
        provider = config.llm_provider_name or "由 Base URL 自动识别"
        print(f"- AI Analysis: AVAILABLE ({provider} / {config.llm_model})")
    else:
        print("- AI Analysis: NOT CONFIGURED")
        if config.llm_partially_configured:
            print("  [WARN] LLM 配置不完整，本次不会把部分配置传给 Worker。")
        print(
            "  [WARN] 如需 AI 打标，请在 env.local 填写 AIMA_LLM_BASE_URL、"
            "AIMA_LLM_MODEL、AIMA_LLM_API_KEY 后重启后端。"
        )


def _start_child(
    name: str,
    command: list[str],
    *,
    root: Path,
    environment: dict[str, str],
) -> ChildProcess:
    kwargs: dict[str, object] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, cwd=root, env=environment, **kwargs)
    return ChildProcess(name=name, process=process)


def _wait_for_ready(children: list[ChildProcess], *, timeout_seconds: float = 45.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "API 尚未响应"
    while time.monotonic() < deadline:
        for child in children:
            return_code = child.process.poll()
            if return_code is not None:
                raise LocalDevError(f"{child.name} 在 readiness 前退出（exit={return_code}）")
        try:
            with urlopen(_READY_URL, timeout=1.5) as response:  # noqa: S310 - fixed localhost URL
                payload = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and payload.get("status") == "ok":
                    return
                last_error = f"status={response.status} payload={payload!r}"
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}"
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = type(exc).__name__
        time.sleep(0.4)
    raise LocalDevError(f"API 未在 {timeout_seconds:.0f}s 内 ready：{last_error}")


def _stop_child(child: ChildProcess) -> None:
    process = child.process
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass
    print(f"[STOP] {child.name}")


if __name__ == "__main__":
    raise SystemExit(main())
