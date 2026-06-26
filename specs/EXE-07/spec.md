# Feature Specification: EXE-07 수수료산출내역 (5-4)

**Feature Branch**: `EXE-07-fee-sheet`  **Created**: 2026-06-26  **Status**: Draft
**Input**: SprintContract.fee_items를 5-4 수수료산출내역 시트에 계약/집행/당기 컬럼으로 분리 기록한다.

---

## 작성 규칙

모든 Functional Requirement는 EARS 5패턴 중 하나만 사용. 한 요구 = 한 동작 = 검증 가능.
값을 모르면 임의로 정하지 않고 `[NEEDS CLARIFICATION: 무엇을 확인해야 하나]`.

---

## 도메인 분류

EXE-07은 **도메인 기능**이다. FeeItem 데이터를 Excel 시트에 기록하는 쓰기 레이어이며,
수식 계산은 Excel 템플릿 자체가 담당한다(J/M/S/Z 열). 백엔드 비즈니스 로직(`contract_builder.py`,
`excel/fee_sheet.py`)이 존재하며, EXE-06(Sprint_Contract 생성)의 결과를 소비한다.

---

## User Scenarios & Testing

### User Story 1 — 0차 수수료 항목 기록 (Priority: P1)

사업관리자는 발주처 계약서(계약 컬럼)와 협력사 견적서(집행 컬럼)의 수수료 항목을
5-4 시트에 행별로 분리 기록하여, 마진 구조가 한눈에 보이도록 확인하고 싶다.

- **Independent Test**: fee_items 3건의 SprintContract로 0차 시트 생성 후, H/I/K/L/Q/R 셀 값이 FeeItem 필드와 1:1 일치하는지 단독 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** SprintContract에 fee_items 3건이 있고 revision=0이며 vendor가 제공된 상태,
     **When** FeeSheetWriter._write()를 실행하면,
     **Then** 시트 행 8~10에 H=contract_qty, I=contract_unit_price, K=execution_qty, L=execution_unit_price, Q=current_period_qty, R=execution_unit_price가 기록되고 AJ열에 vendor가 기록된다.
     (`fee_sheet.py:85-95` 참조)
  2. **Given** SprintContract에 fee_items 1건이 있고 revision=0이며 vendor=None인 상태,
     **When** FeeSheetWriter._write()를 실행하면,
     **Then** AJ열에 아무 값도 기록되지 않는다(AJ셀이 None 또는 빈 문자열).
     (`fee_sheet.py:94-95` 참조)

### User Story 2 — 역마진 차단 (Priority: P1)

사업관리자는 협력사 집행단가가 발주처 계약단가를 초과하는 항목이 집행계획서에
기록되는 일을 방지하고 싶다.

- **Independent Test**: execution_unit_price > contract_unit_price인 FeeItem을 SprintContract에 포함해 Reviewer를 실행하면 "역마진" 오류가 반환되는지 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** FeeItem의 execution_unit_price가 contract_unit_price보다 큰 상태,
     **When** _verify_fee_structure()가 해당 행을 검증하면,
     **Then** "역마진" 문자열을 포함한 오류가 errors 목록에 추가되어 margin_structure_ok=False가 반환된다.
     (`reviewer.py:191-193` 참조)

### User Story 3 — 수량×단가=금액 1원 정밀도 검증 (Priority: P1)

사업관리자는 모든 행의 계약금액/집행금액/당기금액이 수량×단가와 1원도 차이나지 않는지
Reviewer가 자동으로 확인하기를 원한다.

- **Independent Test**: contract_qty=3, contract_unit_price=5500000, contract_amount=16500001(1원 오차)인 FeeItem을 검증하면 오류가 발생하는지 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** FeeItem.contract_amount와 contract_qty × contract_unit_price 간 차이가 1원을 초과하는 상태,
     **When** _verify_fee_structure()가 해당 셀을 검증하면,
     **Then** "계약:" 또는 "집행:" 문자열을 포함한 오류가 errors 목록에 추가되고 contract_calc_ok=False가 반환된다.
     (`reviewer.py:169-189` 참조)

### User Story 4 — 수정집행 차수 기록 (Priority: P2)

사업관리자는 revision>=1인 수정집행 시, 당초(이전 차수)와 변경(현재 차수) 값을
각 열에 분리 기록하고 싶다.

