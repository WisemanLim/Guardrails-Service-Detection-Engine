"""Phase 1 — domain-agnostic privacy detectors.

Each detector is a thin wrapper over `regex` with optional checksum gating.
All run in O(n) and have no external model dependency, so they boot cold
in <50ms.
"""
from __future__ import annotations

from typing import Iterable, List

import regex as re

from .base import Detector
from .luhn import luhn_valid
from .registry import DetectorRegistry


class RegexDetector(Detector):
    def __init__(
        self,
        *,
        detector_id: str,
        pattern: str,
        category: str,
        sub_category: str,
        locales: List[str],
        io_types: List[str],
        confidence: float,
        rule_hint: str,
        domain: str = "global",
        flags: int = re.IGNORECASE,
        luhn: bool = False,
    ) -> None:
        self.detector_id = detector_id
        self.domain = domain
        self.locales = locales
        self.io_types = io_types
        self.category = category
        self.sub_category = sub_category
        self._pattern = re.compile(pattern, flags)
        self._confidence = confidence
        self._rule_hint = rule_hint
        self._luhn = luhn

    def scan(self, text: str) -> Iterable[dict]:
        for m in self._pattern.finditer(text):
            matched = m.group(0)
            if self._luhn:
                digits = "".join(ch for ch in matched if ch.isdigit())
                if not luhn_valid(digits):
                    continue
            yield {
                "detector_id": self.detector_id,
                "category": self.category,
                "sub_category": self.sub_category,
                "locale": self.locales[0],
                "start": m.start(),
                "end": m.end(),
                "matched_text": matched,
                "confidence": self._confidence,
                "rule_hint": self._rule_hint,
            }


def register_global_privacy(reg: DetectorRegistry) -> None:
    DETECTORS: list[Detector] = [
        # Korean Resident Registration Number — XXXXXX-Y...... (13 digits).
        RegexDetector(
            detector_id="pii.id.rrn.kr",
            pattern=r"\b\d{6}[- ]?\d{7}\b",
            category="pii",
            sub_category="national_id_kr",
            locales=["ko-KR", "*"],
            io_types=["input", "output"],
            confidence=0.98,
            rule_hint="PRIV_ID_IN_001",
        ),
        # US SSN.
        RegexDetector(
            detector_id="pii.id.ssn.us",
            pattern=r"\b(?!000|666)[0-8]\d{2}[- ]\d{2}[- ]\d{4}\b",
            category="pii",
            sub_category="ssn_us",
            locales=["en", "*"],
            io_types=["input", "output"],
            confidence=0.97,
            rule_hint="PRIV_ID_IN_002",
        ),
        # Japan MyNumber (12 digits, often grouped).
        RegexDetector(
            detector_id="pii.id.mynumber.jp",
            pattern=r"\b\d{4}[- ]?\d{4}[- ]?\d{4}\b",
            category="pii",
            sub_category="mynumber_jp",
            locales=["ja-JP", "*"],
            io_types=["input", "output"],
            confidence=0.85,
            rule_hint="PRIV_ID_IN_003",
        ),
        # Generic passport (1 letter + 7-9 digits) — heuristic, mid confidence.
        RegexDetector(
            detector_id="pii.id.passport",
            pattern=r"\b[A-Z]\d{7,9}\b",
            category="pii",
            sub_category="passport",
            locales=["*"],
            io_types=["input", "output"],
            confidence=0.75,
            rule_hint="PRIV_ID_IN_004",
        ),
        # Email.
        RegexDetector(
            detector_id="pii.contact.email",
            pattern=r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
            category="pii",
            sub_category="email",
            locales=["*"],
            io_types=["input", "output"],
            confidence=0.95,
            rule_hint="PRIV_CONTACT_IN_001",
        ),
        # Korean mobile.
        RegexDetector(
            detector_id="pii.contact.phone.kr",
            pattern=r"\b01[016789][- .]?\d{3,4}[- .]?\d{4}\b",
            category="pii",
            sub_category="phone_kr",
            locales=["ko-KR", "*"],
            io_types=["input", "output"],
            confidence=0.95,
            rule_hint="PRIV_CONTACT_IN_002",
        ),
        # NANP / E.164-ish US phone.
        RegexDetector(
            detector_id="pii.contact.phone.us",
            pattern=r"\b(?:\+?1[- .]?)?\(?\d{3}\)?[- .]?\d{3}[- .]?\d{4}\b",
            category="pii",
            sub_category="phone_us",
            locales=["en", "*"],
            io_types=["input", "output"],
            confidence=0.80,
            rule_hint="PRIV_CONTACT_IN_003",
        ),
        # Credit card with Luhn gate.
        RegexDetector(
            detector_id="pii.financial.card",
            pattern=r"\b(?:\d[ -]*?){13,19}\b",
            category="pii",
            sub_category="card_number",
            locales=["*"],
            io_types=["input", "output"],
            confidence=0.96,
            rule_hint="PRIV_FIN_IN_001",
            luhn=True,
        ),
        # IBAN.
        RegexDetector(
            detector_id="pii.financial.iban",
            pattern=r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
            category="pii",
            sub_category="iban",
            locales=["*"],
            io_types=["input", "output"],
            confidence=0.90,
            rule_hint="PRIV_FIN_IN_002",
        ),
        # Generic API-key shape.
        RegexDetector(
            detector_id="credentials.api_key",
            pattern=r"\b(?:sk|pk|api|key|token)[_-][A-Za-z0-9_-]{16,}\b",
            category="credentials",
            sub_category="api_key",
            locales=["*"],
            io_types=["input", "output"],
            confidence=0.92,
            rule_hint="PRIV_CRED_IN_002",
        ),
        # Korean driver's license (XX-XX-XXXXXX-XX-like).
        RegexDetector(
            detector_id="pii.id.driver_license.kr",
            pattern=r"\b\d{2}[- ]?\d{2}[- ]?\d{6}[- ]?\d{2}\b",
            category="pii",
            sub_category="driver_license_kr",
            locales=["ko-KR", "*"],
            io_types=["input", "output"],
            confidence=0.80,
            rule_hint="PRIV_ID_IN_005",
        ),
        # Korean business registration number 사업자등록번호.
        RegexDetector(
            detector_id="pii.id.brn.kr",
            pattern=r"\b\d{3}-\d{2}-\d{5}\b",
            category="pii",
            sub_category="business_reg_kr",
            locales=["ko-KR", "*"],
            io_types=["input", "output"],
            confidence=0.70,
            rule_hint="PRIV_ID_IN_006",
        ),
        # IPv4 (telemetry / log PII when combined with user_id).
        RegexDetector(
            detector_id="pii.log.ipv4",
            pattern=r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b",
            category="pii",
            sub_category="ip_address",
            locales=["*"],
            io_types=["input", "output"],
            confidence=0.60,
            rule_hint="PRIV_LOG_IN_001",
        ),
    ]
    for d in DETECTORS:
        reg.register(d)
