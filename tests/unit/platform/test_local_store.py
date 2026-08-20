import hashlib
import os
import subprocess
from io import BytesIO

import pytest
from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.platform.storage import ArtifactSizeLimitError


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


def test_local_store_does_not_overwrite_if_publish_races(tmp_path, monkeypatch) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    real_link = os.link

    def publish_competitor_then_link(source, destination) -> None:
        destination.write_bytes(b"competing immutable value")
        real_link(source, destination)

    monkeypatch.setattr(os, "link", publish_competitor_then_link)

    with pytest.raises(FileExistsError):
        store.put("raw/race", b"losing value")

    assert store.read("raw/race") == b"competing immutable value"


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
    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        if os.name != "nt" or exc.winerror != 1314:
            raise
        # 未开启开发者模式的 Windows 普通账户不能创建 symlink；目录 Junction
        # 同样能验证父目录重解析点不能逃逸 Artifact 根目录。
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            pytest.skip("当前 Windows 环境既不能创建 symlink，也不能创建目录 Junction")
    store = LocalArtifactStore(root)

    with pytest.raises(ValueError):
        store.put("link/escape", b"data")

    assert not (outside / "escape").exists()


def test_local_store_streams_and_enforces_actual_byte_limit(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")

    stored = store.put_stream(
        "file-import/raw.xlsx",
        BytesIO(b"streamed-xlsx"),
        max_bytes=20,
    )
    copied = BytesIO()
    copied_summary = store.copy_to("file-import/raw.xlsx", copied)

    assert stored.byte_size == copied_summary.byte_size == len(b"streamed-xlsx")
    assert stored.sha256 == copied_summary.sha256
    assert copied.getvalue() == b"streamed-xlsx"

    with pytest.raises(ArtifactSizeLimitError):
        store.put_stream("file-import/too-large.xlsx", BytesIO(b"12345"), max_bytes=4)
    assert store.exists("file-import/too-large.xlsx") is False
