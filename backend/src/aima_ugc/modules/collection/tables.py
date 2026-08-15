"""Collection 模块拥有的 Run/Scope、Provider Request/Attempt 与预算账本表。"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint

from aima_ugc.platform.database.metadata import metadata

collection_runs_table = Table(
    "collection_runs",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("job_id", Uuid(), ForeignKey("jobs.id"), nullable=False),
    Column("trigger_type", Text(), nullable=False),
    Column("config_snapshot", JSONB(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("requested_count", Integer(), nullable=False, server_default=text("0")),
    Column("succeeded_count", Integer(), nullable=False, server_default=text("0")),
    Column("failed_count", Integer(), nullable=False, server_default=text("0")),
    Column("content_count", Integer(), nullable=False, server_default=text("0")),
    Column("comment_count", Integer(), nullable=False, server_default=text("0")),
    Column("error_summary", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_id"),
    CheckConstraint(
        "trigger_type in ('manual','api','backfill')",
        name="trigger_type_allowed",
    ),
    CheckConstraint(
        "status in ('queued','running','partial_success','succeeded','failed','cancelled')",
        name="status_allowed",
    ),
    CheckConstraint(
        "requested_count >= 0 and succeeded_count >= 0 and failed_count >= 0 "
        "and content_count >= 0 and comment_count >= 0",
        name="counts_nonnegative",
    ),
    info={"owner": "collection"},
)

collection_scopes_table = Table(
    "collection_scopes",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("run_id", Uuid(), ForeignKey("collection_runs.id"), nullable=False),
    Column("platform", Text(), nullable=False),
    Column("source_type", Text(), nullable=False),
    Column("source_value", Text(), nullable=False),
    Column("operation_group", Text(), nullable=False),
    Column("status", Text(), nullable=False),
    Column(
        "pagination_state",
        JSONB(),
        nullable=False,
        server_default=text("'{}'::jsonb"),
    ),
    Column("progress", Integer(), nullable=False, server_default=text("0")),
    Column("stop_reason", Text()),
    Column("stats", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    UniqueConstraint("run_id", "platform", "source_type", "source_value", "operation_group"),
    info={"owner": "collection"},
)

provider_requests_table = Table(
    "provider_requests",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("scope_id", Uuid(), ForeignKey("collection_scopes.id"), nullable=False),
    Column("provider_config_id", Uuid(), ForeignKey("provider_configs.id")),
    Column("provider", Text(), nullable=False),
    Column("operation", Text(), nullable=False),
    Column("request_fingerprint", Text(), nullable=False),
    Column("request_params", JSONB(), nullable=False),
    Column(
        "pagination_input",
        JSONB(),
        nullable=False,
        server_default=text("'{}'::jsonb"),
    ),
    Column("status", Text(), nullable=False),
    Column("attempt_count", Integer(), nullable=False, server_default=text("0")),
    Column("estimated_cost", Numeric(18, 6), nullable=False, server_default=text("0")),
    Column("actual_cost", Numeric(18, 6), nullable=False, server_default=text("0")),
    Column("cost_currency", Text()),
    Column("cost_unit", Text()),
    Column("unit_price_snapshot", Numeric(18, 6)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Column("error_code", Text()),
    Column("error_detail", Text()),
    UniqueConstraint("scope_id", "request_fingerprint"),
    CheckConstraint("char_length(provider) > 0", name="provider_nonempty"),
    CheckConstraint("char_length(operation) > 0", name="operation_nonempty"),
    CheckConstraint("char_length(status) > 0", name="status_nonempty"),
    CheckConstraint(
        "status in ('pending','dispatching','completed','not_sent','unknown')",
        name="status_allowed",
    ),
    CheckConstraint(
        "request_fingerprint ~ '^[0-9a-f]{64}$'",
        name="request_fingerprint_sha256",
    ),
    CheckConstraint(
        "jsonb_typeof(request_params) = 'object'",
        name="request_params_object",
    ),
    CheckConstraint(
        "jsonb_typeof(pagination_input) = 'object'",
        name="pagination_input_object",
    ),
    CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
    CheckConstraint(
        "estimated_cost >= 0 and actual_cost >= 0 "
        "and (unit_price_snapshot is null or unit_price_snapshot >= 0)",
        name="costs_nonnegative",
    ),
    CheckConstraint(
        "cost_currency is null or cost_currency ~ '^[A-Z]{3}$'",
        name="cost_currency_format",
    ),
    info={"owner": "collection"},
)

provider_request_attempts_table = Table(
    "provider_request_attempts",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column(
        "provider_request_id",
        Uuid(),
        ForeignKey("provider_requests.id"),
        nullable=False,
    ),
    Column("attempt_no", Integer(), nullable=False),
    Column("dispatch_status", Text(), nullable=False),
    Column("dispatch_started_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
    Column("http_status", Integer()),
    Column("external_request_id", Text()),
    Column("raw_artifact_id", Uuid(), ForeignKey("artifacts.id")),
    Column("estimated_cost", Numeric(18, 6), nullable=False, server_default=text("0")),
    Column("actual_cost", Numeric(18, 6), nullable=False, server_default=text("0")),
    Column("cost_currency", Text()),
    Column("cost_unit", Text()),
    Column("unit_price_snapshot", Numeric(18, 6)),
    Column("billing_status", Text(), nullable=False),
    Column(
        "potential_duplicate_charge",
        Boolean(),
        nullable=False,
        server_default=text("false"),
    ),
    Column("error_code", Text()),
    Column("error_detail", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("provider_request_id", "attempt_no"),
    UniqueConstraint("id", "provider_request_id"),
    CheckConstraint("attempt_no >= 1", name="attempt_no_positive"),
    CheckConstraint(
        "dispatch_status in ('reserved','dispatching','completed','not_sent','unknown')",
        name="dispatch_status_allowed",
    ),
    CheckConstraint(
        "(dispatch_status = 'reserved' and dispatch_started_at is null "
        "and completed_at is null) or "
        "(dispatch_status = 'dispatching' and dispatch_started_at is not null "
        "and completed_at is null) or "
        "(dispatch_status = 'not_sent' and dispatch_started_at is null "
        "and completed_at is not null) or "
        "(dispatch_status in ('completed','unknown') and dispatch_started_at is not null "
        "and completed_at is not null)",
        name="dispatch_times_consistent",
    ),
    CheckConstraint(
        "dispatch_status not in ('reserved','dispatching') or raw_artifact_id is null",
        name="unfinished_has_no_raw",
    ),
    CheckConstraint(
        "completed_at is null or completed_at >= created_at",
        name="completed_after_created",
    ),
    CheckConstraint(
        "dispatch_started_at is null or completed_at is null "
        "or completed_at >= dispatch_started_at",
        name="completed_after_dispatch",
    ),
    CheckConstraint(
        "http_status is null or http_status between 100 and 599",
        name="http_status_range",
    ),
    CheckConstraint(
        "billing_status in ('not_billable','estimated','confirmed','unknown')",
        name="billing_status_allowed",
    ),
    CheckConstraint(
        "estimated_cost >= 0 and actual_cost >= 0 "
        "and (unit_price_snapshot is null or unit_price_snapshot >= 0)",
        name="costs_nonnegative",
    ),
    CheckConstraint(
        "cost_currency is null or cost_currency ~ '^[A-Z]{3}$'",
        name="cost_currency_format",
    ),
    CheckConstraint(
        "billing_status <> 'not_billable' or "
        "(estimated_cost = 0 and actual_cost = 0 "
        "and coalesce(unit_price_snapshot, 0) = 0)",
        name="not_billable_has_zero_cost",
    ),
    CheckConstraint(
        "billing_status <> 'confirmed' or cost_currency is not null",
        name="confirmed_has_currency",
    ),
    CheckConstraint(
        "dispatch_status <> 'not_sent' or "
        "(billing_status = 'not_billable' and potential_duplicate_charge = false "
        "and error_code is not null and error_detail is not null)",
        name="not_sent_consistent",
    ),
    CheckConstraint(
        "dispatch_status <> 'unknown' or "
        "(billing_status = 'unknown' and potential_duplicate_charge = true "
        "and error_code is not null and error_detail is not null)",
        name="unknown_consistent",
    ),
    info={"owner": "collection"},
)

provider_budget_accounts_table = Table(
    "provider_budget_accounts",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column("provider_config_id", Uuid(), ForeignKey("provider_configs.id"), nullable=False),
    Column("scope_type", Text(), nullable=False),
    Column("scope_key", Text(), nullable=False),
    Column("run_id", Uuid(), ForeignKey("collection_runs.id")),
    Column("content_id", Uuid(), ForeignKey("contents.id")),
    Column("period_start", DateTime(timezone=True), nullable=False),
    Column("period_end", DateTime(timezone=True), nullable=False),
    Column("dimension", Text(), nullable=False),
    Column("unit", Text(), nullable=False),
    Column("limit_amount", Numeric(18, 6), nullable=False),
    Column("reserved_amount", Numeric(18, 6), nullable=False, server_default=text("0")),
    Column("settled_amount", Numeric(18, 6), nullable=False, server_default=text("0")),
    Column("unknown_amount", Numeric(18, 6), nullable=False, server_default=text("0")),
    Column("enabled", Boolean(), nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "provider_config_id",
        "scope_key",
        "period_start",
        "dimension",
        "unit",
    ),
    CheckConstraint(
        "scope_type in ('global','run','run_comments','content_comments')",
        name="scope_type_allowed",
    ),
    CheckConstraint("period_end > period_start", name="period_valid"),
    CheckConstraint(
        "dimension in ('request_count','monetary_cost')",
        name="dimension_allowed",
    ),
    CheckConstraint(
        "(dimension = 'request_count' and unit = 'request') or "
        "(dimension = 'monetary_cost' and unit ~ '^[A-Z]{3}$')",
        name="dimension_unit_consistent",
    ),
    CheckConstraint(
        "limit_amount >= 0 and reserved_amount >= 0 and settled_amount >= 0 "
        "and unknown_amount >= 0",
        name="amounts_nonnegative",
    ),
    CheckConstraint(
        "(scope_type = 'global' and run_id is null and content_id is null "
        "and scope_key = 'global') or "
        "(scope_type = 'run' and run_id is not null and content_id is null "
        "and scope_key = 'run:' || run_id::text) or "
        "(scope_type = 'run_comments' and run_id is not null and content_id is null "
        "and scope_key = 'run_comments:' || run_id::text) or "
        "(scope_type = 'content_comments' and content_id is not null and run_id is null "
        "and scope_key = 'content_comments:' || content_id::text)",
        name="scope_identity_consistent",
    ),
    ExcludeConstraint(
        ("provider_config_id", "="),
        ("scope_key", "="),
        ("dimension", "="),
        ("unit", "="),
        (func.tstzrange(Column("period_start"), Column("period_end"), "[)"), "&&"),
        name="ex_provider_budget_accounts_no_overlap",
        using="gist",
    ),
    info={"owner": "collection"},
)

provider_budget_reservations_table = Table(
    "provider_budget_reservations",
    metadata,
    Column("id", Uuid(), primary_key=True),
    Column(
        "budget_account_id",
        Uuid(),
        ForeignKey("provider_budget_accounts.id"),
        nullable=False,
    ),
    Column("provider_request_id", Uuid(), ForeignKey("provider_requests.id"), nullable=False),
    Column("provider_request_attempt_id", Uuid(), nullable=False),
    Column("reserved_amount", Numeric(18, 6), nullable=False),
    Column("settled_amount", Numeric(18, 6)),
    Column("status", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("budget_account_id", "provider_request_attempt_id"),
    ForeignKeyConstraint(
        ["provider_request_attempt_id", "provider_request_id"],
        ["provider_request_attempts.id", "provider_request_attempts.provider_request_id"],
    ),
    CheckConstraint(
        "reserved_amount >= 0 and (settled_amount is null or settled_amount >= 0)",
        name="amounts_nonnegative",
    ),
    CheckConstraint(
        "status in ('reserved','settled','released','unknown')",
        name="status_allowed",
    ),
    CheckConstraint(
        "(status in ('reserved','unknown') and settled_amount is null) or "
        "(status = 'settled' and settled_amount is not null) or "
        "(status = 'released' and coalesce(settled_amount, 0) = 0)",
        name="status_amount_consistent",
    ),
    info={"owner": "collection"},
)

Index(
    "ix_collection_runs_status_created_at",
    collection_runs_table.c.status,
    collection_runs_table.c.created_at.desc(),
)
Index(
    "ix_collection_scopes_run_id_status",
    collection_scopes_table.c.run_id,
    collection_scopes_table.c.status,
)
Index(
    "ix_provider_requests_scope_id_created_at",
    provider_requests_table.c.scope_id,
    provider_requests_table.c.created_at,
)
Index(
    "ix_provider_attempts_dispatch_status_started_at",
    provider_request_attempts_table.c.dispatch_status,
    provider_request_attempts_table.c.dispatch_started_at,
)
Index(
    "ix_provider_request_attempts_completed_at",
    provider_request_attempts_table.c.completed_at,
)
Index(
    "ix_provider_budget_accounts_provider_config_id_period",
    provider_budget_accounts_table.c.provider_config_id,
    provider_budget_accounts_table.c.period_start,
    provider_budget_accounts_table.c.period_end,
)
Index(
    "ix_provider_budget_reservations_attempt_id",
    provider_budget_reservations_table.c.provider_request_attempt_id,
)
