# Feature Specification: EXE-04 기본정보 확인 게이트

**Feature Branch**: `EXE-04-basic-info-gate`  **Created**: 2026-06-26  **Status**: Draft
**Input**: 소스 추출(EXE-02) 완료 후 사용자가 6개 탭의 기본정보를 검토·확정하는 프론트엔드 전용 게이트

> **범위 선언**: 이 기능은 **프론트엔드 전용**이다. 백엔드 게이트 엔드포인트가 없으며, 게이트 상태(`confirmedTabs`)는 React 상태 + `ExtractedData` 클라이언트 스토어에만 존재한다. 코드 근거: `frontend/lib/types.ts:106`, `frontend/components/pages/review-page.tsx:114`.

---

## User Scenarios & Testing

### User Story 1 — 추출 결과 탭별 확인 후 익스포트 진행 (Priority: P1)

담당자는 소스 추출이 완료되면 기본 정보·산출내역·인원투입계획·공사공정표·요율보증·현장조직 6개 탭을 순서대로 검토하고, 각 탭에서 "확인 완료" 버튼을 눌러 확정 상태로 표시한다. 이후 익스포트 진행 여부는 단위 확정 게이트(`importPending`)에만 의존하며, 탭 확정 자체가 익스포트를 비활성화하지는 않는다. 확인 완료한 탭은 초록 배지로 구분된다.

- **Independent Test**: 6개 탭 각각에 대해 "확인 완료" 클릭 → `confirmedTabs` Set에 해당 tabId 포함 여부 단독 검증
- **Acceptance (Given/When/Then)**:
  1. **Given** 추출 데이터가 로드된 리뷰 페이지가 표시되고, **When** 사용자가 임의 탭에서 "확인 완료" 버튼을 클릭하면, **Then** 해당 탭의 상태가 `"ok"`로 변하고 초록 색상 배지와 "확인 완료" 텍스트가 표시된다.
  2. **Given** 탭 상태가 `"ok"` (확인 완료)인 상태에서, **When** "확인 취소" 버튼을 클릭하면, **Then** 해당 탭의 상태가 `"ok"` 이전 값(`"ready"` 또는 `"warn"`)으로 돌아간다.

### User Story 2 — 탭별 재추출 시 확인 상태 자동 해제 (Priority: P1)

재추출은 데이터를 갱신하므로, 기존에 확인 완료한 탭에서 재추출이 실행되면 해당 탭의 확인 상태가 자동으로 해제되어야 한다. 담당자가 재추출 후 다시 검토 없이 이전 확인 상태가 남아 있는 오류를 방지한다.

- **Independent Test**: 탭 확인 완료 후 "이 탭만 재추출" 클릭 → `confirmedTabs`에서 해당 tabId 제거 여부 단독 검증
- **Acceptance (Given/When/Then)**:
  1. **Given** "calc" 탭이 확인 완료(`confirmedTabs`에 포함)된 상태에서, **When** "이 탭만 재추출" 버튼을 클릭하고 재추출이 완료되면, **Then** `confirmedTabs`에서 "calc" 탭이 제거되고 탭 상태가 `"ok"` 이전 값으로 변경된다.

### User Story 3 — 차수·프로젝트 전환 시 확인 상태 재동기화 (Priority: P1)

차수 전환 또는 프로젝트 전환 시, 이전 차수의 stale 확인 상태가 신규 차수에 그대로 표시되는 위양성을 방지하기 위해 서버 데이터(`extractedData.confirmedTabs`)를 기준으로 재동기화한다.

- **Independent Test**: revision prop 변경 후 `confirmedTabs` React state가 `extractedData.confirmedTabs` 기준으로 재초기화되는지 단독 검증
- **Acceptance (Given/When/Then)**:
  1. **Given** 0차에서 일부 탭이 확인 완료된 상태에서, **When** 사용자가 1차로 전환하면, **Then** `confirmedTabs`는 1차의 `extractedData.confirmedTabs` 값 기준으로 재동기화되고 0차의 확인 상태가 표시되지 않는다.

### User Story 4 — 필수 필드 미입력 시 탭 경고 상태 표시 (Priority: P1)

기본 정보 탭은 필수 6개 필드(`projectName/client/pm/startDate/endDate/revenue`) 중 하나라도 누락되거나, 신뢰도가 `"guess"`인 미확인 필드가 있으면 `"warn"` 상태로 표시된다. 사용자는 이를 보고 누락 항목을 수정한다.

