# requirements.txt — 코드 리뷰
> 리뷰 레벨: 2
> [← INDEX.md](.review/CODE-REVIEW-Lv2/INDEX.md)

**파일 요약**
- 역할: Dockerfile `pip install -r` 타깃, 런타임 의존성 최소 명세
- 진입점 거리: 0 (이미지 빌드 시점)
- LOC: 5
- export: pip 의존성 5종
- 의존 모듈: N/A
- 외부 패키지: fastapi, uvicorn[standard], pydantic, regex, orjson
- 부수효과: pip install 시 트랜지티브 의존성 다수 추가 (starlette, pydantic-core, anyio, sniffio, h11, httptools, uvloop, websockets, watchfiles, click, h11 등)
- 동시성: N/A
- 테스트 커버리지: N/A (이미지 빌드 검증으로 간접)

```txt path=requirements.txt lines=1-5
fastapi>=0.110
uvicorn[standard]>=0.27
pydantic>=2.6
regex>=2024.4.16
orjson>=3.9
```

**분석 / Analysis (Level 2)**

- L1 `fastapi>=0.110`: pyproject와 동일 하한. **중복 정의**: pyproject `[project].dependencies`와 requirements.txt가 동일 항목을 따로 관리 — 한쪽 갱신 시 표류 위험.
- L2 `uvicorn[standard]>=0.27`: extras `standard` 포함 → uvloop, httptools, websockets, watchfiles 트랜지티브 → 이미지 사이즈 증가. websockets/watchfiles는 본 서비스에서 미사용. extras를 줄이면 슬림.
- L3 `pydantic>=2.6`: v2 의존. `pydantic-core` (rust)는 wheels 제공 → slim 이미지에서도 빌드 불필요.
- L4 `regex>=2024.4.16`: 날짜 기반 calver. C extension wheels 제공.
- L5 `orjson>=3.9`: rust 기반 JSON. PyPy 미지원 — 본 컨테이너는 CPython이라 무관.

**짚어볼 점**

- **단일 진실 원천(SoT) 부재**: pyproject `[project].dependencies` ↔ requirements.txt 가 둘 다 권위 있음처럼 보임. 한쪽이 누락/오래되면 빌드 vs 설치 시 차이. `pip-compile`로 생성하거나 한쪽으로 정리 권장.
- **lock 없음**: 해시 핀 (`--hash=...`) 미사용 → supply-chain 공격 시 검출 불가.
- **dev/test/ner 의존성 미포함**: 의도된 분리 (이미지 슬림). 다만 `httpx`가 starlette TestClient에 transitive로 깔리는지 여부에 따라 컨테이너 내부 테스트 실행 가능성 달라짐. (FastAPI 0.110+ 는 httpx를 testclient extras로 분리 → 이미지에 미포함.)
- **OS 패키지 의존성 표기 부재**: regex/pydantic-core/orjson은 C/Rust extension. slim 이미지에 wheels 있으면 OK지만, 향후 ARM64 등 미지원 휠 발생 시 빌드 실패 가능성 → comment 한 줄로 wheels 의존을 명시하면 운영자 친화적.

**파일 수준 평가**

- 강점:
  1. 핵심 의존성만 5줄로 최소 명세 — 가독성/이미지 슬림에 유리.
  2. pyproject와 정합 — 현재 시점 일치.

- 위험:
  1. pyproject 중복 — 의존성 표류(drift) 위험.
  2. 해시/lock 부재 — supply-chain 공격에 노출.
  3. `uvicorn[standard]`의 미사용 extras로 이미지 증가.

- 개선 권고:
  1. `pip-compile pyproject.toml -o requirements.txt --generate-hashes`로 자동 생성 + CI 게이트.
  2. extras 축소 또는 `uvicorn` 단독 + `uvloop` 명시.
  3. requirements.txt 상단에 SoT/생성방법 comment 추가.

- 재읽기 권고 레벨: **1** — 의존성 변경 시에만 재방문.

---

- 상위 폴더 abstract: [`.review/CODE-REVIEW-Lv2/INDEX.md`](.review/CODE-REVIEW-Lv2/INDEX.md)
- 관련 파일: [`pyproject.toml.md`](pyproject.toml.md), [`Dockerfile.md`](Dockerfile.md)
