# Feature Specification: EXE-11 — 연도분리 엔진 (공유)

**Feature Branch**: `EXE-11-fiscal-year-split`  **Created**: 2026-06-26  **Status**: Draft
**Input**: 사업 기간이 회계연도 경계를 걸칠 때, 금액·수량을 당기/이후1/이후2 버킷으로 배분하는 공유 계산 엔진

> **성격**: 공유 엔진 — `_fiscal_year_shares` / `_split_by_shares` 함수를 EXE-06·07·08·09가 소비.
> 이 spec의 FR은 위 두 함수 및 `common_sheet.py:_calc_period_ratios`의 **현재 구현(as-is)** 동작을 정형화한다.
> `.kiro` 요구(Requirement 3·7·8·9·10)의 미구현 모델 확장(settlement_cumulative_qty 등 신규 필드, 이월 차수 생성 API, SprintContract is_multi_year 등)은 **[TO-BE]** 절에 별도 표기하며 as-is 스펙과 섞지 않는다.

---

## ⚙ 작성 규칙

모든 Functional Requirement는 EARS 5패턴 중 하나로만 작성한다. 값은 출처 file:line이 있는 단일 값만 인용한다. 충돌값은 `[NEEDS CLARIFICATION]`으로 처리한다.

---

## User Scenarios & Testing

### User Story 1 — 다년도 사업 연도분리 비율 계산 (Priority: P1)

집행계획서 작성자는 사업 기간이 2025.09 ~ 2026.09처럼 회계연도 경계를 걸칠 때, 수동 계산 없이 당기/이후1/이후2 비율을 시스템이 산출해 주기를 원한다.
- **Independent Test**: `_fiscal_year_shares("2025-09-01", "2026-09-30", 2025)` 호출 결과의 `current + next1 + next2 + prev` ≈ 1.0 (부동소수 허용 범위 내) 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** `start_date="2025-09-01"`, `end_date="2026-09-30"`, `fiscal_year=2025`, **When** `_fiscal_year_shares` 호출, **Then** `current`(2025년 내 개월 비율) + `next1`(2026년 내 개월 비율) 합이 ≈ 1.0이고 total_mm > 0.
  2. **Given** `start_date="2025-01-01"`, `end_date="2025-12-31"`, `fiscal_year=2025`, **When** `_fiscal_year_shares` 호출, **Then** 반환값이 `None`(단년도 — 배분 불필요).
  3. **Given** `start_date="2024-06-01"`, `end_date="2027-03-31"`, `fiscal_year=2025`, **When** `_fiscal_year_shares` 호출, **Then** `prev`(2024년 구간), `current`(2025년), `next1`(2026년), `next2`(2027년) 모두 > 0.

### User Story 2 — 금액 배분 및 합계 보존 (Priority: P1)

집행계획서 작성자는 다년도 배분 시 당기 + 이후1 + 이후2 금액 합계가 원래 집행 총액과 일치하기를 원한다(1원 오차 FAIL).
- **Independent Test**: `_split_by_shares(amount=10_000_000, shares={"current":0.333,"next1":0.334,"next2":0.333,"prev":0})` 호출 후 `cur + nx1 + nx2 == 10_000_000` 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** prev=0인 shares, amount=N원, **When** `_split_by_shares` 호출, **Then** `cur + nx1 + nx2 == round(N)`(1원 오차 없음 — 잔여분 nx2 보정).
  2. **Given** prev>0인 shares(중간 차수 시나리오), **When** `_split_by_shares` 호출, **Then** `cur + nx1 + nx2 <= round(N)`(prev 구간 제외, 합계 ≤ N).

### User Story 3 — 공통 시트 비율 기록 (Priority: P2)

집행계획서 작성자는 공통 시트 D13~D16 행에 정산누계/당기계획/당기이후(내년)/당기이후(내후년~) 비율이 자동으로 채워지기를 원한다.
- **Independent Test**: `_calc_period_ratios("2025-09-01", "2026-09-30", 2025)` 반환값 `{13: ≈0.33, 14: ≈0.67, 15: None·0, 16: None}` 형태 검증 (실제 날짜 계산치).
- **Acceptance (Given/When/Then)**:
  1. **Given** 다년도 기간, `fiscal_year=2025`, **When** `CommonSheetWriter._write()` 실행, **Then** `col13`(정산누계비율), `col14`(당기계획비율), `col15`(당기이후 내년비율), `col16`(당기이후 내후년~비율) 셀에 비율값 기록.
  2. **Given** 단년도 사업(`start.year == end.year`), **When** `_fiscal_year_shares` 호출, **Then** `None` 반환 → 연도분리 로직 미실행.

