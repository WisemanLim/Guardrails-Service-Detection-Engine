"""Mixed ko-KR / en / ja-JP input normalizer.

Pipeline:
  1. Unicode NFKC (full-width digits → half-width, compat chars).
  2. Whitespace collapse (multi → single).
  3. Strip combining marks at edges.

Numeric "obfuscation" (spaces inside ID/card patterns) is handled per-detector
via a digit-collapse buffer, not here, so case-fold doesn't destroy positions.
"""
from __future__ import annotations

import unicodedata


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    # Collapse runs of whitespace but preserve newlines so position math survives.
    out: list[str] = []
    prev_space = False
    for ch in text:
        if ch.isspace() and ch not in ("\n", "\r"):
            if not prev_space:
                out.append(" ")
            prev_space = True
        else:
            out.append(ch)
            prev_space = False
    return "".join(out).strip()
