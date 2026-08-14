"""采集业务模块。"""

from .decision import CollectionDecisionService
from .execution import (
    CollectionExecution,
    CollectionExecutionService,
    CollectionRunRecord,
    CollectionScopeDefinition,
    CollectionScopeRecord,
    DuplicateCollectionScopeError,
    UnsupportedCollectionTriggerError,
)
from .provider_dispatch import (
    ProviderDispatchOutcome,
    ProviderDispatchPreparation,
    ProviderDispatchService,
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
from .provider_recovery import (
    ProviderAttemptReconciler,
    ProviderRecoveryCandidate,
)

__all__ = [
    "CollectionDecisionService",
    "CollectionExecution",
    "CollectionExecutionService",
    "CollectionRunRecord",
    "CollectionScopeDefinition",
    "CollectionScopeRecord",
    "DuplicateCollectionScopeError",
    "PreparedProviderAttempt",
    "ProviderAttemptRecord",
    "ProviderAttemptReconciler",
    "ProviderDispatchOutcome",
    "ProviderDispatchPreparation",
    "ProviderDispatchService",
    "ProviderRecoveryCandidate",
    "ProviderPersistenceConflictError",
    "ProviderPersistenceService",
    "ProviderRequestLineageMismatchError",
    "ProviderRequestNotFoundError",
    "ProviderRequestRecord",
    "ProviderScopeNotFoundError",
    "UnsupportedCollectionTriggerError",
]
