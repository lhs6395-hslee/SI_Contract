# Feature Specification: EXE-05 — 견적서 충돌 감지·해결

**Feature Branch**: `EXE-05-conflict-detection`  **Created**: 2026-06-26  **Status**: Draft
**Input**: 다중 견적서가 업로드된 상황에서 견적서 간·내부 충돌을 감지하고, 사용자가 선택을 완료하기 전까지 Sprint_Contract 생성을 차단한다.

> **적용 헌법**: `.specify/memory/constitution.md` v1.0.0 — 값 미창작, EARS 5패턴, 측정형 SC.
> **성격**: 백엔드 AI 감지(`ai_core.py:522 cross_validate`, `main.py:675 /api/validate`) + 프론트엔드 UI 해결 흐름(`other-pages.tsx:24 ConflictsPage`, `review-page.tsx:706`)의 혼합 기능.

---

## User Scenarios & Testing

### User Story 1 — 동일 협력사 중복 견적서 처리 (Priority: P1)

담당자가 같은 협력사의 견적서를 날짜가 다른 버전으로 두 장 업로드했을 때, 시스템은 유형 A 충돌을 감지해 두 견적서 중 어느 것을 채택할지 사용자에게 선택을 요구한다. 사용자가 선택을 완료하기 전에는 집행계획서 엑셀 생성(익스포트)이 차단된다.

- **Independent Test**: 동일 협력사명의 견적서 두 파일(날짜만 다름)을 업로드한 뒤 `/api/validate` 응답의 `conflicts` 배열에 유형 A 항목이 포함되는지 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 같은 협력사명의 견적서 두 파일이 업로드된 상태, **When** 시스템이 `/api/validate`를 호출하면, **Then** 응답 `conflicts` 배열에 `type="mismatch"` 또는 충돌 항목이 1건 이상 포함되고 `severity`가 `"high"`이다.
  2. **Given** 충돌 항목이 `conflictCount > 0` 상태, **When** 프론트엔드가 review-page를 렌더링하면, **Then** 충돌 알림 배너가 표시되고 "충돌 해결 →" 버튼이 활성화된다.
  3. **Given** 사용자가 충돌 해결 페이지에서 아직 선택을 완료하지 않은 상태, **When** 익스포트를 시도하면, **Then** "모든 충돌을 해결해야 익스포트할 수 있습니다" 메시지가 표시되고 익스포트가 차단된다.

### User Story 2 — 완전 동일 견적서 중복 제출 (Priority: P1)

담당자가 내용이 완전히 동일한 견적서를 두 장 업로드했을 때, 시스템은 유형 A' 충돌로 감지하고 자동 병합하지 않는다. 내용이 같더라도 반드시 사용자가 "1장으로 처리" 여부를 확인해야 한다.

- **Independent Test**: 동일 파일을 두 번 업로드한 뒤 충돌 감지 결과가 반환되는지 확인. `ConflictsPage`에서 자동 해결 없이 사용자 선택 UI가 표시되는지 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 동일한 견적서 파일이 두 장 업로드된 상태, **When** 충돌 감지가 실행되면, **Then** 유형 A'에 해당하는 충돌 항목이 감지 결과에 포함된다.
  2. **Given** 유형 A' 충돌이 감지된 상태, **When** 시스템이 충돌 처리를 수행하면, **Then** 자동 병합 없이 사용자 선택 UI(확인 / 아니오)가 표시된다.

### User Story 3 — 동일 품목 금액 불일치(유형 B) 해결 (Priority: P1)

두 개의 다른 견적서에 같은 품목이 서로 다른 단가로 기재된 경우, 시스템은 유형 B 충돌로 감지하고 사용자에게 어느 금액을 사용할지 선택(A 출처 / B 출처 / 직접 입력)하게 한다.

- **Independent Test**: 동일 품목명을 포함한 두 견적서에서 단가가 다르도록 구성 후 `/api/validate` 호출, 충돌 항목 존재 확인. ConflictsPage에서 두 옵션 버튼과 "직접 입력" 버튼이 렌더링되는지 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 동일 품목의 단가가 출처마다 다른 추출 데이터, **When** `/api/validate`를 호출하면, **Then** 응답 `conflicts`에 해당 필드(`field`)를 포함한 항목이 반환된다.
  2. **Given** 충돌 해결 페이지에서 사용자가 옵션 A 또는 B를 선택하고 "해결 완료"를 누르면, **Then** 선택된 값이 `extractedData`에 반영되고 `conflicts` 배열이 비워지며 `conflictCount`가 0이 된다.

### User Story 4 — 견적서 내 합계 불일치(유형 D) 감지 (Priority: P2)

하나의 견적서 안에서 행 합산 금액과 견적서에 명시된 합계가 다를 때, 시스템은 유형 D 충돌로 표면화한다.

