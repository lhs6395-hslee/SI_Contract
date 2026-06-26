# Feature Specification: EXE-08 집행예산 산출내역서·집계표

**Feature Branch**: `EXE-08-breakdown-sheet`  **Created**: 2026-06-26  **Status**: Draft
**Input**: SprintContract(budget_items + active_items)를 받아 공통 시트 비목 블록(행23~112)에 금액을 기록하고, 5.집행예산산출내역서·4.집행예산집계표 수식 체인이 자동 집계되도록 한다.

---

## ⚙ 작성 규칙

모든 Functional Requirement는 EARS 표기 5패턴 중 하나로만 작성한다.  
값을 모르면 임의로 정하지 않고 `[NEEDS CLARIFICATION: 무엇을 확인해야 하나]`로 표시한다.

---

## 범위 명기

**이 기능의 성격: 도메인(공통 시트 입력 레이어)**

- `BreakdownSheetWriter`는 **공통 시트**(`wb["공통"]`)의 차수별 열(E=0차, F=1차 … P=11차)에  
  비목 금액을 직접 입력하는 레이어다.
- `5.집행예산산출내역서` 및 `4.집행예산집계표`는 **모두 수식 시트**로, 입력값이 아닌 공통 시트 참조  
  수식으로 구성된다. 이 기능은 수식 시트를 수정하지 않는다.
- **EXE-09(노무비 상세)와 BUDGET_BLOCKS 공유**: `BUDGET_BLOCKS`의 `labor`/`bonus` 블록은  
  EXE-09가 급료·상여 산출 규칙을 소유하고, EXE-08은 해당 산출 결과를 수신해 블록에 기록한다.
- **EXE-11(연도분리 엔진) 소비**: 다년도 사업 시 `_fiscal_year_shares`/`_split_by_shares`를  
  호출해 당기/이후1/이후2를 배분한다. 연도분리 로직 자체는 EXE-11 소유.
- **퇴직금·보험료는 산출내역서 수식이 자동 계산**하므로 이 기능이 직접 입력하지 않는다.  
  (`company_standards.py:44-46 AUTO_CALCULATED_KEYWORDS`)

---

## User Scenarios & Testing

### User Story 1 — active_items 기준 비목 기록 (Priority: P1)

집행 담당자가 확정한 비목 항목(active_items=true)의 금액을 산출내역서 양식에 정확히 반영하고 싶다.  
budget_items 각 카테고리가 공통 시트 해당 행에 기록되면, 5.집행예산산출내역서 수식이 자동으로  
집행금액·계약금액·당기/이후 금액을 집계한다.

- **Independent Test**: `BreakdownSheetWriter._write()` 실행 후 `공통[E25]`(급료 집행행)에 기대값이 기록되는지 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** `budget_items = [BudgetItem(category="labor", execution_amount=39_250_000, ...)]`이고 `revision=0`일 때,  
     **When** `BreakdownSheetWriter._write()`를 실행하면,  
     **Then** `공통!E25 = 39_250_000`이고 `StepResult.status = completed`, `inputs_used`에 출처(`budget_items.labor.execution`)가 기록된다.

### User Story 2 — 이중 계상 방지 (Priority: P1)

퇴직금·보험료 항목이 costItems에 포함되어도 공통 시트에 이중으로 기입되어서는 안 된다.

- **Independent Test**: `is_auto_calculated("퇴직금")`이 True를 반환하고, `budget_items`에서 해당 항목이 스킵된다.
- **Acceptance (Given/When/Then)**:
  1. **Given** `costItems`에 `name="퇴직금"`인 항목이 포함되어 있을 때,  
     **When** `build_sprint_contract()`를 호출하면,  
     **Then** `budget_items`에 `퇴직금` 카테고리가 포함되지 않고, `conflict_resolutions`에  
     `conflict_type="자동계산중복"` 항목이 추가된다.

### User Story 3 — 하위 호환 급료 산출 (Priority: P2)

`budget_items`에 labor가 없을 때 `staff_plan`에서 급료를 산출해 기록한다.

- **Independent Test**: `budget_items`에 labor 없이 `staff_plan` 2명이 있을 때,  
  `공통!E25`에 `monthly_rate × sum(months)` 합계가 기록된다.
- **Acceptance (Given/When/Then)**:
  1. **Given** `budget_items`에 `category="labor"`가 없고 `staff_plan`에 직접 인원 2명이 있을 때,  
     **When** `BreakdownSheetWriter._write()`를 실행하면,  
     **Then** `공통!E25 = sum(monthly_rate × months)`, `inputs_used[*].source = "staff_plan 급료합계"`이다.
