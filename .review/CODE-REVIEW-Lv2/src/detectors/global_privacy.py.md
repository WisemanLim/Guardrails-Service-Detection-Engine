# `src/detectors/global_privacy.py` — File Review (Level 2)

## Pre-Review Header

- 역할: P1 PII detector 13개 + 공통 `RegexDetector` 베이스 클래스 정의 및 일괄 등록 함수.
- 진입점에서의 거리: 2
- 라인 수: 214 (<600 → block-mode 불필요, 단 길이상 블록 나눠 검토)
- 주요 export: `RegexDetector`, `register_global_privacy(reg)`
- 의존 모듈 (internal): `.base.Detector`, `.luhn.luhn_valid`, `.registry.DetectorRegistry`
- 사용된 외부 패키지: `regex` (PCRE 호환)
- 부수효과: `register_global_privacy(reg)` 호출 시 13개 detector를 registry에 append.
- 동시성 모델: detector 인스턴스는 immutable + thread-safe. `regex.compile`이 thread-safe.
- 테스트 커버리지 흔적: 5건 (RRN/SSN/email/card-pass/card-fail).

---

## Block A — `RegexDetector` 클래스 (L1–63)

```python path=src/detectors/global_privacy.py lines=1-63
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
```

**분석 / Analysis (Level 2)**
- L11: `import regex as re` — stdlib `re` 가 아닌 PyPI `regex`. 차이점: Unicode property (`\p{L}`), `\b` Unicode-aware, possessive 양화자 등. 본 파일 패턴이 단순 ASCII라 사실상 stdlib 호환이지만 일관 위해 `regex` 사용.
- L18: `Detector` 상속. abstract `scan` 구현.
- L20–32: `__init__` — `*` 로 키워드-only 강제. 13개 detector 정의가 깔끔.
- L31 `flags: int = re.IGNORECASE` — 기본 case-insensitive. RRN/SSN/카드는 영향 없지만 email 도메인부, API key prefix(`sk_`/`SK_`) 등에 영향. **흔한 실수**: case-insensitive 가 의도치 않게 IBAN `[A-Z]{2}` 부분도 lowercase 통과시킴 → 의도된 노이즈 허용일 수 있음.
- L34–40: 인스턴스 속성 6개 + private 3개. `Detector` ABC의 클래스 annotation 과 1:1 대응.
- L40 `self._pattern = re.compile(pattern, flags)` — 부팅 시점 한 번 컴파일. cold start <50ms 보장의 핵심.
- L45–62: `scan`
  - L46 `self._pattern.finditer(text)` — 전체 문자열 스캔, lazy iterator.
  - L47 `matched = m.group(0)` — 전체 매치 문자열.
  - L48–51 Luhn 게이팅: `_luhn=True` 시만. 실패는 `continue` → 다음 매치.
  - L52–62 dict yield — `Detector` docstring의 9개 키 모두 포함.
  - **L56 `"locale": self.locales[0]`** — locales 리스트의 첫 원소만 응답에 노출. 카드 detector는 `locales=["*"]` 라 응답에 `"locale": "*"` 나옴. 호출자가 `*` 를 받는다는 사실을 명시 안 함 → API 사용자가 혼란 가능.
  - `m.start()` / `m.end()` 는 **정규화된 텍스트 기준** 인덱스. README에 명시되어 있으나 응답에서 추가 강조 가치 있음.

**짚어볼 점 / Watch-outs (Block A)**
- **Pattern flag 통일**: 모든 detector가 IGNORECASE. RRN/SSN/카드/전화/IP는 의미 없으나 IBAN/API key는 IGNORECASE가 입력 폭을 넓힘. 의도된 거면 OK.
- **`scan`이 generator 라 한 번만 소비 가능** — 호출자가 `list(det.scan(norm))` 으로 재사용 의도 시 명확화.
- **컴파일 캐시**: detector 인스턴스 1개당 컴파일 1회. 13개 = 13컴파일. `regex` 모듈은 컴파일된 객체를 재사용 안 한다고 가정.

---

## Block B — `register_global_privacy()` L65–214

13개 detector 정의를 카테고리·locale·confidence와 함께 모아둔 데이터-지향 구간. 패턴별로 별도 검토.

### B-1. RRN (L65–77)

```python path=src/detectors/global_privacy.py lines=65-77
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
```

**분석**
- 패턴 `\b\d{6}[- ]?\d{7}\b` — 6+(separator 0/1)+7. 합계 13자리 숫자.
- `[- ]?` — 하이픈 또는 공백 1개 허용. 다른 separator (·, .) 비허용.
- `confidence=0.98` — 최고치. RRN 형식이 매우 구체적이라 합리.
- **흔한 오탐**: 13자리 무작위 숫자(주문번호 등)도 매치. 첫 자리 1~4 / 7자리 첫 자리 1~4 같은 RRN 규칙 미적용. checksum 미적용 (RRN은 마지막 자리 체크섬 알고리즘 존재).
- locales `["ko-KR", "*"]` — `*` 가 와일드카드 의미라 모든 locale 통과. 자세히는 registry.resolve 의 `"*" not in d.locales` 로직.

