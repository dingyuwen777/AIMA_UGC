"""WisersOne 登录态持久目录的行为验证。"""

import json
from pathlib import Path

import pytest

from aima_ugc.adapters.providers.wisersone.auth import AuthStateError, prepare_auth


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