### Edge Cases
- `fiscal_year`가 `None`이면 → `_fiscal_year_shares` 반환값 `None`(연도분리 미실행) [공식 코드 `contract_builder.py:174`].
- `start_date`·`end_date` 파싱 실패(ValueError/TypeError)이면 → `None` 반환 [공식 코드 `contract_builder.py:169-173`].
- prev 비율이 `1e-9` 미만이면 → nx2 = round(amount) - cur - nx1 (잔여분 전액 이후2) [공식 코드 `contract_builder.py:197-199`].
- `total_mm <= 0`이면 → `None` 반환 [공식 코드 `contract_builder.py:178`].
- 3개 회계연도 초과분(이후2 버킷): `fiscal_year+2`년 이후는 단일 이후2 버킷으로 합산 [공식 코드 `contract_builder.py:187`].
- 시작일이 월 1일이 아닌 경우 일할 계산: `start_ratio = (days_in_month - start.day + 1) / 30` [공식 코드 `contract_builder.py:153-156`].
- `_mm_between(start, end)` 에서 `end < start`이면 → `0.0` 반환(음수 구간 → 빈 기간으로 처리) [공식 코드 `contract_builder.py:147-157` 루프 구조상 월 순회 중 조건 미충족 시 0 누적].

---

## Functional Requirements (EARS)

### 핵심 엔진 함수 (`_fiscal_year_shares`, `_split_by_shares`)

- **FR-001a** (event): WHEN `_fiscal_year_shares(start_date, end_date, fiscal_year)` 가 호출될 때, THE SYSTEM SHALL 사업 기간을 `_mm_between`으로 개월수(`total_mm`)로 환산한다.
  - `[공식 코드]` `backend/services/contract_builder.py:176`

- **FR-001b** (event): WHEN `_fiscal_year_shares` 가 `total_mm > 0` 인 유효한 기간을 환산한 뒤, THE SYSTEM SHALL `{"current": float, "next1": float, "next2": float, "prev": float, "total_mm": float}` 비율 딕셔너리를 반환한다.
  - `[공식 코드]` `backend/services/contract_builder.py:189-190`

- **FR-002** (unwanted): IF 사업 기간이 단일 회계연도 내에 있거나(`end.year == start.year`) `fiscal_year`가 `[start.year, end.year]` 범위 밖이거나 `total_mm <= 0`이면, THEN THE SYSTEM SHALL `None`을 반환하여 연도분리 로직을 실행하지 않는다.
  - `[공식 코드]` `backend/services/contract_builder.py:174-178`

- **FR-003** (unwanted): IF `start_date` 또는 `end_date` 파싱이 실패하면(`ValueError` 또는 `TypeError`), THEN THE SYSTEM SHALL `None`을 반환하고 예외를 전파하지 않는다.
  - `[공식 코드]` `backend/services/contract_builder.py:169-173`

- **FR-004a** (event): WHEN `_fiscal_year_shares` 가 구간 계산을 수행할 때, THE SYSTEM SHALL `fiscal_year`년에 해당하는 개월수를 `total_mm` 대비 비율(`current`)로 산출한다.
  - `[공식 코드]` `backend/services/contract_builder.py:185`

- **FR-004b** (event): WHEN `_fiscal_year_shares` 가 구간 계산을 수행할 때, THE SYSTEM SHALL `fiscal_year+1`년에 해당하는 개월수를 `total_mm` 대비 비율(`next1`)로 산출한다.
  - `[공식 코드]` `backend/services/contract_builder.py:186`

- **FR-004c** (event): WHEN `_fiscal_year_shares` 가 구간 계산을 수행할 때, THE SYSTEM SHALL `fiscal_year+2`년 이후 종료일까지의 개월수를 `total_mm` 대비 비율(`next2`)로 산출한다(3개 연도 초과분 단일 합산).
  - `[공식 코드]` `backend/services/contract_builder.py:187`

