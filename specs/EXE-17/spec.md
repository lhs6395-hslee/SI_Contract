# Feature Specification: EXE-17 — 계정 격리·인가

**Feature Branch**: `EXE-17-account-isolation`
**Created**: 2026-06-26
**Status**: Draft
**Input**: 집행계획서 시스템의 모든 API 엔드포인트에서 계정 간 프로젝트·파일 데이터가 격리되고, 인증되지 않은 접근이 차단되어야 한다.
**성격**: 플랫폼 횡단 관심사 (백엔드 FastAPI + DynamoDB + S3 저장소 전층)

> **범위 주의**: 편집잠금(lock/unlock 엔드포인트: `/api/projects/{id}/lock`, `/api/projects/{id}/unlock`)은 설계 §9 비대상 도메인 — 본 스펙 미포함.

---

## User Scenarios & Testing

### User Story 1 — 일반 사용자는 본인 프로젝트만 조회한다 (Priority: P1)

집행담당자(일반 user)가 로그인 후 프로젝트 목록을 조회할 때, 다른 계정의 프로젝트가 보여서는 안 된다.
본인 프로젝트에만 파이프라인 실행·파일 업로드·다운로드·삭제가 가능하다.

- **Independent Test**: 계정 A로 프로젝트 생성 후, 계정 B로 해당 project_id에 GET/POST 요청 → 404 응답 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 계정 A의 Bearer 토큰으로 프로젝트 P1을 생성한 상태, **When** 계정 B의 Bearer 토큰으로 `GET /api/projects/P1`를 호출하면, **Then** HTTP 404가 반환된다(존재 여부도 노출하지 않음).
  2. **Given** 계정 B의 Bearer 토큰으로 인증된 상태, **When** `GET /api/projects`를 호출하면, **Then** 응답에 계정 A가 소유한 프로젝트가 포함되지 않는다.

### User Story 2 — admin은 전체 프로젝트에 접근한다 (Priority: P1)

시스템 관리자(admin 계정)는 모든 사용자의 프로젝트를 조회하고 관리할 수 있어야 한다.
단, admin 권한은 Basic Auth provider에서 ADMIN_USERNAME 계정에만 부여된다.

- **Independent Test**: admin 토큰으로 `GET /api/projects` 호출 시 전 계정 프로젝트 반환 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** Basic Auth의 admin 계정으로 로그인한 상태, **When** `GET /api/projects`를 호출하면, **Then** 전체 계정의 프로젝트 목록이 반환된다.
  2. **Given** Cognito JWT로 로그인한 일반 Cognito 사용자(이메일 = "admin"이라도), **When** resolve_role이 호출되면, **Then** 반환 role은 "user"이다.

### User Story 3 — 인증 없는 요청은 모두 차단된다 (Priority: P1)

Authorization 헤더 없이 API를 호출하면 모든 보호된 엔드포인트에서 401이 반환되어야 한다.

- **Independent Test**: Authorization 헤더 없이 `GET /api/projects` 호출 → 401 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** Authorization 헤더가 없는 HTTP 요청, **When** `GET /api/projects`를 호출하면, **Then** HTTP 401이 반환된다.
  2. **Given** 만료된 Bearer 토큰, **When** 임의 보호 엔드포인트를 호출하면, **Then** HTTP 401이 반환된다.

### User Story 4 — 레거시 프로젝트는 admin이 소유한다 (Priority: P2)

owner 필드가 없는 기존(레거시) 프로젝트는 admin 소유로 간주하여, 일반 사용자가 접근할 수 없다.

- **Independent Test**: DynamoDB에 owner 필드 없는 레코드 삽입 후 일반 사용자 접근 시 404 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** DynamoDB에 `owner` 필드가 없는 레거시 프로젝트 레코드가 있고 일반 user 계정으로 인증된 상태, **When** 해당 project_id로 조회 요청하면, **Then** HTTP 404가 반환된다.

### User Story 5 — S3 파일은 계정별 폴더로 격리된다 (Priority: P1)

파일 업로드·다운로드·삭제가 모두 `projects/{owner}/{project_id}/` 경로를 사용하여 다른 계정의 파일과 S3 경로가 겹치지 않는다.

- **Independent Test**: 계정 A로 파일 업로드 후 S3 key 확인 → `projects/A-email/project_id/filename` 구조 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 계정 A(owner = "a@example.com")로 프로젝트 P1에 파일 업로드, **When** S3에 저장된 key를 확인하면, **Then** key는 `projects/a@example.com/P1/{filename}` 형태이다.

