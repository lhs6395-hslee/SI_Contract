# Tasks: EXE-09 — 노무비 상세 (급료/상여/퇴직/명절)

**Feature Branch**: `EXE-09-labor-detail`  **Created**: 2026-06-26  **Status**: Draft
**작업 깊이**: 문서까지. 코드 구현·자동실행 비대상(설계 §9). 각 task는 사람이 읽는 산출물.

---

## Task 1: 급료 자동 산출 로직 검증 (FR-001a, FR-001b, FR-002, FR-007)

**대상 수용기준**: SC-001(오차 0원), SC-005(플래그 100%)

### 실패 테스트 (구현 전 작성)

```python
# test_exe09_labor_salary.py

def test_salary_auto_calc_no_budget_items():
    """
    Given: budget_items에 category="labor" 없음, internal_staff에 과장 3M/M
    When: build_sprint_contract 호출
    Then: BudgetItem(category="labor", execution_amount=16_500_000) 생성
          (과장 5,500,000 × 3 = 16,500,000 — 잠정값, 단가표 확정 후 갱신)
    """
    pass  # RED

def test_salary_grade_partial_match():
    """
    Given: grade="과장(PM)"
    When: standard_rate_for("과장(PM)") 호출
    Then: 5_500_000 반환 (부분일치)
    """
    pass  # RED

def test_salary_conflict_flag_on_auto_calc():
    """
    Given: 급료 자동 산출 완료
    When: SprintContract 반환
    Then: ConflictResolution(conflict_type="급료확인")이 standards_conflicts에 포함됨
    """
    pass  # RED
```

### 최소 구현 체크리스트

- [ ] `company_standards.py` — `standard_rate_for(grade)` 부분일치 로직이 존재하는지 확인 (`line 53-60`).
- [ ] `contract_builder.py:436` — `has_labor_budget` 체크 분기 존재 확인.
- [ ] `contract_builder.py:454-491` — 자동 산출 블록(rate × mm 금액 산출, FR-001a) 동작 확인.
- [ ] `contract_builder.py:488-496` — BudgetItem(category="labor") 추가(FR-001b) 및 conflict 플래그(FR-007) 동작 확인.
- [ ] `[NEEDS CLARIFICATION]` 직급 단가표 충돌 확정 전: GRADE_RATES 현행값(과장 5,500,000) 유지하고 테스트 예상값을 잠정값으로 명기.

### 통과 조건

- `standard_rate_for("과장")` == 5,500,000 (잠정, 단가표 확정 시 갱신)
- `standard_rate_for("과장(PM)")` == 5,500,000 (부분일치)
- 과장 3M/M → execution_amount == 16,500,000 (잠정)
- execution_amount 계산 오차 == 0원 (SC-001)
- standards_conflicts에 conflict_type="급료확인" 존재

### 커밋 단위

```
test(exe09): 급료 자동 산출 + 부분일치 + 플래그 (RED)
impl(exe09): 급료 자동 산출 로직 (GREEN)
```

---

## Task 2: 급료 단가 불일치 감지 (FR-003, SC-005)

**대상 수용기준**: SC-005(플래그 100%), 입력값 보존

### 실패 테스트

```python
def test_salary_mismatch_flag_preserves_input():
    """
    Given: budget_items에 labor 존재(execution_amount=20_000_000),
           internal_staff 과장 3M/M, GRADE_RATES 기준 16_500_000
    When: build_sprint_contract 호출
    Then: - BudgetItem.execution_amount == 20_000_000 (입력값 유지)
          - ConflictResolution(conflict_type="급료단가확인") 포함
    """
    pass  # RED

def test_salary_no_flag_when_within_1_won():
    """
    Given: 입력값과 GRADE_RATES 기준값의 차이가 1원 이하
    When: build_sprint_contract 호출
    Then: conflict_type="급료단가확인" 없음
    """
    pass  # RED
```

### 최소 구현 체크리스트

