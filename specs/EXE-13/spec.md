# Feature Specification: EXE-13 — 수정집행 (차수별 7시트)

**Feature Branch**: `EXE-13-revision-sheets`  **Created**: 2026-06-26  **Status**: Draft
**Input**: 수정집행(revision >= 1) 발생 시 차수별 7시트를 xlsx ZIP 내부에 동적으로 생성하고, 공통!E5 참조를 고정 숫자로 교체하여 HLOOKUP 체인이 올바른 차수 열을 가리키도록 한다.

---

## 작성 규칙 적용

- 모든 FR은 EARS 5패턴. 한 FR = 한 동작. 모호어 금지.
- 값 미창작: 출처 있는 단일 값만 인용 (file:line 명기). 충돌값은 `[NEEDS CLARIFICATION]`.
- non-goal: 파일 CRUD, 편집잠금, 챗봇, OTEL/Security 미들웨어.

---

## User Scenarios & Testing

### User Story 1 — 1차 수정집행 발생 (Priority: P1)

담당자가 0차 집행계획서를 확정한 뒤 계약 변경이 생겨 1차 수정집행을 요청한다. 시스템은
기존 0차 7시트를 "(0차)" suffix로 숨김 처리하고, 동일 구조의 "(1차)" 7시트를 추가로
생성하여 활성화한다. 결과 xlsx를 열면 "0. 집행계획(갑지) (1차)" 등 7개 탭이 보이고
이전 "(0차)" 탭은 숨겨져 있다.

- **Independent Test**: `apply_revision_sheets(template, out, [1])` 호출 후 out.xlsx를 openpyxl로 열어 "(1차)" suffix 시트 7개 존재 + "(수정집행)" 원본 시트 숨김 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 유효한 템플릿 xlsx가 존재하고 `revision=1`, **When** `run_pipeline`이 호출되면, **Then** 산출 xlsx에 `"0. 집행계획(갑지) (1차)"` 등 7개 시트가 존재하고 `"(수정집행)"` 원본 7시트의 `state="hidden"`이다.
  2. **Given** (1차) 시트 내 수식이 `공통!E5`를 참조할 때, **When** 시트 XML이 패치되면, **Then** 해당 수식 내 `공통!E5`는 `1`로 교체되어 있다.

### User Story 2 — N차 누적 (2차, 이후) (Priority: P1)

2차 수정집행 시, 1차 시트는 숨겨지고 2차 시트만 보이는 상태가 된다. 이전 차수 시트는
보존(삭제하지 않음)되어 감사 추적이 가능하다.

- **Independent Test**: `apply_revision_sheets(template, out, [1, 2])` → (1차) 7시트 `state="hidden"`, (2차) 7시트 visible.
- **Acceptance (Given/When/Then)**:
  1. **Given** `all_revisions=[1, 2]`일 때, **When** `apply_revision_sheets`가 실행되면, **Then** (2차) 시트는 visible이고 (1차) 시트는 `state="hidden"`이다.
  2. **Given** (2차) 시트 수식 내 `공통!E5-1` 패턴이 있을 때, **When** 패치되면, **Then** 해당 패턴은 `1`(= 2-1)로 교체된다.

### User Story 3 — 차수 상한 초과 거부 (Priority: P1)

양식 구조상 0차~11차(12단계)만 지원한다. revision=12 이상을 요청하면 시스템이 거부한다.

- **Independent Test**: `revision=12`로 `run_pipeline` 호출 → HTTP 422 또는 pipeline 상태 `escalated` 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** `revision=12`인 SprintContract, **When** 파이프라인이 시작되면, **Then** 시스템은 산출물을 생성하지 않고 차수 상한 초과 오류를 반환한다.

### User Story 4 — 0차(수정 없음) (Priority: P1)

revision=0이면 수정집행 시트 생성 없이 원본 템플릿 그대로 사용한다.