### Edge Cases

- 신규 프로젝트(레코드 미존재) 파일 업로드: `_project_owner`의 `require_exists=False` 분기 — 현재 사용자를 임시 owner로 간주하여 S3 경로를 결정.
- DynamoDB 일시 장애 시 `save_project`의 owner 보존: 조회 실패(lookup_failed=True)이면 신규 owner를 기록하지 않음 — 기존 소유권 보호.
- 동시 생성 경합: `attribute_not_exists(project_id)` 조건부 put 실패 시 선행 레코드의 owner를 읽어 유지. `[공식 코드: backend/services/project_store.py:220-236]`
- PyJWT 미설치 환경: Cognito 토큰 검증을 클레임+kid 매칭으로 폴백. 서명 미검증 상태를 WARNING 로그로 기록. `[공식 코드: backend/services/cognito_auth.py:108-109]`
- kid 없는 토큰: JWKS 매칭 전에 거부(이전 우회 취약점 수정). `[공식 코드: backend/services/cognito_auth.py:95-96]`

---

## Functional Requirements (EARS)

- **FR-001** (unwanted): IF 유효한 Bearer 토큰이 없으면, THEN THE SYSTEM SHALL 모든 API 엔드포인트에 대해 접근을 거부한다.
  - 코드 근거: `backend/services/cognito_auth.py:123-144` `require_auth` FastAPI dependency — Authorization 헤더 미제공 시 HTTP 401, 유효하지 않은 토큰 시 HTTP 401.

- **FR-002** (event): WHEN `POST /api/auth/login`에서 Basic Auth 자격증명을 수신하면, THE SYSTEM SHALL username이 ADMIN_USERNAME이고 provider가 "basic"인 경우에만 role을 "admin"으로, 나머지는 "user"로 판별한다.
  - 코드 근거: `backend/services/cognito_auth.py:24-26` `resolve_role` — provider="basic" AND email==ADMIN_USERNAME 조건만 "admin".

- **FR-003** (unwanted): IF Cognito JWT 토큰의 `kid`가 JWKS에 없거나 비어 있으면, THEN THE SYSTEM SHALL 해당 토큰을 거부한다.
  - 코드 근거: `backend/services/cognito_auth.py:94-96` — `not kid or kid not in keys`이면 None 반환.

- **FR-004** (unwanted): IF Cognito JWT 토큰의 `iss`·`aud`/`client_id`·`exp` 클레임이 서버 설정값과 불일치하거나 만료되면, THEN THE SYSTEM SHALL 해당 토큰을 거부한다.
  - 코드 근거: `backend/services/cognito_auth.py:80-89` — iss/client_id/exp 순차 검증.

- **FR-005** (complex): WHEN 프로젝트 조회·수정·삭제·파이프라인 실행·결과 조회가 발생하면, IF 소유자 또는 admin이 아니면, THEN THE SYSTEM SHALL HTTP 404를 반환한다.
  - 코드 근거: `backend/main.py:827-840` `_assert_project_access` — 비소유자에게 존재 사실도 숨김(404).

- **FR-006** (unwanted): IF 요청한 프로젝트의 `owner` 필드가 현재 사용자의 email과 다르면, THEN THE SYSTEM SHALL HTTP 404를 반환하여 프로젝트의 존재 여부를 노출하지 않는다.
  - 코드 근거: `backend/main.py:837-839` — `owner != current_user.get("email")`이면 `HTTPException(404, "Project not found")`.

- **FR-007** (state): WHILE `owner` 필드가 없는 레거시 프로젝트에 접근 중이면, THE SYSTEM SHALL 해당 프로젝트의 실효 소유자를 LEGACY_OWNER(ADMIN_USERNAME)로 간주하여 일반 사용자 접근을 거부한다.
  - 코드 근거: `backend/main.py:837` — `project.get("owner") or LEGACY_OWNER`; `backend/services/cognito_auth.py:21-22` LEGACY_OWNER = ADMIN_USERNAME.

- **FR-008** (event): WHEN 프로젝트 목록(`GET /api/projects`)을 조회하면, THE SYSTEM SHALL admin은 전체 프로젝트를, 일반 user는 본인 email과 일치하는 `owner` 프로젝트만 반환한다.
  - 코드 근거: `backend/main.py:844-851`; `backend/services/project_store.py:99-121` `list_projects_cached` — `is_admin=True`이면 전체, 아니면 `owner` 필터 메모리 적용.

