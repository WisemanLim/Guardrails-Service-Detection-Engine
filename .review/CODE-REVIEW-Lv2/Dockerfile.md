# Dockerfile — 코드 리뷰
> 리뷰 레벨: 2
> [← INDEX.md](.review/CODE-REVIEW-Lv2/INDEX.md)

**파일 요약**
- 역할: Detection Engine 컨테이너 이미지 빌드 정의 (uvicorn 단일 프로세스)
- 진입점 거리: 0 (런타임 진입 — `uvicorn src.main:app`)
- LOC: 15
- export: 컨테이너 이미지 (스테이지명 `base` 단일)
- 의존 모듈: `python:3.11-slim` 베이스, `requirements.txt`
- 외부 패키지: pip 설치된 5종 (fastapi/uvicorn[standard]/pydantic/regex/orjson)
- 부수효과: pip 캐시·바이트코드 비활성, `WORKDIR /app` 설정, `PORT=8081` 노출
- 동시성: uvicorn 단일 워커 (워커 수 미지정 → 기본 1) — 컨테이너 오케스트레이터에서 수평 확장 가정
- 테스트 커버리지: 직접 없음 (이미지 빌드 검증은 외부 CI/compose 책임)

```dockerfile path=Dockerfile lines=1-15
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

EXPOSE 8081
ENV PORT=8081
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8081"]
```

**분석 / Analysis (Level 2)**

- L1 `FROM python:3.11-slim AS base`: pyproject `requires-python = ">=3.11"`과 정합. slim 변형은 빌드툴 부재 → C extension 컴파일 필요한 패키지가 추가되면 (예: `presidio-analyzer` 의 일부 의존) 실패. P1 의존성은 모두 wheels 제공되므로 OK. multi-stage 의도(`AS base`)가 있으나 `FROM ... AS final` 후속 단계가 없어 실제로는 single-stage. 의미 없는 alias.
- L2-4 `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `PIP_NO_CACHE_DIR=1`: 정석. `.pyc` 미생성으로 이미지 슬림, stdout/stderr 즉시 플러시(K8s 로깅 안전), pip 캐시 비활성. **흔한 실수 회피 OK.**
- L6 `WORKDIR /app`: 디렉토리 자동 생성. OK.
- L8-9 requirements 먼저 복사 → 설치: Docker 레이어 캐시 최적화 패턴. src 변경 시 pip install이 재실행되지 않음. OK.
- L9 `pip install --no-cache-dir`: ENV의 `PIP_NO_CACHE_DIR=1`과 중복이지만 명시적이라 무해.
- L11 `COPY src ./src`: `tests/`, `pyproject.toml`, `Dockerfile` 자체는 미포함 → 런타임 이미지 슬림. 단 editable install 안 됨 → `src.main` import는 sys.path에 `/app` 추가가 필요. uvicorn은 cwd를 sys.path에 자동 추가하므로 OK.
- L13 `EXPOSE 8081`: 문서적 효과만. 실제 바인딩은 L15. OK.
- L14 `ENV PORT=8081`: `config.py` 에서 `os.getenv("PORT", "8081")`로 읽혀 health 응답에 반영. L15 `--port`는 8081 하드코딩 → ENV 변경해도 uvicorn은 8081에서 listen. **불일치 가능성**: 운영자가 `-e PORT=9000`을 주어도 8081에서만 listen, health 응답 `port` 필드는 9000. 일관성 결여.
- L15 `CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8081"]`: exec form OK. 워커 수 미지정 → 기본 1. CPU-bound regex 워크로드라 GIL 영향 받음 → 멀티프로세스 워커(`--workers N`)가 적절할 수 있음. 컨테이너 오케스트레이터에 위임하는 정책일 수도 있어 trade-off.

**짚어볼 점**

- **루트 사용자**: `USER` 지시어 없음 → root로 실행. PII 처리 서비스라 컨테이너 탈출/RCE 시 영향 큼. `RUN useradd -r -u 1001 app && USER app` 권장.
- **healthcheck 부재**: `HEALTHCHECK CMD curl -fsS http://localhost:8081/health || exit 1` 누락 → 오케스트레이터(특히 docker run 직사용)에서 자동 복구 어려움.
- **시그널 처리**: exec form CMD이므로 PID 1이 uvicorn. `tini`/`dumb-init` 미사용 → 자식 좀비 처리, SIGTERM 정상 종료는 uvicorn 자체 핸들러에 의존. uvicorn은 SIGINT/SIGTERM 처리하지만, 멀티워커 사용 시 init 프로세스 권장.
- **베이스 이미지 핀**: `python:3.11-slim`은 부동 태그 → 빌드 재현성 약함. `python:3.11.9-slim-bookworm` 같은 핀이 더 안전.
- **레이어 정리**: `apt-get` 미사용이므로 캐시 정리 불필요. OK.
- **`.dockerignore` 의존**: INDEX §1.1에 `.dockerignore` 존재 표기 — `tests/`, `.review/`, `__pycache__/` 가 제외돼야 빌드 컨텍스트 슬림. 본 리뷰 범위에서 미확인.
- **시크릿 빌드 인자 없음**: PII 서비스지만 빌드 타임 시크릿 주입 안 함 → OK (런타임 ENV만 사용).
- **SBOM/취약점 스캔**: 자동화 미설정. trivy/grype 외부 파이프라인 권장.

**파일 수준 평가**

- 강점:
  1. requirements.txt → src 순서 레이어 캐시 친화적.
  2. `PYTHONUNBUFFERED`/`DONTWRITEBYTECODE`/`PIP_NO_CACHE_DIR` 3종 기본 위생 충실.
  3. exec-form CMD로 PID 1 신호 처리 안정.

- 위험:
  1. root 사용자 실행 — PII 트래픽 다루는 서비스에서는 표준 위반.
  2. `PORT` ENV ↔ uvicorn `--port` 하드코딩 불일치.
  3. healthcheck/init 부재 — 컨테이너 단독 운영 시 자가복구 어려움.

- 개선 권고:
  1. 비루트 유저 추가: `RUN useradd -r -u 1001 app && chown -R app /app` + `USER app`.
  2. `CMD`를 `sh -c 'exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8081}'` 로 바꾸거나 entrypoint 스크립트 도입 → ENV 일관성. (shell form은 시그널 이슈 — `exec` 필수)
  3. `HEALTHCHECK --interval=30s CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8081/health').status==200 else 1)"` 추가 (curl 미설치 환경 대응).

- 재읽기 권고 레벨: **2** — 컨테이너 운영 정책(루트/init/포트 일관성) 변경 시 재방문. 코드 변경 없이도 보안 강화 여지가 큼.

---

- 상위 폴더 abstract: [`.review/CODE-REVIEW-Lv2/INDEX.md`](.review/CODE-REVIEW-Lv2/INDEX.md)
- 관련 파일: [`requirements.txt.md`](requirements.txt.md), [`pyproject.toml.md`](pyproject.toml.md), [`src/main.py.md`](src/main.py.md), [`src/config.py.md`](src/config.py.md)