- **Independent Test**: revision=1, prev_fee_items["0"] 1건, 현재 fee_items 1건으로 시트 생성 후 H/I(당초 계약), K/L(변경 계약), N/O(당초 집행), Q/R(변경 집행) 셀이 올바르게 채워지는지 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** SprintContract.revision=1이고 prev_fee_items["0"]에 이전 FeeItem이 있는 상태,
     **When** FeeSheetWriter._write()를 실행하면,
     **Then** 현재 차수 시트의 H/I열에 이전 차수의 contract_qty/contract_unit_price, K/L열에 현재 차수의 contract_qty/contract_unit_price, N/O열에 이전 차수의 execution_qty/execution_unit_price, Q/R열에 현재 차수의 execution_qty/execution_unit_price가 기록된다.
     (`fee_sheet.py:119-127` 참조)

### User Story 5 — 다년도 당기 배분 후 사용자 확인 플래그 (Priority: P2)

사업관리자는 사업기간이 회계연도 경계를 걸칠 때, 당기수량이 자동 배분됨을 알고
관문에서 재확인하고 싶다.

- **Independent Test**: 2025-10-01~2026-03-31 사업에 fiscal_year=2025인 FeeItem을 _build_fee_items()로 처리하면 ConflictResolution에 "연도배분확인" 항목이 추가되는지 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 사업기간이 회계연도 경계를 걸치고(start_year ≠ end_year) fiscal_year가 명시된 상태,
     **When** _build_fee_items()가 fy_shares를 계산하여 current_period_qty를 산출하면,
     **Then** fee_conflicts 목록에 conflict_type="연도배분확인"인 ConflictResolution이 추가된다.
     (`contract_builder.py:266-273` 참조)

### Edge Cases

- 수수료 항목이 없는 경우(fee_items=[]) → FeeSheetWriter._write()가 즉시 반환하여 시트를 수정하지 않는다. (`fee_sheet.py:43-44` 참조)
- 기본 템플릿 슬롯(행 8~16, 최대 9건)을 초과하는 항목 → insert_rows로 행을 추가한 뒤 템플릿 행 서식을 복사한다. (`fee_sheet.py:70-76` 참조)
- contractAmount/executionAmount가 명시적으로 제공된 경우 → 자동 일할계산을 수행하지 않는다. (`contract_builder.py:228` `has_confirmed_amount` 로직 참조)
- 수식 셀(J/M/S)에 금액이 수량×단가와 다를 때 → `_force_if_mismatch`가 값으로 강제 입력한다. (`fee_sheet.py:137-142` 참조)
- 이전 차수 항목 매칭: 품명+협력사 일치 우선, 없으면 동일 순번으로 fallback. (`fee_sheet.py:145-153` 참조)

---

## Functional Requirements (EARS)

### 열 구조 기록 (0차)

- **FR-001** (ubiquitous): THE SYSTEM SHALL 수수료 항목의 계약 컬럼(H=계약수량, I=계약단가)과 집행 컬럼(K=집행수량, L=집행단가, Q=당기수량, R=당기단가)을 분리하여 각 행에 기록한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:85-93` (_write_base_rows)

- **FR-002** (ubiquitous): THE SYSTEM SHALL 수수료 항목의 자재코드(D열)·품명(E열)·규격(F열)·단위(G열)를 각 행에 기록한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:81-84`

- **FR-003a** (optional WHERE): WHERE vendor가 제공된 경우이고 revision=0이면, THE SYSTEM SHALL 협력사명을 AJ열에 기록한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:94-95`

- **FR-003b** (optional WHERE): WHERE vendor가 제공된 경우이고 revision >= 1이면, THE SYSTEM SHALL 협력사명을 AQ열에 기록한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:134-135`

### 수식 셀 보호

- **FR-004** (unwanted): IF 수식 셀(J/M/S)의 금액값이 해당 행의 수량×단가와 1원 이상 다르면, THEN THE SYSTEM SHALL 해당 셀에 계산값을 강제로 입력한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:87` `_force_if_mismatch`, `137-142`

- **FR-005** (unwanted): IF 셀이 수식(data_type="f")으로 설정되어 있고 금액값이 수량×단가와 일치하면, THEN THE SYSTEM SHALL 해당 셀에 값을 쓰지 않고 수식을 유지한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:156-161` (_write_cell_direct)

### 마진 무결성

- **FR-006a** (unwanted): IF 집행단가(L열)가 계약단가(I열)보다 크고 계약단가가 0보다 큰 경우, THEN THE SYSTEM SHALL 해당 행에 역마진 오류를 errors 목록에 기록한다.
  - 코드 근거: `backend/services/reviewer.py:191-192`

