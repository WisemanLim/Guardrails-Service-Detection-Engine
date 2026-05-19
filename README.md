# Guardrails-Service-Detection-Engine

LLM/RAG 가드레일의 **민감정보·PII 탐지** 계층. ko-KR / en / ja-JP 혼합 입력을 정규화하고, 정규식·키워드·(예정) NER·LLM-as-judge를 조합해 매치 결과와 위험 점수를 반환한다.

## 컴포넌트 책임

PRD §3.2 ③. 핵심 6가지:

1. **혼합 입력 정규화** — NFKC + 공백 통일 + 토큰 경계 보존
2. **정규식 매처** — RRN, SSN, MyNumber, 여권, 카드(+Luhn), 전화, 이메일, IBAN, 비즈니스등록번호, IP, API key 등
3. **키워드/사전 매처 (확장 포인트)** — 병명·약물·정당명 사전
4. **NER (확장 포인트)** — spaCy/transformers/Presidio (`[ner]` extras)
5. **LLM-as-judge (확장 포인트)** — semantic classifier
6. **위험 점수 합산** — confidence 최댓값 기반, 카테고리 셋 추출

## 스택

- Python 3.11+
- FastAPI 0.110 + Uvicorn
- regex (PCRE 호환, `\b` Unicode-aware)
- Pydantic v2
- orjson (응답 직렬화)
- (선택) spaCy + Presidio (`pip install -e .[ner]`)
- (개발) pytest + httpx (`pip install -e .[dev]`)

## 디렉토리 구조

```
src/
├── main.py                       # FastAPI app factory
├── config.py                     # ENV → Settings
├── normalize/
│   └── normalizer.py             # NFKC + 공백 정규화
├── detectors/
│   ├── base.py                   # Detector ABC
│   ├── registry.py               # 도메인/locale/io_type 기반 필터
│   ├── bootstrap.py              # 활성 도메인 별 register_*() 호출
│   ├── luhn.py                   # 카드번호 체크섬
│   └── global_privacy.py         # P1 PII detector 13개
└── api/
    ├── health.py                 # GET /health
    ├── normalize.py              # POST /normalize
    └── detect.py                 # POST /detect

tests/
└── test_detectors.py             # 8 케이스 (pytest)
```

## REST API

### `GET /health`

```json
{
  "status": "ok",
  "domains": ["global"],
  "locales": ["ko-KR", "en"],
  "detectors": ["pii.id.rrn.kr", "pii.id.ssn.us", ...]
}
```

### `POST /normalize`

```json
{ "text": "９００１０１-1234567", "locale": "ko-KR" }
```

응답:

```json
{ "normalized_text": "900101-1234567", "digits_only_view": "9001011234567" }
```

### `POST /detect`

```json
{
  "text": "My SSN is 123-45-6789.",
  "domain": "global",
  "locale": "en",
  "io_type": "input"
}
```

응답:

```json
{
  "normalized_text": "My SSN is 123-45-6789.",
  "matches": [
    {
      "detector_id": "pii.id.ssn.us",
      "category": "pii",
      "sub_category": "ssn_us",
      "locale": "en",
      "start": 10,
      "end": 21,
      "matched_text": "123-45-6789",
      "confidence": 0.97,
      "rule_hint": "PRIV_ID_IN_002"
    }
  ],
  "risk_score": 0.97,
  "categories": ["pii.ssn_us"]
}
```

## P1 Detector 카탈로그 (13개)