- **FR-004d** (event): WHEN `_fiscal_year_shares` 가 구간 계산을 수행할 때, THE SYSTEM SHALL `fiscal_year` 이전 구간의 개월수를 `total_mm` 대비 비율(`prev`)로 산출한다.
  - `[공식 코드]` `backend/services/contract_builder.py:188`

- **FR-005a** (event): WHEN `_split_by_shares(amount, shares)` 가 호출될 때, THE SYSTEM SHALL `cur = round(amount × shares["current"])`를 산출한다.
  - `[공식 코드]` `backend/services/contract_builder.py:194`

- **FR-005b** (event): WHEN `_split_by_shares(amount, shares)` 가 호출될 때, THE SYSTEM SHALL `nx1 = round(amount × shares["next1"])`를 산출한다.
  - `[공식 코드]` `backend/services/contract_builder.py:195`

- **FR-005c** (unwanted): IF `shares["prev"] < 1e-9`(이전 구간이 없으면), THEN THE SYSTEM SHALL `nx2 = round(amount) - cur - nx1`으로 잔여분을 이후2에 배정하여 `cur + nx1 + nx2 == round(amount)`를 보존한다.
  - `[공식 코드]` `backend/services/contract_builder.py:197-199`

  > **반환형**: `(cur: int, nx1: int, nx2: int)` 튜플. `[공식 코드]` `contract_builder.py:193-201`, plan.md 아키텍처 개요 참조.

- **FR-006** (unwanted): IF `shares["prev"] >= 1e-9`(이전 구간이 존재하면), THEN THE SYSTEM SHALL `nx2 = round(amount × shares["next2"])`로 산출하고, prev 구간 금액은 이후2에 더하지 않는다(정산누계는 실적 기반 별도 입력).
  - `[공식 코드]` `backend/services/contract_builder.py:197-200`

- **FR-007a** (ubiquitous): THE SYSTEM SHALL `_mm_between(start, end)` 에서 시작월이 월 1일(`start.day == 1`)이면 해당 월을 1.0으로 계산한다.
  - `[공식 코드]` `backend/services/contract_builder.py:153`

- **FR-007b** (unwanted): IF `_mm_between` 호출 시 `start.day != 1`(시작월이 1일이 아닌 경우), THEN THE SYSTEM SHALL `(days_in_month - start.day + 1) / 30` 으로 해당 월의 일할 비율을 계산한다.
  - `[공식 코드]` `backend/services/contract_builder.py:153-156`

### 공통 시트 비율 기록 (`_calc_period_ratios`)

- **FR-008a** (event): WHEN `CommonSheetWriter._write()` 에서 `fiscal_year`와 사업 기간이 유효할 때, THE SYSTEM SHALL `_calc_period_ratios(start_str, end_str, fiscal_year)`를 호출하여 D13~D16 비율 딕셔너리를 얻는다.
  - `[공식 코드]` `backend/services/excel/common_sheet.py:162-165`

- **FR-008b** (event): WHEN `CommonSheetWriter._write()` 에서 `_calc_period_ratios` 반환값이 유효할 때, THE SYSTEM SHALL D13(정산누계비율)/D14(당기계획비율)/D15(당기이후 내년비율)/D16(당기이후 내후년~비율) 셀에 비율을 기록한다.
  - `[공식 코드]` `backend/services/excel/common_sheet.py:166-171`

- **FR-009** (unwanted): IF `_calc_period_ratios` 에서 `start` 또는 `end` 파싱 실패이면, THEN THE SYSTEM SHALL `{13: None, 14: None, 15: None, 16: None}` 을 반환하고 해당 셀을 기록하지 않는다.
  - `[공식 코드]` `backend/services/excel/common_sheet.py:35-36`

- **FR-010a** (ubiquitous): THE SYSTEM SHALL `_calc_period_ratios` 에서 각 구간 비율을 `round(d / total_days, 6)` 으로 산출한다.
  - `[공식 코드]` `backend/services/excel/common_sheet.py:54`

- **FR-010b** (unwanted): IF `_calc_period_ratios` 에서 산출된 비율이 0 이하이면, THEN THE SYSTEM SHALL 해당 셀 값으로 `None`을 반환한다.
  - `[공식 코드]` `backend/services/excel/common_sheet.py:55-56`

### 소비 기능 연동