- **Acceptance (Given/When/Then)**:
  1. **Given** `revision=0`, **When** `run_pipeline`이 호출되면, **Then** `apply_revision_sheets`는 호출되지 않고 `load_template()`만 사용된다.

### Edge Cases

- 템플릿에 "(수정집행)" suffix 시트가 일부 누락된 경우 → 해당 시트는 건너뜀(continue).
- `all_revisions=[]`일 때 → 템플릿을 단순 복사(`shutil.copy2`).
- 원본 시트 수식에서 따옴표 없는 시트명 참조(`5.집행예산산출내역서!G8` 공백 없는 패턴) → `[NEEDS CLARIFICATION: _patch_sheet_refs_to_zero:100 조건 분기의 완전성 — 공백 포함 시트명은 따옴표 필수이나 공백 없는 경우에만 추가 패치 적용, 커버리지 범위 확인 필요]`

---

## Functional Requirements (EARS)

- **FR-001** (event): WHEN `SprintContract.revision >= 1` 이면, THE SYSTEM SHALL 현재 차수와 이전 차수(`prev_revisions` 키)를 합산한 `all_revisions` 목록에 대해 차수별 7시트를 xlsx에 추가한다.
  - 코드 근거: `orchestrator.py:97-113` (`apply_revision_sheets` 호출)

- **FR-002** (ubiquitous): THE SYSTEM SHALL 다음 7개 시트명을 수정집행 시트 세트로 관리한다: `"0. 집행계획(갑지) (수정집행)"`, `"4. 집행예산집계표 (수정집행)"`, `"5.집행예산산출내역서 (수정집행)"`, `"5-1. 재료비산출내역 (수정집행)"`, `"5-2. 회선비산출내역 (수정집행)"`, `"5-3. 소모품비산출내역 (수정집행)"`, `"5-4. 수수료산출내역 (수정집행)"`.
  - 코드 근거: `excel/revision_sheets.py:21-29 _REV_SHEET_TEMPLATE_NAMES`

- **FR-003** (event): WHEN 차수 N에 대해 시트가 생성될 때, THE SYSTEM SHALL 템플릿 시트명 내 `"(수정집행)"`을 `"(N차)"`로 대체한 이름으로 새 시트를 등록한다.
  - 코드 근거: `excel/revision_sheets.py:51-53 _revision_sheet_name`

- **FR-004a** (event): WHEN 새 차수 시트 XML이 생성될 때, THE SYSTEM SHALL 수식 내 `공통!E5-1` 패턴을 `(N-1)`로 교체한다.
  - 코드 근거: `excel/revision_sheets.py:56-74 _replace_e5_in_formula` (더 긴 패턴 우선 처리)

- **FR-004b** (event): WHEN 새 차수 시트 XML이 생성될 때, THE SYSTEM SHALL 수식 내 `공통!E5` 단독 패턴을 `N`으로 교체한다.
  - 코드 근거: `excel/revision_sheets.py:56-74 _replace_e5_in_formula` (FR-004a 처리 후 잔여 패턴 처리)

- **FR-005** (event): WHEN 새 차수 시트 XML이 생성될 때, THE SYSTEM SHALL 수식 내 `"(수정집행)"` 시트 참조를 `"(N차)"` 참조로 교체한다.
  - 코드 근거: `excel/revision_sheets.py:128-133 _patch_sheet_xml`

- **FR-006** (event): WHEN 원본(0차) 시트 XML이 복사될 때, THE SYSTEM SHALL 해당 XML 내 `_ORIGINAL_SHEET_NAMES` 시트 참조를 `"(0차)"` suffix로 교체한다.
  - 코드 근거: `excel/revision_sheets.py:77-109 _patch_sheet_refs_to_zero`

- **FR-007a** (event): WHEN `apply_revision_sheets`가 실행될 때, THE SYSTEM SHALL 원본 7개 시트(`_ORIGINAL_SHEET_NAMES`)를 `"(0차)"` suffix로 rename한다.
  - 코드 근거: `excel/revision_sheets.py:296-301`