- [ ] `contract_builder.py:446` — `abs(std_total - labor_total) > 1` 분기 존재 확인.
- [ ] `contract_builder.py:440-453` — 불일치 시 입력값 유지, conflict 추가 로직 확인.
- [ ] 임계값 1원(constitution §IV "1원 정밀도") 준수 확인.

### 통과 조건

- 입력값과 GRADE_RATES 차이 > 1원 → execution_amount 변경 없음 + 플래그 생성
- 차이 ≤ 1원 → 플래그 미생성

### 커밋 단위

```
test(exe09): 급료 단가 불일치 감지 1원 임계 (RED)
impl(exe09): 급료 단가 불일치 감지 로직 (GREEN)
```

---

## Task 3: holidays_in_period 경계 조건 (FR-005, SC-007)

**대상 수용기준**: SC-007(경계 포함 100%)

### 실패 테스트

```python
def test_holidays_include_exact_start():
    """
    Given: start=date(2026, 2, 17), end=date(2026, 3, 31)
           설날=date(2026, 2, 17) (HOLIDAYS 테이블)
    When: holidays_in_period(start, end)
    Then: [("설날", date(2026, 2, 17))] 반환 (start=명절당일 포함)
    """
    pass  # RED

def test_holidays_include_exact_end():
    """
    Given: start=date(2026, 1, 1), end=date(2026, 2, 17)
    When: holidays_in_period(start, end)
    Then: [("설날", date(2026, 2, 17))] 반환 (end=명절당일 포함)
    """
    pass  # RED

def test_holidays_exclude_outside_period():
    """
    Given: start=date(2026, 2, 18), end=date(2026, 9, 24)
           설날=date(2026, 2, 17), 추석=date(2026, 9, 25)
    When: holidays_in_period(start, end)
    Then: [] 반환 (양쪽 모두 범위 밖)
    """
    pass  # RED
```

### 최소 구현 체크리스트

- [ ] `company_standards.py:71` — `start <= day <= end` 조건 존재 확인.
- [ ] HOLIDAYS 테이블에 2026년 설날 `date(2026, 2, 17)`, 추석 `date(2026, 9, 25)` 확인.
- [ ] 연도 범위 루프(`range(start.year, end.year + 1)`) 확인.

### 통과 조건

- 경계 포함(start=day, end=day) → 명절 포함
- 경계 밖(day < start, day > end) → 빈 목록
- 2028년 이후 → 빈 목록 (HOLIDAYS 미정의 — [NEEDS CLARIFICATION] 연간 갱신 정책)

### 커밋 단위

```
test(exe09): holidays_in_period 경계 조건 3케이스 (RED)
impl(exe09): 확인 (기존 코드 통과 검증)
```

---

## Task 4: 상여 자동 산출 및 미책정 (FR-004a, FR-004b, FR-006, FR-008, SC-002, SC-003)

**대상 수용기준**: SC-002(100%), SC-003(100%), SC-008([NEEDS CLARIFICATION] 보류)

### 실패 테스트

```python
def test_bonus_created_when_holiday_in_period():
    """
    Given: start=2026-01-01, end=2026-12-31
           budget_items에 bonus 없음
           internal_staff: 과장 6M/M (rate=5_500_000, 잠정)
           추석=2026-09-25(기간 내)
    When: build_sprint_contract 호출
    Then: BudgetItem(category="bonus") 존재
          execution_amount > 0
          ConflictResolution(conflict_type="상여확인") 존재
    주의: execution_amount 기대값은 [NEEDS CLARIFICATION] 상여 공식 확정 전 잠정.
           현행 코드: round(5_500_000 × months_before / 9)
    """
    pass  # RED

def test_bonus_not_created_when_no_holiday():
    """
    Given: start=2025-03-01, end=2025-05-31
           명절 없음 (설날=1/29, 추석=10/6, 모두 기간 밖)
    When: build_sprint_contract 호출
    Then: BudgetItem(category="bonus") 없음
    """
    pass  # RED

def test_bonus_skipped_when_already_exists():
    """
    Given: budget_items에 category="bonus" 이미 존재
    When: build_sprint_contract 호출
    Then: 기존 bonus BudgetItem 그대로 유지 (추가 생성 없음)
    """
    pass  # RED

def test_bonus_months_before_zero_skipped():
    """
    Given: start=2026-09-25, end=2026-12-31, 추석=2026-09-25
           months_before = (2026-9 - 2026-9)*12 + 9 - 9 = 0
    When: build_sprint_contract 호출
    Then: 해당 인원에 대한 상여 없음 (months_before <= 0 처리)
    """
    pass  # RED
```

