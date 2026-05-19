"""Detector contract. Every detector is plug-in–style so future domains
(P2 manufacturing-food, P3+) only need to register additional concrete classes.

Implementations live under src/detectors/<domain>/...; the registry maps
(domain, locale, io_type) tuples to a list of detectors at boot.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List


class Detector(ABC):
    detector_id: str
    domain: str
    locales: List[str]
    io_types: List[str]
    category: str
    sub_category: str

    @abstractmethod
    def scan(self, text: str) -> Iterable[dict]:
        """Yield match dicts with keys:
        detector_id, category, sub_category, locale, start, end,
        matched_text, confidence, rule_hint (optional).
        """
        ...
