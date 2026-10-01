"""selected 自动车型清理只消费创建时冻结的身份范围。"""

from uuid import uuid4

import pytest
from aima_ugc.adapters.persistence.postgres.brand_vehicle import PostgresBrandVehicleRepository
from aima_ugc.adapters.persistence.postgres.vehicles import PostgresVehicleCatalogRepository
from aima_ugc.bootstrap.administration_http import PostgresAdministrationHttpService
from aima_ugc.contracts.administration import (
    VehicleModelCreateRequest,
    VehicleModelMergeRequest,
    VehicleModelUpdateRequest,
)
from aima_ugc.modules.content.tables import contents_table
from aima_ugc.modules.vehicles.models import ContentVehicleEvidence
from aima_ugc.modules.vehicles.tables import content_vehicle_evidence_table
from aima_ugc.platform.time import beijing_now
from sqlalchemy import select

from tests.integration.ingestion.test_brand_first_replay import (
    _client,
)
from tests.integration.ingestion.test_brand_first_replay import (
    runtime as runtime,
)
from tests.integration.ingestion.test_canonical_replay_worker import (
    _create_brand,
    _import_canonical,
    _principal,
)


@pytest.mark.parametrize("retired_status", ["deprecated", "merged"])
def test_selected_cleanup_freezes_reparented_and_retired_ids_and_preserves_outside_and_manual(
    runtime,
    retired_status: str,
) -> None:
    client = _client(runtime)
    a = _create_brand(runtime, alias="冻结品牌A")
    b = _create_brand(runtime, alias="范围外品牌B")
    administration = PostgresAdministrationHttpService(runtime)

    def create_model(brand_id, suffix):
        return administration.create_vehicle_model(
            VehicleModelCreateRequest(display_name=suffix, brand_id=brand_id, aliases=(suffix,)),
            principal=_principal(),
            request_id=f"frozen-create-{suffix}",
        ).id

    inside = create_model(a, "范围内车型")
    outside = create_model(b, "范围外车型")
    retired = create_model(b if retired_status == "merged" else a, "旧车型")
    if retired_status == "merged":
        administration.merge_vehicle_model(
            retired,
            VehicleModelMergeRequest(target_vehicle_model_id=inside),
            principal=_principal(),
            request_id="frozen-merge",
        )
    else:
        administration.update_vehicle_model(
            retired,
            VehicleModelUpdateRequest(status="deprecated"),
            principal=_principal(),
            request_id="frozen-deprecate",
        )
    _import_canonical(
        client,
        runtime,
        filename="frozen-scope.xlsx",
        rows=(("frozen-scope", "冻结品牌A 无车型"),),
        brand_ids=(a,),
        expected_rows_ingested=1,
    )
    with runtime.database.new_session() as session, session.begin():
        content_id = session.scalar(select(contents_table.c.id))
        snapshot = PostgresBrandVehicleRepository(session).snapshot(brand_ids=(a,))
        owner = PostgresVehicleCatalogRepository(session)
        for model_id in (inside, outside, retired):
            owner.append_evidence(
                ContentVehicleEvidence(
                    id=uuid4(),
                    content_id=content_id,
                    content_version=1,
                    vehicle_model_id=model_id,
                    source="alias_match",
                    matched_text="旧文本匹配",
                    source_field="title",
                    catalog_version=snapshot.catalog_version,
                    confidence=None,
                    is_manual_locked=False,
                    is_active=True,
                    created_at=beijing_now(),
                )
            )
        owner.append_evidence(
            ContentVehicleEvidence(
                id=uuid4(),
                content_id=content_id,
                content_version=1,
                vehicle_model_id=inside,
                source="manual_review",
                matched_text=None,
                source_field=None,
                catalog_version=snapshot.catalog_version,
                confidence=None,
                is_manual_locked=True,
                is_active=True,
                created_at=beijing_now(),
            )
        )
    administration.update_vehicle_model(
        inside,
        VehicleModelUpdateRequest(brand_id=b),
        principal=_principal(),
        request_id="frozen-move-a-to-b",
    )
    administration.update_vehicle_model(
        outside,
        VehicleModelUpdateRequest(brand_id=a),
        principal=_principal(),
        request_id="frozen-move-b-to-a",
    )
    with runtime.database.new_session() as session, session.begin():
        PostgresVehicleCatalogRepository(session).converge_automatic_alias_evidence_for_replay(
            entries=((content_id, 1, ()),),
            source_pairs=((content_id, 1),),
            replace_existing=False,
            include_import_text_matches=True,
            replace_vehicle_model_ids=snapshot.automatic_evidence_vehicle_ids,
        )
    with runtime.database.engine.connect() as connection:
        rows = connection.execute(select(content_vehicle_evidence_table)).mappings().all()
        active_auto = {
            row["vehicle_model_id"]
            for row in rows
            if row["source"] == "alias_match" and row["is_active"]
        }
        assert active_auto == {outside}
        assert all(row["is_active"] for row in rows if row["source"] == "manual_review")