### 최소 구현 체크리스트

- [ ] `contract_builder.py:513` — `has_bonus_budget` 체크 존재 확인.
- [ ] `contract_builder.py:519` — `holidays_in_period(_s, _e)` 호출 존재 확인.
- [ ] `contract_builder.py:540` — `amount = round(rate * months_before / 9)` 공식 확인 (잠정, FR-004a).
- [ ] `contract_builder.py:555-559` — BudgetItem(category="bonus") 추가(FR-004b) 확인.
- [ ] `contract_builder.py:538-539` — `if months_before <= 0: continue` 존재 확인.
- [ ] `contract_builder.py:556-559` — "상여확인" conflict 플래그 추가 확인.
- [ ] `[NEEDS CLARIFICATION]` 상여 공식 확정 전: 테스트 기대값에 "(잠정, 공식 확정 시 갱신)" 주석 명기.

### 통과 조건

- 기간 내 명절 + bonus 없음 → BudgetItem(category="bonus") 생성 + "상여확인" 플래그
- 기간 내 명절 없음 → bonus 미생성
- bonus 이미 존재 → 추가 생성 없음
- months_before ≤ 0 → 해당 인원 상여 0

### 커밋 단위

```
test(exe09): 상여 산출·미책정·예외 케이스 (RED)
impl(exe09): 상여 산출 로직 검증 (GREEN)
```

---

## Task 5: AUTO_CALCULATED_KEYWORDS 이중계상 방지 (FR-009 unwanted, SC-006)

**대상 수용기준**: SC-006(이중계상 0건)

### 실패 테스트

```python
def test_retirement_not_placed_as_budget_item():
    """
    Given: costItems에 {"name": "퇴직금", "amount": 3_000_000} 포함
    When: build_sprint_contract 호출
    Then: BudgetItem(category 포함 어디에도) "퇴직금" 설명 항목 없음
    """
    pass  # RED

def test_insurance_keywords_excluded():
    """
    Given: costItems에 "국민연금"/"건강보험"/"산재보험"/"고용보험" 항목 포함
    When: build_sprint_contract 호출
    Then: 해당 항목이 budget_items에 배치되지 않음
    """
    pass  # RED
```

### 최소 구현 체크리스트

- [ ] `company_standards.py:44-45` — AUTO_CALCULATED_KEYWORDS 튜플 존재 확인.
- [ ] `company_standards.py:48-50` — `is_auto_calculated(item_name)` 함수 존재 확인.
- [ ] costItems 처리 경로에서 `is_auto_calculated` 호출 후 건너뜀 로직 확인.

### 통과 조건

- AUTO_CALCULATED_KEYWORDS 포함 항목이 costItems에 있어도 budget_items 배치 0건

### 커밋 단위

```
test(exe09): AUTO_CALCULATED_KEYWORDS 이중계상 방지 (RED)
impl(exe09): 확인 (기존 코드 통과 검증)
```

---

## Task 6: 다년도 연도분리 노무비 배분 (FR-010, FR-011a, FR-011b, SC-004)

**대상 수용기준**: SC-004(오차 1원 이내)

### 실패 테스트

