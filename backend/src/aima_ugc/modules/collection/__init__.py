"""采集业务模块。"""

from .execution import (
    CollectionExecution,
    CollectionExecutionService,
    CollectionRunRecord,
    CollectionScopeDefinition,
    CollectionScopeRecord,
    DuplicateCollectionScopeError,
    UnsupportedCollectionTriggerError,
)

__all__ = [
    "CollectionExecution",
    "CollectionExecutionService",
    "CollectionRunRecord",
    "CollectionScopeDefinition",
    "CollectionScopeRecord",
    "DuplicateCollectionScopeError",
    "UnsupportedCollectionTriggerError",
]
