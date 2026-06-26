# Tasks: EXE-03 사내기준보정

**Feature**: EXE-03 사내기준보정
**Created**: 2026-06-26
**Status**: Draft
**Spec**: `specs/EXE-03/spec.md` | **Plan**: `specs/EXE-03/plan.md`

---

> **주의**: 이 tasks.md는 사람이 읽는 산출물이다. `/speckit-implement` 자동 실행 비대상.
> 각 task는 "실패 테스트 작성 → 최소 구현 → 테스트 통과 → 커밋" 단위로 기술된다.
> 직급 단가표(FR-09)·상여금 공식(FR-06)·보험요율(FR-10) 관련 task는
> `[NEEDS CLARIFICATION]` 해소 전까지 구현 착수 불가이므로 별도 표기한다.

---

## Task T-01: AUTO_CALCULATED 이중 계상 방지 (FR-11)

**수용기준 (Given/When/Then)**:
- **Given** costItems에 AUTO_CALCULATED_KEYWORDS에 해당하는 비목(퇴직금, 건강보험 등)이 포함되어 있을 때,
- **When** build_sprint_contract가 호출되면,
- **Then** 해당 costItem은 budget_items에 포함되지 않는다.

**실패 테스트 작성**
```python
# tests/test_company_standards_correction.py
def test_auto_calculated_not_in_budget_items():
    """퇴직금/보험료 costItem이 budget_items에 이중 계상되지 않는다."""
    extracted_data = {
        "extracted": {},
        "costItems": [
            {"category": "labor", "name": "퇴직금", "executionAmount": 500_000},
            {"category": "labor", "name": "건강보험", "executionAmount": 200_000},
        ],
        "staffPlan": [],
    }
    contract = build_sprint_contract("proj1", extracted_data)
    names = [b.desc for b in contract.budget_items]
    assert not any("퇴직금" in (n or "") for n in names)
    assert not any("건강보험" in (n or "") for n in names)
```

**최소 구현**: `company_standards.is_auto_calculated` 함수가 존재하고 `contract_builder.py:378-384`의 필터 로직이 동작한다. 신규 구현 불필요(기존 코드 검증).

**통과 기준**: 위 테스트가 녹색이다. ConflictResolution의 conflict_type 열거값은 `models.py` 정의를 우선 확인하고 단언한다 (`[NEEDS CLARIFICATION: models.py conflict_type 열거값 확인 필요 — 'AUTO_CALCULATED 필터 적용' 관련 값]`).

**커밋 단위**: `test(EXE-03-T01): AUTO_CALCULATED 이중 계상 방지 검증`

---

## Task T-02: labor 없음 → GRADE_RATES fallback 급료 생성 (FR-01)

**수용기준 (Given/When/Then)**:
- **Given** costItems에 labor 비목이 없고 staffPlan에 type="직접" 인원이 1명 이상 있을 때,
- **When** build_sprint_contract가 호출되면,
- **Then** GRADE_RATES 기반 BudgetItem(category="labor")이 1개 생성되고 conflict_type="급료확인" ConflictResolution이 포함된다.

