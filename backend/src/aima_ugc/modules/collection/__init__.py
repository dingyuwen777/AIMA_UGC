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
from .provider_persistence import (
    PreparedProviderAttempt,
    ProviderAttemptRecord,
    ProviderPersistenceConflictError,
    ProviderPersistenceService,
    ProviderRequestLineageMismatchError,
    ProviderRequestNotFoundError,
    ProviderRequestRecord,
    ProviderScopeNotFoundError,
)

__all__ = [
    "CollectionExecution",
    "CollectionExecutionService",
    "CollectionRunRecord",
    "CollectionScopeDefinition",
    "CollectionScopeRecord",
    "DuplicateCollectionScopeError",
    "PreparedProviderAttempt",
    "ProviderAttemptRecord",
    "ProviderPersistenceConflictError",
    "ProviderPersistenceService",
    "ProviderRequestLineageMismatchError",
    "ProviderRequestNotFoundError",
    "ProviderRequestRecord",
    "ProviderScopeNotFoundError",
    "UnsupportedCollectionTriggerError",
]
