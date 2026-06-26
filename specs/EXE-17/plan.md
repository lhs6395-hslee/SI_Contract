# Implementation Plan: EXE-17 — 계정 격리·인가

**Feature Branch**: `EXE-17-account-isolation`
**Created**: 2026-06-26
**Status**: Draft
**Spec**: `specs/EXE-17/spec.md`

---

## 1. 아키텍처 개요

EXE-17은 **코드 구현이 이미 완료된** 플랫폼 횡단 관심사 스펙이다. 본 plan.md는 현행 구현의 아키텍처를 명세화하고 각 FR과 실제 컴포넌트의 매핑을 기록한다.

### 레이어 구조

```
[클라이언트]
    │  Bearer {token}
    ▼
[FastAPI 인증 게이트]
    ├─ require_auth(cognito_auth.py:123)
    │    ├─ Cognito JWT 검증 (verify_cognito_token)
    │    └─ Basic Auth 폴백 (_verify_basic_token, main.py:1071)
    ▼
[인가 게이트]
    ├─ _assert_project_access(main.py:827)    ← 프로젝트 CRUD, 파이프라인
    └─ _project_owner(main.py:324)            ← 파일 업로드/조회/삭제
    ▼
[저장소 레이어]
    ├─ DynamoDB (project_store.py)
    │    ├─ save_project: owner 보존 + 조건부 put
    │    └─ list_projects_cached: 버전 스탬프 캐시 + 메모리 owner 필터
    └─ S3 (s3_storage.py)
         └─ _project_prefix: projects/{owner}/{project_id}/ 경로 격리
```

### 기술 스택

| 계층 | 기술 |
|------|------|
| API 프레임워크 | FastAPI (Python) |
| 인증 | AWS Cognito JWT (RS256) + Basic Auth (HMAC-SHA256) |
| 프로젝트 저장소 | AWS DynamoDB (없으면 메모리 dict fallback) |
| 파일 저장소 | AWS S3 (없으면 로컬 디렉토리 fallback) |
| JWT 라이브러리 | PyJWT + cryptography (미설치 시 클레임+kid 폴백) |
| Cognito JWKS | urllib.request (자체 구현, 1시간 메모리 캐시) |

---

## 2. FR ↔ 컴포넌트 매핑

### FR-001: 모든 엔드포인트 Bearer 토큰 필수

| 항목 | 상세 |
|------|------|
| **컴포넌트** | `backend/services/cognito_auth.py:123-144` `require_auth` |
| **FastAPI 연결** | `main.py`의 각 엔드포인트에 `dependencies=[Depends(require_auth)]` 또는 파라미터 `current_user: dict = Depends(require_auth)` |
| **동작** | Authorization 헤더 미제공 → 즉시 HTTP 401. 유효하지 않은 토큰 → HTTP 401. |
| **적용 엔드포인트** (코드 근거: `main.py:514,544,605~629,641,675,689,708,772,786,844,854,861,876,893,909,920,1010,1023,1032`) | `/api/classify`, `/api/extract*`, `/api/import`, `/api/validate`, `/api/export`, `/api/pipeline/*`, `/api/projects*`, `/api/files/*`, `/api/settings`, `/api/chat`, `/api/projects/{id}/lock*` |

### FR-002: admin 권한 판별 (resolve_role)

| 항목 | 상세 |
|------|------|
| **컴포넌트** | `backend/services/cognito_auth.py:24-26` `resolve_role(email, provider)` |
| **로직** | `provider == "basic" AND email == ADMIN_USERNAME` → "admin". 나머지(Cognito 포함) → "user". |
| **호출 위치** | `cognito_auth.py:137` (Cognito 경로), `main.py:1109` (Basic Auth 로그인), `main.py:1127,1131` (`/api/auth/me`) |
| **의존** | `ADMIN_USERNAME` env var (기본값 "admin", `cognito_auth.py:18`) |

### FR-003, FR-004: Cognito 토큰 검증