### B-2. US SSN (L78–88)

```python path=src/detectors/global_privacy.py lines=78-88
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
```

**분석**
- `(?!000|666)[0-8]\d{2}` — 첫 영역 area number 000/666 제외, 9XX 도 `[0-8]` 로 제외 (SSA 규정과 일치).
- separator `[- ]` 가 required (RRN과 달리 `?` 없음). 공백 또는 하이픈 1개. 9자리 연속 숫자(`123456789`)는 안 잡힘. 우회 가능성.
- `\d{2}` group / `\d{4}` serial — 9자리 합계 OK.
- confidence 0.97.

### B-3. JP MyNumber (L89–98)

```python path=src/detectors/global_privacy.py lines=89-98
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
```

**분석**
- 4-4-4 = 12자리. 일본 마이넘버 표준.
- separator 1개 optional. checksum 미적용.
- confidence 0.85 — 12자리 무작위 숫자 오탐 위험 반영.
- 위험: 카드(13–19자리) 패턴과 부분 겹침. 동일 입력이 두 detector에 매치 가능 → 두 매치 다 응답에 포함. 위험 점수는 max라 무해.

### B-4. Passport (L99–109)

```python path=src/detectors/global_privacy.py lines=99-109
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
```

**분석**
- 1글자 + 7~9숫자. **flags=IGNORECASE** 적용되므로 `[a-z]` 도 매치. 의도가 대문자만이면 `re.IGNORECASE` 를 끄거나 패턴을 `(?-i:[A-Z])` 로 명시.
- 오탐 폭이 매우 큼 — 제품 코드, 항공편(`KE5901`) 등이 매치. 0.75 confidence는 그 인식.

### B-5. Email (L110–121)

```python path=src/detectors/global_privacy.py lines=110-121
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
```

**분석**
- 일반 email regex. RFC 5322 완전 호환은 아니나 99% PII 케이스 커버.
- `\b` 가 한국어/일본어 뒤 email 경계에서 어떻게 동작하는지 — `regex` 모듈의 Unicode-aware `\b` 라 한글/email 사이는 경계로 인식 → 한국어 본문 내 email 잡힘.

### B-6. Phone KR (L122–132)

```python path=src/detectors/global_privacy.py lines=122-132
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
```

**분석**
- `01[016789]` — 010/011/016/017/018/019. 한국 통신사 prefix.
- separator `.` 도 허용. 중간부 3~4자리.
- 오탐 적음. 0.95 합리.

### B-7. Phone US (L133–143)

```python path=src/detectors/global_privacy.py lines=133-143
        # NANP / E.164-ish US phone.
        RegexDetector(
            detector_id="pii.contact.phone.us",
            pattern=r"\b(?:\+?1[- .]?)?\(?\d{3}\)?[- .]?\d{3}[- .]?\d{3}\b",
            category="pii",
            sub_category="phone_us",
            locales=["en", "*"],
            io_types=["input", "output"],
            confidence=0.80,
            rule_hint="PRIV_CONTACT_IN_003",
        ),
```

**분석**
- 옵션 `+1`, 옵션 괄호 `(...)`, 3-3-3 (마지막이 3 아닌 4여야 표준 NANP). **L137 마지막 그룹이 `\d{3}` — 정확한 NANP 형식은 마지막이 4자리** (예: 555-123-4567). 따라서 이 패턴은 10자리 모두 매칭이 아닌 9자리에서 끝남. **버그 의심** — README 표는 "NANP / E.164-ish" 인데 실제 마지막 그룹이 4가 아닌 3. 테스트 케이스 부재로 발견 안 됨.
  - 비교: 다른 통화 통상 패턴은 `\d{4}` 종결.
- confidence 0.80 — 오탐 인식 반영.

### B-8. Card with Luhn (L144–155)

```python path=src/detectors/global_privacy.py lines=144-155
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
```

**분석**
- `\b(?:\d[ -]*?){13,19}\b` — digit + optional separators 반복 13~19회. lazy 양화자.
- **ReDoS 잠재**: `[ -]*?` lazy + `{13,19}` quantifier 조합. 비-digit 산재 입력에서 백트래킹 비용 큼. 단, max_length=200_000 + Pydantic 검증이 1차 cap. 운영 환경에서 실제 시간 측정 필요.
- Luhn gate=True → 정규식 매치 후 digits 추출 → checksum 검증.
- separator `.` 미허용 (점은 IP, IBAN 등과 충돌 회피 의도).

### B-9. IBAN (L156–166)

```python path=src/detectors/global_privacy.py lines=156-166
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
```

**분석**
- 2글자 country + 2 체크digit + 11~30 영숫자. 표준 IBAN 길이 15~34.
- **IGNORECASE** 영향으로 `kr12abc...` 같이 lowercase도 매치. ISO 13616은 uppercase 명시이나 실용적 허용.
- mod-97 체크섬 미적용 — IBAN 표준은 checksum 가능. global_privacy에 luhn만 게이팅 옵션이라 미지원. 오탐 가능성.

