"""当前应用 Schema 的机器注册入口。"""

from aima_ugc.modules.system.tables import audit_events_table, system_settings_table
from aima_ugc.platform.database.metadata import metadata
from aima_ugc.platform.storage.tables import artifacts_table

__all__ = ["artifacts_table", "audit_events_table", "metadata", "system_settings_table"]