- **[NEEDS CLARIFICATION: `staff_plan` 항목에 `monthly_rate`가 없을 때 `standard_rate_for(grade)`를 fallback으로 사용하는지 여부 및 해당 시 직급 단가표 어느 값을 기준으로 하는지 — 설계 §6-1 항목 1 충돌: `company_standards.py` 과장 550만 / `executor.md:101` 600만 / `REPORT_eps_values.md:144` 650만]**

### User Story 4 — 다년도 사업 당기/이후 배분 (Priority: P2)

프로젝트 기간이 회계연도를 걸치면 비목 금액이 당기/이후1/이후2로 분리 기록되어야 한다.

- **Independent Test**: 2025-10-01 ~ 2026-06-30, 회계연도 2025 설정 시  
  `공통!E27`(당기)와 `공통!E28`(이후1)의 합계가 `공통!E25`(집행)와 같다.
- **Acceptance (Given/When/Then)**:
  1. **Given** `project_period.start="2025-10-01"`, `project_period.end="2026-06-30"`, `fiscal_year=2025`이고  
     `budget_items.labor.execution_amount=39_000_000`일 때,  
     **When** `BreakdownSheetWriter._write()`를 실행하면,  
     **Then** `공통!E27 + 공통!E28 = 39_000_000`이고, 두 값 모두 0이 아니다.

### Edge Cases

- `BUDGET_BLOCKS`에 없는 `category` 값은 무시된다. (`breakdown_sheet.py:55-56 block = BUDGET_BLOCKS.get(item.category)`)
- `bonus` 블록은 `contract` 행이 없다(`None`). `block.get("contract")` = `None` → 해당 셀 기록 생략.  
  (`breakdown_sheet.py:26-28 "bonus": {"contract": None, ...}`)
- VAT/부가세 항목은 `build_sprint_contract`에서 이미 제외 처리된다. (`contract_builder.py:382-384`)
- 셀 색상이 `FF0070C0`(파란)이면 `write_cell`이 기록을 생략한다. (`base.py:85-86`)
- 수식 셀(`data_type == "f"`)에는 기록하지 않는다. (`base.py:87-88`)

---

## Functional Requirements (EARS)

- **FR-001** (event): WHEN `budget_items` 중 `active_items`가 true인 비목을 수신하면, THE SYSTEM SHALL 해당 카테고리의 `BUDGET_BLOCKS` 행에 계약·집행·정산·당기·이후1·이후2 금액을 공통 시트 차수 열에 기록한다.  
  *코드 근거:* `breakdown_sheet.py:52-67 BreakdownSheetWriter._write()`

- **FR-002** (ubiquitous): THE SYSTEM SHALL `write_cell` 호출 시 `inputs_used`에 셀 참조·값·출처(`source`)를 항상 보존한다.  
  *코드 근거:* `base.py:82-97 SheetWriter.write_cell()`

- **FR-003a** (unwanted): IF 비목 카테고리가 `AUTO_CALCULATED_KEYWORDS`(퇴직금·보험료·국민연금·건강보험·산재보험·고용보험)에 해당하면, THEN THE SYSTEM SHALL 해당 항목을 비목 입력에서 제외한다.  
  *코드 근거:* `company_standards.py:43-50 is_auto_calculated()`, `contract_builder.py:377-382`

- **FR-003b** (unwanted): IF 비목 카테고리가 `AUTO_CALCULATED_KEYWORDS`에 해당하면, THEN THE SYSTEM SHALL 해당 항목을 `conflict_type="자동계산중복"`으로 `conflict_resolutions`에 플래그한다.  
  *코드 근거:* `contract_builder.py:377-382`

- **FR-004** (unwanted): IF 비목 이름에 VAT·V.A.T·부가세가 포함되면, THEN THE SYSTEM SHALL 해당 항목을 비목 입력에서 제외한다.  
  *코드 근거:* `contract_builder.py:382-384`

- **FR-005a** (state): WHILE `budget_items`에 `category="labor"`가 없고 `staff_plan`에 직접 인원이 있는 동안, THE SYSTEM SHALL `monthly_rate × sum(months)` 합계로 급료를 산출해 `labor` 블록 집행 행에 기록한다.  
  *코드 근거:* `breakdown_sheet.py:69-88`, `contract_builder.py:454-496`  
  **[NEEDS CLARIFICATION: staff_plan 항목에 `monthly_rate`가 없을 때 `standard_rate_for(grade)`를 fallback으로 사용하는지 여부 및 해당 시 직급 단가표 어느 값을 기준으로 하는지 — 설계 §6-1 항목 1 충돌: `company_standards.py` 과장 550만 / `executor.md:101` 600만 / `REPORT_eps_values.md:144` 650만]**

- **FR-005b** (state): WHILE `budget_items`에 `category="labor"`가 없고 `staff_plan`에 직접 인원이 있는 동안, THE SYSTEM SHALL `conflict_type="급료확인"`으로 관문 재확인을 요청한다.  
  *코드 근거:* `breakdown_sheet.py:69-88`, `contract_builder.py:454-496`

