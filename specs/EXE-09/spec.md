# Feature Specification: 노무비 상세 (급료/상여/퇴직/명절)

**Feature Branch**: `EXE-09-labor-detail`  **Created**: 2026-06-26  **Status**: Draft
**Input**: 직급·M/M·투입기간·명절일자를 입력받아 급료·상여·퇴직금 노무비 항목을 산출하고 BudgetItem으로 배치한다.

---

## 작성 규칙 준수 선언

- 모든 FR은 EARS 5패턴 중 하나. 모호어("should/적절히/가능하면") 금지. 한 FR = 한 동작.
- 출처 있는 단일 값만 인용(file:line 명기). 충돌 출처 2개 이상은 `[NEEDS CLARIFICATION]`.
- non-goal(파일 CRUD·편집잠금·챗봇·OTEL/RateLimit) 미포함.

---

## User Scenarios & Testing

### User Story 1 — 급료 자동 산출 (Priority: P1)

PM이 집행계획서를 작성할 때, 소스 문서에 노무비 금액이 없고 직급·M/M 정보만 있으면,
시스템이 사내 직급단가표(`company_standards.py:16-22 GRADE_RATES`)로 급료를 자동 산출하고
관문 재확인 플래그를 단다.

- **Independent Test**: staffPlan에 과장 3M/M, budget_items에 labor 없음 → 급료 BudgetItem 생성, conflict_type="급료확인" 플래그 존재 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** budget_items에 category="labor"가 없고 internal_staff에 직급·M/M이 있을 때,
     **When** build_sprint_contract가 호출되면,
     **Then** 시스템은 GRADE_RATES 기준 `rate × M/M`로 급료를 산출하고 BudgetItem(category="labor")을 추가한다.
  2. **Given** 급료가 자동 산출되었을 때,
     **When** 결과가 반환되면,
     **Then** ConflictResolution(conflict_type="급료확인")이 포함되어 관문에서 사용자 재확인을 요구한다.

### User Story 2 — 급료 단가 불일치 감지 (Priority: P1)

소스 문서에 노무비 금액이 이미 있을 때, 그 금액이 사내 직급단가표와 다르면
시스템이 단가 불일치 플래그를 달고 입력값을 그대로 유지한다.

- **Independent Test**: budget_items에 labor 존재, 입력 금액 ≠ GRADE_RATES 기준 계산값 → conflict_type="급료단가확인" 생성, labor 금액 변경 없음 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** budget_items에 category="labor"가 있고 internal_staff가 있을 때,
     **When** GRADE_RATES 기준 산출값과 입력 금액의 차이가 1원 초과이면,
     **Then** 시스템은 입력값을 유지하고 ConflictResolution(conflict_type="급료단가확인")을 추가한다.

### User Story 3 — 상여금 산출 (Priority: P1)

투입기간 내 명절(설날/추석)이 있을 때, 시스템이 상여금을 자동 산출한다.
상여 공식이 출처 간 충돌하므로, 시스템이 현재 코드 공식을 적용하되
관문에서 사용자 재확인을 요구한다.

- **Independent Test**: 투입기간 내 추석 포함, budget_items에 bonus 없음 → BudgetItem(category="bonus") 생성, "상여확인" 플래그 존재 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** budget_items에 category="bonus"가 없고 투입기간 내 명절이 존재할 때,
     **When** build_sprint_contract가 호출되면,
     **Then** 시스템은 명절별로 상여금을 산출하고 BudgetItem(category="bonus")을 추가하며 ConflictResolution(conflict_type="상여확인")을 포함한다.
  2. **Given** 투입기간 내 명절이 없을 때,
     **When** build_sprint_contract가 호출되면,
     **Then** 시스템은 상여금 BudgetItem을 생성하지 않는다.

### User Story 4 — 투입기간 밖 명절 미책정 (Priority: P1)

명절 날짜가 투입기간 [start, end] 범위 밖에 있으면 상여를 책정하지 않는다.

- **Independent Test**: start=2026-02-01, end=2026-02-05, 설날=2026-02-17 → bonus BudgetItem 없음 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 명절 날짜가 start > 날짜 또는 날짜 > end인 경우,
     **When** holidays_in_period가 호출되면,
     **Then** 해당 명절을 결과 목록에 포함하지 않는다.

### User Story 5 — 퇴직금 자동 계산 (Priority: P2)

퇴직금은 `(급료+상여)/12` 수식으로 엑셀 시트가 자동 계산한다.
시스템은 퇴직금을 직접 산출하거나 BudgetItem으로 배치하지 않는다.