- **FR-009** (event): WHEN 파일을 S3에 업로드·조회·삭제하면, THE SYSTEM SHALL `projects/{owner}/{project_id}/` 형태의 계정별 폴더 경로를 사용한다.
  - 코드 근거: `backend/services/s3_storage.py:35-41` `_project_prefix` — `owner` 지정 시 `projects/{owner}/{project_id}` prefix 사용.

- **FR-010** (optional): WHERE `stored_files`가 특정 projectId를 참조하는 import 요청이면, THE SYSTEM SHALL 해당 프로젝트에 대해 `_assert_project_access`를 호출하여 미인가 파일 접근을 차단한다.
  - 코드 근거: `backend/main.py:651-660` — `pid`가 있으면 `_assert_project_access(pid, current_user)` 호출.

- **FR-011a** (event): WHEN 프로젝트를 저장하면, THE SYSTEM SHALL 기존 `owner` 필드를 덮어쓰지 않는다.
  - 코드 근거: `backend/services/project_store.py:209-210` `save_project` — `existing_owner`가 있으면 항상 보존.

- **FR-011b** (unwanted): IF DynamoDB 조회가 실패하면, THEN THE SYSTEM SHALL 신규 owner를 기록하지 않는다.
  - 코드 근거: `backend/services/project_store.py:211` `save_project` — `lookup_failed=True`이면 신규 owner 기록 금지.

- **FR-012** (event): WHEN 신규 프로젝트를 DynamoDB에 처음 저장할 때, THE SYSTEM SHALL `attribute_not_exists(project_id)` 조건부 put을 시도하고 경합 실패 시 선행 레코드의 owner를 읽어 유지한다.
  - 코드 근거: `backend/services/project_store.py:220-236` — ConditionExpression + 폴백 get_item 재조회.

- **FR-013a** (event): WHEN Basic Auth 세션 토큰을 생성하면, THE SYSTEM SHALL HMAC-SHA256 서명과 8시간 만료를 포함한 토큰을 발급한다.
  - 코드 근거: `backend/main.py:1063-1070` `_create_basic_token` — 8시간=28800초.

- **FR-013b** (event): WHEN Basic Auth 세션 토큰을 검증하면, THE SYSTEM SHALL 상수 시간 비교(compare_digest)를 사용한다.
  - 코드 근거: `backend/main.py:1071-1088` `_verify_basic_token` — `hmac.compare_digest`.

---

## Success Criteria (측정형)

- **SC-001**: 비소유자 계정의 타인 프로젝트 접근 요청 **100%** 가 HTTP 404를 반환한다. (코드 근거: `backend/main.py:839` `HTTPException(404, "Project not found")`)
- **SC-002**: Authorization 헤더가 없는 요청 **100%** 가 HTTP 401을 반환한다. (코드 근거: `backend/services/cognito_auth.py:130` `HTTPException(401, "Not authenticated")`)
- **SC-003**: 만료된 Cognito 토큰(`exp` < 현재시각) 검증 **100%** 가 거부된다. (코드 근거: `backend/services/cognito_auth.py:87-89`)
- **SC-004**: kid가 없거나 JWKS에 없는 Cognito 토큰 **100%** 가 거부된다. (코드 근거: `backend/services/cognito_auth.py:95-96`)
- **SC-005**: admin 계정 판별은 `provider == "basic" AND username == ADMIN_USERNAME` 조건 **100%** 일치 시에만 role="admin"이 부여된다. (코드 근거: `backend/services/cognito_auth.py:26`)
- **SC-006**: S3 파일 업로드 key는 `owner` 지정 시 **100%** 가 `projects/{owner}/{project_id}/` prefix를 포함한다. (코드 근거: `backend/services/s3_storage.py:41`)
- **SC-007**: `GET /api/projects` 응답에서 일반 user에게 타인 프로젝트가 노출되는 비율 **0%**. (코드 근거: `backend/services/project_store.py:121` — owner 필터 메모리 적용)
- **SC-008**: 동시 생성 경합 시 선행 레코드 owner 덮어쓰기 발생 횟수 **0건**. (코드 근거: `backend/services/project_store.py:220-236`)
- **SC-009**: Basic Auth 세션 토큰 만료 시간 = **28,800초(8시간)**. (코드 근거: `backend/main.py:1066`)
- **SC-010**: JWKS 캐시 TTL = **3,600초(1시간)**. (코드 근거: `backend/services/cognito_auth.py:40`)

---

## Key Entities

