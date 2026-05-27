# `src/detectors/luhn.py` — File Review (Level 2)

## Pre-Review Header

- 역할: 카드 번호 체크섬(Luhn) 검증.
- 진입점에서의 거리: 3 (api/detect → registry → global_privacy → luhn)
- 라인 수: 14
- 주요 export: `luhn_valid(digits: str) -> bool`
- 의존 모듈 (internal): 없음
- 사용된 외부 패키지: 없음 (stdlib만, 사실상 builtin)
- 부수효과: 없음.
- 동시성 모델: 순수 함수.
- 테스트 커버리지 흔적: `test_card_luhn_pass`, `test_card_luhn_fail` (간접).

---

## Source

```python path=src/detectors/luhn.py lines=1-14
def luhn_valid(digits: str) -> bool:
    s = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        if not ch.isdigit():
            return False
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        s += d
    return s % 10 == 0 and len(digits) >= 13
```

**분석 / Analysis (Level 2)**
- L1: 인자 타입 `str`. `digits` 라는 이름이 "이미 digits-only" 임을 암시. 호출자(`global_privacy.py:49`)가 `"".join(ch for ch in matched if ch.isdigit())` 로 전처리.
- L2: `s = 0` 누산기.
- L3: `parity = len(digits) % 2` — Luhn 알고리즘 표준: 오른쪽부터 매 두 번째 자릿수에 ×2. 왼쪽부터 인덱싱하므로 길이의 홀짝에 따라 doubling 위치가 결정됨. `parity = len % 2` 이면 짝수 길이(예: 16자리 카드)에서 i=0, 2, 4… (=짝수 인덱스, 길이 16 → parity=0 → i%2==0 시 doubling = 0,2,4… → 오른쪽에서 보면 1,3,5… 위치를 doubling). 표준 Luhn 결과 일치.
- L4–6: 각 char가 digit 인지 검증. 비-digit이면 False — fail-safe.
- L7–11: doubling + 9 초과 시 -9 (= 자릿수 합) — Luhn 표준.
- L12: 합산.
- L13: `s % 10 == 0 and len(digits) >= 13` — Luhn pass + **최소 길이 13**. ISO/IEC 7812 카드 PAN 13–19 자리 범위와 일치.
- **흔한 실수 회피**: 단순 `s % 10 == 0` 만 체크하면 길이 0 / 짧은 숫자 시퀀스도 통과 → false positive 폭증. 13자리 floor가 카드 오탐 1차 방어.

**짚어볼 점 / Watch-outs**
- **상한 미설정**: 19자리 초과(예: 100자리 숫자열)도 `s % 10 == 0` 이면 통과. 정규식이 `{13,19}` 제한하므로 호출 컨텍스트에서 차단됨. 그러나 luhn 모듈 단독 호출 시 false positive 위험. 상한 검사 추가 권장 (`13 <= len(digits) <= 19`).
- **빈 문자열**: `digits=""` 시 `s=0`, `s%10==0` True, `len>=13` False → False. 안전.
- **Unicode digit**: `"1234567890123"` 중 일부가 NFKC 후에도 비-ASCII digit이라면? `ch.isdigit()` 는 Unicode digit 포괄 (Arabic-Indic 등) → True 반환하지만 `int(ch)` 도 Unicode digit 변환 지원. 다만 NFKC 후엔 거의 ASCII로 통일되므로 실무엔 무해.
- **`isdigit` vs `isdecimal`**: `isdigit()` 는 superscript ², ³ 같은 것도 True인데 `int(ch)` 가 변환 못 해 ValueError 던질 수 있음. NFKC 후 superscript 가 일반 digit으로 풀려 안전하지만 corner case 인식 필요.
- **상수 시간 비교 아님**: 카드 검증은 보안 비교(타이밍 공격) 영역 아니라 일반 비교 OK.

---

## File-level Verdict

- **강점**
  1. 14 LOC 표준 Luhn, 13자리 최소 길이 floor.
  2. 비-digit 입력에 fail-safe False.
  3. 외부 의존 0.
- **위험**
  1. 상한 미설정 — 단독 호출 시 long-string false positive.
  2. `int(ch)` 가 Unicode superscript 등에서 ValueError 잠재 (NFKC가 1차 방어).
  3. 함수 단위 테스트 직접 없음 — endpoint 간접만.
- **개선 권고**
  1. `if not (13 <= len(digits) <= 19): return False` 라인 추가.
  2. 단위 테스트 `tests/test_luhn.py` 신설 — 알려진 valid/invalid 벡터 (4111111111111111 등) + 비-digit + Unicode edge.
  3. 타입 힌트 강화: `digits: str` 그대로지만 docstring에 "digits-only ASCII expected" 명시.
- **재읽기 권고 레벨**: **낮음**.