- **Independent Test**: 퇴직금(AUTO_CALCULATED_KEYWORDS에 포함)이 costItems에 있어도 budget_items에 배치되지 않는 것을 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** costItems에 "퇴직금" 항목이 있을 때,
     **When** build_sprint_contract가 호출되면,
     **Then** 시스템은 퇴직금을 별도 BudgetItem으로 추가하지 않는다(이중계상 방지).

### User Story 6 — 연도 경계 시 노무비 분리 (Priority: P2)

다년도 사업일 때 급료·상여 BudgetItem에 current_amount/next1_amount/next2_amount가 배분된다.

- **Independent Test**: 2025-10-01~2026-03-31, fiscal_year=2025 → 급료 BudgetItem의 current_amount + next1_amount = execution_amount 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 투입기간이 회계연도 경계를 걸치고 fy_shares가 존재할 때,
     **When** 급료 BudgetItem이 생성되면,
     **Then** `current_amount + next1_amount + next2_amount = execution_amount` (1원 이내 오차).

### Edge Cases

- 직급 문자열이 "과장(PM)"처럼 복합형인 경우 → `standard_rate_for` 부분일치(`company_standards.py:54-60`)로 처리.
- internal_staff는 type="직접"인 인원만(`contract_builder.py:437`). 현장사원(type != "직접")은 본 기능 범위 밖.
- budget_items에 category="bonus"가 이미 있으면 상여 자동 산출을 건너뜀(`contract_builder.py:513`).
- 명절 날짜 상수가 2025~2027만 정의됨(`company_standards.py:37-41`). 2028년 이후 프로젝트는 holidays_in_period가 빈 목록을 반환.
- months_before ≤ 0이면 해당 인원의 상여는 0으로 처리(`contract_builder.py:538-539`).

---

## Functional Requirements (EARS)

**[NEEDS CLARIFICATION] 포함 FR에 대한 사전 안내**: FR-004a(상여 공식), FR-005(직급 단가표)는
출처 3곳이 충돌하므로 현재 코드 구현값을 잠정 적용하나 인간 게이트에서 반드시 재확인해야 한다.

- **FR-001a** (event): WHEN `build_sprint_contract`가 호출되고 `budget_items`에 `category="labor"` 항목이 없으며 `internal_staff`(type="직접")가 1명 이상이고 start_date·end_date가 있을 때, THE SYSTEM SHALL `GRADE_RATES`에서 각 인원의 직급 단가를 조회하여 `rate × totalMM`로 급료 금액을 산출한다.
  - 코드 근거: `contract_builder.py:454-491`

- **FR-001b** (event): WHEN FR-001a의 급료 금액 산출이 완료되면, THE SYSTEM SHALL BudgetItem(category="labor", execution_amount=산출금액)을 budget_items에 추가한다.
  - 코드 근거: `contract_builder.py:488-496`

- **FR-002** (ubiquitous): THE SYSTEM SHALL `standard_rate_for(grade)` 함수로 직급 문자열 부분일치(예: "과장(PM)")를 허용해 GRADE_RATES에서 단가를 조회한다.
  - 코드 근거: `company_standards.py:53-60`

- **FR-003** (unwanted): IF `budget_items`에 `category="labor"`가 있고 `internal_staff`가 있으며 GRADE_RATES 기준 산출값과 입력 금액의 차이가 1원을 초과하면, THEN THE SYSTEM SHALL 입력값을 변경하지 않고 ConflictResolution(conflict_type="급료단가확인")을 추가한다.
  - 코드 근거: `contract_builder.py:440-453`

- **FR-004a** (event): WHEN `budget_items`에 `category="bonus"`가 없고 투입기간 내 명절이 1건 이상 존재할 때, THE SYSTEM SHALL 명절별·인원별로 `round(rate × months_before / 9)` 공식으로 상여금을 산출한다.
  - 코드 근거: `contract_builder.py:512-555, :540`
  - `[NEEDS CLARIFICATION]` **상여 공식 3중 충돌**:
    - 출처 A `executor.md:109` — "1M/M 급여 전액, 비율 계산 없음"
    - 출처 B `contract_builder.py:540` — `rate * months_before / 9`
    - 출처 C `REPORT_eps_values.md:155` — `=6500000*3/9` (months_before/9 방식)
    - 현재 코드(출처 B·C)를 잠정 적용. 운영팀(FDE) 인터뷰로 확정 필요.

- **FR-004b** (event): WHEN FR-004a의 상여금 산출이 완료되면, THE SYSTEM SHALL BudgetItem(category="bonus", execution_amount=산출합계)을 budget_items에 추가한다.
  - 코드 근거: `contract_builder.py:555-559`

