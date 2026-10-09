"""为输入等价的内容版本保留真实 Analysis 与人工审核来源；不修复历史数据。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261009_0083"
down_revision: str | Sequence[str] | None = "20261003_0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DDL = """

CREATE TABLE analysis_content_version_reuses (
	content_id UUID NOT NULL,
	target_content_version INTEGER NOT NULL,
	source_analysis_result_id UUID NOT NULL,
	source_content_version INTEGER NOT NULL,
	input_hash TEXT NOT NULL,
	input_hash_algorithm TEXT NOT NULL,
	manual_override_source_version INTEGER,
	relevance_review_source_version INTEGER,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
        CONSTRAINT pk_analysis_content_version_reuses PRIMARY KEY (content_id,
target_content_version),
        CONSTRAINT fk_analysis_content_version_reuses_content_id_target_co_3dd0 FOREIGN
KEY(content_id, target_content_version) REFERENCES content_versions (content_id, version_no),
        CONSTRAINT fk_analysis_content_version_reuses_content_id_source_co_ff9f FOREIGN
KEY(content_id, source_content_version) REFERENCES content_versions (content_id, version_no),
        CONSTRAINT fk_analysis_content_version_reuses_content_id_manual_ov_531c FOREIGN
KEY(content_id, manual_override_source_version) REFERENCES content_versions (content_id,
version_no),
        CONSTRAINT fk_analysis_content_version_reuses_content_id_relevance_522e FOREIGN
KEY(content_id, relevance_review_source_version) REFERENCES content_versions (content_id,
version_no),
        CONSTRAINT ck_analysis_content_version_reuses_source_precedes_target CHECK
(source_content_version < target_content_version),
        CONSTRAINT ck_analysis_content_version_reuses_manual_precedes_target CHECK
(manual_override_source_version < target_content_version),
        CONSTRAINT ck_analysis_content_version_reuses_review_precedes_target CHECK
(relevance_review_source_version < target_content_version),
        CONSTRAINT ck_analysis_content_version_reuses_input_hash_sha256_length CHECK
(char_length(input_hash) = 64),
        CONSTRAINT ck_analysis_content_version_reuses_hash_protocol_known CHECK
(input_hash_algorithm = 'content-labeling-input-sha256-v1'),
        CONSTRAINT fk_analysis_content_version_reuses_source_analysis_resu_7e2f FOREIGN
KEY(source_analysis_result_id) REFERENCES analysis_content_results (id)
)

"""

EFFECTIVE = """

CREATE FUNCTION effective_analysis_source(p_content_id uuid, p_version integer, p_scheme uuid
DEFAULT NULL)
RETURNS TABLE(analysis_result_id uuid, source_content_version integer,
              manual_override_version integer, relevance_review_id uuid)
LANGUAGE sql VOLATILE ROWS 1 AS $$
    WITH reuse AS (
        SELECT relation.* FROM analysis_content_version_reuses relation
        JOIN analysis_content_results source ON source.id = relation.source_analysis_result_id
          AND source.content_id = relation.content_id
          AND source.content_version = relation.source_content_version
          AND source.input_hash = relation.input_hash
          AND source.schema_version IN
('content-label-analysis.v1','content-label-analysis.v2','content-label-analysis.v3')
        WHERE relation.content_id = p_content_id AND relation.target_content_version = p_version
          AND relation.input_hash_algorithm = 'content-labeling-input-sha256-v1'
    ), selected AS (
        SELECT result.id, result.content_version FROM analysis_content_results result
        JOIN analysis_content_runs run ON run.id = result.analysis_run_id
        WHERE result.content_id = p_content_id AND result.content_version = p_version
          AND (p_scheme IS NULL OR run.analysis_scheme_version_id = p_scheme)
        ORDER BY run.sequence_no DESC, result.id DESC LIMIT 1
    ), source AS (
        SELECT selected.id, selected.content_version FROM selected
        UNION ALL
        SELECT result.id, result.content_version FROM reuse
        JOIN analysis_content_results result ON result.id = reuse.source_analysis_result_id
        JOIN analysis_content_runs run ON run.id = result.analysis_run_id
        WHERE NOT EXISTS (SELECT 1 FROM selected)
          AND (p_scheme IS NULL OR run.analysis_scheme_version_id = p_scheme)
    )
    SELECT source.id, source.content_version,
        CASE WHEN source.id IS NULL THEN NULL
             WHEN EXISTS (SELECT 1 FROM analysis_content_manual_overrides manual
                          WHERE manual.content_id=p_content_id AND
manual.content_version=p_version)
                 THEN p_version ELSE reuse.manual_override_source_version END,
        CASE WHEN source.id IS NULL THEN NULL ELSE (
            SELECT review.id FROM analysis_content_relevance_reviews review
            WHERE review.content_id=p_content_id AND review.content_version=COALESCE(
                (SELECT current_review.content_version FROM analysis_content_relevance_reviews
current_review
                 WHERE current_review.content_id=p_content_id AND
current_review.content_version=p_version LIMIT 1),
                reuse.relevance_review_source_version)
            ORDER BY review.review_no DESC, review.reviewed_at DESC, review.id DESC LIMIT 1
        ) END
    FROM (VALUES (1)) singleton(n) LEFT JOIN source ON true LEFT JOIN reuse ON true;