- **Independent Test**: 행 합산 ≠ 명시 합계인 견적서를 업로드하고 충돌 감지 결과를 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 행 합산 금액이 견적서 명시 합계와 다른 문서, **When** 충돌 감지가 실행되면, **Then** `conflicts` 결과에 합계 불일치를 나타내는 항목이 포함된다.

### Edge Cases

- 견적서가 1개뿐일 때 → 유형 A/A'/B/D 충돌 없음(유형 C만 가능); `conflicts` 배열이 빈 배열이어야 한다.
- 견적서가 0개일 때 → `/api/validate` 호출 시 빈 `conflicts` 반환.
- 충돌 해결 후 페이지를 벗어났다 돌아왔을 때 → `extractedData.conflicts`가 `[]`이므로 ConflictsPage는 "충돌 없음" 안내를 표시한다.
- 견적서 내 동일 품명 중복(유형 C): `[NEEDS CLARIFICATION: 유형 C는 cross_validate 프롬프트(ai_core.py:509-519)의 "mismatch|missing|warning" 분류로 커버되는지, 별도 프론트 처리가 있는지 확인 필요]`

---

## Functional Requirements (EARS)

> 모든 FR은 EARS 5패턴 중 하나. 한 FR = 한 동작. 모호어 금지.

### 충돌 감지 (백엔드)

- **FR-001** (event): WHEN 추출된 데이터가 `/api/validate`에 전달되면, THE SYSTEM SHALL 충돌/누락/경고 목록을 `{"conflicts": [...]}` 형태로 반환한다.
  - 코드 근거: `main.py:675-684` `/api/validate` 엔드포인트, `ai_core.py:522-527` `cross_validate`.

- **FR-002** (unwanted): IF 견적서가 2개 이상이고 동일 협력사 견적서가 날짜만 다르게 존재하면(유형 A), THEN THE SYSTEM SHALL 해당 충돌을 `conflicts` 목록에 포함해 반환한다.
  - 코드 근거: `ai_core.py:509-519` `VALIDATE_PROMPT` — "mismatch|missing|warning" 감지.
  - 유형 정의 출처: `PROJECT.md:43` = `planner.md:109` (일치, [공식 코드]).

