"""当前应用 Schema 的机器注册入口。"""

from aima_ugc.modules.analysis.manual_override_tables import (
    analysis_content_manual_overrides_table,
)
from aima_ugc.modules.analysis.relevance_review_tables import (
    analysis_content_relevance_reviews_table,
)
from aima_ugc.modules.analysis.scheme_tables import (
    analysis_scheme_versions_table,
    analysis_schemes_table,
)
from aima_ugc.modules.analysis.tables import (
    analysis_content_label_pairs_table,
    analysis_content_request_items_table,
    analysis_content_requests_table,
    analysis_content_results_table,
    analysis_content_run_targets_table,
    analysis_content_runs_table,
)
from aima_ugc.modules.collection.candidate_tables import (
    collection_candidate_ingestions_table,
    collection_candidates_table,
)
from aima_ugc.modules.collection.corrective_tables import (
    collection_content_actions_table,
    collection_plan_decision_policies_table,
)
from aima_ugc.modules.collection.scheduler_schema import register_scheduler_schema
from aima_ugc.modules.collection.tables import (
    collection_plan_keyword_packs_table,
    collection_plan_platforms_table,
    collection_plan_vehicle_models_table,
    collection_plans_table,
    collection_runs_table,
    collection_schedule_occurrences_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.content.account_tables import account_external_ids_table
from aima_ugc.modules.content.availability_tables import (
    content_availability_observations_table,
)
from aima_ugc.modules.content.extended_tables import (
    comment_locations_table,
    comment_media_table,
    comment_mentions_table,
    comment_thread_coverage_observations_table,
    content_external_ids_table,
    content_locations_table,
    content_media_table,
    content_mentions_table,
    content_topics_table,
)
from aima_ugc.modules.content.source_constraints import register_content_source_constraints
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
from aima_ugc.modules.ingestion.historical_tables import (
    historical_import_campaign_items_table,
    historical_import_campaigns_table,
    processing_import_batch_identities_table,
    processing_import_batch_item_conflicts_table,
    processing_import_batch_items_table,
)
from aima_ugc.modules.ingestion.tables import (
    processing_import_batches_table,
    register_ingestion_schema,
)
from aima_ugc.modules.notification.tables import (
    notification_events_table,
    notification_inbox_items_table,
)
from aima_ugc.modules.reporting.tables import (
    reporting_data_export_items_table,
    reporting_data_exports_table,
)
from aima_ugc.modules.system.tables import (
    audit_events_table,
    global_relevance_config_table,
    keyword_pack_items_table,
    keyword_packs_table,
    keywords_table,
    provider_configs_table,
    system_settings_table,
)
from aima_ugc.modules.vehicles.tables import (
    content_vehicle_evidence_table,
    content_vehicle_review_locks_table,
    keyword_pack_vehicle_models_table,
    vehicle_catalog_versions_table,
    vehicle_model_aliases_table,
    vehicle_models_table,
)
from aima_ugc.platform.database.metadata import metadata
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from aima_ugc.platform.storage.tables import artifacts_table

register_scheduler_schema()
register_content_source_constraints()
register_ingestion_schema()

__all__ = [
    "analysis_content_label_pairs_table",
    "analysis_content_manual_overrides_table",
    "analysis_content_relevance_reviews_table",
    "analysis_content_request_items_table",
    "analysis_content_requests_table",
    "analysis_content_results_table",
    "analysis_content_run_targets_table",
    "analysis_content_runs_table",
    "analysis_scheme_versions_table",
    "analysis_schemes_table",
    "account_external_ids_table",
    "accounts_table",
    "artifacts_table",
    "audit_events_table",
    "global_relevance_config_table",
    "historical_import_campaign_items_table",
    "historical_import_campaigns_table",
    "collection_candidate_ingestions_table",
    "collection_candidates_table",
    "collection_content_actions_table",
    "collection_plan_decision_policies_table",
    "collection_plan_keyword_packs_table",
    "collection_plan_platforms_table",
    "collection_plan_vehicle_models_table",
    "collection_plans_table",
    "collection_runs_table",
    "collection_schedule_occurrences_table",
    "collection_scopes_table",
    "comment_coverage_observations_table",
    "comment_locations_table",
    "comment_media_table",
    "comment_mentions_table",
    "comment_metric_observations_table",
    "comment_thread_coverage_observations_table",
    "comment_versions_table",
    "comments_table",
    "content_external_ids_table",
    "content_locations_table",
    "content_media_table",
    "content_mentions_table",
    "content_metric_observations_table",
    "content_availability_observations_table",
    "content_topics_table",
    "content_versions_table",
    "contents_table",
    "job_attempt_events_table",
    "jobs_table",
    "keyword_pack_vehicle_models_table",
    "keyword_pack_items_table",
    "keyword_packs_table",
    "keywords_table",
    "metadata",
    "notification_events_table",
    "notification_inbox_items_table",
    "processing_import_batches_table",
    "processing_import_batch_identities_table",
    "processing_import_batch_item_conflicts_table",
    "processing_import_batch_items_table",
    "provider_configs_table",
    "provider_request_attempts_table",
    "provider_requests_table",
    "reporting_data_export_items_table",
    "reporting_data_exports_table",
    "system_settings_table",
    "content_vehicle_evidence_table",
    "content_vehicle_review_locks_table",
    "vehicle_catalog_versions_table",
    "vehicle_model_aliases_table",
    "vehicle_models_table",
]