$$
"""

GUARD = """

CREATE FUNCTION guard_analysis_content_version_reuse() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM analysis_content_results result
        WHERE result.id=NEW.source_analysis_result_id AND result.content_id=NEW.content_id
          AND result.content_version=NEW.source_content_version AND
result.input_hash=NEW.input_hash
          AND result.schema_version IN
('content-label-analysis.v1','content-label-analysis.v2','content-label-analysis.v3'))
    THEN RAISE EXCEPTION 'Analysis reuse source does not match its persisted result'; END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_analysis_reuse_guard BEFORE INSERT OR UPDATE ON
analysis_content_version_reuses
FOR EACH ROW EXECUTE FUNCTION guard_analysis_content_version_reuse();
"""

PROJECTION = """

            CREATE OR REPLACE FUNCTION
refresh_voice_plaza_content_projection_batch(p_content_ids uuid[])
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
                LEFT JOIN LATERAL effective_analysis_source(content.id, content.current_version)
AS effective ON true
                LEFT JOIN analysis_content_results AS analysis ON analysis.id =
effective.analysis_result_id
                LEFT JOIN analysis_content_manual_overrides AS manual
                  ON manual.content_id = content.id AND manual.content_version =
effective.manual_override_version
                LEFT JOIN analysis_content_relevance_reviews AS review ON review.id =
effective.relevance_review_id
                LEFT JOIN LATERAL (
                    SELECT jsonb_agg(jsonb_build_object('primary_label', pair.primary_label,
                        'secondary_label', pair.secondary_label) ORDER BY pair.ordinal) AS items
                    FROM analysis_content_label_pairs AS pair WHERE pair.analysis_result_id =
analysis.id
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

PREVIOUS_PROJECTION = """

            CREATE OR REPLACE FUNCTION
refresh_voice_plaza_content_projection_batch(p_content_ids uuid[])
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

TRIGGERS = """

CREATE TRIGGER trg_voice_plaza_reuse_insert AFTER INSERT ON analysis_content_version_reuses
REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT
WHEN (current_setting('aima.defer_voice_plaza', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_fact_statement();
CREATE TRIGGER trg_voice_plaza_reuse_update AFTER UPDATE ON analysis_content_version_reuses
REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows FOR EACH STATEMENT
WHEN (current_setting('aima.defer_voice_plaza', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_fact_statement();
CREATE TRIGGER trg_voice_plaza_reuse_delete AFTER DELETE ON analysis_content_version_reuses
REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT
WHEN (current_setting('aima.defer_voice_plaza', true) IS DISTINCT FROM 'on')
EXECUTE FUNCTION refresh_voice_plaza_projection_from_content_fact_statement();
"""


def upgrade() -> None:
    for statement in (DDL, EFFECTIVE, GUARD, PROJECTION, TRIGGERS):
        op.execute(sa.text(statement))


def downgrade() -> None:
    op.execute(sa.text(PREVIOUS_PROJECTION))
    op.execute(sa.text("DROP FUNCTION effective_analysis_source(uuid, integer, uuid)"))
    op.drop_table("analysis_content_version_reuses")
    op.execute(sa.text("DROP FUNCTION guard_analysis_content_version_reuse()"))