- **FR-003** (unwanted): IF 견적번호·날짜·금액이 모두 같은 견적서 파일이 2개 이상 존재하면(유형 A'), THEN THE SYSTEM SHALL 유형 A' 충돌을 감지하고 자동 병합하지 않으며 `conflicts` 목록에 포함해 반환한다.
  - 유형 정의 출처: `PROJECT.md:44` = `planner.md:110` (일치, [공식 코드]).
  - 헌법 V조: 완전 동일 견적서(유형 A') 자동 병합 금지.

- **FR-004** (unwanted): IF 다른 문서에 동일 품목이 서로 다른 단가 또는 금액으로 기재되면(유형 B), THEN THE SYSTEM SHALL 해당 품목의 불일치를 `conflicts` 목록에 포함해 반환한다.
  - 유형 정의 출처: `PROJECT.md:45` = `planner.md:111` (일치, [공식 코드]).

- **FR-005** (unwanted): IF 동일 견적서 내에 동일 품명이 2행 이상 존재하면(유형 C), THEN THE SYSTEM SHALL 해당 중복을 `conflicts` 목록에 포함해 반환한다.
  - 유형 정의 출처: `PROJECT.md:46` = `planner.md:112` (일치, [공식 코드]).

- **FR-006** (unwanted): IF 견적서 행 합산 금액이 견적서 명시 합계와 다르면(유형 D), THEN THE SYSTEM SHALL 합계 불일치를 `conflicts` 목록에 포함해 반환한다.
  - 유형 정의 출처: `PROJECT.md:47` = `planner.md:113` (일치, [공식 코드]).

### 충돌 해결 게이트 (프론트엔드)

- **FR-007** (event): WHEN `/api/validate` 응답의 `conflicts` 배열이 1건 이상이면, THE SYSTEM SHALL `conflictCount`를 해당 건수로 설정하고 review-page에 충돌 알림 배너를 표시한다.
  - 코드 근거: `app/page.tsx:183,203`, `review-page.tsx:706-712`.
  - 레이어 위치(구현 상세): `frontend/app/page.tsx`, `frontend/components/pages/review-page.tsx`.

- **FR-008** (state): WHILE `conflictCount > 0`인 동안, THE SYSTEM SHALL 익스포트 흐름 진입을 차단하고 "충돌 해결 →" 진입 경로를 제공한다.
  - 코드 근거: `other-pages.tsx:54` `allResolved` 플래그 — 미해결 시 해결 버튼 비활성.
  - `[NEEDS CLARIFICATION: 익스포트 차단의 정확한 구현 위치 — review-page.tsx에서 export 버튼의 disabled 조건을 코드로 재확인 필요]`

- **FR-009** (event): WHEN 충돌 해결 페이지(ConflictsPage)가 열리면, THE SYSTEM SHALL 각 충돌 항목에 대해 옵션 A(출처 A 값) / 옵션 B(출처 B 값) / 직접 입력 중 하나를 선택하는 UI를 제시한다.
  - 코드 근거: `other-pages.tsx:96-122` 옵션 A/B 버튼, `other-pages.tsx:29-31` `picks`/`customValues` 상태.
  - 레이어 위치(구현 상세): `frontend/components/pages/other-pages.tsx`.

- **FR-010** (unwanted): IF 사용자가 전체 충돌 항목을 모두 선택하지 않은 상태이면, THEN THE SYSTEM SHALL "해결 완료" 버튼을 비활성화하고 해결 완료 처리를 차단한다.
  - 코드 근거: `other-pages.tsx:53-54` `resolvedCount === rawConflicts.length` 조건.
  - 레이어 위치(구현 상세): `frontend/components/pages/other-pages.tsx`.

- **FR-011** (event): WHEN 사용자가 모든 충돌을 선택하고 "해결 완료"를 누르면, THE SYSTEM SHALL 선택된 값을 `extractedData`에 반영하고 `conflicts` 배열을 비운다.
  - 코드 근거: `other-pages.tsx:56-78` `handleResolve` 함수.
  - 레이어 위치(구현 상세): `frontend/components/pages/other-pages.tsx`.

- **FR-011b** (event): WHEN 충돌 해결이 완료되면(`conflicts` 배열이 비워진 직후), THE SYSTEM SHALL `conflictCount`를 0으로 설정하고 review 화면으로 이동한다.
  - 코드 근거: `other-pages.tsx:75-77` `setConflictCount(0)`, `setRoute("review")`.

### 해결 결과 보존 (백엔드)

- **FR-012** (ubiquitous): THE SYSTEM SHALL 충돌 해결 결과(`conflict_type`, `description`, `options`, `user_choice`, `resolved_value`)를 `SprintContract.conflict_resolutions` 필드에 보존한다.
  - 코드 근거: `models/sprint_contract.py:51-56` `ConflictResolution`, `sprint_contract.py:168`.

- **FR-013a** (event): WHEN Reviewer가 Stage 2 충돌 해결 검증을 수행하면, THE SYSTEM SHALL `conflict_resolutions` 내 모든 항목에 `user_choice`가 채워져 있는지 확인한다.
  - 코드 근거: `reviewer.py:248-284` `_verify_conflict_resolution`.

- **FR-013b** (event): WHEN Reviewer가 Stage 2 충돌 해결 검증을 수행하면, THE SYSTEM SHALL `conflict_resolutions` 내 모든 항목에 `resolved_value`가 존재하는지 확인한다.
  - 코드 근거: `reviewer.py:248-284` `_verify_conflict_resolution`.

- **FR-014** (unwanted): IF `ConflictResolution` 항목에 `user_choice`가 비어 있으면, THEN THE SYSTEM SHALL Reviewer Stage 2를 "미해결 충돌" 오류로 FAIL 처리한다.
  - 코드 근거: `reviewer.py:263-264` `if not cr.user_choice: errors.append(...)`.

---

## Success Criteria (측정형)

- **SC-001**: `/api/validate` 응답 시간이 `[NEEDS CLARIFICATION: 목표 응답 시간 미정. Bedrock 호출 포함 시 P95 기준 수립 필요]` 이하.
- **SC-002**: 유형 A/A'/B/C/D 각각에 대한 검증 사례셋 테스트 케이스에서 **감지율 100%** (0건 누락 FAIL). 검증 사례셋 건수: `[NEEDS CLARIFICATION: 검증 사례셋 정의 미완]`.
- **SC-003**: 유형 A' 충돌이 감지된 경우 자동 병합 발생 건수 **0건** — 반드시 사용자 선택 후 처리.
- **SC-004**: 충돌이 1건 이상인 상태에서 익스포트를 시도하는 경우 차단 성공률 **100%** (프론트엔드 UI 게이트 기준). `[NEEDS CLARIFICATION: 익스포트 버튼 disabled 조건의 정확한 구현 위치(review-page.tsx 해당 라인) 확인 후 측정 기준 및 테스트 추가 필요]`
- **SC-005**: 모든 충돌이 해결된 후 `extractedData.conflicts.length === 0`이고 `conflictCount === 0`인 상태가 review-page에서 확인 가능 — 충돌 알림 배너 미표시.
- **SC-006**: Reviewer Stage 2에서 `user_choice` 미충족 충돌 항목이 있을 경우 FAIL 판정 **100%**.

---

## Key Entities

| 엔티티 | 위치 | 역할 |
|--------|------|------|
| `Conflict` | `frontend/lib/types.ts:118` | 프론트 충돌 표현 — type/message/field/valueA/valueB/sources |
| `ConflictResolution` | `backend/models/sprint_contract.py:51` | 백엔드 충돌 해결 레코드 — conflict_type/description/options/user_choice/resolved_value |
| `SprintContract.conflict_resolutions` | `backend/models/sprint_contract.py:168` | 해결 결과 컨테이너 |
| `cross_validate` | `backend/services/ai_core.py:522` | Bedrock 호출 교차 검증 함수 |
| `/api/validate` | `backend/main.py:675` | 교차 검증 엔드포인트 (인증 필요) |
| `ConflictsPage` | `frontend/components/pages/other-pages.tsx:24` | 충돌 해결 UI 컴포넌트 |
| `conflictCount` | `frontend/app/page.tsx:38`, `frontend/lib/store.ts:24` | 전역 충돌 건수 상태 |
| `_verify_conflict_resolution` | `backend/services/reviewer.py:248` | Reviewer Stage 2 검증 함수 |

**충돌 유형 정의 (단일 일치 출처):**

| 유형 | 설명 | 출처 |
|------|------|------|
| A | 동일 협력사 견적서가 2개 이상 (날짜 다름) | `PROJECT.md:43` = `planner.md:109` |
| A' | 견적번호·날짜·금액이 모두 같은 파일 2개 이상 | `PROJECT.md:44` = `planner.md:110` |
| B | 다른 문서에 동일 품목인데 단가/금액 다름 | `PROJECT.md:45` = `planner.md:111` |
| C | 같은 견적서 안에 동일 품명 2행 이상 | `PROJECT.md:46` = `planner.md:112` |
| D | 견적서 행 합산 ≠ 견적서 명시 합계 | `PROJECT.md:47` = `planner.md:113` |

---

## Assumptions

1. `cross_validate`의 Bedrock 호출 프롬프트(`VALIDATE_PROMPT`, `ai_core.py:509-519`)는 유형 A/A'/B/C/D를 명시적 유형 코드로 반환하지 않고 `"mismatch|missing|warning"` 분류와 `field`/`message`로 반환한다 — 프론트의 `Conflict.type` 필드와 매핑은 현행 코드 기준 잠정. [공식 코드: `ai_core.py:514-518`]
2. 충돌 감지는 Bedrock AI 기반(비결정성) — 동일 입력에 대해 동일 충돌을 항상 감지한다고 보장되지 않는다. 검증 사례셋 기반 검증은 복수 시드로 반복 실행 필요.
3. `USE_AI_SERVICE=true` 환경에서는 `/api/validate` 호출이 `ai-service`로 프록시된다(`main.py:678-680`). 이 경로의 동작은 EXE-05 스코프 동일.
4. 현재 `cross_validate`는 견적서 추출 데이터 전체(`data: dict`)를 받아 교차 검증하며, 유형 A/A' 감지를 위한 다중 견적서 식별은 Bedrock 프롬프트에 의존한다 — AI 오감지 가능성 있음 (잠정).
5. 충돌 해결 UI(ConflictsPage)는 프론트엔드 전용 상태(`picks`, `customValues`) 기반이며 별도 백엔드 해결 API 엔드포인트는 없다. 해결 결과는 `extractedData` 업데이트 후 저장 시 백엔드 `conflict_resolutions`에 반영된다.

---

## Clarifications Retained

설계 문서 §6-1 및 코드 검토 기반 미확정 항목:

1. **유형별 감지 커버리지**: `VALIDATE_PROMPT`(ai_core.py:509-519)가 유형 C(견적서 내 동일 품명 중복)와 유형 D(행 합산 ≠ 명시 합계)를 감지하도록 설계됐는지, 아니면 별도 결정론 로직이 필요한지 확인 필요.
2. **익스포트 차단 구현 위치**: 프론트엔드에서 `conflictCount > 0`일 때 익스포트 버튼이 어디서 어떻게 차단되는지 — review-page.tsx의 정확한 disabled 조건 재확인 필요.
3. **SC-001 응답 시간 목표**: `/api/validate` P95 응답 시간 수치 — Bedrock 호출 포함 베이스라인 측정 후 확정.
4. **SC-002 검증 사례셋 정의**: 유형별 대표 테스트 케이스 건수 및 기준 — 사용자가 사내 기준으로 직접 확정 필요.
5. **수수료 코드 1/2/3 판단 기준**: `contract_builder.py`의 `ConflictResolution(conflict_type="자동계산중복"/"연도배분확인"/"급료단가확인")` 등 내부 생성 충돌 유형과 사용자 대면 A/A'/B/C/D 유형의 관계 — 설계 §6-1 5번 항목.