- **FR-006b** (unwanted): IF 집행단가(L열)가 계약단가(I열)보다 크고 계약단가가 0보다 큰 경우, THEN THE SYSTEM SHALL margin_structure_ok=False를 반환한다.
  - 코드 근거: `backend/services/reviewer.py:193`

### 금액 정밀도 검증

- **FR-007a** (unwanted): IF 계약금액 또는 집행금액이 수량×단가와 1원을 초과하는 차이를 보이면, THEN THE SYSTEM SHALL 해당 행에 오류를 errors 목록에 기록한다.
  - 코드 근거: `backend/services/reviewer.py:168-188`

- **FR-007b** (unwanted): IF 계약금액이 수량×단가와 1원을 초과하는 차이를 보이면, THEN THE SYSTEM SHALL contract_calc_ok=False를 반환한다.
  - 코드 근거: `backend/services/reviewer.py:176`

- **FR-007c** (unwanted): IF 집행금액이 수량×단가와 1원을 초과하는 차이를 보이면, THEN THE SYSTEM SHALL execution_calc_ok=False를 반환한다.
  - 코드 근거: `backend/services/reviewer.py:189`

### 일할계산

- **FR-008** (event): WHEN 수수료 항목의 단위가 "M/M" 또는 "월"이고 시작일이 월 중간이며 수량이 정수이고 contractAmount/executionAmount가 미제공된 경우, THE SYSTEM SHALL 시작월 잔여일/30(30일 고정 분모) + 이후 완전 월수로 수량을 일할계산한다.
  - 코드 근거: `backend/services/contract_builder.py:103-130` (_calc_prorated_qty), `229-231`

- **FR-009** (unwanted): IF contractAmount 또는 executionAmount가 명시적으로 제공된 경우, THEN THE SYSTEM SHALL 자동 일할계산을 수행하지 않고 제공된 금액을 그대로 사용한다.
  - 코드 근거: `backend/services/contract_builder.py:228` (has_confirmed_amount)

### 당기(회계연도) 배분

- **FR-010a** (event): WHEN 사업기간이 회계연도 경계를 걸치고(시작연도 ≠ 종료연도) fiscal_year가 제공된 경우, THE SYSTEM SHALL 회계연도 내 개월 비율(fy_shares["current"])로 당기수량과 당기금액을 산출한다.
  - 코드 근거: `backend/services/contract_builder.py:160-190` (_fiscal_year_shares), `262-268`

- **FR-010b** (event): WHEN 사업기간이 회계연도 경계를 걸치고(시작연도 ≠ 종료연도) fiscal_year가 제공된 경우, THE SYSTEM SHALL conflict_type="연도배분확인"인 ConflictResolution을 fee_conflicts 목록에 생성한다.
  - 코드 근거: `backend/services/contract_builder.py:269-273`

- **FR-011** (unwanted): IF currentQty 또는 currentAmount가 명시적으로 제공된 경우, THEN THE SYSTEM SHALL 자동 비율 배분을 수행하지 않고 제공된 당기값을 그대로 사용한다.
  - 코드 근거: `backend/services/contract_builder.py:256-261`

- **FR-012** (unwanted): IF 사업기간이 단년도(시작연도=종료연도)이면, THEN THE SYSTEM SHALL 집행수량 전체를 당기수량으로 설정한다.
  - 코드 근거: `backend/services/contract_builder.py:274-276`

### 템플릿 행 확장

- **FR-013a** (event): WHEN fee_items 건수가 기본 템플릿 슬롯(9건)을 초과하면, THE SYSTEM SHALL 합계행 위에 초과분만큼 행을 삽입한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:70-73` (0차), `100-103` (수정집행)

- **FR-013b** (event): WHEN fee_items 건수가 기본 템플릿 슬롯(9건)을 초과하면, THE SYSTEM SHALL 삽입된 행에 직전 템플릿 행의 셀 서식을 복사한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:74-76` (0차), `104-106` (수정집행)

### 수정집행 차수 열 분리

- **FR-014** (event): WHEN revision >= 1인 경우, THE SYSTEM SHALL 수정집행 양식으로 당초(이전 차수)를 H/I/N/O열에, 변경(현재 차수)를 K/L/Q/R열에, 당기를 X/Y열에 분리 기록한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:97-135` (_write_rev_rows)

- **FR-015a** (event): WHEN 이전 차수 prev_fee_items가 있고 revision >= 1인 경우, THE SYSTEM SHALL 품명과 협력사명이 일치하는 이전 차수 항목을 당초값으로 매핑한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:144-149` (_match_item 일치 경로)

