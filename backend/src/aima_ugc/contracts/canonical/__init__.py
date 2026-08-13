"""AIMA Canonical V1 公共契约。"""

from .author import CanonicalAuthorV1
from .comment import CanonicalCommentV1
from .content import CanonicalContentV1
from .media import (
    CanonicalLocationV1,
    CanonicalMediaV1,
    CanonicalMentionV1,
    CanonicalTopicV1,
)
from .metrics import CanonicalMetricsV1
from .source import CanonicalSourceV1

__all__ = [
    "CanonicalAuthorV1",
    "CanonicalCommentV1",
    "CanonicalContentV1",
    "CanonicalLocationV1",
    "CanonicalMediaV1",
    "CanonicalMentionV1",
    "CanonicalMetricsV1",
    "CanonicalSourceV1",
    "CanonicalTopicV1",
]
