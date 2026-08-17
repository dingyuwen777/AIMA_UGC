"""当前应用 Schema 的机器注册入口。"""

from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.scheduler_schema import register_scheduler_schema
from aima_ugc.modules.collection.tables import (
    collection_plan_keyword_packs_table,
    collection_plan_platforms_table,
    collection_plans_table,
    collection_runs_table,
    collection_schedule_occurrences_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.account_tables import account_external_ids_table
from aima_ugc.modules.content.tables import (
    accounts_table,
    comment_coverage_observations_table,
    comment_metric_observations_table,
    comment_versions_table,
    comments_table,
    content_metric_observations_table,
    content_versions_table,
    contents_table,
)
from aima_ugc.modules.system.tables import (
    audit_events_table,
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
    provider_configs_table,
    system_settings_table,
)
from aima_ugc.platform.database.metadata import metadata
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from aima_ugc.platform.storage.tables import artifacts_table

register_scheduler_schema()

__all__ = [
    "account_external_ids_table",
    "accounts_table",
    "artifacts_table",
    "audit_events_table",
    "collection_candidate_ingestions_table",
    "collection_candidates_table",
    "collection_plan_keyword_packs_table",
    "collection_plan_platforms_table",
    "collection_plans_table",
    "collection_runs_table",
    "collection_schedule_occurrences_table",
    "collection_scopes_table",
    "comment_coverage_observations_table",
    "comment_metric_observations_table",
    "comment_versions_table",
    "comments_table",
    "content_metric_observations_table",
    "content_versions_table",
    "contents_table",
    "job_attempt_events_table",
    "jobs_table",
    "keyword_pack_items_table",
    "keyword_packs_table",
    "keywords_table",
    "metadata",
    "provider_configs_table",
    "provider_request_attempts_table",
    "provider_requests_table",
    "system_settings_table",
]