- **FR-007b** (event): WHEN `apply_revision_sheets`가 실행될 때, THE SYSTEM SHALL 원본 7개 시트(`_ORIGINAL_SHEET_NAMES`)를 `state="hidden"`으로 설정한다.
  - 코드 근거: `excel/revision_sheets.py:296-301`

- **FR-008** (event): WHEN `apply_revision_sheets`가 실행될 때, THE SYSTEM SHALL 템플릿 `"(수정집행)"` 7시트를 `state="hidden"`으로 설정한다.
  - 코드 근거: `excel/revision_sheets.py:303-307`

- **FR-009** (event): WHEN `apply_revision_sheets`가 실행될 때, THE SYSTEM SHALL `all_revisions` 중 최신 차수(`max(all_revisions)`)가 아닌 이전 차수 시트를 `state="hidden"`으로 설정한다.
  - 코드 근거: `excel/revision_sheets.py:243 is_visible`, `excel/revision_sheets.py:309-317`

- **FR-010** (unwanted): IF `SprintContract.revision > 11` 이면, THEN THE SYSTEM SHALL 차수 상한(MAX_REVISION=11) 초과로 처리를 거부하고 오류를 반환한다.
  - 코드 근거: `company_standards.py:11-12 MAX_REVISION = 11` (HLOOKUP 범위 $E$8:$P$149, 갑지 변경차수표 1~11차)
  - 주의: 현재 orchestrator.py에 MAX_REVISION 초과 명시적 게이트 코드 없음 — Assumption 참조.

- **FR-011** (state): WHILE `revision == 0` 동안, THE SYSTEM SHALL `apply_revision_sheets`를 호출하지 않고 `load_template()`을 직접 사용한다.
  - 코드 근거: `orchestrator.py:104, 113-114`

- **FR-012** (ubiquitous): THE SYSTEM SHALL 새 시트를 xlsx ZIP에 추가할 때 workbook.xml(시트 등록), workbook.xml.rels(rId 관계), `[Content_Types].xml`(콘텐츠 타입) 세 파일을 일관되게 갱신한다.
  - 코드 근거: `excel/revision_sheets.py:329-348`

- **FR-013** (ubiquitous): THE SYSTEM SHALL 공통 시트의 `E5` 셀에 현재 차수 번호를 기록한다(HLOOKUP 기준값).
  - 코드 근거: `excel/common_sheet.py:77-78` (`self.ws["E5"].value = revision`)

- **FR-014** (ubiquitous): THE SYSTEM SHALL 차수에 따른 열(E=0차, F=1차, ..., P=11차)을 `rev_col(revision)` 함수로 결정한다.
  - 코드 근거: `excel/utils.py:6-8 rev_col`

---

## Success Criteria (측정형)

- **SC-001**: `apply_revision_sheets(template, out, [N])` 호출 결과 xlsx에 `"(N차)"` suffix 시트가 **정확히 7개** 존재한다. (근거: `revision_sheets.py:21-29` 7시트 목록)
- **SC-002**: 생성된 (N차) 시트 XML 내 `공통!E5` 텍스트가 **0건**이다 (모두 정수로 교체됨). (근거: `_replace_e5_in_formula`)
- **SC-003**: `all_revisions=[1, 2]` 시, (1차) 7시트의 `state` 속성이 `"hidden"`이고 (2차) 7시트에 `state` 속성이 없다(visible). (근거: `orchestrator.py:243`)
- **SC-004**: `all_revisions=[]` 시, 출력 파일이 템플릿과 바이트 동일하다. (근거: `apply_revision_sheets:169-171`)
- **SC-005**: `revision=12`(MAX_REVISION+1) 요청 시, 파이프라인이 산출물 xlsx를 생성하지 않고 오류 상태를 반환한다. (근거: `company_standards.py:12`)
- **SC-006**: 수정집행 N차 체인(rev 0~6)에서 각 차수의 `"5-4. 수수료산출내역 (N차)"` 시트의 H9(당초), K9(변경), X9(당기)가 `golden_docs.json` 내 `B2_6차수정` 체인 기준값과 비교하여 1% 미만 오차 이내이다. (근거: `.pipeline/tests/test_revision_chain.py:144-151`, 검증 사례셋: `golden_docs.json`)
- **SC-007**: N차 시트 생성 후 workbook.xml의 시트 등록 수 = (기존 시트 수) + 7×(차수 수)이다.

