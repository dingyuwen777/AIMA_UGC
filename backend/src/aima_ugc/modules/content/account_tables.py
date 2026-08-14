"""Content 模块拥有的账号备用稳定外部 ID 表。"""

from sqlalchemy import Column, ForeignKey, Table, Text, UniqueConstraint, Uuid

from aima_ugc.platform.database.metadata import metadata

account_external_ids_table = Table(
    "account_external_ids",
    metadata,
    Column("account_id", Uuid(), ForeignKey("accounts.id"), nullable=False),
    Column("id_type", Text(), nullable=False),
    Column("external_id", Text(), nullable=False),
    UniqueConstraint("account_id", "id_type"),
    UniqueConstraint("id_type", "external_id"),
    info={"owner": "content"},
)