```python
def test_salary_split_by_fiscal_year():
    """
    Given: start=2025-10-01, end=2026-03-31, fiscal_year=2025
           internal_staff: 과장 6M/M (rate=5_500_000, 잠정)
           fy_shares 존재 (당기=2025년 개월비율, 이후1=2026년 개월비율)
    When: build_sprint_contract 호출
    Then: BudgetItem(category="labor").current_amount + next1_amount = execution_amount (1원 이내)
    """
    pass  # RED

def test_bonus_split_by_holiday_year():
    """
    Given: start=2025-09-01, end=2026-03-31, fiscal_year=2025
           추석=2025-10-06(fiscal_year 내)
           설날=2026-02-17(fiscal_year+1)
    When: build_sprint_contract 호출
    Then: BudgetItem(category="bonus").current_amount 내 추석 상여 귀속
          next1_amount 내 설날 상여 귀속
          current_amount + next1_amount + next2_amount = execution_amount (1원 이내)
    """
    pass  # RED
```

### 최소 구현 체크리스트

- [ ] `contract_builder.py:473-484` — fy_shares 존재 시 `_split_by_shares` 호출 확인.
- [ ] `contract_builder.py:542-551` — 명절 연도 기준 bonus_cur/bonus_nx1 배분 로직 확인 (FR-011a).
- [ ] `contract_builder.py:552-554` — 잔액 next2_amount 설정 로직 확인 (FR-011b).
- [ ] `_split_by_shares` (`contract_builder.py:193-201`) — prev가 없을 때 nx2 잔여분 처리 (`round(amount) - cur - nx1`) 확인.
- [ ] 합계 정합성: `cur + nx1 + nx2 = round(total)`, 오차 ≤ 1원.

### 통과 조건

- 급료: `current_amount + next1_amount + next2_amount = execution_amount` (1원 이내)
- 상여: 명절 연도 기준 귀속, 합계 정합성 유지
- fy_shares 없는 단년도: current_amount = execution_amount, next1/next2 = 0

### 커밋 단위

```
test(exe09): 다년도 급료·상여 연도분리 (RED)
impl(exe09): 확인 (기존 EXE-11 엔진 통과 검증)
```

---

## Task 7: 통합 게이트 검증 + [NEEDS CLARIFICATION] 관리

**대상**: 전체 SC, 충돌 항목 표면화

### 통합 체크리스트

- [ ] SC-001~SC-007 테스트 전원 GREEN (SC-007: 경계 4케이스 4/4 PASS 확인).
- [ ] SC-008 — 상여 공식 확정 전 SKIP 처리 및 `[NEEDS CLARIFICATION]` 주석 유지.
- [ ] 관문 플래그("급료확인"/"급료단가확인"/"상여확인") 생성이 전 시나리오에서 확인됨.
- [ ] 퇴직금 BudgetItem 이중계상 0건 확인.
- [ ] 단가 3중 충돌 항목: GRADE_RATES 현행값(잠정) 적용 + 테스트에 "(잠정)" 주석 명기.
- [ ] 상여 공식 3중 충돌 항목: `rate × months_before / 9` 현행값(잠정) 적용 + 주석.

### [NEEDS CLARIFICATION] 추적 항목

운영팀(FDE) 인터뷰로 아래 2건이 확정되면 즉시 해당 task로 돌아가 테스트 기대값·GRADE_RATES·FR-004 업데이트:

| 번호 | 항목 | 충돌 출처 | 확정 후 작업 |
|------|------|---------|------------|
| NC-01 | 직급 단가표 | `company_standards.py:16-22` / `executor.md:101` / `REPORT_eps_values.md:144` | GRADE_RATES 수정 + Task 1 테스트 기대값 갱신 |
| NC-02 | 상여 공식 | `executor.md:109` / `contract_builder.py:540` / `REPORT_eps_values.md:155` | FR-004a 수식 변경 + Task 4 테스트 기대값 갱신 + SC-008 수치 설정 |
| NC-03 | 명절 날짜 갱신 정책 | `company_standards.py:37-41` (2025~2027만 정의) | 갱신 담당자·주기 확정 + HOLIDAYS 갱신 절차 추가 |

### 최종 커밋 단위

```
feat(sdd): EXE-09 노무비 상세 spec/plan/tasks
```