- **FR-005** (state): WHILE `holidays_in_period(start, end)`가 명절 목록을 조회하는 동안, THE SYSTEM SHALL HOLIDAYS 테이블(`company_standards.py:37-41`)에서 start ≤ 명절 날짜 ≤ end 조건을 만족하는 명절만 반환한다.
  - 코드 근거: `company_standards.py:63-74`
  - **직급 단가 3중 충돌** (상여 산출에 사용되는 rate):
    - `[NEEDS CLARIFICATION]` 출처 A `company_standards.py:16-22` — 과장 5,500,000원
    - 출처 B `executor.md:101` — 과장 6,000,000원
    - 출처 C `REPORT_eps_values.md:144` — 과장 6,500,000원
    - 현재 코드(출처 A, GRADE_RATES)를 잠정 적용. 운영팀 확정 필요.

- **FR-006** (unwanted): IF `holidays_in_period`가 빈 목록을 반환하면, THEN THE SYSTEM SHALL 상여금 BudgetItem을 생성하지 않는다.
  - 코드 근거: `contract_builder.py:522` (`if holidays:` 분기)

- **FR-007** (event): WHEN FR-001b에 의해 BudgetItem(category="labor")이 추가되면, THE SYSTEM SHALL ConflictResolution(conflict_type="급료확인")을 standards_conflicts에 추가해 관문에서 사용자 재확인을 요구한다.
  - 코드 근거: `contract_builder.py:493-496`

- **FR-008** (event): WHEN FR-004b에 의해 BudgetItem(category="bonus")이 추가되면, THE SYSTEM SHALL ConflictResolution(conflict_type="상여확인")을 standards_conflicts에 추가해 관문에서 사용자 재확인을 요구한다.
  - 코드 근거: `contract_builder.py:556-559`

- **FR-009** (unwanted): IF costItems의 항목 이름이 `is_auto_calculated` 함수에 의해 AUTO_CALCULATED_KEYWORDS에 해당하는 것으로 판별되면, THEN THE SYSTEM SHALL 해당 항목을 BudgetItem으로 배치하지 않는다(이중계상 방지).
  - 코드 근거: `company_standards.py:44-50 AUTO_CALCULATED_KEYWORDS`

- **FR-010** (optional): WHERE fy_shares가 존재하는 다년도 사업에서 급료를 산출할 때, THE SYSTEM SHALL `_split_by_shares(salary_total, fy_shares)`로 current_amount/next1_amount/next2_amount를 배분한다.
  - 코드 근거: `contract_builder.py:473-484`

- **FR-011a** (optional): WHERE fy_shares가 존재하는 다년도 사업에서 상여를 산출할 때, THE SYSTEM SHALL 명절이 속한 연도(fiscal_year, fiscal_year+1)를 기준으로 bonus_cur/bonus_nx1을 배분한다.
  - 코드 근거: `contract_builder.py:542-551`

- **FR-011b** (optional): WHERE fy_shares가 존재하는 다년도 사업에서 상여를 산출할 때, THE SYSTEM SHALL `round(total_bonus) - bonus_cur - bonus_nx1`의 잔액을 next2_amount로 설정한다.
  - 코드 근거: `contract_builder.py:552-554`

- **FR-012** (unwanted): IF 개별 인원의 months_before가 0 이하이면, THEN THE SYSTEM SHALL 해당 인원에 대한 상여금을 0으로 처리하고 bonus_lines에 추가하지 않는다.
  - 코드 근거: `contract_builder.py:538-539`

---

## Success Criteria (측정형)

- **SC-001**: 급료 자동 산출 시 `rate × totalMM` 계산값과 BudgetItem.execution_amount 간 오차가 **0원** (1원 정밀도 FAIL). 코드 근거: constitution §IV.
- **SC-002**: 투입기간 내 명절이 있을 때 BudgetItem(category="bonus") 생성 여부가 **100%** 일치. 코드 근거: `contract_builder.py:522`.
- **SC-003**: 투입기간 밖 명절에 대해 상여 BudgetItem 미생성이 **100%** 일치. 코드 근거: `company_standards.py:68-72`.
- **SC-004**: 다년도 사업에서 `current_amount + next1_amount + next2_amount = execution_amount` 오차 **1원 이내**. 코드 근거: `contract_builder.py:474-483, _split_by_shares:193-201`.
- **SC-005**: 급료 단가 불일치(1원 초과) 시 conflict_type="급료단가확인" 플래그 생성 **100%**. 코드 근거: `contract_builder.py:446`.
- **SC-006**: AUTO_CALCULATED_KEYWORDS 항목(퇴직금/보험료 등)이 costItems에 있어도 BudgetItem으로 배치되는 경우 **0건**. 코드 근거: `company_standards.py:44-50`.
- **SC-007**: `holidays_in_period` 경계 조건 4개 케이스(start=명절당일 포함, end=명절당일 포함, day<start 제외, day>end 제외) 모두 기대 결과와 일치하여 **4/4 PASS**. 코드 근거: `company_standards.py:71` (`start <= day <= end`).
- **SC-008**: 상여 공식 확정 후 — 상여 산출 결과값과 확정 공식 계산값의 오차 **0원**. [NEEDS CLARIFICATION: 공식 미확정으로 목표 수치 보류]

