from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

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
    assert docker_calls == [("stop", local_runtime.POSTGRES_CONTAINER)]
    assert all("rm" not in arguments for arguments in docker_calls)
    assert all("volume" not in arguments for arguments in docker_calls)


def test_stop_postgres_container_reports_missing_or_already_stopped_without_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(local_runtime.shutil, "which", lambda _name: "docker")
    monkeypatch.setattr(local_runtime, "_docker_inspect", lambda *_args: None)

    assert local_runtime.stop_postgres_container() == "missing"

    monkeypatch.setattr(local_runtime, "_docker_inspect", lambda *_args: "{}")
    monkeypatch.setattr(local_runtime, "_docker_field", lambda *_args: "false")
    monkeypatch.setattr(
        local_runtime,
        "_run_docker",
        lambda *_args, **_kwargs: pytest.fail("stopped container must not be stopped again"),
    )

    assert local_runtime.stop_postgres_container() == "already_stopped"
