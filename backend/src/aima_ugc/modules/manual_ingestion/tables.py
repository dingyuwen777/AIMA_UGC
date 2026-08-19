"""兼容导入；Stage 8A 正式 Schema Owner 位于 ``modules.ingestion``。"""

from aima_ugc.modules.ingestion.tables import (
    processing_import_batches_table,
)
from aima_ugc.modules.ingestion.tables import (
    register_ingestion_schema as register_manual_ingestion_schema,
)

__all__ = ["processing_import_batches_table", "register_manual_ingestion_schema"]
