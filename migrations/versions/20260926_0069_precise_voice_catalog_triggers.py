"""只在目录的投影依赖字段变化时刷新声音广场维度。

Revision ID: 20260926_0069
Revises: 20260926_0068
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0069"
down_revision: str | Sequence[str] | None = "20260926_0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_catalog_refresh_function(*, precise: bool) -> None:
    """保留语句级同步刷新，只改变哪些目录更新会枚举关联 Content。"""

    old_ids = "SELECT id FROM new_rows UNION SELECT id FROM old_rows"
    brand_ids = (
        "SELECT COALESCE(new_rows.id, old_rows.id) AS id "
        "FROM old_rows FULL JOIN new_rows ON old_rows.id = new_rows.id "
        "WHERE old_rows.id IS NULL OR new_rows.id IS NULL "
        "OR old_rows.role IS DISTINCT FROM new_rows.role"
        if precise
        else old_ids
    )
    model_ids = (
        "SELECT COALESCE(new_rows.id, old_rows.id) AS id "
        "FROM old_rows FULL JOIN new_rows ON old_rows.id = new_rows.id "
        "WHERE old_rows.id IS NULL OR new_rows.id IS NULL "
        "OR old_rows.merged_into_id IS DISTINCT FROM new_rows.merged_into_id"
        if precise
        else old_ids
    )
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION refresh_voice_plaza_projection_from_catalog_statement()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                changed_catalog_ids uuid[];
                affected_content_ids uuid[];
            BEGIN
                -- Transition table 按 ID 对齐；别名 touch、版本和显示名不影响本投影。
                IF TG_TABLE_NAME = 'vehicle_brands' THEN
                    SELECT array_agg(changed.id) INTO changed_catalog_ids
                    FROM ({brand_ids}) AS changed;
                ELSE
                    SELECT array_agg(changed.id) INTO changed_catalog_ids
                    FROM ({model_ids}) AS changed;
                END IF;

                IF COALESCE(cardinality(changed_catalog_ids), 0) = 0 THEN
                    RETURN NULL;
                END IF;

                IF TG_TABLE_NAME = 'vehicle_brands' THEN
                    SELECT array_agg(DISTINCT content_id) INTO affected_content_ids
                    FROM (
                        SELECT evidence.content_id
                        FROM content_brand_evidence AS evidence
                        WHERE evidence.brand_id = ANY(changed_catalog_ids)
                        UNION
                        SELECT evidence.content_id
                        FROM content_vehicle_evidence AS evidence
                        JOIN vehicle_models AS model ON model.id = evidence.vehicle_model_id
                        WHERE model.brand_id = ANY(changed_catalog_ids)
                    ) AS affected;
                ELSE
                    SELECT array_agg(DISTINCT evidence.content_id)
                    INTO affected_content_ids
                    FROM content_vehicle_evidence AS evidence
                    WHERE evidence.vehicle_model_id = ANY(changed_catalog_ids);
                END IF;

                IF COALESCE(cardinality(affected_content_ids), 0) > 0 THEN
                    PERFORM refresh_voice_plaza_vehicle_dimensions_batch(affected_content_ids);
                END IF;
                RETURN NULL;
            END;
            $$
            """
        )
    )


def upgrade() -> None:
    """过滤与声音广场派生维度无关的目录 UPDATE。"""

    _replace_catalog_refresh_function(precise=True)


def downgrade() -> None:
    """恢复 0061 的所有目录 UPDATE 都触发刷新的行为。"""

    _replace_catalog_refresh_function(precise=False)