- **FR-011** (optional): WHERE 사업이 다년도(`fy_shares is not None`)이면, THE SYSTEM SHALL 수수료 항목(FeeItem)의 당기 수량·금액을 `fy_shares["current"]` 비율로 산출하고 `ConflictResolution(conflict_type="연도배분확인")` 플래그를 추가하여 관문 재확인을 요청한다.
  - `[공식 코드]` `backend/services/contract_builder.py:262-273`

- **FR-012** (unwanted): IF 수수료 항목에 `currentQty` 또는 `currentAmount` 명시값이 있으면, THEN THE SYSTEM SHALL 자동 비율 배분 대신 사용자 확인값을 그대로 사용한다(자동 처리 금지 원칙).
  - `[공식 코드]` `backend/services/contract_builder.py:256-261`

---

## Success Criteria (측정형)

- **SC-001**: `prev=0` 조건에서 `_split_by_shares` 호출 시 `cur + nx1 + nx2 == round(amount)`가 **100%** 케이스에서 성립한다(1원 오차 FAIL). `[공식 코드]` `contract_builder.py:197-199`
- **SC-002**: `_fiscal_year_shares` 반환값의 `current + next1 + next2 + prev` 합계가 `1.0 ± 1e-6` 범위 내에 있어야 한다. `[공식 코드]` `contract_builder.py:185-190`
- **SC-003**: `start_date`·`end_date`·`fiscal_year` 파싱 불가 입력에 대해 `_fiscal_year_shares`가 예외 전파 없이 `None`을 반환해야 한다. `[공식 코드]` `contract_builder.py:169-173`
- **SC-004**: 단년도 사업(`start.year == end.year`)에서 `_fiscal_year_shares`가 `None`을 반환하여 연도분리 로직이 실행되지 않아야 한다. `[공식 코드]` `contract_builder.py:174`
- **SC-005**: `_calc_period_ratios` 반환 비율의 합계(None 제외)가 `1.0 ± 1e-4` 범위 내에 있어야 한다. `[공식 코드]` `common_sheet.py:49-56`
  - **허용 오차 근거**: SC-002(개월수 기반, 1e-6)보다 완화된 이유는 `_calc_period_ratios`가 일수(`(end - start).days + 1`) 기반으로 비율을 계산하고 각 구간을 독립적으로 `round(..., 6)` 하기 때문에 부동소수 누적 오차가 개월수 방식 대비 크다. 허용 오차 1e-4는 최장 3개 연도(약 1095일) 구간에서 6자리 반올림 오차가 누적될 때 합계 오차가 최대 3e-6×구간수 수준임을 고려한 실용 기준이다. `[공식 코드]` `common_sheet.py:39` (일수 기반 분모), Assumptions NC-01 참조.
- **SC-006**: `fy_shares` 비nil 시 FeeItem에 `ConflictResolution(conflict_type="연도배분확인")` 레코드가 **반드시** 1건 포함되어야 한다. `[공식 코드]` `contract_builder.py:266-273`
- **SC-007**: 수수료 항목에 `currentQty`/`currentAmount` 명시값이 있을 때 `_build_fee_items`가 `fy_shares` 비율 계산을 건너뛰어야 한다. `[공식 코드]` `contract_builder.py:256-261`

---

## Key Entities

| 엔티티 | 정의 | 출처 |
|--------|------|------|
| `fiscal_year_shares` | `{"current": float, "next1": float, "next2": float, "prev": float, "total_mm": float}` — 비율 딕셔너리 | `contract_builder.py:189-190` |
| `FeeItem.current_period_qty` | 당기 집행 수량 | `contract_builder.py:284` |
| `FeeItem.current_period_amount` | 당기 집행 금액 | `contract_builder.py:285` |
| `BudgetItem.current_amount` | 비목별 당기 금액 | `models.py` (BudgetItem) |
| `BudgetItem.next1_amount` | 비목별 이후1(내년) 금액 | `models.py` |
| `BudgetItem.next2_amount` | 비목별 이후2(내후년~) 금액 | `models.py` |
| `ConflictResolution(conflict_type="연도배분확인")` | 자동 배분 관문 재확인 플래그 | `contract_builder.py:266` |
| `_calc_period_ratios` 반환 | `{13: prev비율, 14: cur비율, 15: next1비율, 16: next2비율}` | `common_sheet.py:58-63` |

---

## Assumptions