| 항목 | 상세 |
|------|------|
| **컴포넌트** | `backend/services/cognito_auth.py:69-114` `verify_cognito_token` |
| **검증 순서** | 1) JWT 형식 파싱 → 2) iss 검증 → 3) aud/client_id 검증 → 4) exp 검증 → 5) JWKS kid 매칭 → 6) RSA 서명 검증(PyJWT 가용 시) |
| **kid 우회 차단** | `cognito_auth.py:94-96` — `not kid or kid not in keys`이면 None 반환 |
| **JWKS 캐시** | `cognito_auth.py:34-49` `_fetch_jwks` — 1시간(3600초) 메모리 캐시 |
| **PyJWT 폴백** | `cognito_auth.py:108-109` — ImportError 시 서명 미검증 WARNING 로그 |

### FR-005, FR-006: 프로젝트 인가 게이트 (_assert_project_access) [FR-005: complex 패턴]

| 항목 | 상세 |
|------|------|
| **컴포넌트** | `backend/main.py:827-840` `_assert_project_access(project_id, current_user)` |
| **로직** | 프로젝트 미존재 → 404. role="admin" → 통과. owner != email → 404(존재 노출 없음). |
| **호출 위치** | `main.py:660, 718, 778, 789, 857, 869, 880, 895, 1014, 1027, 1035` |
| **반환** | 인가된 경우 project dict 반환(후속 처리에 재사용) |

### FR-007: 레거시 프로젝트 소유자 귀속

| 항목 | 상세 |
|------|------|
| **컴포넌트** | `backend/main.py:837`, `backend/services/cognito_auth.py:21-22` |
| **로직** | `project.get("owner") or LEGACY_OWNER` — owner 필드 없으면 ADMIN_USERNAME 귀속 |
| **동일 패턴** | `project_store.py:121` list 필터에서도 동일 적용 — `(p.get("owner") or LEGACY_OWNER) == owner` |

### FR-008: 프로젝트 목록 owner 필터 (list_projects_cached)

| 항목 | 상세 |
|------|------|
| **컴포넌트** | `backend/services/project_store.py:99-121` `list_projects_cached` |
| **캐시 전략** | DynamoDB `__meta__` 레코드 버전 스탬프 확인 → 불일치 시 전체 scan 갱신 |
| **필터** | scan 결과를 메모리에서 owner 필터(N+1 get_item 방지) |
| **admin 분기** | `is_admin=True` → 전체 반환; `owner=None & not admin` → 빈 목록 |
| **호출 위치** | `main.py:850-851` — `list_projects_cached(owner=..., is_admin=...)` |

### FR-009: S3 계정별 경로 격리 (_project_prefix)

| 항목 | 상세 |
|------|------|
| **컴포넌트** | `backend/services/s3_storage.py:35-41` `_project_prefix(project_id, revision, owner)` |
| **경로 규칙** | owner 있음: `projects/{owner}/{project_id}/` (+ `rev{N}/` if revision) |
| | owner 없음(레거시): `projects/{project_id}/` |
| **적용 함수** | `upload_file(60)`, `list_files(78)`, `get_file(111)`, `delete_file(154)` |
| **레거시 fallback** | `list_files`/`get_file` — owner 경로 우선 조회, 빈 결과면 레거시 경로 fallback |

### FR-010: import 엔드포인트 파일 접근 인가

| 항목 | 상세 |
|------|------|
| **컴포넌트** | `backend/main.py:651-660` — `POST /api/import` 내부 |
| **조건** | `stored_files`에 `projectId`가 있으면 `_assert_project_access(pid, current_user)` 호출 |
| **없으면** | 직접 업로드 파일만 처리(인가 불필요) |

### FR-011a, FR-011b, FR-012: save_project owner 보존·원자성

| 항목 | 상세 |
|------|------|
| **컴포넌트** | `backend/services/project_store.py:160-244` `save_project` |
| **owner 보존 로직** | `existing_owner` 있으면 항상 덮어쓰기(line 209-210). `lookup_failed=True`이면 신규 owner 기록 금지(line 211). |
| **원자적 신규 생성** | `attribute_not_exists(project_id)` 조건부 put(line 222). 실패 시 선행 레코드 owner 재조회(line 227-235). |
| **Consistent Read** | `ConsistentRead=True`로 stale read 방지(line 189) |