- **Independent Test**: REQUIRED_FIELDS 중 하나가 null인 extractedData를 주입 후 tabStatus("basic") 반환값이 "warn"인지 검증
- **Acceptance (Given/When/Then)**:
  1. **Given** `extractedData.extracted.projectName.value`가 null인 상태에서, **When** 리뷰 페이지가 렌더링되면, **Then** 기본 정보 탭에 주황 배지가 표시되고 "필수 미입력 N건" 텍스트가 보인다.

### User Story 5 — import 단위 미확정 시 익스포트 차단 (Priority: P1)

집행계획서 역추출(import) 0차의 경우, 금액 단위(천원/원)가 확정되지 않으면 익스포트 버튼이 비활성화된다. 탭 확인 상태와 무관하게 `importPending` 조건이 우선 적용된다.

- **Independent Test**: `extractedData.importMeta` 존재 + `unitConfirmed=false` 상태에서 익스포트 버튼 `disabled` 속성 검증
- **Acceptance (Given/When/Then)**:
  1. **Given** `importMeta`가 있고 `unitConfirmed`가 false인 리뷰 페이지에서, **When** 하단 버튼 영역이 렌더링되면, **Then** "익스포트로" 버튼에 `disabled` 속성이 설정되어 클릭이 불가능하다.

### Edge Cases

- 탭 재추출 중(`tabReExtracting=true`) 이면 "이 탭만 재추출" 버튼이 비활성화된다.
- `extractedData`가 null이면 탭별 상태 계산(`tabStatus`)에서 `"warn"`을 반환한다.
- `history` 탭(`maxRevision >= 1`일 때만 노출)은 `TabActionBar` 확인 대상에서 제외된다.
- confirmedTabs 초기화는 `useState` 마운트 1회만 발생하므로, revision/projectId 변경 시 `useEffect`로 재동기화한다(코드 근거: `review-page.tsx:120-122`).
- 탭 확인 완료 자체는 익스포트를 **허용**하거나 **차단**하지 않는다. 익스포트 차단 조건은 `importPending`만이다.
- 재추출 API 호출이 실패(reject)하면 `confirmedTabs`는 변경되지 않는다(FR-007b). `unconfirmTab`은 성공 경로에서만 호출된다(코드 근거: `review-page.tsx:316`, `try` 블록 내부 성공 직후 위치).

---

## Functional Requirements (EARS)

> 본 기능은 프론트엔드 전용이다. 모든 FR에서 "THE SYSTEM"은 클라이언트(Next.js 리뷰 페이지)를 지칭하며, 백엔드 로직/API 호출을 포함하지 않는다.

- **FR-001a** (event): WHEN EXE-02 소스 추출 결과가 리뷰 페이지에 로드되면, THE SYSTEM SHALL 6개 탭(`basic / calc / people / schedule / rates / org`)을 렌더링한다.

- **FR-001b** (event): WHEN EXE-02 소스 추출 결과가 리뷰 페이지에 로드되면, THE SYSTEM SHALL 각 탭의 초기 확인 상태를 `extractedData.confirmedTabs`에서 읽어 `confirmedTabs` Set을 초기화한다.

- **FR-002a** (ubiquitous): THE SYSTEM SHALL 각 탭의 상태를 `"ok"`(확인 완료) / `"ready"`(데이터 있음·미확인) / `"warn"`(데이터 부족 또는 필수 미입력)의 세 단계로 구분한다.

- **FR-002b** (ubiquitous): THE SYSTEM SHALL 각 탭의 상태를 색상 배지로 표시한다.

- **FR-003a** (event): WHEN 사용자가 탭의 "확인 완료" 버튼을 클릭하면, THE SYSTEM SHALL 해당 탭의 상태를 `"ok"`로 설정한다.

- **FR-003b** (event): WHEN 사용자가 탭의 "확인 완료" 버튼을 클릭하면, THE SYSTEM SHALL 해당 tabId를 `confirmedTabs` Set에 추가한다.

- **FR-003c** (event): WHEN 사용자가 탭의 "확인 완료" 버튼을 클릭하면, THE SYSTEM SHALL 해당 tabId를 `extractedData.confirmedTabs` 배열에 추가한다.