---

## Key Entities

| 엔티티 | 설명 | 코드 근거 |
|--------|------|---------|
| `BudgetItem` | 노무비 항목 (category, desc, execution_amount, contract_amount, current_amount, next1_amount, next2_amount) | `contract_builder.py` |
| `GRADE_RATES` | 직급별 월단가 테이블 (부장/차장/과장/대리/사원) | `company_standards.py:16-22` |
| `HOLIDAYS` | 연도별 명절 날짜 상수 (2025~2027) | `company_standards.py:37-41` |
| `AUTO_CALCULATED_KEYWORDS` | 이중계상 방지 키워드 (퇴직금/보험료/국민연금 등) | `company_standards.py:44-45` |
| `ConflictResolution` | 관문 플래그 (conflict_type, description) | `contract_builder.py` |
| `internal_staff` | type="직접" 인원 목록 | `contract_builder.py:437` |
| `fy_shares` | 연도분리 비율 (current/next1/next2/prev) | `contract_builder.py:160 _fiscal_year_shares` |

---

## Assumptions

아래 값은 코드 현행값 = **잠정** (권위 출처 확정 전까지 관문 재확인 운용).

| 가정 항목 | 현행값 | 코드 출처 | 상태 |
|----------|--------|---------|------|
| 부장 월단가 | 7,500,000원/월 | `company_standards.py:17` | 잠정 — 3중 충돌 |
| 차장 월단가 | 6,500,000원/월 | `company_standards.py:18` | 잠정 — 3중 충돌 |
| 과장 월단가 | 5,500,000원/월 | `company_standards.py:19` | 잠정 — 3중 충돌 |
| 대리 월단가 | 4,500,000원/월 | `company_standards.py:20` | 잠정 — 3중 충돌 |
| 사원 월단가 | 3,500,000원/월 | `company_standards.py:21` | 잠정 — 3중 충돌 |
| 상여 공식 | `rate × months_before / 9` | `contract_builder.py:540` | 잠정 — 3중 충돌 |
| 퇴직금 공식 | `(급료+상여)/12` — 엑셀 수식 자동 계산 | `REPORT_eps_values.md:163` (`=(G11+G21)/12`) | 확정 |
| 퇴직공제부금 | 0 고정 | `executor.md:152` | 확정 |
| 명절 날짜 범위 | 2025~2027만 정의 | `company_standards.py:37-41` | 잠정 — 연간 갱신 필요 |
| 직급 부분일치 | "과장(PM)" → 과장 단가 적용 | `company_standards.py:56-59` | 잠정 |
| 다년도 연도분리 | EXE-11 `_split_by_shares` 위임 | `contract_builder.py:474` | 확정 |

---

## Clarifications Retained

이 기능에서 해소 전까지 코드 구현을 잠정 적용하는 `[NEEDS CLARIFICATION]` 항목:

1. **상여 공식 3중 충돌** (설계 §6-1 #2)
   - 출처 A `executor.md:109`: "1M/M 급여 전액, 비율 없음"
   - 출처 B `contract_builder.py:540`: `rate * months_before / 9`
   - 출처 C `REPORT_eps_values.md:155`: `=6500000*3/9` (months_before=3 사례)
   - 해소 방법: 운영팀(FDE) 인터뷰. 확정 후 SC-008 목표 수치 갱신 및 FR-004a 업데이트.

2. **직급 단가표 3중 충돌** (설계 §6-1 #1, EXE-03과 공유)
   - 출처 A `company_standards.py:16-22`: 과장 5,500,000원
   - 출처 B `executor.md:101`: 과장 6,000,000원
   - 출처 C `REPORT_eps_values.md:144`: 과장 6,500,000원
   - 해소 방법: 운영팀(FDE) 인터뷰. 확정 후 GRADE_RATES 코드 수정 및 Assumptions 업데이트.

3. **명절 날짜 2028년 이후 미정의** — HOLIDAYS 테이블 연간 갱신 정책 미명시. 담당자 확인 필요.