| ID | sub_category | locale | conf | 메모 |
| :-- | :-- | :-- | --: | :-- |
| `pii.id.rrn.kr` | national_id_kr | ko-KR/* | 0.98 | 주민등록번호 6-7 |
| `pii.id.ssn.us` | ssn_us | en/* | 0.97 | US SSN, 000/666 prefix 제외 |
| `pii.id.mynumber.jp` | mynumber_jp | ja-JP/* | 0.85 | 4-4-4 그룹 |
| `pii.id.passport` | passport | * | 0.75 | 1글자+7-9숫자 (휴리스틱) |
| `pii.contact.email` | email | * | 0.95 | 표준 이메일 |
| `pii.contact.phone.kr` | phone_kr | ko-KR/* | 0.95 | 01[016789]-…-… |
| `pii.contact.phone.us` | phone_us | en/* | 0.80 | NANP / E.164-ish |
| `pii.financial.card` | card_number | * | 0.96 | 13-19 자리 + Luhn |
| `pii.financial.iban` | iban | * | 0.90 | 2글자+2숫자+11-30영숫자 |
| `pii.id.driver_license.kr` | driver_license_kr | ko-KR/* | 0.80 | 2-2-6-2 |
| `pii.id.brn.kr` | business_reg_kr | ko-KR/* | 0.70 | 3-2-5 |
| `pii.log.ipv4` | ip_address | * | 0.60 | RFC 1918 포함 |
| `credentials.api_key` | api_key | * | 0.92 | sk/pk/api/key/token + 16+ 영숫자 |

## Detector 등록 모델 (플러그인)

```python
# src/detectors/base.py
class Detector(ABC):
    detector_id: str
    domain: str             # "global" | "manufacturing-food" | "*"
    locales: List[str]
    io_types: List[str]
    category: str
    sub_category: str
    @abstractmethod
    def scan(self, text: str) -> Iterable[dict]: ...
```

### Phase 확장 시

```python
# src/detectors/manufacturing_food.py  (Phase 2 도입 시 추가)
def register_manufacturing_food(reg: DetectorRegistry) -> None:
    reg.register(EmployeeContactDetector(...))
    reg.register(WorkerHealthDetector(...))
```

`bootstrap.py`는 활성 도메인이 `manufacturing-food`를 포함할 때만 import → 모듈 없으면 silent skip. **P1 단독 배포 시 P2 모듈이 없어도 깨지지 않음.**

## 도메인/locale 필터 규칙

`DetectorRegistry.resolve` 매칭:

- `d.domain` ∈ {`*`, `global`, 요청 domain}
- `d.locales` ∋ locale 또는 `*`
- `d.io_types` ∋ io_type 또는 `both`
- 옵션: `enabled_categories` 화이트리스트

## 환경 변수

| 변수 | 기본 | 설명 |
| :-- | :-- | :-- |
| `PORT` | `8081` | |
| `LOG_LEVEL` | `info` | |
| `GUARDRAILS_ENABLED_DOMAINS` | `global` | CSV — bootstrap 시 register 대상 |
| `GUARDRAILS_LOCALES` | `ko-KR,en` | health 응답용 |

## 로컬 개발

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 또는: pip install -e .[dev]

uvicorn src.main:app --port 8081 --reload
```

## 테스트

```bash
pytest -q
```

현재 8 케이스:
- 한국 RRN 탐지
- US SSN 탐지
- email 탐지
- 카드 Luhn pass
- 카드 Luhn fail (오탐 없음 검증)
- 무해 문장 통과
- 전각 숫자 정규화
- /health detector 카탈로그 노출

## ko-KR / en / ja-JP 혼합 입력 정규화 (PRD §8.2)

1. **NFKC** — 전각/반각, 호환문자 통일
2. **공백 정규화** — 다중 공백 → 1, 줄바꿈은 위치 보존
3. **토큰 경계** — Hangul/Latin/CJK/Digit/Symbol 별 토큰화 (현재는 정규식 boundary로 처리)
4. **숫자 패턴 전처리** — 공백·하이픈 포함 매치 후 digits-only 비교 (Luhn)

예: `John(010-1234-5678)이 line 3에서 issue 신고`
→ 정규화 후 `pii.contact.phone.kr` 매치 (`010-1234-5678`) + `pii.contact.email`는 미매치.

## 우회 입력 대응 (PRD §7-3.1)

- 카드/RRN: `\d[ -]*?` 패턴 → `9 0 0 1 0 1 - 1 2 3 4 5 6 7`도 매치
- 전각 숫자: NFKC로 흡수
- 향후 base64/hex 인코딩 탐지: M2에서 별도 detector 추가 예정

## Docker

```bash
docker build -t guardrails-detection-engine .
docker run --rm -p 8081:8081 guardrails-detection-engine
```

## 도메인 확장 워크플로우 (P1 → P2)

1. `src/detectors/manufacturing_food.py` 작성
2. `register_manufacturing_food(reg)` 함수 export
3. `bootstrap.py`는 이미 `if "manufacturing-food" in domains: import` 분기 있음 → 코드 변경 불필요
4. Container ENV `GUARDRAILS_ENABLED_DOMAINS=global,manufacturing-food`로 재기동

P1 단독 배포는 영향 없음 — P2 모듈이 없으면 bootstrap에서 ImportError catch → silent skip.

## 성능 특성

- Cold start < 50ms (외부 모델 의존 없음)
- 13개 detector × 입력 길이 O(n) 정규식 스캔
- /detect P95 < 30ms (single-pod, 1KB 입력 기준 추정)

## 향후 작업 (M2+)

- spaCy NER (PERSON, ORG, LOC) — `entity_types` 패턴 활용
- Presidio analyzer 통합 (recognizer-level 확장)
- LLM-as-judge wrapper (Anthropic/OpenAI 옵션)
- 사전 기반 키워드 매처 (도메인 vocab JSON 외부화)
- 일본어 형태소 분석 (Sudachi)
- prompt injection / jailbreak 패턴 (OWASP LLM01)