- `[잠정 — 코드 현행값]` `_mm_between`의 일할 분모는 30 고정 (`contract_builder.py:156`). 실제 월 일수 대신 30을 사용한다. 이 업계 관행이 권위 문서로 확정되지 않았으므로 잠정.
- `[잠정 — 코드 현행값]` 회계연도는 1월~12월 기준 (`fiscal_year:int` = 연도 정수). 비역년 회계연도 지원은 현행 코드 범위 밖.
- `[잠정 — 코드 현행값]` 3개 회계연도 초과분(fiscal_year+2년~종료)은 단일 이후2 버킷으로 합산 (`contract_builder.py:187`).
- `[잠정 — 코드 현행값]` `_calc_period_ratios`는 개월수 대신 일수(`(end - start).days + 1`)로 비율 계산. `_fiscal_year_shares`의 개월수 기반 계산과 방법론적으로 다르다(`common_sheet.py:39` vs `contract_builder.py:176`). 실무 적용 기준은 `[NEEDS CLARIFICATION]` 참조.

---

## [TO-BE] 미구현 모델 확장 (.kiro 요구 흡수)

다음 항목은 `.kiro` Requirement 3·7·8·9·10에서 요구된 기능이나 현재 코드에 구현되지 않았다. 구현 전 별도 사이클에서 사용자 확인 후 진행한다.

| 항목 | 근거 | 상태 |
|------|------|------|
| `FeeItem.settlement_cumulative_qty/amount` 신규 필드 | Kiro Req.3 | 코드 미구현 |
| `FeeItem.post_current_qty/amount` 신규 필드 | Kiro Req.3 | 코드 미구현 |
| `SprintContract.is_multi_year` 필드 | Kiro Req.9 | 코드 미구현 |
| `SprintContract.fiscal_years` 목록 필드 | Kiro Req.9 | 코드 미구현 |
| `SprintContract.carryover_source_revision` 필드 | Kiro Req.9 | 코드 미구현 |
| 이월 차수 생성 API (`POST /api/carryover`) | Kiro Req.10 | 엔드포인트 없음 |
| 정산누계 자동 누적 (prev_cur + prev_settlement → new_settlement) | Kiro Req.8 | 코드 미구현 |
| Fee_Sheet_Writer col14~20 정산누계/당기이후 기록 | Kiro Req.4 | 코드 미구현 |
| 이월 시 fiscal_year 갱신·data 이동 로직 | Kiro Req.7 | 코드 미구현 |

---

## Clarifications Retained

### [NEEDS CLARIFICATION] NC-01 — 비율 계산 방법론 이원화

- **항목**: 당기 비율 산출 방식이 두 함수 간 다름.
  - `_fiscal_year_shares` (`contract_builder.py:176`): **개월수** 기반 (`_mm_between`)
  - `_calc_period_ratios` (`common_sheet.py:39`): **일수** 기반 (`(end - start).days + 1`)
- **충돌 출처**: `contract_builder.py:176` vs `common_sheet.py:39`
- **확인 필요**: 어느 기준이 집행계획서 양식의 권위 기준인가? 두 비율이 다를 때 공통 시트 셀과 수수료 시트 셀의 비율이 불일치할 수 있음.

### [NEEDS CLARIFICATION] NC-02 — `_mm_between` 일할 분모 30 고정

- **항목**: 시작월 일할 계산 시 분모가 30 고정 (`contract_builder.py:156`). 실제 월 일수(28/30/31일)를 사용하지 않음.
- **출처**: `contract_builder.py:156` 주석 "업계 관행"
- **확인 필요**: 이 관행의 공식 근거 문서(계약 규정, 발주처 가이드 등). 적용 대상(M/M 단위만? 전체?)

### [NEEDS CLARIFICATION] NC-03 — prev 구간 금액의 실적 반영 기준

- **항목**: `prev` 비율(이전 회계연도 구간)이 존재할 때 `_split_by_shares`는 nx2만 별도 계산(`rate × amount`)하고 prev 금액은 반환하지 않음. 정산누계(settlement_cumulative)는 실적 기반 별도 입력이라 자동 입력하지 않는다고 코드 주석에 명시되어 있으나 (`contract_builder.py:166-167`), 이월 차수 생성 시 prev 구간 금액이 어느 필드로 귀속되는지 미정.
- **충돌 출처**: `contract_builder.py:166-167` 주석(자동 입력 금지) vs Kiro Req.8(정산누계 자동 계산)
- **확인 필요**: 이월 차수 생성 시 prev 금액 처리 방침.
