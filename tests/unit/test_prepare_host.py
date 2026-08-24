from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "deploy"))

import prepare_host as host_preparation  # noqa: E402


def test_runtime_bind_compatible_relaxes_only_data_and_logs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    directory_calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(host_preparation.os, "geteuid", lambda: 0)
    monkeypatch.setattr(host_preparation, "_guard_postgres_password_recovery", lambda _root: None)
    monkeypatch.setattr(host_preparation, "_secure_secret", lambda *_args, **_kwargs: None)

    def capture_directory(
        _root: Path,
        spec: host_preparation.DirectorySpec,
        *,
        check_only: bool,
        strict_permissions: bool = True,
    ) -> None:
        del check_only
        directory_calls.append((spec.relative, strict_permissions))

    monkeypatch.setattr(host_preparation, "_ensure_directory", capture_directory)

    host_preparation.prepare_host(
        tmp_path.resolve(),
        check_only=False,
        runtime_only=True,
        runtime_bind_compatible=True,
    )

    relaxed = {
        relative
        for relative, strict_permissions in directory_calls
        if not strict_permissions
    }
    assert relaxed == {"runtime/data", "runtime/logs"}
    assert all(
        strict_permissions
        for relative, strict_permissions in directory_calls
        if relative not in relaxed
    )


def test_non_strict_directory_keeps_structural_checks_but_tolerates_posix_translation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    spec = host_preparation.DirectorySpec("runtime/data", 10001, 10001, 0o750)

    def unsupported_permission_change(*_args: object, **_kwargs: object) -> None:
        raise OSError("filesystem does not expose exact POSIX ownership")

    monkeypatch.setattr(host_preparation.os, "chown", unsupported_permission_change)
    monkeypatch.setattr(host_preparation.os, "chmod", unsupported_permission_change)

    host_preparation._ensure_directory(
        tmp_path,
        spec,
        check_only=False,
        strict_permissions=False,
    )

    assert (tmp_path / "runtime/data").is_dir()


def test_default_runtime_preparation_keeps_all_directory_permissions_strict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    directory_calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(host_preparation.os, "geteuid", lambda: 0)
    monkeypatch.setattr(host_preparation, "_guard_postgres_password_recovery", lambda _root: None)
    monkeypatch.setattr(host_preparation, "_secure_secret", lambda *_args, **_kwargs: None)

    def capture_directory(
        _root: Path,
        spec: host_preparation.DirectorySpec,
        *,
        check_only: bool,
        strict_permissions: bool = True,
    ) -> None:
        del check_only
        directory_calls.append((spec.relative, strict_permissions))

    monkeypatch.setattr(host_preparation, "_ensure_directory", capture_directory)

    host_preparation.prepare_host(
        tmp_path.resolve(),
        check_only=False,
        runtime_only=True,
    )

    assert directory_calls
    assert all(strict_permissions for _, strict_permissions in directory_calls)
