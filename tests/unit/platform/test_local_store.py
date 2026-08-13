import hashlib

import pytest
from aima_ugc.adapters.storage.local import LocalArtifactStore


def test_local_store_writes_atomically_and_is_immutable(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    payload = b"immutable artifact bytes"

    result = store.put("raw/item-1", payload)

    assert result.sha256 == hashlib.sha256(payload).hexdigest()
    assert result.byte_size == len(payload)
    assert store.exists("raw/item-1") is True
    assert store.read("raw/item-1") == payload

    with pytest.raises(FileExistsError):
        store.put("raw/item-1", b"replacement")
    assert store.read("raw/item-1") == payload


@pytest.mark.parametrize(
    "storage_key",
    ["../escape", "/absolute", "raw/../escape", r"raw\escape", "raw//escape"],
)
def test_local_store_rejects_unsafe_storage_keys(tmp_path, storage_key: str) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")

    with pytest.raises(ValueError):
        store.put(storage_key, b"data")


def test_local_store_rejects_parent_symlink_escape(tmp_path) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    store = LocalArtifactStore(root)

    with pytest.raises(ValueError):
        store.put("link/escape", b"data")

    assert not (outside / "escape").exists()
