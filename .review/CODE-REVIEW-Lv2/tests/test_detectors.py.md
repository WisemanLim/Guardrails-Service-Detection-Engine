# `tests/test_detectors.py` — File Review (Level 2)

## Pre-Review Header

- 역할: `/detect`, `/normalize`, `/health` 회귀 케이스 8건.
- 진입점에서의 거리: 0 (테스트 진입)
- 라인 수: 60
- 주요 export: 테스트 함수 8개
- 의존 모듈 (internal): `src.main.app`
- 사용된 외부 패키지: `fastapi.testclient` (실제로는 `httpx` 내부 사용)
- 부수효과: 모듈 import 시 `TestClient(app)` 생성 → app 부팅 트리거 → detector registry 채워짐.
- 동시성 모델: pytest 직렬 실행. 동기 핸들러 호출.
- 테스트 커버리지 흔적: 자기 자신.

---

## Source

```python path=tests/test_detectors.py lines=1-60
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def post_detect(text: str, locale: str = "ko-KR", io_type: str = "input") -> dict:
    r = client.post(
        "/detect",
        json={"text": text, "domain": "global", "locale": locale, "io_type": io_type},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_korean_rrn_detected():
    body = post_detect("제 주민등록번호는 900101-1234567 입니다.", locale="ko-KR")
    assert any(m["sub_category"] == "national_id_kr" for m in body["matches"])
    assert body["risk_score"] >= 0.9


def test_us_ssn_detected():
    body = post_detect("My SSN is 123-45-6789.", locale="en")
    assert any(m["sub_category"] == "ssn_us" for m in body["matches"])


def test_email_detected():
    body = post_detect("Contact me at user@example.com.", locale="en")
    assert any(m["sub_category"] == "email" for m in body["matches"])


def test_card_luhn_pass():
    body = post_detect("Card: 4111 1111 1111 1111", locale="en")
    assert any(m["sub_category"] == "card_number" for m in body["matches"])


def test_card_luhn_fail():
    body = post_detect("Number 1234 5678 9012 3456 is not a card.", locale="en")
    assert not any(m["sub_category"] == "card_number" for m in body["matches"])


def test_benign_passes_through():
    body = post_detect("오늘 회의는 3시입니다.", locale="ko-KR")
    assert body["risk_score"] == 0


def test_normalize_endpoint_strips_fullwidth():
    r = client.post("/normalize", json={"text": "９００１０１-1234567", "locale": "ko-KR"})
    assert r.status_code == 200
    assert "900101-1234567" in r.json()["normalized_text"]


def test_health_lists_detectors():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "pii.id.rrn.kr" in body["detectors"]
```

**분석 / Analysis (Level 2)**
- L1–3: `TestClient(app)` 가 `app` import → `create_app()` 실행 → detector 13건 등록. **모듈 전역 `client`** 라 단일 인스턴스. fixtures 사용 안 함.
- L5: `client = TestClient(app)` — `httpx` 위의 WSGI/ASGI 브리지. test 함수가 직접 client 호출.
- L8–14: `post_detect` 헬퍼 — domain 고정 `"global"`. assert r.status_code == 200 → 422 / 500 시 즉시 실패.
- L17–20: RRN 테스트. `900101-1234567` (정확히 RRN 형식) 매치 + `risk_score >= 0.9`. confidence 0.98 이므로 통과.
- L23–25: SSN. `123-45-6789` 가 area=123 (000/666 제외 분기) → 매치.
- L28–30: email. 매우 단순.
- L33–35: 카드 `4111 1111 1111 1111` (Visa 테스트 카드, Luhn pass).
- L38–40: `1234 5678 9012 3456` (Luhn fail → 미매치). 더불어 `card_number` sub_category 가 응답에 없는지만 확인 → 다른 detector(예: passport `[A-Z]\d{7,9}`) 매치 여부는 검사 안 함. 의도 OK.
- L43–45: 무해 문장 risk_score == 0. **`== 0` 정수 비교, 실제 응답은 `0.0` (float)** — Python 에서 `0.0 == 0` True 라 통과. 다만 stricter equality (예: `is`) 가 아니라 OK.
- L48–51: `/normalize`. 전각 `９００１０１` → 반각 `900101`. NFKC 검증.
- L54–59: `/health` 응답에 RRN id 포함.

**짚어볼 점 / Watch-outs**
- **모듈 전역 `client` + `app` import 부수효과**: ENV (`GUARDRAILS_ENABLED_DOMAINS` 등) 변경 후 재import 가 필요한 시나리오에선 곤란. 현재 default 만 검증.
- **negative 케이스 부족**: 매치 검증은 `any(...) == True` 패턴이라 false negative 검사에 약함. 예를 들어 RRN 테스트는 RRN만 검사하고 IBAN, 카드 등 다른 detector 의 false positive 가 같은 응답에 섞여 있어도 통과.
- **카드 Luhn fail 테스트**: `1234 5678 9012 3456` 가 마침 16자리. 그러나 passport(`[A-Z]\d{7,9}`) 와 충돌은 lowercase 가 아니어서 무관. 다만 다른 detector 매치 검증 없음.
- **`enabled_categories`, `io_type="both"`, unknown domain 등 분기 미테스트**.
- **`pytest-asyncio` 선언했으나 비동기 테스트 없음** — 핸들러가 동기라 필요 없으나 의존성으로만 남음.
- **status_code 만 검증** — body 스키마는 `body["matches"]` 등 dict key 접근으로 implicit 검증. 422 케이스(예: too long text) 없음.

---

## File-level Verdict

- **강점**
  1. 60 LOC로 핵심 happy-path 8건 균형있게 커버.
  2. `post_detect` 헬퍼로 중복 제거.
  3. NFKC 정규화 + 카드 Luhn 통합 검증 — 회귀 충실.
- **위험**
  1. negative/edge case 거의 0 — false positive 회귀 검출 약함.
  2. `client = TestClient(app)` 전역 → 테스트 격리·ENV 재설정 불가.
  3. `registry.resolve` 분기·`enabled_categories` 미테스트.
- **개선 권고**
  1. pytest fixture (`@pytest.fixture` `client`) 도입 + `monkeypatch.setenv` 와 결합.
  2. `registry.resolve` 단위 테스트 별도 파일 신설 (8~16 매트릭스).
  3. 422/500 케이스 (200KB 초과, unknown io_type, detector dict 키 누락 mock) 추가.
- **재읽기 권고 레벨**: **중**. 정탐/오탐 회귀 매트릭스가 곧 product 품질 — 테스트가 자라야 함.
