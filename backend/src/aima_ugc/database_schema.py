"""当前应用 Schema 的机器注册入口。"""

from aima_ugc.modules.collection.tables import (
    collection_runs_table,
    collection_scopes_table,
    provider_request_attempts_table,
    provider_requests_table,
)
from aima_ugc.modules.system.tables import audit_events_table, system_settings_table
from aima_ugc.platform.database.metadata import metadata
from aima_ugc.platform.jobs.tables import job_attempt_events_table, jobs_table
from aima_ugc.platform.storage.tables import artifacts_table

__all__ = [
    "artifacts_table",
    "audit_events_table",
    "collection_runs_table",
    "collection_scopes_table",
    "job_attempt_events_table",
    "jobs_table",
    "metadata",
    "provider_request_attempts_table",
    "provider_requests_table",
    "system_settings_table",
]
