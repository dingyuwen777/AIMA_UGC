"""Collection 模块的 Provider-neutral 生产入口。"""

from .raw_artifact import (
    CapturedRawArtifact,
    RawArtifactIntegrityError,
    RawArtifactService,
    raw_storage_key,
)
from .transport import (
    ProviderClient,
    ProviderDispatchResult,
    ProviderTransport,
    ProviderTransportFailure,
    ProviderTransportRequest,
    ProviderTransportResponse,
)

__all__ = [
    "CapturedRawArtifact",
    "ProviderClient",
    "ProviderDispatchResult",
    "ProviderTransport",
    "ProviderTransportFailure",
    "ProviderTransportRequest",
    "ProviderTransportResponse",
    "RawArtifactIntegrityError",
    "RawArtifactService",
    "raw_storage_key",
]
