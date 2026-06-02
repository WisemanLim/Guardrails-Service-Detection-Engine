"""Boot-time detector wiring. Each phase adds a register_<phase>() call.

P1: register_global_privacy()    — domain-agnostic PII baseline (detectors
    carry domain="global"/"*", so registry.resolve() includes them for every
    request domain). The Policy-side "privacy" leaf domain reuses this same
    baseline — no separate detector module is required for it.
P2: register_manufacturing_food() — placeholder, not yet implemented.

The "privacy" domain is intentionally NOT gated here: enabling it on the
Policy side toggles the 245-rule bundle, while detection's PII patterns ride
the always-on "global" baseline.
"""
from __future__ import annotations

from typing import Iterable

from .registry import DetectorRegistry


def bootstrap_builtins(reg: DetectorRegistry, *, enabled_domains: Iterable[str]) -> None:
    domains = set(enabled_domains)
    if "global" in domains:
        from .global_privacy import register_global_privacy
        register_global_privacy(reg)
    if "manufacturing-food" in domains:
        try:
            from .manufacturing_food import register_manufacturing_food  # type: ignore
        except ImportError:
            # P2 bundle not yet shipped — silently skip.
            return
        register_manufacturing_food(reg)
