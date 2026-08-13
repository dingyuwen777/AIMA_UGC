"""Canonical V1 来源追溯结构。"""

from .base import CanonicalBaseModel


class CanonicalSourceV1(CanonicalBaseModel):
    provider_name: str
