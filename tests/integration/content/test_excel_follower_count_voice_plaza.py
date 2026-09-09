"""Excel 作者粉丝数进入 PostgreSQL 后的声音广场读取与排序回归。"""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from aima_ugc.bootstrap.api import create_app
from aima_ugc.bootstrap.content_http import PostgresContentHttpService
from aima_ugc.bootstrap.import_http import PostgresImportHttpService
from aima_ugc.bootstrap.worker import (
    create_collection_job_registry,
    create_job_worker,
    create_worker_runtime,
)
from aima_ugc.contracts.http import ContentListQuery
from aima_ugc.modules.content.tables import (
    accounts_table,
    content_versions_table,
    contents_table,
)
from aima_ugc.platform.config import load_settings
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import insert, select, update


def _follower_workbook() -> bytes:
    """构造包含粉丝数、零值和缺失值的正式 Excel Import 输入。"""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "文章"
    sheet.append(
        [
            "媒体名称（中文）",
            "标题",
            "内文",
            "作者",
            "粉丝数",
            "出版日期",
            "原文链接",
        ]
    )
    for index, follower_count in enumerate((12_000, 0, None), start=1):
        sheet.append(
            [
                "小红书",
                f"爱玛粉丝排序{index}",
                "爱玛真实体验",
                f"作者{index}",
                follower_count,
                f"2026-09-0{index} 10:00:00",
                f"https://www.xiaohongshu.com/explore/excel-fans-{index}",
            ]
        )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _import_workbook(client: TestClient) -> None:
    """通过正式 HTTP Import 与冻结词包配置提交测试 Excel。"""

    pack = client.post(
        "/api/v1/keyword-packs",
        json={"name": f"Excel 粉丝数 {uuid4()}"},
    )
    assert pack.status_code == 201
    keyword = client.post(
        f"/api/v1/keyword-packs/{pack.json()['id']}/keywords",
        json={"text": "爱玛", "priority": 10},
    )
    assert keyword.status_code == 201
    uploaded = client.post(
        "/api/v1/import-batches",
        files=[
            (
                "file",
                (
                    "followers.xlsx",
                    _follower_workbook(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            ),
            ("keyword_pack_ids", (None, pack.json()["id"])),
        ],
    )
    assert uploaded.status_code == 202


def test_excel_follower_count_is_persisted_visible_sortable_and_account_current_wins(
    tmp_path: Path,
) -> None:
    """Excel 快照要可展示/排序，后续稳定账号 Current 仍拥有更高读取优先级。"""

    settings = load_settings().model_copy(
        update={"data_dir": tmp_path / "data", "log_dir": tmp_path / "logs"}
    )
    runtime = create_worker_runtime(settings=settings)
    try:
        with runtime.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "TRUNCATE TABLE jobs, artifacts, keyword_packs, accounts RESTART IDENTITY CASCADE"
            )
        client = TestClient(create_app(import_service=PostgresImportHttpService(runtime)))
        _import_workbook(client)
        worker = create_job_worker(
            runtime=runtime,
            registry=create_collection_job_registry(runtime=runtime),
            worker_id="excel-follower-count-test",
            lease_seconds=120,
            retry_delay_seconds=0,
        )
        assert worker.run_once() is True

        with runtime.database.engine.begin() as connection:
            snapshots = dict(
                connection.execute(
                    select(contents_table.c.external_content_id, content_versions_table.c.author_snapshot)
                    .join(
                        content_versions_table,
                        (content_versions_table.c.content_id == contents_table.c.id)
                        & (
                            content_versions_table.c.version_no
                            == contents_table.c.current_version
                        ),
                    )
                    .order_by(contents_table.c.external_content_id)
                ).all()
            )
        assert snapshots["excel-fans-1"]["follower_count"] == 12_000
        assert snapshots["excel-fans-2"]["follower_count"] == 0
        assert snapshots["excel-fans-3"].get("follower_count") is None

        service = PostgresContentHttpService(
            runtime,
            cursor_signing_secret=b"excel-follower-count-test-key-32-bytes-minimum",
        )
        descending = service.list_contents(
            ContentListQuery(sort_by="follower_count", sort_direction="desc", limit=10)
        )
        assert [
            (item.external_content_id, item.author_follower_count) for item in descending.items
        ] == [
            ("excel-fans-1", 12_000),
            ("excel-fans-2", 0),
            ("excel-fans-3", None),
        ]
        ascending = service.list_contents(
            ContentListQuery(sort_by="follower_count", sort_direction="asc", limit=10)
        )
        assert [
            (item.external_content_id, item.author_follower_count) for item in ascending.items
        ] == [
            ("excel-fans-2", 0),
            ("excel-fans-1", 12_000),
            ("excel-fans-3", None),
        ]

        now = datetime(2026, 9, 9, tzinfo=UTC)
        with runtime.database.engine.begin() as connection:
            content_id = connection.execute(
                select(contents_table.c.id).where(
                    contents_table.c.external_content_id == "excel-fans-2"
                )
            ).scalar_one()
            account_id = uuid4()
            connection.execute(
                insert(accounts_table).values(
                    id=account_id,
                    platform="xiaohongshu",
                    external_account_id="stable-account-2",
                    current_follower_count=30_000,
                    first_seen_at=now,
                    last_seen_at=now,
                    updated_at=now,
                )
            )
            connection.execute(
                update(contents_table)
                .where(contents_table.c.id == content_id)
                .values(author_account_id=account_id)
            )

        enriched = service.list_contents(
            ContentListQuery(sort_by="follower_count", sort_direction="desc", limit=10)
        )
        assert [
            (item.external_content_id, item.author_follower_count) for item in enriched.items
        ][:2] == [
            ("excel-fans-2", 30_000),
            ("excel-fans-1", 12_000),
        ]
    finally:
        runtime.close()