- **FR-004a** (event): WHEN 사용자가 탭의 "확인 취소" 버튼을 클릭하면, THE SYSTEM SHALL 해당 탭의 상태를 `"ok"` 이전 상태(`"ready"` 또는 `"warn"`)로 복원한다.

- **FR-004b** (event): WHEN 사용자가 탭의 "확인 취소" 버튼을 클릭하면, THE SYSTEM SHALL 해당 tabId를 `confirmedTabs` Set 및 `extractedData.confirmedTabs` 배열에서 제거한다.

- **FR-005a** (unwanted): IF `basic` 탭에서 필수 필드(`projectName / client / pm / startDate / endDate / revenue`) 중 하나 이상이 null 또는 빈 문자열이면, THEN THE SYSTEM SHALL 해당 탭을 `"warn"` 상태로 설정한다.

- **FR-005b** (unwanted): IF `basic` 탭에서 필수 필드(`projectName / client / pm / startDate / endDate / revenue`) 중 하나 이상이 null 또는 빈 문자열이면, THEN THE SYSTEM SHALL 미입력 필드 이름 목록을 하단 요약 바에 렌더링한다.

- **FR-006a** (unwanted): IF `basic` 탭에서 신뢰도가 `"guess"`이고 수동 확인(`manuallyVerified`)되지 않은 필드가 1개 이상이면, THEN THE SYSTEM SHALL 해당 탭을 `"warn"` 상태로 유지한다.

- **FR-006b** (unwanted): IF `basic` 탭에서 신뢰도가 `"guess"`이고 수동 확인(`manuallyVerified`)되지 않은 필드가 1개 이상이면, THEN THE SYSTEM SHALL 해당 필드 이름 목록을 하단 요약 바에 "확인 필요 N건"으로 렌더링한다.

- **FR-007** (event): WHEN 사용자가 탭의 "이 탭만 재추출" 버튼을 클릭하여 재추출이 **성공적으로** 완료되면, THE SYSTEM SHALL `unconfirmTab`을 호출하여 해당 탭을 `confirmedTabs`에서 제거한다.

- **FR-007b** (unwanted): IF 탭 재추출 API 호출이 실패(reject)하면, THEN THE SYSTEM SHALL `confirmedTabs`를 변경하지 않는다.

- **FR-008** (event): WHEN `revision` 또는 `projectId` props가 변경되면, THE SYSTEM SHALL `confirmedTabs` React 상태를 `extractedData.confirmedTabs` 값으로 재동기화한다.

- **FR-009a** (unwanted): IF `extractedData.importMeta`가 존재하고 `extractedData.unitConfirmed`가 false이면, THEN THE SYSTEM SHALL "익스포트로" 진행 버튼에 `disabled` 속성을 설정한다.

- **FR-009b** (unwanted): IF `extractedData.importMeta`가 존재하고 `extractedData.unitConfirmed`가 false이면, THEN THE SYSTEM SHALL "금액 단위 확정 필요" 상태 텍스트를 표시한다.

- **FR-010a** (state): WHILE 탭 재추출(`tabReExtracting`)이 진행 중인 동안, THE SYSTEM SHALL "이 탭만 재추출" 버튼을 비활성화한다.

- **FR-010b** (state): WHILE 탭 재추출(`tabReExtracting`)이 진행 중인 동안, THE SYSTEM SHALL 경과 시간(초)을 표시한다.

- **FR-011a** (ubiquitous): THE SYSTEM SHALL 탭 확인 상태(`confirmedTabs`)를 `ExtractedData` 클라이언트 스토어에 배열(`string[]`)로 영속한다.

- **FR-011b** (event): WHEN 페이지가 재방문되면, THE SYSTEM SHALL `ExtractedData` 클라이언트 스토어의 `confirmedTabs` 배열을 읽어 이전 확인 상태를 복원한다.

---

## Success Criteria (측정형)

