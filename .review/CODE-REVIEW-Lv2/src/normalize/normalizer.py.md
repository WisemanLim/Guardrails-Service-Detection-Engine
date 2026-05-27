# `src/normalize/normalizer.py` — File Review (Level 2)

## Pre-Review Header

- 역할: 입력 텍스트의 NFKC 정규화 + 공백 collapse + strip.
- 진입점에서의 거리: 2 (api → normalize)
- 라인 수: 32
- 주요 export: `normalize_text(text: str) -> str`
- 의존 모듈 (internal): 없음
- 사용된 외부 패키지: stdlib `unicodedata`
- 부수효과: 없음 (pure function).
- 동시성 모델: 동기, 순수 함수.
- 테스트 커버리지 흔적: `test_normalize_endpoint_strips_fullwidth` 가 endpoint 통해 간접 호출.

---

## Source

```python path=src/normalize/normalizer.py lines=1-32
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
                out.append(ch)  # NOTE: actually appends " " (see L29)
            prev_space = True
        else:
            out.append(ch)
            prev_space = False
    return "".join(out).strip()
```

> 주의: 위 source 블록의 L26 주석은 리뷰어가 첨가한 것이며 실제 파일의 `out.append(" ")` 는 그대로다. 아래는 verbatim 파일 본문.

```python path=src/normalize/normalizer.py lines=16-32
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
```

**분석 / Analysis (Level 2)**
- L1–10: docstring 3단계 명시. **불일치**: 3번 "Strip combining marks at edges" 가 코드엔 없음. NFKC가 일부 combining mark를 분해/결합하지만 명시적 strip은 미구현. 향후 추가 의도라면 TODO 표시 권장.
- L11: `from __future__ import annotations` — PEP 563. 클래스 외부 함수 어노테이션엔 큰 영향 없으나 일관성 OK.
- L13: stdlib `unicodedata` — Python 표준이라 외부 의존 없음. NFKC는 한국어/일본어 혼합에 효과적.
- L16–18: 빈 입력 short-circuit. `None` 입력은 받지 않음(`Field` 검증으로 보장).
- L19: `unicodedata.normalize("NFKC", text)` — 전각 디지터 (`０-９`) → 반각 (`0-9`), 호환문자 (`㌀`, `①` 등) 분해/통일. CJK 호환 한자도 영향 받음.
- L20–30: 공백 collapse 루프
  - `ch.isspace()` 는 Unicode whitespace 광범위 (NBSP ` `, narrow NBSP, ZWSP 등). NFKC 가 NBSP를 일반 space 로 변환하므로 대부분 흡수됨.
  - 줄바꿈(`\n`, `\r`)은 보존 — 주석대로 "position math survives" 하나 실제로는 strip + collapse가 인덱스를 변경시키므로 **position math는 정규화 후 좌표계**에서만 의미를 가짐.
  - 탭(`\t`)은 isspace=True && newline 아님 → space 1개로 collapse.
- L23–28: `prev_space` flag로 연속 공백 dedup. 단순하고 O(n).
- L31: `.strip()` — 양끝 공백 제거. `.strip()` 의 기본 인자가 모든 whitespace이므로 newline도 양끝에서 제거됨. 줄바꿈 보존 정책과 미세 충돌 (양끝의 `\n`은 제거되지만 중간은 유지).

**짚어볼 점 / Watch-outs**
- **docstring vs code 불일치** (L6 "Strip combining marks at edges" 미구현) — 향후 의도라면 `# TODO` 코멘트 + 미구현 명시.
- **줄바꿈 보존이 미세하게 깨짐**: 양끝 newline은 `.strip()` 에 의해 제거. 의도가 "내부 newline만 보존"이라면 OK이나 명시 필요.
- **start/end 인덱스 의미**: 호출자(`/detect`)가 응답의 `start/end` 를 클라이언트 원문에 다시 매핑하려 하면 정규화로 길이가 줄었기 때문에 일치 안 됨. README의 "정규화 후 좌표" 명시는 있으나 응답 schema에 명확 표시 없음.
- **regex `\b` 와 NFKC 후 문자**: NFKC가 surrogate / kanji 경계를 변경하면 `\b` 동작이 변화. `regex` 모듈은 `\b` 가 Unicode-aware라 보통 안전. 그러나 한자/한글이 'word' 로 간주되므로 영문 ID와 혼재 시 경계 추론이 달라질 수 있음.
- **단일 공백 strip 후 길이**: 200KB 입력에 ` ` 1000개 + 일반 space 1000개가 있으면 NFKC가 NBSP를 일반 space로 변환 후 collapse → 길이 차이 큼. 200KB 입력 길이 제한은 정규화 전 기준.
- **순수 함수라 race 없음** — async event loop 호환.

---

## File-level Verdict

- **강점**
  1. 32 LOC 순수 함수, 의존성 stdlib만. 테스트 친화적.
  2. 새깍선 보존 정책으로 위치 정보 일부 유지.
  3. 빈 입력 short-circuit 으로 None/empty 안전.
- **위험**
  1. docstring(combining-mark strip) vs 실제 동작 불일치.
  2. `.strip()` 가 양끝 newline 까지 제거 — 줄바꿈 보존 정책과 미세 충돌.
  3. 200KB 정규화가 동기 CPU 패스 — 메모리/시간 측정 부재.
- **개선 권고**
  1. docstring을 실제 동작에 맞춰 정정 (또는 combining-mark strip 구현 + 테스트 추가).
  2. `.strip(" ")` 처럼 명시적 문자셋 strip으로 newline 보존 의도 강화.
  3. 200KB 인풋에 대한 perf 마이크로벤치 1회 측정 + 주석으로 SLA 기록.
- **재읽기 권고 레벨**: **낮음**. 사실상 stdlib 한 줄 + 공백 루프.