| 엔티티 | 위치 | 설명 |
|--------|------|------|
| `UserContext` | `cognito_auth.py:require_auth` 반환값 | `{email, role, provider}` — 모든 인가 판단의 기준 |
| `owner` 필드 | DynamoDB 프로젝트 레코드 | 프로젝트 소유자 email — 인가 게이트 기준값 |
| `LEGACY_OWNER` | `cognito_auth.py:21` | owner 없는 레거시 레코드의 실효 소유자 = ADMIN_USERNAME |
| `ADMIN_USERNAME` | `cognito_auth.py:18`, `main.py:1045` | Basic Auth admin 계정명 (env 기본값: "admin") |
| `S3 key prefix` | `s3_storage.py:35-41` | `projects/{owner}/{project_id}/` — 계정별 파일 격리 경로 |
| `_assert_project_access` | `main.py:827-840` | 프로젝트 인가 게이트 함수 — 소유자/admin 외 404 |
| `_project_owner` | `main.py:324-340` | 파일 op용 owner 해석 + 인가 (require_exists 분기 포함) |
| `list_projects_cached` | `project_store.py:99-121` | 버전 스탬프 기반 캐시 + 메모리 owner 필터 |
| `JWT_SECRET` | `main.py:1054` | Basic Auth 세션 토큰 서명 키 (Secrets Manager → env → 랜덤) |
| `JWKS cache` | `cognito_auth.py:34-49` | Cognito JWKS 1시간 캐시 |

---

## Assumptions

이하 값은 코드에서 읽은 **현행값**이며 **잠정**이다. 권위 있는 설계 문서 확정 전까지 변경 가능.

| 항목 | 현행값 | 코드 위치 |
|------|--------|----------|
| ADMIN_USERNAME 기본값 | "admin" | `cognito_auth.py:18`, `main.py:1045` |
| TEST_USERNAME 기본값 | "test" | `main.py:1048` |
| Basic Auth 토큰 유효기간 | 28,800초 (8시간) | `main.py:1066` |
| JWKS 캐시 TTL | 3,600초 (1시간) | `cognito_auth.py:40` |
| LEGACY_OWNER | ADMIN_USERNAME | `cognito_auth.py:21-22` |
| Cognito 기본 User Pool ID | "ap-northeast-2_Wz3a01s3w" | `cognito_auth.py:29` (env 우선) |
| Cognito 기본 Client ID | "6aarjh4rm676q8c61ll8li24h9" | `cognito_auth.py:30` (env 우선) |
| PyJWT 미설치 시 동작 | 클레임+kid 검증만(서명 미검증), WARNING 로그 | `cognito_auth.py:108-109` |
| DynamoDB 조회 실패 시 owner 처리 | 신규 owner 기록 금지(기존 소유권 보호) | `project_store.py:196, 211` |
| JWT_SECRET 미설정 시 | 워커별 랜덤(멀티워커 환경에서 401 위험), WARNING 로그 | `main.py:1055-1057` |
| S3 레거시 경로 fallback | `owner=None`이면 `projects/{project_id}/` | `s3_storage.py:35-41` |

---

## Clarifications Retained

설계 §6-1 기준 EXE-17에 직접 해당하는 충돌/미확정 항목:

1. **[NEEDS CLARIFICATION]** PyJWT 미설치 운영 환경 허용 여부 — `cognito_auth.py:108-109`는 클레임+kid 검증만으로 폴백 처리하나, 프로덕션에서 서명 미검증 상태가 허용 기준인지 정책 문서에 명시되어 있지 않음. 확인 필요: 운영팀(보안) + PyJWT 의존성 설치 정책.

2. **[NEEDS CLARIFICATION]** JWT_SECRET 미설정 시 랜덤 폴백 허용 여부 — `main.py:1055-1057`에서 WARNING 로그를 남기나, EKS 멀티워커 환경에서 실질적으로 토큰 검증 실패를 야기함. Secrets Manager 필수화 여부 미확정.

3. **[NEEDS CLARIFICATION]** Basic Auth 토큰 유효기간(28,800초) 운영 정책 기준 — 코드 상수값이나 보안 정책 문서 근거 없음. 확인 필요: 보안팀.

4. **[NEEDS CLARIFICATION]** DynamoDB 테이블에 user별 파티션 키 추가 계획 — `project_store.py:289-290`에 "user별 파티션 키가 없어 query 전환 불가 — scan 1회로 통합" 주석이 있으나, 향후 아키텍처 전환 계획 유무 불명. 확인 필요: 인프라팀.
