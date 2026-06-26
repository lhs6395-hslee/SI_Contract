# Feature Specification: EXE-03 사내기준보정

**Feature Branch**: `EXE-03-company-standards-correction`
**Created**: 2026-06-26
**Status**: Draft
**Input**: 소스 문서에 급료·요율·상여가 없거나 사내 표준과 충돌할 때, 사내 기준 테이블(GRADE_RATES / DEFAULT_RATES / HOLIDAYS)을 fallback으로 적용하고 모든 적용 결과에 관문 재확인 플래그를 부착한다.

---

## 범주화

**EXE-03은 도메인 로직(백엔드)이다.**
`company_standards.py`의 상수 테이블과 `contract_builder.py:411-559`의 보정 분기로 구현된다.
프론트엔드 UI·편집은 EXE-04(기본정보 확인 게이트) 관할이며 본 기능에 포함되지 않는다.

---

## Non-goals (범위 밖)

다음 항목은 EXE-03의 구현 범위에 포함되지 않는다.

1. **코드 구현 자동 실행**: `speckit-implement` 비대상 (tasks.md 주의 참조).
2. **파일 CRUD**: 집행계획서 파일 저장·읽기·삭제는 EXE-02(소스 추출) 및 EXE-06(SprintContract 생성) 관할.
3. **EXE-04 UI 관할**: 관문 화면에서 ConflictResolution을 사용자에게 표시하고 확인받는 UI는 EXE-04 관할.
4. **EXE-09 최종 금액 산출**: 급료·상여·퇴직금·보험료의 최종 시트 배치 및 금액 확정은 EXE-09 관할. EXE-03은 fallback 적용과 플래그 생성까지만 담당한다.
5. **수수료 코드 판단 로직**: 수수료 코드 1/2/3 정량 판단 기준은 EXE-07 귀속 (Clarifications #6 참조).

---

## User Scenarios & Testing

### User Story 1 — 급료 소스 없음: 직급단가표 fallback (Priority: P1)

담당 PM이 협력사 견적서만 업로드한 경우처럼, 소스 문서에 직접 노무비(labor 비목)가 기재되지 않았다.
시스템은 staffPlan의 직급에 대응하는 사내 단가표 값을 자동 계산하되, 관문에서 반드시 사용자가 재확인하도록 플래그를 발행해야 한다.

- **Independent Test**: staffPlan에 직급="과장", totalMM=3인 인원만 입력하고 costItems에 labor 항목을 제거한 후 `/api/projects/{id}/save`를 호출했을 때 SprintContract.budget_items에 category="labor" BudgetItem이 생성되고 conflict_type="급료확인" ConflictResolution이 포함되는지 확인한다.
- **Acceptance (Given/When/Then)**:
  1. **Given** costItems에 labor 비목이 없고 staffPlan에 직접 투입 인원이 1명 이상 있을 때, **When** build_sprint_contract가 호출되면, **Then** 사내 직급단가표 기준으로 급료 BudgetItem이 생성되고 conflict_type="급료확인" ConflictResolution이 포함된다.

### User Story 2 — 급료 소스 있음: 단가표 불일치 재확인 플래그 (Priority: P1)

소스 문서에 노무비 금액이 있지만 사내 직급단가표 계산값과 다를 경우, 시스템은 입력값을 그대로 유지하되 차이를 사용자에게 알려야 한다.

- **Independent Test**: costItems에 labor 비목(executionAmount=16_500_000)과 staffPlan에 직급="과장", totalMM=3이 함께 있을 때 build_sprint_contract 호출 후 SprintContract.conflicts에 conflict_type="급료단가확인"이 존재하고 budget_items.labor.execution_amount=16_500_000(입력값 보존)인지 확인한다.
- **Acceptance (Given/When/Then)**:
  1. **Given** costItems에 labor 비목이 있고 그 금액이 사내 단가표 기준 금액과 1원 이상 차이날 때, **When** build_sprint_contract가 호출되면, **Then** 입력 금액은 변경 없이 유지되고 conflict_type="급료단가확인" ConflictResolution이 생성된다.

### User Story 3 — 상여금: 투입 기간 내 명절만 책정 (Priority: P1)

투입 기간이 2026-01-01 ~ 2026-05-31일 때, 2026년 추석(2026-09-25)은 기간 밖이므로 추석 상여를 책정하지 않아야 한다. 2026년 설날(2026-02-17)은 기간 내이므로 상여를 책정해야 한다.

- **Independent Test**: start_date=2026-01-01, end_date=2026-05-31, staffPlan에 직접 인원 1명으로 호출했을 때 SprintContract.budget_items의 category="bonus" 항목이 설날 상여만 포함하고 추석 상여는 0임을 확인한다.
- **Acceptance (Given/When/Then)**:
  1. **Given** 투입기간 [start_date, end_date]가 설정되어 있고 HOLIDAYS 테이블에 해당 연도 명절이 등록되어 있을 때, **When** build_sprint_contract가 호출되면, **Then** 투입기간 내에 포함된 명절에 대해서만 상여가 책정되고 기간 밖 명절은 0으로 처리된다.

### User Story 4 — 요율 fallback: 소스 없으면 DEFAULT_RATES 적용 (Priority: P2)

소스에 보험요율 정보가 없는 경우 DEFAULT_RATES 테이블의 정산 기준 요율이 fallback으로 사용된다. 이 요율에는 별도 공문이 있으면 덮어쓸 수 있어야 한다.

- **Acceptance (Given/When/Then)**:
  1. **Given** ExtractedData에 rates 필드가 없고 DEFAULT_RATES가 적용될 때, **When** build_sprint_contract가 호출되면, **Then** SprintContract.rate_set은 DEFAULT_RATES의 값으로 채워지고 "코드 현행값=잠정" 표기를 동반한 ConflictResolution이 생성된다.

### Edge Cases

- staffPlan 인원의 grade가 GRADE_RATES 테이블에 없는 경우(예: "수석") → `[NEEDS CLARIFICATION: GRADE_RATES 미정의 직급에 대한 fallback 처리 정책]`
- HOLIDAYS 테이블에 없는 연도(2028 이후)의 투입 기간 → 명절 상여 0으로 처리 (company_standards.py:63, `HOLIDAYS.get(year, {})` 기본값 빈 dict)
- 직급 문자열이 복합 형식(예: "과장(PM)")인 경우 → `standard_rate_for`의 부분 일치로 처리 (company_standards.py:55-60)

---

## Functional Requirements (EARS)

- **FR-01** (unwanted): IF ExtractedData의 costItems에 labor 카테고리 비목이 없고 staffPlan에 직접 투입 인원(type="직접")이 1명 이상 있으면, THEN THE SYSTEM SHALL 사내 직급단가표(GRADE_RATES)를 사용해 급료 BudgetItem을 자동 산출하고 conflict_type="급료확인" ConflictResolution을 생성한다.

- **FR-02** (unwanted): IF ExtractedData의 costItems에 labor 비목이 있고 해당 금액이 사내 직급단가표 기준 계산값과 1원 이상 차이나면, THEN THE SYSTEM SHALL 입력 금액을 변경하지 않고 유지하며 conflict_type="급료단가확인" ConflictResolution을 생성한다.

- **FR-03** (unwanted): IF staffPlan의 직급 문자열이 GRADE_RATES 키와 완전 일치하지 않으면, THEN THE SYSTEM SHALL 직급 문자열에 GRADE_RATES 키가 포함(부분 일치)되는 항목의 단가를 사용해 급료를 산출한다.

- **FR-04** (unwanted): IF 명절 날짜가 투입기간 [start_date, end_date] 밖에 있으면, THEN THE SYSTEM SHALL 해당 명절에 대한 상여를 책정하지 않는다.

- **FR-05** (unwanted): IF costItems에 bonus 카테고리 비목이 없고 투입기간 내에 명절이 1개 이상 포함되면, THEN THE SYSTEM SHALL 상여 BudgetItem을 자동 산출하고 conflict_type="상여확인" ConflictResolution을 생성한다.

- **FR-08** (unwanted): IF ExtractedData의 rates 필드가 없거나 null이면, THEN THE SYSTEM SHALL DEFAULT_RATES 테이블 값을 RateSet에 적용하고 "코드 현행값=잠정" 표기를 동반한 ConflictResolution을 생성한다.

- **FR-11** (ubiquitous): THE SYSTEM SHALL AUTO_CALCULATED_KEYWORDS에 해당하는 costItem을 budget_items 생성 전 필터링한다.

> **삭제된 FR 목록 (Clarifications Retained으로 이동)**
> FR-06 (상여금 공식 충돌 문서 기술), FR-07 (umbrella 플래그 기술), FR-09 (직급 단가 충돌 문서 기술), FR-10 (보험요율 이원화 문서 기술), FR-12 (간접/관리비율 근거 문서 기술) — 런타임 동작이 아닌 문서 상태 기술이거나 검증 기준 없는 umbrella FR이므로 EARS 준수를 위해 삭제. 각 충돌 내용은 Clarifications Retained에 귀속.

---

## Success Criteria (측정형)

- **SC-01**: GRADE_RATES 테이블에 정의된 직급에 대해 fallback 급료 계산 시 `rate × totalMM` 수식의 1원 오차도 발생하지 않는다 (1원 정밀도, constitution IV조).
- **SC-02**: 투입기간 내 명절 포함 여부 판정이 `holidays_in_period`(company_standards.py:63) 기준으로 100% 일치한다.
- **SC-03**: 자동 산출된 급료·상여·요율 항목 중 ConflictResolution이 부착되지 않은 항목이 0건이다.
- **SC-04**: AUTO_CALCULATED_KEYWORDS에 해당하는 costItem이 budget_items에 포함되는 경우(이중 계상)가 0건이다.

> **SC-05~08 이동 (Clarifications Retained)**: 상여금 공식·직급 단가·보험요율·하도급노무비율의 수치 기준은 충돌 해소 전까지 측정형 SC를 설정할 수 없다. 각 항목은 Clarifications Retained #2~5에 귀속되며, NC 해소 후 SC를 추가한다.

---

## Key Entities

| 엔티티 | 출처 |
|--------|------|
| `GRADE_RATES: dict[str, int]` | `company_standards.py:16-22` — 직급별 원/월 단가 |
| `DEFAULT_RATES: dict[str, float]` | `company_standards.py:27-34` — 요율 fallback 테이블 |
| `HOLIDAYS: dict[int, dict[str, date]]` | `company_standards.py:37-41` — 2025~2027 명절 날짜 상수 |
| `AUTO_CALCULATED_KEYWORDS: tuple` | `company_standards.py:44-45` — 이중 계상 방지 키워드 |
| `BudgetItem(category, desc, contract_amount, execution_amount, current_amount, next1_amount, next2_amount)` | `models.py` |
| `ConflictResolution(conflict_type, description)` | `models.py` — 관문 재확인 플래그 |
| `RateSet` | `models.py` — 보험요율 세트 |
| `SprintContract.budget_items: list[BudgetItem]` | `contract_builder.py:297` |
| `SprintContract.conflicts: list[ConflictResolution]` | `contract_builder.py:297` |

---

## Assumptions

다음 값은 코드 현행값이며 권위 출처(공문/경영 결정)가 미확정 상태이다. 사용자 확정 전까지 "잠정"으로 사용.

| 항목 | 현행 코드값 | 출처(file:line) | 잠정 여부 |
|------|------------|----------------|---------|
| 간접비율 | 1.9% | `company_standards.py:28` + `REPORT:97` (일치) | 잠정 — 공문 경로 없음 |
| 일반관리비율 | 3.0% | `company_standards.py:29` + `REPORT:98` (일치) | 잠정 — 공문 경로 없음 |
| 정산 국민연금 | 4.5% | `company_standards.py:30` | 잠정 — 매년 변동 |
| 정산 건강보험 | 4.0041% | `company_standards.py:31` | 잠정 — 매년 변동 |
| 정산 산재보험 | 0.766% | `company_standards.py:32` | 잠정 — 매년 변동 |
| 고용보험 | 1.75% | `company_standards.py:34` | 잠정 |
| 퇴직공제부금 | 0 고정(사용 안 함) | `executor.md:152` | 정책 확정값 |
| 명절 날짜 2025년 설날 | 2025-01-29 | `company_standards.py:38` | 매년 갱신 필요 |
| 명절 날짜 2025년 추석 | 2025-10-06 | `company_standards.py:38` | 매년 갱신 필요 |
| 명절 날짜 2026년 설날 | 2026-02-17 | `company_standards.py:39` | 매년 갱신 필요 |
| 명절 날짜 2026년 추석 | 2026-09-25 | `company_standards.py:39` | 매년 갱신 필요 |
| 명절 날짜 2027년 설날 | 2027-02-07 | `company_standards.py:40` | 매년 갱신 필요 |
| 명절 날짜 2027년 추석 | 2027-09-15 | `company_standards.py:40` | 매년 갱신 필요 |
| MAX_REVISION | 11 | `company_standards.py:12` | 양식 구조 한계(확정) |

---

## Clarifications Retained

EXE-03에 귀속되는 강제 `[NEEDS CLARIFICATION]` 항목 (설계서 §6-1). SC-05~08이 이 항목들에 귀속되며, 각 NC 해소 후 해당 SC를 추가한다.

1. **직급 단가표 3중 충돌** (구 FR-09 이동)
   - `company_standards.py:16-22` — 과장 5,500,000원/월
   - `.claude/agents/executor.md:101` — 과장 6,000,000원/월
   - `.pipeline/analysis/REPORT_eps_values.md:144` — 과장 6,500,000원/월 (실양식 역추출)
   - **해소 방법**: 사용자가 사내 기준 문서(직급단가표 원본)로 단일 출처를 직접 확정.
   - **해소 후 SC 추가 예정**: `rate × totalMM` 1원 정밀도 수치 검증 (SC-01 확장).

2. **상여금 계산 공식 충돌** (구 FR-06 이동)
   - `.claude/agents/executor.md:109` — "1M/M 급여 전액, 비율 계산 없음"
   - `backend/services/contract_builder.py:540` — `rate * months_before / 9`
   - `.pipeline/analysis/REPORT_eps_values.md:155` — `=6500000*3/9` (실양식 역추출)
   - **해소 방법**: 사용자가 사내 기준으로 /9 기준의 "명절까지 투입개월" 정의와 "전액" 정의 중 어느 쪽이 적용 기준인지 직접 확정.
   - **해소 후 SC 추가 예정**: 상여금 수치 정밀도 SC.

3. **보험요율 이원화** (구 FR-10 이동)
   - `company_standards.py:30-34` — 정산 기준 (국민 4.5%, 건강 4.0041%, 산재 0.766%)
   - `.pipeline/analysis/REPORT_eps_values.md:174-180` — 집행 기준 (국민 4.75%, 건강 4.0674%, 산재 0.796%)
   - **해소 방법**: 적용 기준연도·갱신 정책 및 집행/정산 이원화 근거 공문 확인.
   - **해소 후 SC 추가 예정**: 요율 수치 정밀도 SC.

4. **간접·일반관리비율 문서 근거 부재** (구 FR-12 이동)
   - `company_standards.py:26` — "윤지민과장 문의 — 25년 기준" 주석만 존재, 공문 경로 없음.
   - 코드 현행값(잠정): indirect_rate=1.9%, admin_rate=3.0% (`company_standards.py:28-29`, `REPORT_eps_values.md:97-98` 동일 일치).
   - **해소 방법**: 담당자 공문 또는 정책 결정 문서 경로 확보.
   - **해소 후 SC 추가 예정**: 간접/관리비율 수치 검증 SC.

5. **하도급노무비율 수치 미명시** (설계서 §6-1 항목5)
   - `.claude/agents/executor.md:153` — 산재·고용보험 공식에 `외주비×하도급노무비율`이 등장하나 비율 수치 미기재.
   - **해소 방법**: 안전보건팀 공문 또는 표준계약서에서 비율 수치 확인.
   - **해소 후 SC 추가 예정**: 하도급노무비율 수치 검증 SC.

6. **수수료 코드 1/2/3 정량 판단 기준** (설계서 §6-1 항목5 대응 — **EXE-07 귀속**)
   - `planner.md` 추측값으로 출처 미확정. EXE-07 spec.md에 귀속 표기가 있어야 하며, EXE-03 구현 범위 밖이다.
   - Non-goals §5 참조.
