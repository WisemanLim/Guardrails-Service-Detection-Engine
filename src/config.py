import os
from dataclasses import dataclass, field
from typing import List


def _csv(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    port: int = int(os.getenv("PORT", "8081"))
    log_level: str = os.getenv("LOG_LEVEL", "info")
    enabled_domains: List[str] = field(
        default_factory=lambda: _csv("GUARDRAILS_ENABLED_DOMAINS", "global")
    )
    enabled_locales: List[str] = field(
        default_factory=lambda: _csv("GUARDRAILS_LOCALES", "ko-KR,en")
    )


settings = Settings()
