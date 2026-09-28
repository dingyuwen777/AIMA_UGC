from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from aima_ugc.bootstrap import feishu_bitable_mirror as mirror_module
from aima_ugc.bootstrap.feishu_bitable_mirror import PostgresFeishuBitableMirrorService


class _Transaction:
    def __enter__(self) -> _Transaction:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _Session:
    def begin(self) -> _Transaction:
        return _Transaction()

    def close(self) -> None:
        return None


class _Database:
    def new_session(self) -> _Session:
        return _Session()


def test_worker_claims_one_mirror_before_processing_the_next(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    first = SimpleNamespace(id=uuid4())
    second = SimpleNamespace(id=uuid4())
    pending = [first, second]
    events: list[tuple[str, object]] = []

    def claim_due(self, *, worker_id: str, limit: int, lease_seconds: int):  # type: ignore[no-untyped-def]
        del self, worker_id, lease_seconds
        events.append(("claim", limit))
        if not pending:
            return ()
        return (pending.pop(0),)

    monkeypatch.setattr(
        mirror_module.PostgresFeishuBitableMirrorRepository,
        "claim_due",
        claim_due,
    )
    monkeypatch.setattr(
        mirror_module.FeishuConfig,
        "from_settings",
        lambda settings: SimpleNamespace(app_secret_file="mirror-secret"),
    )
    monkeypatch.setattr(
        mirror_module,
        "read_secret_file",
        lambda path, *, root: SimpleNamespace(get_secret_value=lambda: "secret"),
    )

    service = PostgresFeishuBitableMirrorService(
        SimpleNamespace(
            database=_Database(),
            settings=SimpleNamespace(external_secret_root=Path(".")),
        )
    )

    def sync_mirror(mirror, *, config, app_secret):  # type: ignore[no-untyped-def]
        del config, app_secret
        events.append(("sync", mirror.id))
        return 1, 0, 0

    monkeypatch.setattr(service, "_sync_mirror", sync_mirror)

    result = service.run_once(limit=2)

    assert result.scanned == 2
    assert result.succeeded == 2
    assert events == [
        ("claim", 1),
        ("sync", first.id),
        ("claim", 1),
        ("sync", second.id),
    ]
