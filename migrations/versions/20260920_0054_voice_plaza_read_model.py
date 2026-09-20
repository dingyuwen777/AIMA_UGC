"""建立声音广场增量读模型与可恢复回填状态。

Revision ID: 20260920_0054
Revises: 20260920_0053
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260920_0054"
down_revision: str | Sequence[str] | None = "20260920_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """只建立派生结构与增量刷新；历史数据交给持久 Job 分块回填。"""

    op.create_table(
        "voice_plaza_content_projection",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("sort_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column("analysis_result_id", sa.Uuid()),
        sa.Column("analysis_status", sa.Text(), nullable=False),
        sa.Column("effective_relevance", sa.Text()),
        sa.Column("relevance_source", sa.Text()),
        sa.Column("effective_voice_type", sa.Text()),
        sa.Column("effective_sentiment", sa.Text()),
        sa.Column(
            "labels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "brand_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column(
            "vehicle_model_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column("competition_scope", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_version > 0",
            name=op.f("ck_voice_plaza_content_projection_content_version_positive"),
        ),
        sa.CheckConstraint(
            "analysis_status in ('completed','pending','stale')",
            name=op.f("ck_voice_plaza_content_projection_analysis_status_allowed"),
        ),
        sa.CheckConstraint(
            "effective_relevance is null or effective_relevance in ('relevant','irrelevant')",
            name=op.f("ck_voice_plaza_content_projection_effective_relevance_allowed"),
        ),
        sa.CheckConstraint(
            "relevance_source is null or relevance_source in ('ai','manual_review')",
            name=op.f("ck_voice_plaza_content_projection_relevance_source_allowed"),
        ),
        sa.CheckConstraint(
            "(effective_relevance is null) = (relevance_source is null)",
            name=op.f("ck_voice_plaza_content_projection_relevance_consistent"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(labels) = 'array'",
            name=op.f("ck_voice_plaza_content_projection_labels_array"),
        ),
        sa.CheckConstraint(
            "competition_scope in "
            "('none_detected','owned_only','competitor_only','other_only','mixed')",
            name=op.f("ck_voice_plaza_content_projection_competition_scope_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_vp_projection_content"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_result_id"],
            ["analysis_content_results.id"],
            name=op.f("fk_vp_projection_analysis_result"),
        ),
        sa.PrimaryKeyConstraint("content_id", name=op.f("pk_voice_plaza_content_projection")),
    )
    op.create_index(
        "ix_voice_plaza_projection_latest",
        "voice_plaza_content_projection",
        [sa.text("sort_at DESC"), sa.text("content_id DESC")],
        postgresql_where=sa.text(
            "is_visible IS TRUE AND effective_relevance IS DISTINCT FROM 'irrelevant'"
        ),
    )
    op.create_index(
        "ix_voice_plaza_projection_published_latest",
        "voice_plaza_content_projection",
        [sa.text("published_at DESC NULLS LAST"), sa.text("content_id DESC")],
        postgresql_where=sa.text(
            "is_visible IS TRUE AND effective_relevance IS DISTINCT FROM 'irrelevant'"
        ),
    )
    op.create_index(
        "ix_voice_plaza_projection_platform_latest",
        "voice_plaza_content_projection",
        [
            "platform",
            sa.text("published_at DESC NULLS LAST"),
            sa.text("content_id DESC"),
        ],
        postgresql_where=sa.text(
            "is_visible IS TRUE AND effective_relevance IS DISTINCT FROM 'irrelevant'"
        ),
    )
    op.create_index(
        "ix_voice_plaza_projection_content_type_latest",
        "voice_plaza_content_projection",
        [
            "content_type",
            sa.text("published_at DESC NULLS LAST"),
            sa.text("content_id DESC"),
        ],
        postgresql_where=sa.text(
            "is_visible IS TRUE AND effective_relevance IS DISTINCT FROM 'irrelevant'"
        ),
    )
    op.create_index(
        "ix_voice_plaza_projection_analysis_status_latest",
        "voice_plaza_content_projection",
        [
            "analysis_status",
            sa.text("published_at DESC NULLS LAST"),
            sa.text("content_id DESC"),
        ],
        postgresql_where=sa.text("is_visible IS TRUE"),
    )
    op.create_index(
        "ix_voice_plaza_projection_relevance_latest",
        "voice_plaza_content_projection",
        [
            "effective_relevance",
            sa.text("published_at DESC NULLS LAST"),
            sa.text("content_id DESC"),
        ],
        postgresql_where=sa.text("is_visible IS TRUE"),
    )
    op.create_index(
        "ix_voice_plaza_projection_labels_gin",
        "voice_plaza_content_projection",
        ["labels"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_voice_plaza_projection_brand_ids_gin",
        "voice_plaza_content_projection",
        ["brand_ids"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_voice_plaza_projection_vehicle_ids_gin",
        "voice_plaza_content_projection",
        ["vehicle_model_ids"],
        postgresql_using="gin",
    )

    op.create_table(
        "voice_plaza_filter_catalog",
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("secondary_value", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("content_count", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "dimension in ('content_type','sentiment','voice_type','label')",
            name=op.f("ck_voice_plaza_filter_catalog_dimension_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(value) > 0",
            name=op.f("ck_voice_plaza_filter_catalog_value_nonempty"),
        ),
        sa.CheckConstraint(
            "content_count > 0",
            name=op.f("ck_voice_plaza_filter_catalog_content_count_positive"),
        ),
        sa.PrimaryKeyConstraint(
            "dimension",
            "value",
            "secondary_value",
            name=op.f("pk_voice_plaza_filter_catalog"),
        ),
    )
    op.create_table(
        "voice_plaza_filter_catalog_entries",
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("secondary_value", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.CheckConstraint(
            "dimension in ('content_type','sentiment','voice_type','label')",
            name=op.f("ck_voice_plaza_filter_catalog_entries_dimension_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(value) > 0",
            name=op.f("ck_voice_plaza_filter_catalog_entries_value_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["voice_plaza_content_projection.content_id"],
            name=op.f("fk_vp_filter_entries_projection"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "content_id",
            "dimension",
            "value",
            "secondary_value",
            name=op.f("pk_voice_plaza_filter_catalog_entries"),
        ),
    )
    op.create_index(
        "ix_voice_plaza_filter_entries_catalog",
        "voice_plaza_filter_catalog_entries",
        ["dimension", "value", "secondary_value"],
    )
    op.create_table(
        "voice_plaza_projection_state",
        sa.Column("singleton", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("generation", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_content_id", sa.Uuid()),
        sa.Column("projected_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_content_count", sa.BigInteger()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "singleton",
            name=op.f("ck_voice_plaza_projection_state_singleton_true"),
        ),
        sa.CheckConstraint(
            "status in ('pending','running','ready','failed')",
            name=op.f("ck_voice_plaza_projection_state_status_allowed"),
        ),
        sa.CheckConstraint(
            "generation > 0",
            name=op.f("ck_voice_plaza_projection_state_generation_positive"),
        ),
        sa.CheckConstraint(
            "projected_count >= 0",
            name=op.f("ck_voice_plaza_projection_state_projected_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "total_content_count is null or total_content_count >= 0",
            name=op.f("ck_voice_plaza_projection_state_total_content_count_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("singleton", name=op.f("pk_voice_plaza_projection_state")),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO voice_plaza_projection_state (
                singleton, status, projected_count, updated_at
            ) VALUES (true, 'pending', 0, clock_timestamp())
            """
        )
    )
    _create_projection_functions_and_triggers()


