"""采集业务模块。"""

from .decision import CollectionDecisionService
from .execution import (
    CollectionExecution,
    CollectionExecutionService,
    CollectionRunRecord,
    CollectionScopeDefinition,
    CollectionScopeRecord,
    DuplicateCollectionScopeError,
    InvalidCollectionRunPlanBindingError,
    UnsupportedCollectionTriggerError,
)
from .planning import (
    CollectionPlanDefinition,
    CollectionPlanningService,
    CollectionPlanRecord,
    CollectionScheduleOccurrenceRecord,
    DuplicatePlanKeywordPackError,
    DuplicatePlanPlatformError,
    PlanPlatformDefinition,
    UnsafePlanConfigError,
    UnsupportedPlanTimezoneError,
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
    "CollectionPlanDefinition",
    "CollectionPlanningService",
    "CollectionPlanRecord",
    "CollectionRunRecord",
    "CollectionScheduleOccurrenceRecord",
    "CollectionScopeDefinition",
    "CollectionScopeRecord",
    "DuplicateCollectionScopeError",
    "DuplicatePlanKeywordPackError",
    "DuplicatePlanPlatformError",
    "InvalidCollectionRunPlanBindingError",
    "PlanPlatformDefinition",
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
    "UnsafePlanConfigError",
    "UnsupportedCollectionTriggerError",
    "UnsupportedPlanTimezoneError",
]
