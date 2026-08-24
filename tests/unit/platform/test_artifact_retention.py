from datetime import UTC, datetime, timedelta

from aima_ugc.adapters.storage.local import LocalArtifactStore
from aima_ugc.platform.storage.retention import (
    EXPORT_RETENTION,
    IMPORT_SOURCE_RETENTION,
    ORPHAN_RETENTION,
    PROVIDER_RAW_RETENTION,
    initial_artifact_expiry,
    import_source_expiry,
)


def test_artifact_retention_policy_matches_approved_windows() -> None:
    observed_at = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)

    assert PROVIDER_RAW_RETENTION == timedelta(days=30)
    assert IMPORT_SOURCE_RETENTION == timedelta(days=7)
    assert EXPORT_RETENTION == timedelta(days=7)
    assert ORPHAN_RETENTION == timedelta(days=1)
    assert initial_artifact_expiry("provider-raw", observed_at) == observed_at + timedelta(days=30)
    assert initial_artifact_expiry("content-export.xlsx", observed_at) == observed_at + timedelta(days=7)
    assert initial_artifact_expiry("file-import.raw", observed_at) is None
    assert import_source_expiry(observed_at) == observed_at + timedelta(days=7)


def test_local_artifact_store_delete_is_idempotent(tmp_path) -> None:
    store = LocalArtifactStore(tmp_path / "artifacts")
    stored = store.put("content-export.xlsx/example.xlsx", b"xlsx")
    assert stored.byte_size == 4
    assert store.exists("content-export.xlsx/example.xlsx")

    store.delete("content-export.xlsx/example.xlsx")
    assert not store.exists("content-export.xlsx/example.xlsx")

    # Housekeeping 重试时物理文件可能已经被上一实例删除；重复删除必须保持成功。
    store.delete("content-export.xlsx/example.xlsx")
