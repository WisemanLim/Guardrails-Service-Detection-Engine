"""Detector registry. Domain-scoped, swappable, hot-extensible.

Phase rollout contract:
  P1 enables {"global"}.
  P2 will additionally register detectors for "manufacturing-food" without
  touching P1 behavior. The registry filters by enabled_domains at boot
  (via bootstrap_builtins) and per-request via resolve(domain=...).
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from .base import Detector


class DetectorRegistry:
    def __init__(self) -> None:
        self._detectors: List[Detector] = []

    def register(self, detector: Detector) -> None:
        self._detectors.append(detector)

    def list_ids(self) -> List[str]:
        return [d.detector_id for d in self._detectors]

    def resolve(
        self,
        *,
        domain: str,
        locale: str,
        io_type: str,
        categories: Optional[List[str]] = None,
    ) -> Iterable[Detector]:
        for d in self._detectors:
            if d.domain not in {"*", domain, "global"}:
                continue
            if locale not in d.locales and "*" not in d.locales:
                continue
            if io_type not in d.io_types and "both" not in d.io_types:
                continue
            if categories and d.category not in categories:
                continue
            yield d


registry = DetectorRegistry()