---

## Key Entities

| 엔티티 | 위치 | 설명 |
|--------|------|------|
| `SprintContract.revision` | `backend/models/sprint_contract.py:162` | 현재 차수 (0 이상 정수) |
| `SprintContract.prev_revisions` | `backend/models/sprint_contract.py:175` | 이전 차수 데이터 `{"0": {...}, ...}` |
| `_REV_SHEET_TEMPLATE_NAMES` | `excel/revision_sheets.py:21-29` | 복사 소스 7시트 이름 목록 |
| `_ORIGINAL_SHEET_NAMES` | `excel/revision_sheets.py:31-39` | 0차 역할 원본 7시트 이름 목록 |
| `apply_revision_sheets(template_path, output_path, all_revisions)` | `excel/revision_sheets.py:152` | 수정집행 시트 생성 진입점 |
| `MAX_REVISION` | `company_standards.py:12` | 최대 차수 = 11 |
| `rev_col(revision)` | `excel/utils.py:6-8` | 차수 → Excel 열 문자 (E=0, P=11) |

---

## Assumptions

- **MAX_REVISION=11 (잠정)**: `company_standards.py:12`에서 단일 출처로 확인된 현행값. HLOOKUP 범위 `$E$8:$P$149`(E~P=12열=0차~11차)와 일치. 권위 출처(양식 설계 문서) 미확정이므로 잠정으로 명기.
- **7시트 목록 (잠정)**: `excel/revision_sheets.py:21-29`에서 단일 출처로 확인. 템플릿 양식 개정 시 변경될 수 있음.
- **E5=현재 차수**: `common_sheet.py:77-78`에서 파란색 셀(`FF0070C0`)로 직접 기록. HLOOKUP에서 `공통!E5`를 참조하는 구조는 템플릿 수식 설계에 의존하며 검토 불가.
- **orchestrator의 MAX_REVISION 게이트 미구현**: 현행 `orchestrator.py`에는 `revision > MAX_REVISION` 명시 거부 코드가 없음. FR-010은 의도된 동작이나 구현 갭 존재 — tasks.md에서 구현 대상으로 분류.
- **공통 시트 견적품의(4행) 고정**: `revision >= 1`이면 0차 값을 유지 (`common_sheet.py:91-116`). 수정집행에서는 4행 값이 변경되지 않음.

---

## Clarifications Retained

설계 §6-1에서 EXE-13에 귀속되는 강제 `[NEEDS CLARIFICATION]` 항목:

1. **MAX_REVISION 초과 시 처리 방식**: 설계 §6-2에서 "채울 값=11"로 제시하나, orchestrator에 명시적 게이트 없음. 거부 시점(API 입력 단계 vs 파이프라인 진입 단계)과 반환 형식 미확정.
   - 출처 확인 필요: `orchestrator.py` 전체 + `main.py` SprintContract 수신 경로.

2. **원본 시트 수식 내 따옴표 없는 시트명 패치 커버리지**: `_patch_sheet_refs_to_zero:100` — 공백 없는 시트명(`5.집행예산산출내역서`)만 추가 패치. 공백 포함 원본 시트명의 따옴표 없는 참조 패턴 미처리 여부 확인 필요.