- **FR-015b** (unwanted): IF 이전 차수 prev_fee_items에 품명과 협력사명이 일치하는 항목이 없으면, THEN THE SYSTEM SHALL 동일 순번(index)의 이전 항목을 fallback으로 사용한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:150-153` (_match_item fallback 경로)

### 수수료 항목 없음

- **FR-016** (unwanted): IF SprintContract.fee_items가 비어 있으면, THEN THE SYSTEM SHALL 5-4 시트를 수정하지 않고 즉시 반환한다.
  - 코드 근거: `backend/services/excel/fee_sheet.py:43-44`

### 자재코드 할당

- **FR-017** (ubiquitous): THE SYSTEM SHALL fee 범주 수수료 항목에 자재코드 1을 할당한다.
  - 코드 근거: `backend/services/contract_builder.py:18` (CATEGORY_TO_CODE={"fee": 1})

---

## Success Criteria (측정형)

- **SC-001**: 0차 시트 생성 시 fee_items 전 행의 H/I/K/L/Q/R 셀이 FeeItem 필드와 **100%** 일치한다.
  - 근거: `backend/services/excel/fee_sheet.py:85-93`, `backend/services/reviewer.py:219-224`

- **SC-002**: 역마진(집행단가 > 계약단가) 행이 존재하는 경우 **100%** 감지된다.
  - 근거: `backend/services/reviewer.py:191-193` (l_val > i_val and i_val > 0)

- **SC-003**: 수량×단가와 금액의 허용 오차는 **1원 미만** 이다. 1원 이상 차이는 FAIL.
  - 근거: `backend/services/reviewer.py:169` (`abs(...) > 1`), `backend/services/excel/fee_sheet.py:141`

- **SC-004**: 기본 슬롯(9건) 초과 시 행 삽입 후 모든 항목이 **누락 없이** 기록된다.
  - 근거: `backend/services/excel/fee_sheet.py:70-76` (DEFAULT_MAX_ITEMS=9)

- **SC-005**: revision >= 1 수정집행 시 당초/변경 컬럼 분리가 **100%** 이루어진다.
  - 근거: `backend/services/excel/fee_sheet.py:116-130`

- **SC-006**: 다년도 사업의 당기수량이 전체 집행수량보다 **작아야** 한다. 같거나 크면 FAIL.
  - 근거: `backend/services/reviewer.py:207-212` (연도분리 검증)

- **SC-007**: 회계연도 배분 후 당기+이후1+이후2의 합이 전체 금액과 **1원 이내** 차이여야 한다(prev=0인 경우 잔여분 이후2 버킷 흡수).
  - 근거: `backend/services/contract_builder.py:193-201` (_split_by_shares)

- **SC-008**: 수식 셀(J/M/S/Z)에 대한 강제 입력은 금액이 수량×단가와 **1원 이상** 다를 때만 수행된다.
  - 근거: `backend/services/excel/fee_sheet.py:139-142`

---

## Key Entities

| 엔터티 | 정의 | 코드 근거 |
|--------|------|-----------|
| `FeeItem` | 수수료 항목 모델. code/vendor/item_name/spec/unit/contract_qty/contract_unit_price/contract_amount/execution_qty/execution_unit_price/execution_amount/current_period_qty/current_period_amount/source_doc | `backend/models/sprint_contract.py:59-73` |
| `SprintContract.fee_items` | FeeItem 목록. revision/prev_fee_items도 보유 | `backend/models/sprint_contract.py` |
| `ConflictResolution` | 연도배분확인 등 게이트 플래그. conflict_type/description/options/user_choice/resolved_value | `backend/models/sprint_contract.py:51-57` |
| `FeeSheetWriter` | 5-4 시트 라이터. sheet_name="5-4. 수수료산출내역" | `backend/services/excel/fee_sheet.py:38-39` |
| `CATEGORY_TO_CODE` | 범주→자재코드 매핑. fee=1 | `backend/services/contract_builder.py:18` |
| `DATA_START_ROW` | 0차 데이터 시작 행. 기본값 8 | `backend/services/excel/fee_sheet.py:18`, `backend/services/reviewer.py:36` |
| `REV_DATA_START_ROW` | 수정집행 데이터 시작 행. 기본값 9 | `backend/services/excel/fee_sheet.py:19` |
| `DEFAULT_MAX_ITEMS` | 기본 템플릿 슬롯 수. 9 | `backend/services/excel/fee_sheet.py:22` |

---

## Assumptions

아래 값은 코드 현행값을 잠정 인용한 것이다. 권위 출처(계약서·요율표 공문)가 별도로 확정되면
해당 값을 우선하며 spec을 갱신해야 한다.

- **A-01 (잠정)**: DATA_START_ROW=8, DEFAULT_MAX_ITEMS=9, DEFAULT_TOTAL_ROW=17 — harness/cell_map.json으로 런타임 오버라이드 가능.
  - 코드 근거: `backend/services/excel/fee_sheet.py:18-22`, `backend/services/reviewer.py:30-37`
- **A-02 (잠정)**: 일할계산 분모 = 30일 고정(업계 관행).
  - 코드 근거: `backend/services/contract_builder.py:117` 주석 "30일 고정 분모 — 업계 관행"
- **A-03 (잠정)**: CATEGORY_TO_CODE["fee"] = 1 (자재코드).
  - 코드 근거: `backend/services/contract_builder.py:18`
- **A-04 (잠정)**: 연도분리 버킷은 당기(current)/이후1(next1)/이후2(next2) 3개 — 3개 연도 초과분은 next2에 합산.
  - 코드 근거: `backend/services/contract_builder.py:160-190` 주석
- **A-05 (잠정)**: 이전 차수 항목 매칭 순서: 품명+협력사명 → 동일 순번 fallback.
  - 코드 근거: `backend/services/excel/fee_sheet.py:144-153`
- **A-06 (잠정)**: 수정집행 0차 원본 시트명 = "5-4. 수수료산출내역 (0차)", N차 시트명 = "5-4. 수수료산출내역 (N차)".
  - 코드 근거: `backend/services/excel/fee_sheet.py:54`, `64-65`

---

## Clarifications Retained

### [NEEDS CLARIFICATION] NC-01: 수수료 코드 1/2/3 정량 판단 기준

설계서 §6-1 항목 5에 해당. CATEGORY_TO_CODE는 fee=1로 하드코딩되어 있으나,
수수료 코드 1/2/3의 비즈니스 의미와 판단 기준이 명시된 공식 문서가 없다.

- 충돌 출처: `backend/services/contract_builder.py:18` (fee=1 단일값) vs `.claude/agents/planner.md` ("[추측] 가능"으로만 기술)
- 확인 방법: 발주처 계약 표준서 또는 수수료 코드 정의 문서 확인

### [NEEDS CLARIFICATION] NC-02: 수수료 시트 DATA_START_ROW/DATA_END_ROW 런타임 값

harness/cell_map.json이 런타임에 로드되어 DATA_START_ROW/DATA_END_ROW를 오버라이드할 수 있다.
기본값(8/16)이 운영 양식과 항상 일치하는지 보장하는 메커니즘이 없다.

- 충돌 출처: `backend/services/excel/fee_sheet.py:18` (DATA_START_ROW=8 기본) vs `backend/services/reviewer.py:30-37` (cell_map.json 우선 로드)
- 확인 방법: 운영 양식 버전별 cell_map.json 관리 정책 확인

### [NEEDS CLARIFICATION] NC-03: 일할계산 소수점 수량(0.1 단위) 반올림 정책

일할계산 결과를 0.1 단위로 반올림하는 규칙(`round(prorated_qty, 1)`)이 업계 표준인지
또는 사내 정책인지 권위 문서가 없다.

- 출처: `backend/services/contract_builder.py:129` 주석 "0.1 단위 반올림" (단일, 근거 미명시)
- 확인 방법: 노무비 산출 지침 또는 집행계획서 작성 지침 확인

### [NEEDS CLARIFICATION] NC-04: 수정집행 당기 열 위치 (Z열 강제 입력 조건)

Z열(수정집행 당기금액)에 강제 입력하는 조건(`current_period_amount != expected`)의
허용 오차 기준이 코드에 명시되지 않아 `round()` 비교만 사용한다.

- 출처: `backend/services/excel/fee_sheet.py:131-133` (round 비교만, > 1 오차 기준 미명시)
- 확인 방법: 수정집행 시트 양식 작성 지침 확인

> **참고**: 직급단가표 3중 충돌(550만/600만/650만) 및 상여금 공식 충돌(전액 vs /9)은
> EXE-07 수수료 항목과 직접 관련 없다(노무비 계산은 EXE-09 관할). EXE-07의 fee_items는
> 견적서에서 추출된 contract_price/execution_price를 그대로 사용한다.
