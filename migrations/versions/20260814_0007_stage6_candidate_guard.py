"""修正 Stage 6 Candidate Raw Artifact 来源门禁。

Revision ID: 20260814_0007
Revises: 20260814_0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260814_0007"
down_revision: str | Sequence[str] | None = "20260814_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_collection_candidate_source() RETURNS trigger AS $$
        DECLARE attempt_status text; artifact_id uuid; artifact_status text;
        BEGIN
          SELECT dispatch_status, raw_artifact_id INTO attempt_status, artifact_id
          FROM provider_request_attempts WHERE id = NEW.provider_request_attempt_id;
          IF attempt_status <> 'completed' OR artifact_id IS NULL THEN
            RAISE EXCEPTION 'Candidate 必须来自 completed 且已绑定 Raw 的 Provider Attempt';
          END IF;
          SELECT storage_status INTO artifact_status FROM artifacts WHERE id = artifact_id;
          IF artifact_status <> 'linked' THEN
            RAISE EXCEPTION 'Candidate Raw Artifact 必须已 linked';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_collection_candidate_source() RETURNS trigger AS $$
        DECLARE attempt_status text; artifact_id uuid; artifact_status text;
        BEGIN
          SELECT dispatch_status, raw_artifact_id INTO attempt_status, artifact_id
          FROM provider_request_attempts WHERE id = NEW.provider_request_attempt_id;
          IF attempt_status <> 'completed' OR artifact_id IS NULL THEN
            RAISE EXCEPTION 'Candidate 必须来自 completed 且已绑定 Raw 的 Provider Attempt';
          END IF;
          SELECT status INTO artifact_status FROM artifacts WHERE id = artifact_id;
          IF artifact_status <> 'linked' THEN
            RAISE EXCEPTION 'Candidate Raw Artifact 必须已 linked';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        """
    )
