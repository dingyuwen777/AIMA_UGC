from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import local_runtime  # noqa: E402

import backend  # noqa: E402


class _ReadyHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        payload = json.dumps({"status": "ok"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def test_stop_postgres_container_stops_running_container_without_removing_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docker_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(local_runtime.shutil, "which", lambda _name: "docker")
    monkeypatch.setattr(local_runtime, "_docker_inspect", lambda *_args: "{}")
    monkeypatch.setattr(local_runtime, "_docker_field", lambda *_args: "true")

    def fake_run_docker(
        _docker: str,
        arguments: tuple[str, ...],
        *,
        failure: str,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del failure, environment
        docker_calls.append(arguments)
        return subprocess.CompletedProcess(["docker", *arguments], 0, "", "")

    monkeypatch.setattr(local_runtime, "_run_docker", fake_run_docker)

    status = local_runtime.stop_postgres_container()

    assert status == "stopped"
    assert ("stop", local_runtime.POSTGRES_CONTAINER) in docker_calls
    assert all(arguments[0] != "rm" for arguments in docker_calls)
    assert all(arguments[0] != "volume" for arguments in docker_calls)


def test_stop_postgres_container_reports_missing_or_already_stopped_without_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docker_calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(local_runtime.shutil, "which", lambda _name: "docker")

    def fake_run_docker(
        _docker: str,
        arguments: tuple[str, ...],
        *,
        failure: str,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del failure, environment
        docker_calls.append(arguments)
        return subprocess.CompletedProcess(["docker", *arguments], 0, "", "")

    monkeypatch.setattr(local_runtime, "_run_docker", fake_run_docker)
    monkeypatch.setattr(local_runtime, "_docker_inspect", lambda *_args: None)

    assert local_runtime.stop_postgres_container() == "missing"
    assert not any(arguments[0] == "stop" for arguments in docker_calls)

    docker_calls.clear()
    monkeypatch.setattr(local_runtime, "_docker_inspect", lambda *_args: "{}")
    monkeypatch.setattr(local_runtime, "_docker_field", lambda *_args: "false")

    assert local_runtime.stop_postgres_container() == "already_stopped"
    assert not any(arguments[0] == "stop" for arguments in docker_calls)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("stopped", "[STOP] PostgreSQL Docker container stopped: aima-ugc-postgres-dev"),
        (
            "already_stopped",
            "[SKIP] PostgreSQL Docker container already stopped: aima-ugc-postgres-dev",
        ),
        ("missing", "[SKIP] PostgreSQL Docker container not found: aima-ugc-postgres-dev"),
    ],
)
def test_backend_postgres_cleanup_logs_exact_container_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    expected: str,
) -> None:
    monkeypatch.setattr(backend, "stop_postgres_container", lambda: status)

    backend._stop_postgres_for_backend()

    assert expected in capsys.readouterr().out


def test_backend_ctrl_c_stops_children_then_postgres(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """后端中断时必须先停子进程，再停开发用 PostgreSQL。"""

    cleanup_order: list[str] = []
    config = local_runtime.LocalDevConfig(
        tikhub_base_url="https://api.tikhub.io",
        tikhub_api_key=None,
        llm_base_url=None,
        llm_provider_name=None,
        llm_model=None,
        llm_api_key=None,
        historical_import_root=None,
        scheduler_enabled=False,
        unknown_keys=(),
    )

    monkeypatch.setattr(backend, "prepare_runtime_directories", lambda _paths: None)
    monkeypatch.setattr(backend, "prepare_cursor_secrets", lambda _paths: None)
    monkeypatch.setattr(backend, "ensure_postgres_container", lambda _paths: None)
    monkeypatch.setattr(backend, "build_runtime_environment", lambda **_kwargs: {})
    monkeypatch.setattr(backend, "_run_migration", lambda **_kwargs: None)
    monkeypatch.setattr(backend, "_provision_tikhub", lambda **_kwargs: False)
    monkeypatch.setattr(backend, "_print_feature_status", lambda **_kwargs: None)
    monkeypatch.setattr(
        backend,
        "_start_child",
        lambda name, *_args, **_kwargs: backend.ChildProcess(name, object()),
    )
    monkeypatch.setattr(
        backend,
        "_wait_for_ready",
        lambda _children: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(
        backend,
        "_stop_child",
        lambda child: cleanup_order.append(child.name),
    )
    monkeypatch.setattr(
        backend,
        "_stop_postgres_for_backend",
        lambda: cleanup_order.append("PostgreSQL"),
    )

    assert backend._run(root=tmp_path, config=config, env_created=False, prepare_only=False) == 0
    assert cleanup_order == ["API", "Worker", "PostgreSQL"]


def test_backend_readiness_does_not_initialize_https_key_logging(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ReadyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        backend,
        "_READY_URL",
        f"http://127.0.0.1:{server.server_port}/health/ready",
    )
    monkeypatch.setenv("SSLKEYLOGFILE", str(tmp_path))
    try:
        backend._wait_for_ready([], timeout_seconds=2)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