- **FR-006** (optional): WHERE 사업기간이 회계연도 경계를 걸치면, THE SYSTEM SHALL `_fiscal_year_shares`와 `_split_by_shares`를 사용해 집행 금액을 당기·이후1·이후2로 배분한다.  
  *코드 근거:* `breakdown_sheet.py:79-88`, `contract_builder.py:160-201`  
  *불변 조건 → SC-002로 이관*: `current + next1 + next2 = execution` 합계 보존은 SC-002가 측정 기준으로 소유한다.

- **FR-007** (unwanted): IF `bonus` 블록의 `contract` 행이 `None`이면, THEN THE SYSTEM SHALL 해당 셀에 값을 기록하지 않는다.  
  *코드 근거:* `breakdown_sheet.py:64-67 "if row is not None:"`

- **FR-008** (unwanted): IF 셀 색상이 `FF0070C0`(파란색, 고정값)이거나 수식 셀(`data_type=="f"`)이면, THEN THE SYSTEM SHALL 해당 셀 값을 덮어쓰지 않는다.  
  *코드 근거:* `base.py:85-88`

- **FR-009** (ubiquitous): THE SYSTEM SHALL 차수(`revision`)에 따라 대상 열을 `rev_col(revision)`으로 결정한다(E=0차, F=1차 … P=11차).  
  *코드 근거:* `utils.py:6-8 rev_col()`, `breakdown_sheet.py:49`

- **FR-010** (unwanted): IF `item.name`이 `CATEGORY_LABELS` 집합의 문자열과 동일하면, THEN THE SYSTEM SHALL 산출내역(`desc`)에 해당 이름을 기록하지 않는다.  
  *코드 근거:* `contract_builder.py:26-33 CATEGORY_LABELS`, `contract_builder.py:389-390`

---

## Success Criteria (측정형)

- **SC-001**: `active_items`가 true인 모든 비목 카테고리에 대해 집행 금액이 공통 시트 대응 행에 오차 0원으로 기록된다. (1원 정밀도 — `constitution.md §IV`)
- **SC-002**: 다년도 배분 시 `current + next1 + next2 = execution_amount`를 1원 오차 이내로 충족한다.  
  *코드 근거:* `contract_builder.py:193-201 _split_by_shares()` — 잔여분을 `nx2 = round(amount) - cur - nx1`으로 보존.
- **SC-003**: `AUTO_CALCULATED_KEYWORDS` 항목이 `budget_items`에 포함되는 경우는 0건이다.
- **SC-004**: VAT/부가세 항목이 공통 시트에 기록되는 경우는 0건이다.
- **SC-005**: `inputs_used` 리스트의 모든 항목에 `source` 필드가 기록되어 있다. (`constraint_compliance["소스_근거_명시"] = True`)  
  *코드 근거:* `base.py:107-108`
- **SC-006** *(Draft — 요율 기준 미확정 시 실행 불가)*: 보험료 요율 검증 — 집행 요율 4.75%/4.0674%/0.796%/1.75% vs. 정산 요율 4.5%/4.0041%/0.766%/1.75%의 적용 기준이 확정된 후, 해당 기준과 공통 시트 요율 셀 값의 오차가 0.0001 미만이다.  
  *코드 근거:* `reviewer.py:376-388`, `REPORT_eps_values.md:174-180`  
  **[NEEDS CLARIFICATION: 집행 요율과 정산 요율 중 어느 기준을 우선 적용하는지, 적용 연도 기준 및 갱신 정책 — 설계 §6-1 항목 3]**  
  *주의: 수치 출처(`REPORT_eps_values.md:174-180`)가 인용되어 있으나 적용 기준이 미결이므로, 기준 확정 전에는 Draft 주석 수준으로 취급하며 SC로서 검증 불가 상태임.*
- **SC-007** *(Draft — 상한값 미확정 시 검증 불가)*: `StepResult.status = completed`가 반환되고 `notes`가 비어 있을 때, 공통 시트의 변경 셀 수가 `inputs_used` 길이와 일치한다.  
  **[NEEDS CLARIFICATION: 허용 최대 입력 셀 수(비목 블록 행 수 기반 상한값) 확정 필요]**  
  *주의: 상한값이 확정될 때까지 이 항목은 검증 가능한 SC 기준을 충족하지 못한다. 상한값 확정 후 Draft 해제.*

---

## Key Entities