### FR-013a, FR-013b: Basic Auth 토큰 발급·검증

| 항목 | 상세 |
|------|------|
| **컴포넌트** | `backend/main.py:1063-1088` `_create_basic_token`/`_verify_basic_token` |
| **토큰 구조** | `base64url({username}:{expiry}:{hmac_sha256[:16]})` |
| **유효기간** | 발급 시각 + 28800초(line 1066) |
| **검증 보안** | `hmac.compare_digest`로 타이밍 공격 방지(line 1081) |
| **JWT_SECRET 의존** | env → Secrets Manager → 랜덤 폴백(main.py:1054-1057) |

---

## 3. 의존 관계

### EXE-17이 의존하는 컴포넌트

| 의존 대상 | 의존 이유 |
|----------|---------|
| `backend/services/project_store.py` | 프로젝트 레코드의 owner 필드 조회·저장 |
| `backend/services/s3_storage.py` | S3 계정별 경로 격리 |
| AWS Cognito User Pool | JWT 발급·JWKS 제공 |
| AWS DynamoDB | 프로젝트 레코드 저장 |
| AWS Secrets Manager | JWT_SECRET 주입 |

### EXE-17이 노출하는 인터페이스 (다른 기능이 소비)

| 인터페이스 | 소비 기능 |
|----------|---------|
| `require_auth` FastAPI dependency | 모든 EXE 기능의 보호 엔드포인트 |
| `_assert_project_access` | EXE-06(Sprint_Contract), EXE-14(import), EXE-15/16(Reviewer) — 파이프라인 인가 |
| `UserContext {email, role, provider}` | EXE-08(산출내역서), EXE-09(노무비) — pipeline current_user 전달 |

### EXE-17과 분리된 기능 (의존 없음)

| 기능 | 이유 |
|------|------|
| EXE-01 ~ EXE-03 (분류·추출·보정) | 인증은 require_auth가 처리 — 비즈니스 로직 독립 |
| 편집잠금(lock/unlock) | 설계 §9 비대상 — `project_store.py:384-467` acquire/release_edit_lock은 본 스펙 범위 밖 |
| OTEL/RateLimit/Security 미들웨어 | 설계 §9 비대상 |

---

## 4. 데이터 흐름 (인가 판단 경로)

```
요청 도착
  │
  ▼
require_auth(cognito_auth.py:123)
  │  Cognito JWT → verify_cognito_token → {email, role="user", provider="cognito"}
  │  Basic Auth  → _verify_basic_token  → {email, role=resolve_role, provider="basic"}
  │  실패 → HTTP 401
  ▼
current_user = {email, role, provider}
  │
  ├─ 프로젝트 접근 시 → _assert_project_access(main.py:827)
  │      load_project → owner 비교 → admin 또는 소유자이면 통과, 아니면 HTTP 404
  │
  ├─ 파일 접근 시 → _project_owner(main.py:324)
  │      load_project → owner 비교 → 통과이면 owner 반환 → s3_storage._project_prefix(owner)
  │
  └─ 목록 조회 시 → list_projects_cached(project_store.py:99)
         전체 scan → 메모리 owner 필터 (admin이면 전체 통과)
```

---

## 5. 알려진 제약·위험

| 항목 | 내용 | 코드 위치 |
|------|------|---------|
| PyJWT 미설치 | 서명 검증 없이 클레임+kid만으로 폴백 — WARNING 로그 | `cognito_auth.py:108-109` |
| JWT_SECRET 랜덤 폴백 | 멀티워커 환경에서 워커별 시크릿 불일치 → 401 | `main.py:1055-1057` |
| DynamoDB scan | 테이블에 user별 파티션 키 없음 → 전체 scan 후 메모리 필터 | `project_store.py:289-290` |
| S3 레거시 경로 | owner 없는 레거시 파일은 `projects/{project_id}/`에 잔존 가능 | `s3_storage.py:38-40` |
| JWKS fetch 실패 | urllib timeout(5초)시 캐시 반환 또는 빈 키 → 모든 Cognito 토큰 거부 | `cognito_auth.py:43-49` |
