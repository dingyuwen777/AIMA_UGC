from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import backend  # noqa: E402
import local_runtime  # noqa: E402


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