| 엔티티 | 설명 | 코드 위치 |
|--------|------|-----------|
| `BreakdownSheetWriter` | 공통 시트 비목 블록 기록 실행자 | `breakdown_sheet.py:43` |
| `BUDGET_BLOCKS` | 비목 카테고리 → 공통 시트 행 번호 매핑 (13종, 행23~112) | `breakdown_sheet.py:26-40` |
| `BudgetItem` | 비목 1건 (카테고리·desc·계약·집행·정산·당기·이후1·이후2) | `models/sprint_contract.py` |
| `SprintContract.budget_items` | 집계 대상 비목 목록 | `contract_builder.py:409` |
| `SprintContract.active_items` | 활성화된 비목 집합 | `contract_builder.py:359` |
| `rev_col(revision)` | 차수 → 열 문자 변환 | `utils.py:6-8` |
| `SheetWriter.write_cell()` | 색상·수식 셀 방어 기록 | `base.py:82-97` |
| `_fiscal_year_shares()` | 연도 경계 비율 계산 (EXE-11 공유) | `contract_builder.py:160` |
| `_split_by_shares()` | 금액 배분 + 합계 보존 (EXE-11 공유) | `contract_builder.py:193` |
| `AUTO_CALCULATED_KEYWORDS` | 이중 계상 방지 키워드 목록 | `company_standards.py:43-45` |
| `CATEGORY_LABELS` | desc 에코 방지 라벨 집합 | `contract_builder.py:26-33` |

---

## Assumptions

아래 값은 코드 현행값으로 인용하되, 권위 출처(공문·계약서)가 확정될 때까지 **잠정값**이다.

| 항목 | 현행 코드값 | 코드 위치 | 비고 |
|------|------------|-----------|------|
| 간접비 요율 | 1.9% | `company_standards.py:28 "indirect_rate": 1.9` | REPORT 97-98 일치, 잠정 |
| 일반관리비 요율 | 3.0% | `company_standards.py:29 "admin_rate": 3.0` | REPORT 98 일치, 잠정 |
| 차수 열 범위 | E(0차) ~ P(11차) = 12열 | `utils.py:6-8`, `company_standards.py:11-12` | MAX_REVISION=11 |
| BUDGET_BLOCKS 비목 13종 | labor/bonus/wage/welfare/travel/vehicle/equipment/rent/transport/comm/print/safety/etc | `breakdown_sheet.py:26-40` | 행23~112 |
| bonus 블록 contract 행 | None (계약금액 행 없음) | `breakdown_sheet.py:28` | 잠정 |
| 산출내역서 입력 셀 색상 | 노란(FFFFFFCC) | `base.py:24 INPUT_COLORS` | 잠정 |
| 고정값 셀 색상 | 파란(FF0070C0) | `base.py:25 SKIP_COLORS` | 잠정 |
| 퇴직금 수식 | `(급료+상여)/12` — 수식 자동계산, 직접 입력 제외 | `REPORT_eps_values.md:159-164` | 잠정 |
| 30일 고정 분모(일할계산) | 30 | `contract_builder.py:118 "30일 고정 분모 — 업계 관행"` | 잠정 |

---

## Clarifications Retained

설계 §6-1 기준, 이 기능에 직접 귀속된 미확정 항목:

1. **[NEEDS CLARIFICATION] 보험료 요율 기준**: 집행 요율(4.75%/4.0674%/0.796%/1.75%) vs. 정산 요율(4.5%/4.0041%/0.766%/1.75%)  
   - 출처 A: `REPORT_eps_values.md:174-180` — 집행/정산 요율 이원화 확인  
   - 출처 B: `company_standards.py:30-34 DEFAULT_RATES` — 정산 기준 요율(4.5/4.0041/0.766/1.75)  
   - 충돌: 집행 열과 정산 열에 서로 다른 요율이 하드코딩됨. 적용 기준연도·갱신 정책 미정.  
   - EXE-03과 동일 충돌 항목.

2. **[NEEDS CLARIFICATION] 간접비·일반관리비 공문 근거**: 1.9%/3.0%는 코드·REPORT 일치 확인됐으나, 원칙적인 수치 확정 근거(공문/계약서)가 없음.  
   - 출처 A: `company_standards.py:28-29` — 주석 "윤지민과장 문의 — 25년 기준"  
   - 출처 B: `REPORT_eps_values.md:97-98` V37=0.019, V38=0.03  
   - 충돌 아님, 단 권위 출처 미확정 → 잠정.

3. **[NEEDS CLARIFICATION] 안전관리비 산출 기준**: 설계 §6-2에 "안전관리비 인원×5만"이 언급되나, 이를 확인할 수 있는 코드·REPORT 출처가 이 파일에 직접 없음.  
   - 출처 미발견: `breakdown_sheet.py`, `contract_builder.py` 내 `safety` 블록에 별도 수식 없음.  
   - 확인 필요: 해당 수식이 양식 수식으로만 처리되는지, 아니면 코드에서 입력하는지.