**[NEEDS CLARIFICATION 대기]**: 이 task의 **단가 수치**는 직급 단가표 3중 충돌(spec.md Clarifications #1) 해소 후 확정한다. 구조 검증(BudgetItem 생성 여부·플래그 존재 여부)은 현행 코드값으로 착수 가능.

**실패 테스트 작성**
```python
def test_labor_fallback_creates_budget_item_and_flag():
    """labor costItem 없이 staffPlan만 있을 때 사내 단가표 fallback이 동작한다."""
    extracted_data = {
        "extracted": {"startDate": "2026-01-01", "endDate": "2026-03-31"},
        "costItems": [],
        "staffPlan": [{"grade": "과장", "totalMM": 3, "type": "직접"}],
    }
    contract = build_sprint_contract("proj1", extracted_data)

    labor_items = [b for b in contract.budget_items if b.category == "labor"]
    assert len(labor_items) == 1, "labor BudgetItem이 1개 생성되어야 한다"
    assert labor_items[0].execution_amount > 0

    conflict_types = [c.conflict_type for c in contract.conflicts]
    assert "급료확인" in conflict_types, "관문 재확인 플래그가 있어야 한다"
```

**최소 구현**: `contract_builder.py:454-496` 기존 코드 검증. 신규 구현 불필요.

**통과 기준**: 위 테스트 녹색. `execution_amount` 값은 GRADE_RATES 단가 확정 후 수치 검증 추가.

**커밋 단위**: `test(EXE-03-T02): labor fallback 구조 검증` → 단가 확정 후 `test(EXE-03-T02b): 수치 검증 추가`

---

## Task T-03: labor 있음 + 단가 불일치 → 재확인 플래그(값 보존) (FR-02)

**수용기준 (Given/When/Then)**:
- **Given** costItems에 labor 비목이 있고 그 금액이 GRADE_RATES 기준 계산값과 1원 이상 차이날 때,
- **When** build_sprint_contract가 호출되면,
- **Then** 입력 금액은 변경 없이 유지되고 conflict_type="급료단가확인" ConflictResolution이 생성된다.

**실패 테스트 작성**
```python
def test_labor_mismatch_keeps_input_and_flags():
    """labor 입력값 ≠ 단가표 기준: 입력값 보존 + 재확인 플래그."""
    input_amount = 16_500_000  # 과장 3M/M, 단가표와 다른 임의값
    extracted_data = {
        "extracted": {},
        "costItems": [
            {"category": "labor", "name": "노무비", "executionAmount": input_amount}
        ],
        "staffPlan": [{"grade": "과장", "totalMM": 3, "type": "직접"}],
    }
    contract = build_sprint_contract("proj1", extracted_data)

    labor_items = [b for b in contract.budget_items if b.category == "labor"]
    assert labor_items[0].execution_amount == input_amount, "입력값이 변경되지 않아야 한다"

    conflict_types = [c.conflict_type for c in contract.conflicts]
    assert "급료단가확인" in conflict_types
```

**최소 구현**: `contract_builder.py:440-453` 기존 코드 검증.

**통과 기준**: 위 테스트 녹색.

**커밋 단위**: `test(EXE-03-T03): labor 불일치 플래그·값 보존 검증`

---

## Task T-04: 직급 부분 일치 처리 (FR-03)

**수용기준 (Given/When/Then)**:
- **Given** staffPlan의 직급 문자열이 GRADE_RATES 키와 완전 일치하지 않지만 키가 문자열에 포함될 때,
- **When** standard_rate_for가 호출되면,
- **Then** 부분 일치하는 GRADE_RATES 키의 단가(int)가 반환된다.

**실패 테스트 작성**
```python
def test_grade_partial_match():
    """복합 직급 문자열에서 단가 부분 일치 조회."""
    from backend.services.company_standards import standard_rate_for
    # 현행 GRADE_RATES 과장 값(잠정) — 단가 수치는 NC 해소 후 확정
    result = standard_rate_for("과장(PM)")
    assert result is not None, "부분 일치로 과장 단가가 반환되어야 한다"
    assert isinstance(result, int)
```

**최소 구현**: `company_standards.py:53-60` 기존 코드 검증.

**통과 기준**: 위 테스트 녹색. 반환값 수치는 직급 단가 NC 해소 후 확정.

**커밋 단위**: `test(EXE-03-T04): 직급 부분 일치 조회 검증`

---

## Task T-05: 명절 기간 내외 판정 (FR-04)

**수용기준 (Given/When/Then)**:
- **Given** HOLIDAYS 테이블에 등록된 연도의 투입기간 [start_date, end_date]가 설정될 때,
- **When** holidays_in_period(start, end)가 호출되면,
- **Then** 투입기간 내에 포함된 명절만 반환되고 기간 밖 명절은 반환되지 않는다. HOLIDAYS 테이블에 없는 연도는 빈 리스트를 반환한다.

**실패 테스트 작성**
```python
from datetime import date
from backend.services.company_standards import holidays_in_period

def test_holiday_in_period_only_includes_in_range():
    """2026년 설날(2/17)은 포함, 추석(9/25)은 제외."""
    result = holidays_in_period(date(2026, 1, 1), date(2026, 5, 31))
    names = [h[0] for h in result]
    assert "설날" in names
    assert "추석" not in names

def test_holiday_unknown_year_returns_empty():
    """2028년(HOLIDAYS 미등록) 투입 기간 → 빈 리스트."""
    result = holidays_in_period(date(2028, 1, 1), date(2028, 12, 31))
    assert result == []
```

**최소 구현**: `company_standards.py:63-74` 기존 코드 검증.

**통과 기준**: 위 두 테스트 모두 녹색.

**커밋 단위**: `test(EXE-03-T05): 명절 기간 판정 검증`

---

## Task T-06: 상여 자동 산출 및 기간 외 미책정 (FR-04, FR-05) — [NEEDS CLARIFICATION 부분 포함]

**수용기준 (Given/When/Then)**:
- **Given** costItems에 bonus 비목이 없고 투입기간 내에 명절이 1개 이상 포함될 때,
- **When** build_sprint_contract가 호출되면,
- **Then** 상여 BudgetItem이 생성되고 conflict_type="상여확인" ConflictResolution이 포함된다.
- **Given** 명절이 투입기간 밖에 있을 때,
- **When** build_sprint_contract가 호출되면,
- **Then** 상여 BudgetItem이 생성되지 않는다.

**[NEEDS CLARIFICATION]**: 상여금 **수치** 검증은 공식 충돌(spec.md Clarifications #2) 해소 전 착수 불가. 구조(BudgetItem 생성/미생성 여부)는 착수 가능.

**실패 테스트 작성**
```python
def test_bonus_created_when_holiday_in_period():
    """명절이 투입기간 내 → 상여 BudgetItem 생성."""
    extracted_data = {
        "extracted": {"startDate": "2026-01-01", "endDate": "2026-05-31"},
        "costItems": [],
        "staffPlan": [{"grade": "과장", "totalMM": 5, "type": "직접"}],
    }
    contract = build_sprint_contract("proj1", extracted_data)
    bonus_items = [b for b in contract.budget_items if b.category == "bonus"]
    assert len(bonus_items) == 1
    assert bonus_items[0].execution_amount > 0
    conflict_types = [c.conflict_type for c in contract.conflicts]
    assert "상여확인" in conflict_types

def test_bonus_not_created_when_holiday_outside_period():
    """명절이 투입기간 외 → 상여 미생성."""
    extracted_data = {
        "extracted": {"startDate": "2026-03-01", "endDate": "2026-07-31"},
        "costItems": [],
        "staffPlan": [{"grade": "과장", "totalMM": 5, "type": "직접"}],
    }
    # 2026-03-01 ~ 2026-07-31: 설날(2/17) 밖, 추석(9/25) 밖
    contract = build_sprint_contract("proj1", extracted_data)
    bonus_items = [b for b in contract.budget_items if b.category == "bonus"]
    assert len(bonus_items) == 0
```

**최소 구현**: `contract_builder.py:512-559` 기존 코드 검증.

**통과 기준**: 구조 테스트 녹색. 수치 테스트는 NC-#2 해소 후 추가.

**커밋 단위**: `test(EXE-03-T06): 상여 자동 산출 구조 검증` → `test(EXE-03-T06b): 수치 검증 (NC 해소 후)`

---

## Task T-07: DEFAULT_RATES fallback (FR-08)

**수용기준 (Given/When/Then)**:
- **Given** ExtractedData.rates 필드가 없거나 null일 때,
- **When** build_sprint_contract가 호출되면,
- **Then** SprintContract.rate_set이 None이 아니고 DEFAULT_RATES 키 세트가 모두 존재한다.

**[NEEDS CLARIFICATION]**: 보험요율 이원화(spec.md Clarifications #3) 해소 전 집행/정산 구분 검증 보류. DEFAULT_RATES 키 존재 여부만 선행 검증. 수치 단언(indirect_rate, admin_rate 등)은 NC-#4 해소 전 삽입 불가.

**실패 테스트 작성**
```python
def test_default_rates_fallback_when_rates_missing():
    """rates 없을 때 DEFAULT_RATES로 rate_set 채움."""
    extracted_data = {
        "extracted": {},
        "costItems": [],
        "staffPlan": [],
        "rates": None,
    }
    contract = build_sprint_contract("proj1", extracted_data)
    assert contract.rate_set is not None
    # 수치 단언은 NC-#3(보험요율 이원화) 및 NC-#4(간접/관리비율 공문) 해소 후 추가
    # assert contract.rate_set.indirect_rate == [NEEDS CLARIFICATION]
    # assert contract.rate_set.admin_rate == [NEEDS CLARIFICATION]
```

**최소 구현**: `build_sprint_contract` 내 rates 없음 분기에서 DEFAULT_RATES를 RateSet으로 변환하는 로직. 기존 코드 확인 후 누락이면 추가.

**통과 기준**: 위 테스트 녹색(rate_set not None). 요율 수치 단언은 NC-#3/4 해소 후 T-07b로 추가.

**커밋 단위**: `test(EXE-03-T07): DEFAULT_RATES fallback 구조 검증`

---

## Task T-08: 모든 자동 산출 항목에 ConflictResolution 부착 확인 (SC-03)

**수용기준 (Given/When/Then)**:
- **Given** EXE-03이 labor fallback·상여 자동 산출·rates fallback 중 1개 이상을 수행할 때,
- **When** build_sprint_contract가 호출되면,
- **Then** 각 자동 산출 항목에 ConflictResolution이 1개 이상 부착된다.
- **Given** 모든 값이 소스 입력으로 제공되어 자동 산출이 없을 때,
- **When** build_sprint_contract가 호출되면,
- **Then** EXE-03 관련 표준 보정 플래그(급료확인, 상여확인)가 생성되지 않는다.

> 이 Task는 구 FR-07(umbrella) 삭제에 따라 SC-03 달성 확인으로 재분류된다.

**실패 테스트 작성**
```python
def test_all_auto_items_have_conflict_flag():
    """labor + 상여 모두 자동 산출 → 각각 ConflictResolution 보유."""
    extracted_data = {
        "extracted": {"startDate": "2026-01-01", "endDate": "2026-05-31"},
        "costItems": [],
        "staffPlan": [{"grade": "과장", "totalMM": 5, "type": "직접"}],
    }
    contract = build_sprint_contract("proj1", extracted_data)
    conflict_types = {c.conflict_type for c in contract.conflicts}
    assert "급료확인" in conflict_types
    assert "상여확인" in conflict_types

def test_no_auto_items_no_standards_conflict():
    """모든 값이 소스에서 입력 → 표준 보정 관련 플래그 없음."""
    extracted_data = {
        "extracted": {},
        "costItems": [
            {"category": "labor", "name": "노무비", "executionAmount": 16_500_000,
             "contractAmount": 17_000_000},
            {"category": "bonus", "name": "상여금", "executionAmount": 2_000_000},
        ],
        "staffPlan": [],
    }
    contract = build_sprint_contract("proj1", extracted_data)
    conflict_types = {c.conflict_type for c in contract.conflicts}
    # 단가 불일치가 없으면 표준 보정 플래그 없어야 함
    assert "급료확인" not in conflict_types
    assert "상여확인" not in conflict_types
```

**최소 구현**: `contract_builder.py:411-559` 기존 플래그 부착 경로 검증.

**통과 기준**: 위 두 테스트 녹색.

**커밋 단위**: `test(EXE-03-T08): 자동 산출 전체 플래그 부착 커버리지`

---

## [NEEDS CLARIFICATION] 대기 Tasks

아래 tasks는 충돌 해소 없이는 수치 기준을 설정할 수 없다.
충돌 해소(운영팀 인터뷰) 후 수용기준에 수치를 채워 착수한다.

| Task ID | 대기 NC | 착수 조건 |
|---------|---------|---------|
| T-NC-01 | 직급 단가표 3중 충돌 (spec Clarifications #1) | 운영팀 인터뷰 후 단일 GRADE_RATES 확정 |
| T-NC-02 | 상여금 공식 충돌 (spec Clarifications #2) | `전액` vs `rate*months/9` 중 어느 공식 사용 확정 |
| T-NC-03 | 보험요율 집행/정산 이원화 (spec Clarifications #3) | 적용 기준연도·갱신 정책 공문 확보 |
| T-NC-04 | 간접/관리비율 공문 (spec Clarifications #4) | 담당자 공문 경로 확인 |
| T-NC-05 | 하도급노무비율 수치 (spec Clarifications #5) | 안전보건팀 공문 수치 확인 |

---

## 실행 순서 (의존 순)

```
T-01 (AUTO_CALCULATED 필터)
  └─ T-08 (전체 플래그 커버리지)
T-04 (직급 부분 일치)
  └─ T-02 (labor fallback) ─── [NC-01 해소 후 수치 추가]
       └─ T-03 (불일치 플래그)
T-05 (명절 기간 판정)
  └─ T-06 (상여 산출) ─────── [NC-02 해소 후 수치 추가]
T-07 (DEFAULT_RATES) ─────── [NC-03 해소 후 수치 재검증]
```

T-01 → T-04 → T-02 → T-05 순으로 착수하면 의존 오류 없음.
T-03, T-06, T-07, T-08은 선행 task 완료 후.

---

## 완료 기준 체크리스트

- [ ] T-01 테스트 녹색 커밋
- [ ] T-02 구조 테스트 녹색 커밋
- [ ] T-03 테스트 녹색 커밋
- [ ] T-04 테스트 녹색 커밋
- [ ] T-05 두 케이스 모두 녹색 커밋
- [ ] T-06 구조 테스트 녹색 커밋
- [ ] T-07 구조 테스트 녹색 커밋
- [ ] T-08 두 케이스 모두 녹색 커밋
- [ ] NC-01~05 해소 후 수치 테스트 추가 커밋
- [ ] `specs/EXE-03/spec.md`의 `[NEEDS CLARIFICATION]` 항목이 0건으로 감소