- **SC-001**: 6개 탭 각각에 대해 "확인 완료" 클릭 후 `confirmedTabs.has(tabId)`가 `true`인 비율 = **100%** (단위테스트 기준).
- **SC-002**: 재추출 완료 후 해당 tabId가 `confirmedTabs`에서 제거되는 비율 = **100%** (단위테스트 기준).
- **SC-003**: revision 변경 후 `confirmedTabs` React state가 `extractedData.confirmedTabs` 기준으로 재동기화되는 지연 = `useEffect` 1 render cycle 이내(브라우저 환경 기준 `[NEEDS CLARIFICATION: 목표 지연 ms 수치 — 현재 useEffect 동기화이므로 render cycle 수로만 측정 가능]`).
- **SC-004**: `importMeta` 존재 + `unitConfirmed=false` 조건에서 익스포트 버튼 `disabled` 속성 = **항상 true** (단위테스트 기준).
- **SC-005**: REQUIRED_FIELDS 중 하나라도 null인 경우 `tabStatus("basic")` 반환값 = `"warn"` **100%** (단위테스트 기준).
- **SC-006**: `[NEEDS CLARIFICATION: 탭 배지 색상 대비 기준(WCAG 수치) 미명시 — 디자인 시스템 기준 확인 전까지 측정형 SC로 등재 불가. Clarifications Retained 항목으로 관리하며 수치 확정 후 SC로 승격한다]`

---

## Key Entities

- **`confirmedTabs: Set<string>`** — 리뷰 페이지 로컬 React state. 확인 완료된 tabId의 집합. 근거: `review-page.tsx:114`
- **`ExtractedData.confirmedTabs: string[]`** — 클라이언트 스토어 영속 배열. 차수 전환 시 재동기화 소스. 근거: `frontend/lib/types.ts:106`
- **`tabStatus(id: string): "ok" | "ready" | "warn"`** — 탭별 상태 계산 함수. 근거: `review-page.tsx:229-238`
- **`TabActionBar`** — 각 탭 하단의 확인/취소/재추출 UI 컴포넌트. 근거: `review-page.tsx:2023`
- **REQUIRED_FIELDS** — `["projectName", "client", "pm", "startDate", "endDate", "revenue"]`. 근거: `review-page.tsx:167`
- **BASIC_KEYS** — 19개 기본정보 필드 목록(추출 여부 카운트 기준). 근거: `review-page.tsx:152`
- **탭 목록 (6개 고정 + 1개 조건부)** — `basic / calc / people / schedule / rates / org` + `history`(maxRevision >= 1 시). 근거: `review-page.tsx:240-248`
- **`importPending`** — `!!importMeta && !unitConfirmed`. 익스포트 차단 조건. 근거: `review-page.tsx:184`

---

## Assumptions

- **잠정(코드 현행값)** 탭 목록 6개(`basic/calc/people/schedule/rates/org`)는 현행 코드 기준이며, 추후 기획 변경으로 탭이 추가/제거될 수 있다. 권위 출처 미확정.
- **잠정(코드 현행값)** REQUIRED_FIELDS 6개는 현행 코드 기준. 필수 필드 목록의 공식 정의 문서 없음.
- `confirmedTabs` 영속은 클라이언트 스토어(로컬)에만 있으며, 백엔드 DB에 별도 저장되지 않는다(백엔드 게이트 엔드포인트 없음 — 설계 §3 확인).
- 탭 확인 완료 자체는 다음 단계(익스포트) 진행을 강제하지 않는다. 단, `importPending` 조건은 익스포트를 독립적으로 차단한다.
- `history` 탭은 `TabActionBar` 확인 대상에 포함되지 않는다(`TAB_NAMES`에 "history" 없음, `review-page.tsx:2028-2031`).

---

## Clarifications Retained

- **SC-003**: 탭 재동기화 지연 목표 ms/render 수치 미정의 — 현재 `useEffect` 동기화이며 정량 목표 미명시.
- **SC-006 (승격 대기)**: 탭 배지 색상 대비 WCAG 수치 미명시 — 디자인 시스템 기준 확인 후 측정형 SC로 승격 가능. 수치 확정 전까지 SC 목록에서 측정형으로 기능하지 않는다.
- confirmedTabs 영속 방식(로컬 스토어 vs 서버 동기화)에 대한 공식 결정 문서 없음 — 현재 코드는 클라이언트 전용이나, 추후 서버 동기화 요구사항이 생길 수 있음.
- **FR-007b 실패 경로**: 재추출 API 실패 시 `confirmedTabs` 불변 동작은 현재 코드 구조(`try` 블록 내 성공 직후 `unconfirmTab` 위치)에서 도출된 것이며, 명시적 설계 결정 문서 없음 — 추후 의도 변경 시 FR-007b 및 Edge Cases 갱신 필요.
