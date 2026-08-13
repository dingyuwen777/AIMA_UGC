"""AIMA Canonical V1 公共契约。"""

from .aggregate import (
    CanonicalAggregateSystemV1,
    CanonicalCommentCoverageV1,
    CanonicalCommentThreadV1,
    CanonicalContentAggregateV1,
)
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
    "CanonicalAggregateSystemV1",
    "CanonicalAuthorV1",
    "CanonicalCommentCoverageV1",
    "CanonicalCommentThreadV1",
    "CanonicalCommentV1",
    "CanonicalContentAggregateV1",
    "CanonicalContentV1",
    "CanonicalLocationV1",
    "CanonicalMediaV1",
    "CanonicalMentionV1",
    "CanonicalMetricsV1",
    "CanonicalSourceV1",
    "CanonicalTopicV1",
]