### B-10. API key (L167–177)

```python path=src/detectors/global_privacy.py lines=167-177
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
```

**분석**
- prefix `sk_`/`pk_`/`api_`/`key_`/`token_` + 16+ 영숫자 (또는 `_`/`-`).
- IGNORECASE → `SK_...`, `Sk_...` 도 매치.
- 16자 lower bound 가 짧음 — `sk_1234567890123456` (16자) 까지 매치. Stripe `sk_` 는 보통 24+. false negative보다 false positive 비중 큼.
- rule_hint `PRIV_CRED_IN_002` — `_001` 이 다른 곳에 있는지 확인 필요 (현 파일 grep 결과 없음, 향후 추가 예약 자리).

### B-11. KR Driver License (L178–188)

```python path=src/detectors/global_privacy.py lines=178-188
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
```

**분석**
- 2-2-6-2 = 12자리. README와 일치.
- 카드 13-19 패턴과 부분 겹침 (12자리는 카드보다 짧음). 동일 입력이 두 detector 적용 가능.

### B-12. KR Business Registration Number (L189–199)

```python path=src/detectors/global_privacy.py lines=189-199
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
```

**분석**
- 3-2-5 = 10자리. **하이픈 required** (`?` 없음). 공백 separator 미지원.
- confidence 0.70 — 가장 낮음. 사업자등록번호는 checksum 알고리즘 있으나 미적용.

### B-13. IPv4 (L200–210)

```python path=src/detectors/global_privacy.py lines=200-210
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
```

**분석**
- 표준 IPv4 옥텟 검증 패턴. 25[0-5] / 2[0-4]\d / [01]?\d?\d.
- `[01]?\d?\d` 가 0-199, 200-249, 250-255 분기 합. 합법적 IPv4 정확히 커버.
- confidence 0.60 — IP 단독으로는 PII 약함 (RFC 1918 사설 IP 포함). README는 "telemetry / log PII when combined with user_id" 라 운영 컨텍스트 의존성 표기.

### Block B 마무리 (L211–213)

```python path=src/detectors/global_privacy.py lines=211-213
    ]
    for d in DETECTORS:
        reg.register(d)
```

- list 정의 끝 + 13건 일괄 등록. 등록 순서 = 매치 순회 순서.

**짚어볼 점 / Watch-outs (Block B 전체)**
- **L137 US phone 마지막 그룹 `\d{3}` — NANP 표준 4자리와 다름. 실제 의도 검증 필요. 회귀 테스트 부재로 미발견.**
- **IGNORECASE 광범위 적용 — IBAN/API key의 대소문자 의미를 약화.**
- **카드 패턴 ReDoS 잠재 — `\b(?:\d[ -]*?){13,19}\b`. fuzz/perf 측정 필요.**
- **체크섬 미적용 detector 다수**: RRN, IBAN, BRN — 형식 매치만으로 confidence 부여. PRD에서 명시한 거라면 OK이나 false positive 비율 측정 권장.
- **`flags`/`luhn` 외 게이팅 메커니즘 부재** — checksum 종류별 (mod-97, RRN checksum) 후속 게이팅 옵션 확장 권장.
- **detector 추가 시 `Detector` 인스턴스 확정 위치가 `register_global_privacy` 함수 내부 변수**. 외부에서 detector 객체에 접근 불가. P2 가 P1 detector를 알 필요는 없으므로 이대로 OK.
- **rule_hint 충돌 검사 부재**: `PRIV_CRED_IN_002` 만 정의 (`_001` 없음). 의도된 번호 예약일 수 있으나 문서화 부재.

---

## File-level Verdict

- **강점**
  1. 13개 detector를 데이터-지향 list로 정의 → 추가/삭제 1행 수정.
  2. RegexDetector 추상화로 패턴/플래그/Luhn 옵션 균일 처리.
  3. Phase 1 도메인-무관 baseline detector를 모두 한 곳에 모음 → 가독성 ↑.
- **위험**
  1. US phone 패턴 마지막 그룹 `\d{3}` (NANP 표준 `\d{4}` 와 불일치 의심).
  2. 카드 패턴 `\b(?:\d[ -]*?){13,19}\b` ReDoS 가능성.
  3. IGNORECASE가 모든 detector에 일괄 적용되어 IBAN/API key의 대소문자 의미 약화.
- **개선 권고**
  1. 패턴별 회귀 테스트 매트릭스 (positive/negative 각각 3건+) 작성 — 특히 US phone, passport, IBAN.
  2. 카드 패턴 단순화: `\b\d(?:[ -]?\d){12,18}\b` 같이 lazy 제거 + greedy bound.
  3. IGNORECASE 기본을 case-sensitive 로 바꾸고 detector별 opt-in. IBAN/API key 의 보안 의미 보호.
- **재읽기 권고 레벨**: **높음**. 정탐/오탐 balance가 곧 product 품질이므로 룰 추가/수정 시 항상 재독해.
