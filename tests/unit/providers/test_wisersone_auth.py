"""WisersOne 登录态持久目录的行为验证。"""

import json
from pathlib import Path

import pytest
from aima_ugc.adapters.providers.wisersone.auth import (
    AuthBusyError,
    AuthStateError,
    atomic_write,
    auth_lock,
    prepare_auth,
)


def _seed(root: Path) -> None:
    root.mkdir()
    (root / "wisersone_state.json").write_text(
        json.dumps({"cookies": [], "origins": []}), encoding="utf-8"
    )
    (root / "wisersone_runtime.json").write_text(
        json.dumps({"home_url": "https://datacenter.wisersone.com/home/123", "home_id": "123"}),
        encoding="utf-8",
    )


def test_seed_once_and_preserve_refreshed_state(tmp_path: Path) -> None:
    seed, runtime = tmp_path / "seed", tmp_path / "runtime"
    _seed(seed)
    prepare_auth(runtime, seed=seed)
    refreshed = '{"cookies": [{"name": "refreshed"}], "origins": []}'
    (runtime / "wisersone_state.json").write_text(refreshed, encoding="utf-8")
    prepare_auth(runtime, seed=seed)
    assert (runtime / "wisersone_state.json").read_text(encoding="utf-8") == refreshed


def test_corrupt_runtime_is_not_overwritten(tmp_path: Path) -> None:
    seed, runtime = tmp_path / "seed", tmp_path / "runtime"
    _seed(seed)
    runtime.mkdir()
    (runtime / "wisersone_state.json").write_text("broken", encoding="utf-8")
    with pytest.raises(AuthStateError):
        prepare_auth(runtime, seed=seed)
    assert (runtime / "wisersone_state.json").read_text(encoding="utf-8") == "broken"


def test_auth_lock_blocks_other_process_and_is_released_on_crash(tmp_path: Path) -> None:
    import subprocess
    import sys

    child = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            "import sys,time; from pathlib import Path; "
            "from aima_ugc.adapters.providers.wisersone.auth import auth_lock; "
            "lock=auth_lock(Path(sys.argv[1])); lock.__enter__(); "
            "print('locked',flush=True); time.sleep(60)",
            str(tmp_path),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None and child.stdout.readline().strip() == "locked"
        with pytest.raises(AuthBusyError), auth_lock(tmp_path, timeout=0.1):
            pytest.fail("另一个进程持锁时不能进入")
    finally:
        child.terminate()
        child.wait(timeout=5)
    with auth_lock(tmp_path, timeout=0.1):
        assert (tmp_path / ".auth.lock").exists()


def test_failed_atomic_replace_keeps_original_and_removes_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    destination = tmp_path / "state.json"
    destination.write_bytes(b"original")

    def fail(*args):
        raise OSError("test replace failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        atomic_write(destination, b"refreshed")
    assert destination.read_bytes() == b"original"
    assert not (tmp_path / "state.json.tmp").exists()