def _create_projection_functions_and_triggers() -> None:
    """建立单 Content 刷新函数和覆盖所有已确认写入边界的触发器。"""

    op.execute(
        sa.text(
            """
            CREATE FUNCTION voice_plaza_has_active_source(p_content_id uuid)
            RETURNS boolean
            LANGUAGE sql
            STABLE
            AS $$
                SELECT
                    EXISTS (
                        SELECT 1
                        FROM processing_import_batch_items AS ledger
                        JOIN historical_import_campaign_items AS campaign_item
                          ON campaign_item.id = ledger.campaign_item_id
                        WHERE ledger.content_id = p_content_id
                          AND NOT EXISTS (
                              SELECT 1
                              FROM historical_import_campaign_revocations AS revocation
                              WHERE revocation.campaign_id = campaign_item.campaign_id
                          )
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM collection_candidate_ingestions AS ingestion
                        JOIN collection_candidates AS candidate
                          ON candidate.id = ingestion.candidate_id
                        JOIN provider_request_attempts AS attempt
                          ON attempt.id = candidate.provider_request_attempt_id
                        JOIN provider_requests AS request
                          ON request.id = attempt.provider_request_id
                        JOIN collection_scopes AS scope ON scope.id = request.scope_id
                        JOIN collection_runs AS run ON run.id = scope.run_id
                        WHERE ingestion.content_id = p_content_id
                          AND (
                              run.data_import_campaign_id IS NULL
                              OR NOT EXISTS (
                                  SELECT 1
                                  FROM historical_import_campaign_revocations AS revocation
                                  WHERE revocation.campaign_id = run.data_import_campaign_id
                              )
                          )
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM content_versions AS version
                        JOIN provider_request_attempts AS attempt
                          ON attempt.id = version.provider_attempt_id
                        JOIN provider_requests AS request
                          ON request.id = attempt.provider_request_id
                        JOIN processing_import_batches AS batch
                          ON batch.id = request.import_batch_id
                        LEFT JOIN historical_import_campaign_items AS campaign_item
                          ON campaign_item.id = batch.historical_campaign_item_id
                        WHERE version.content_id = p_content_id
                          AND request.import_batch_id IS NOT NULL
                          AND (
                              batch.historical_campaign_item_id IS NULL
                              OR NOT EXISTS (
                                  SELECT 1
                                  FROM historical_import_campaign_revocations AS revocation
                                  WHERE revocation.campaign_id = campaign_item.campaign_id
                              )
                          )
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM content_versions AS version
                        JOIN provider_request_attempts AS attempt
                          ON attempt.id = version.provider_attempt_id
                        JOIN provider_requests AS request
                          ON request.id = attempt.provider_request_id
                        JOIN collection_scopes AS scope ON scope.id = request.scope_id
                        JOIN collection_runs AS run ON run.id = scope.run_id
                        WHERE version.content_id = p_content_id
                          AND request.scope_id IS NOT NULL
                          AND (
                              run.data_import_campaign_id IS NULL
                              OR NOT EXISTS (
                                  SELECT 1
                                  FROM historical_import_campaign_revocations AS revocation
                                  WHERE revocation.campaign_id = run.data_import_campaign_id
                              )
                          )
                    );
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION voice_plaza_filter_catalog_entry_delta()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    INSERT INTO voice_plaza_filter_catalog (
                        dimension, value, secondary_value, content_count, updated_at
                    ) VALUES (
                        NEW.dimension, NEW.value, NEW.secondary_value, 1, clock_timestamp()
                    )
                    ON CONFLICT (dimension, value, secondary_value) DO UPDATE
                    SET content_count = voice_plaza_filter_catalog.content_count + 1,
                        updated_at = EXCLUDED.updated_at;
                    RETURN NEW;
                END IF;

                DELETE FROM voice_plaza_filter_catalog
                WHERE dimension = OLD.dimension
                  AND value = OLD.value
                  AND secondary_value = OLD.secondary_value
                  AND content_count = 1;
                IF NOT FOUND THEN
                    UPDATE voice_plaza_filter_catalog
                    SET content_count = content_count - 1,
                        updated_at = clock_timestamp()
                    WHERE dimension = OLD.dimension
                      AND value = OLD.value
                      AND secondary_value = OLD.secondary_value
                      AND content_count > 1;
                END IF;
                RETURN OLD;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_voice_plaza_filter_catalog_entry_delta
            AFTER INSERT OR DELETE ON voice_plaza_filter_catalog_entries
            FOR EACH ROW EXECUTE FUNCTION voice_plaza_filter_catalog_entry_delta()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_content_projection_batch(p_content_ids uuid[])
            RETURNS void
            LANGUAGE plpgsql
            AS $$
            BEGIN
                INSERT INTO voice_plaza_content_projection (
                    content_id,
                    content_version,
                    platform,
                    content_type,
                    published_at,
                    sort_at,
                    is_visible,
                    analysis_result_id,
                    analysis_status,
                    effective_relevance,
                    relevance_source,
                    effective_voice_type,
                    effective_sentiment,
                    labels,
                    brand_ids,
                    vehicle_model_ids,
                    competition_scope,
                    updated_at
                )
                SELECT
                    content.id,
                    content.current_version,
                    content.platform,
                    content.content_type,
                    content.published_at,
                    COALESCE(content.published_at, content.last_seen_at),
                    voice_plaza_has_active_source(content.id),
                    analysis.id,
                    CASE
                        WHEN analysis.id IS NOT NULL THEN 'completed'
                        WHEN EXISTS (
                            SELECT 1 FROM analysis_content_results AS historical_analysis
                            WHERE historical_analysis.content_id = content.id
                        ) THEN 'stale'
                        ELSE 'pending'
                    END,
                    CASE
                        WHEN review.decision IN ('relevant', 'irrelevant')
                            THEN review.decision
                        ELSE analysis.relevance
                    END,
                    CASE
                        WHEN review.decision IN ('relevant', 'irrelevant')
                            THEN 'manual_review'
                        WHEN analysis.relevance IS NOT NULL THEN 'ai'
                        ELSE NULL
                    END,
                    CASE
                        WHEN manual.voice_type_locked THEN manual.voice_type
                        ELSE analysis.voice_type
                    END,
                    CASE
                        WHEN manual.sentiment_locked THEN manual.sentiment
                        ELSE analysis.sentiment
                    END,
                    CASE
                        WHEN manual.labels_locked THEN manual.labels
                        ELSE COALESCE(labels.items, '[]'::jsonb)
                    END,
                    COALESCE(brands.brand_ids, '{}'::uuid[]),
                    COALESCE(vehicles.vehicle_model_ids, '{}'::uuid[]),
                    CASE
                        WHEN COALESCE(brands.role_count, 0) = 0 THEN 'none_detected'
                        WHEN brands.role_count > 1 THEN 'mixed'
                        WHEN brands.has_owned THEN 'owned_only'
                        WHEN brands.has_competitor THEN 'competitor_only'
                        ELSE 'other_only'
                    END,
                    clock_timestamp()
                FROM contents AS content
                LEFT JOIN LATERAL (
                    SELECT result.*
                    FROM analysis_content_results AS result
                    JOIN analysis_content_runs AS run ON run.id = result.analysis_run_id
                    WHERE result.content_id = content.id
                      AND result.content_version = content.current_version
                    ORDER BY run.sequence_no DESC, result.id DESC
                    LIMIT 1
                ) AS analysis ON true
                LEFT JOIN analysis_content_manual_overrides AS manual
                  ON manual.content_id = content.id
                 AND manual.content_version = content.current_version
                LEFT JOIN LATERAL (
                    SELECT relevance_review.decision
                    FROM analysis_content_relevance_reviews AS relevance_review
                    WHERE relevance_review.content_id = content.id
                      AND relevance_review.content_version = content.current_version
                    ORDER BY relevance_review.review_no DESC,
                             relevance_review.reviewed_at DESC,
                             relevance_review.id DESC
                    LIMIT 1
                ) AS review ON true
                LEFT JOIN LATERAL (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'primary_label', pair.primary_label,
                            'secondary_label', pair.secondary_label
                        ) ORDER BY pair.ordinal
                    ) AS items
                    FROM analysis_content_label_pairs AS pair
                    WHERE pair.analysis_result_id = analysis.id
                ) AS labels ON true
                LEFT JOIN LATERAL (
                    SELECT
                        array_agg(DISTINCT evidence.brand_id)
                            FILTER (WHERE evidence.brand_id IS NOT NULL) AS brand_ids,
                        count(DISTINCT brand.role) AS role_count,
                        bool_or(brand.role = 'owned') AS has_owned,
                        bool_or(brand.role = 'competitor') AS has_competitor
                    FROM content_brand_evidence AS evidence
                    JOIN vehicle_brands AS brand ON brand.id = evidence.brand_id
                    WHERE evidence.content_id = content.id
                      AND evidence.content_version = content.current_version
                      AND evidence.is_active
                ) AS brands ON true
                LEFT JOIN LATERAL (
                    SELECT array_agg(DISTINCT COALESCE(model.merged_into_id, model.id))
                        FILTER (WHERE model.id IS NOT NULL) AS vehicle_model_ids
                    FROM content_vehicle_evidence AS evidence
                    JOIN vehicle_models AS model ON model.id = evidence.vehicle_model_id
                    WHERE evidence.content_id = content.id
                      AND evidence.content_version = content.current_version
                      AND evidence.is_active
                ) AS vehicles ON true
                WHERE content.id = ANY(p_content_ids)
                ON CONFLICT (content_id) DO UPDATE
                SET content_version = EXCLUDED.content_version,
                    platform = EXCLUDED.platform,
                    content_type = EXCLUDED.content_type,
                    published_at = EXCLUDED.published_at,
                    sort_at = EXCLUDED.sort_at,
                    is_visible = EXCLUDED.is_visible,
                    analysis_result_id = EXCLUDED.analysis_result_id,
                    analysis_status = EXCLUDED.analysis_status,
                    effective_relevance = EXCLUDED.effective_relevance,
                    relevance_source = EXCLUDED.relevance_source,
                    effective_voice_type = EXCLUDED.effective_voice_type,
                    effective_sentiment = EXCLUDED.effective_sentiment,
                    labels = EXCLUDED.labels,
                    brand_ids = EXCLUDED.brand_ids,
                    vehicle_model_ids = EXCLUDED.vehicle_model_ids,
                    competition_scope = EXCLUDED.competition_scope,
                    updated_at = EXCLUDED.updated_at;

                DELETE FROM voice_plaza_filter_catalog_entries
                WHERE content_id = ANY(p_content_ids);

                INSERT INTO voice_plaza_filter_catalog_entries (
                    content_id, dimension, value, secondary_value
                )
                SELECT projection.content_id, 'content_type', projection.content_type, ''
                FROM voice_plaza_content_projection AS projection
                WHERE projection.content_id = ANY(p_content_ids) AND projection.is_visible
                UNION ALL
                SELECT projection.content_id, 'sentiment', projection.effective_sentiment, ''
                FROM voice_plaza_content_projection AS projection
                WHERE projection.content_id = ANY(p_content_ids)
                  AND projection.is_visible
                  AND projection.effective_sentiment IS NOT NULL
                UNION ALL
                SELECT projection.content_id, 'voice_type', projection.effective_voice_type, ''
                FROM voice_plaza_content_projection AS projection
                WHERE projection.content_id = ANY(p_content_ids)
                  AND projection.is_visible
                  AND projection.effective_voice_type IS NOT NULL
                UNION ALL
                SELECT
                    projection.content_id,
                    'label',
                    label.item ->> 'primary_label',
                    label.item ->> 'secondary_label'
                FROM voice_plaza_content_projection AS projection
                CROSS JOIN LATERAL jsonb_array_elements(projection.labels) AS label(item)
                WHERE projection.content_id = ANY(p_content_ids)
                  AND projection.is_visible
                  AND label.item ->> 'primary_label' <> ''
                  AND label.item ->> 'secondary_label' <> ''
                ON CONFLICT DO NOTHING;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_content_projection(p_content_id uuid)
            RETURNS void
            LANGUAGE sql
            AS $$
                SELECT refresh_voice_plaza_content_projection_batch(ARRAY[p_content_id]);
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_projection_from_content()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                PERFORM refresh_voice_plaza_content_projection(COALESCE(NEW.id, OLD.id));
                RETURN COALESCE(NEW, OLD);
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_projection_from_content_fact()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                PERFORM refresh_voice_plaza_content_projection(
                    COALESCE(NEW.content_id, OLD.content_id)
                );
                RETURN COALESCE(NEW, OLD);
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_projection_from_label()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                resolved_content_id uuid;
            BEGIN
                SELECT result.content_id INTO resolved_content_id
                FROM analysis_content_results AS result
                WHERE result.id = COALESCE(NEW.analysis_result_id, OLD.analysis_result_id);
                IF resolved_content_id IS NOT NULL THEN
                    PERFORM refresh_voice_plaza_content_projection(resolved_content_id);
                END IF;
                RETURN COALESCE(NEW, OLD);
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_projection_from_contribution()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                PERFORM refresh_voice_plaza_content_projection(NEW.content_id);
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION refresh_voice_plaza_projection_from_catalog()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                affected_content_id uuid;
            BEGIN
                IF TG_TABLE_NAME = 'vehicle_brands' THEN
                    FOR affected_content_id IN
                        SELECT DISTINCT evidence.content_id
                        FROM content_brand_evidence AS evidence
                        WHERE evidence.brand_id = COALESCE(NEW.id, OLD.id)
                        UNION
                        SELECT DISTINCT evidence.content_id
                        FROM content_vehicle_evidence AS evidence
                        JOIN vehicle_models AS model ON model.id = evidence.vehicle_model_id
                        WHERE model.brand_id = COALESCE(NEW.id, OLD.id)
                    LOOP
                        PERFORM refresh_voice_plaza_content_projection(affected_content_id);
                    END LOOP;
                ELSE
                    FOR affected_content_id IN
                        SELECT DISTINCT evidence.content_id
                        FROM content_vehicle_evidence AS evidence
                        WHERE evidence.vehicle_model_id = COALESCE(NEW.id, OLD.id)
                    LOOP
                        PERFORM refresh_voice_plaza_content_projection(affected_content_id);
                    END LOOP;
                END IF;
                RETURN COALESCE(NEW, OLD);
            END;
            $$
            """
        )
    )

    for table_name in (
        "content_versions",
        "analysis_content_results",
        "analysis_content_manual_overrides",
        "analysis_content_relevance_reviews",
        "content_brand_evidence",
        "content_vehicle_evidence",
        "historical_import_revocation_content_versions",
    ):
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table_name}_voice_plaza_projection
                AFTER INSERT OR UPDATE OR DELETE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_fact()
                """
            )
        )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_contents_voice_plaza_projection
            AFTER INSERT OR UPDATE ON contents
            FOR EACH ROW EXECUTE FUNCTION refresh_voice_plaza_projection_from_content()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_analysis_labels_voice_plaza_projection
            AFTER INSERT OR UPDATE OR DELETE ON analysis_content_label_pairs
            FOR EACH ROW EXECUTE FUNCTION refresh_voice_plaza_projection_from_label()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_content_contributions_voice_plaza_projection
            AFTER INSERT ON content_source_contributions
            FOR EACH ROW EXECUTE FUNCTION refresh_voice_plaza_projection_from_contribution()
            """
        )
    )
    for table_name in ("vehicle_brands", "vehicle_models"):
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table_name}_voice_plaza_projection
                AFTER UPDATE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION refresh_voice_plaza_projection_from_catalog()
                """
            )
        )


def downgrade() -> None:
    """删除派生读模型；业务事实表与旧查询路径保持不变。"""

    for table_name in ("vehicle_models", "vehicle_brands"):
        op.execute(
            sa.text(
                f"DROP TRIGGER IF EXISTS trg_{table_name}_voice_plaza_projection ON {table_name}"
            )
        )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_content_contributions_voice_plaza_projection "
            "ON content_source_contributions"
        )
    )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_analysis_labels_voice_plaza_projection "
            "ON analysis_content_label_pairs"
        )
    )
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_contents_voice_plaza_projection ON contents"))
    for table_name in (
        "historical_import_revocation_content_versions",
        "content_vehicle_evidence",
        "content_brand_evidence",
        "analysis_content_relevance_reviews",
        "analysis_content_manual_overrides",
        "analysis_content_results",
        "content_versions",
    ):
        op.execute(
            sa.text(
                f"DROP TRIGGER IF EXISTS trg_{table_name}_voice_plaza_projection ON {table_name}"
            )
        )
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_voice_plaza_filter_catalog_entry_delta "
            "ON voice_plaza_filter_catalog_entries"
        )
    )
    for function_name in (
        "refresh_voice_plaza_projection_from_catalog()",
        "refresh_voice_plaza_projection_from_contribution()",
        "refresh_voice_plaza_projection_from_label()",
        "refresh_voice_plaza_projection_from_content_fact()",
        "refresh_voice_plaza_projection_from_content()",
        "refresh_voice_plaza_content_projection(uuid)",
        "refresh_voice_plaza_content_projection_batch(uuid[])",
        "voice_plaza_filter_catalog_entry_delta()",
        "voice_plaza_has_active_source(uuid)",
    ):
        op.execute(sa.text(f"DROP FUNCTION IF EXISTS {function_name}"))

    op.drop_table("voice_plaza_projection_state")
    op.drop_index(
        "ix_voice_plaza_filter_entries_catalog",
        table_name="voice_plaza_filter_catalog_entries",
    )
    op.drop_table("voice_plaza_filter_catalog_entries")
    op.drop_table("voice_plaza_filter_catalog")
    op.drop_index(
        "ix_voice_plaza_projection_vehicle_ids_gin",
        table_name="voice_plaza_content_projection",
    )
    op.drop_index(
        "ix_voice_plaza_projection_brand_ids_gin",
        table_name="voice_plaza_content_projection",
    )
    op.drop_index(
        "ix_voice_plaza_projection_labels_gin",
        table_name="voice_plaza_content_projection",
    )
    op.drop_index(
        "ix_voice_plaza_projection_relevance_latest",
        table_name="voice_plaza_content_projection",
    )
    op.drop_index(
        "ix_voice_plaza_projection_analysis_status_latest",
        table_name="voice_plaza_content_projection",
    )
    op.drop_index(
        "ix_voice_plaza_projection_content_type_latest",
        table_name="voice_plaza_content_projection",
    )
    op.drop_index(
        "ix_voice_plaza_projection_platform_latest",
        table_name="voice_plaza_content_projection",
    )
    op.drop_index(
        "ix_voice_plaza_projection_published_latest",
        table_name="voice_plaza_content_projection",
        if_exists=True,
    )
    op.drop_index(
        "ix_voice_plaza_projection_latest",
        table_name="voice_plaza_content_projection",
    )
    op.drop_table("voice_plaza_content_projection")
