# Tasks: EXE-08 집행예산 산출내역서·집계표

**Created**: 2026-06-26  **Status**: Draft
**Spec**: `specs/EXE-08/spec.md` | **Plan**: `specs/EXE-08/plan.md`

> 이 파일은 사람이 읽는 산출물이다. 자동 implement 비의존.
> 각 task는 "실패 테스트 → 최소 구현 → 통과 → 커밋" 단위로 기술된다.

---

## TASK-01: BUDGET_BLOCKS 비목 기록 — 주 경로 (FR-001, FR-009)

**목표**: `budget_items`의 카테고리가 `BUDGET_BLOCKS`에 있을 때, 해당 행에 계약·집행·정산·당기·이후1·이후2 금액을 차수 열에 오차 없이 기록한다.

**수용기준 (Given/When/Then)**:
- Given `SprintContract.budget_items = [BudgetItem(category="labor", execution_amount=39_250_000, contract_amount=104_000_000, current_amount=39_250_000)]`이고 `revision=0`일 때,
- When `BreakdownSheetWriter(wb, contract).execute(step_id=3)`를 실행하면,
- Then `wb["공통"]["E25"].value == 39_250_000`이고 `wb["공통"]["E24"].value == 104_000_000`이며 `StepResult.status == "completed"`.

**실패 테스트**:
```python
def test_budget_blocks_writes_labor_execution():
    wb = load_template()
    contract = make_contract(budget_items=[BudgetItem(category="labor", execution_amount=39_250_000)])
    writer = BreakdownSheetWriter(wb, contract)
    result = writer.execute(step_id=3)
    ws = wb["공통"]
    assert ws["E25"].value == 39_250_000, f"급료 집행행 불일치: {ws['E25'].value}"
    assert result.status == StepStatus.completed
```

**최소 구현 위치**: `breakdown_sheet.py:48-67 BreakdownSheetWriter._write()`

**검증 게이트**: SC-001 (1원 오차 = 실패)

**커밋 단위**: `test(exe-08): BUDGET_BLOCKS labor 기록 실패테스트 → 통과`

---

## TASK-02: bonus 블록 contract=None 처리 (FR-007)

**목표**: `bonus` 블록의 `contract` 행이 `None`일 때, 해당 셀에 값을 쓰지 않고 나머지 행(execution, settled, current, next1, next2)은 정상 기록한다.

**수용기준**:
- Given `BudgetItem(category="bonus", execution_amount=4_000_000)`, `revision=0`일 때,
- When `BreakdownSheetWriter._write()`를 실행하면,
- Then `wb["공통"]["E31"].value == 4_000_000`이고, 계약금액 행(`None` 대응 셀)에는 값이 쓰이지 않는다.

**실패 테스트**:
```python
def test_bonus_no_contract_row():
    wb = load_template()
    contract = make_contract(budget_items=[BudgetItem(category="bonus", execution_amount=4_000_000)])
    writer = BreakdownSheetWriter(wb, contract)
    writer.execute(step_id=3)
    ws = wb["공통"]
    assert ws["E31"].value == 4_000_000, "상여 집행행 미기록"
    # bonus의 contract=None → 해당 행에 값 없음 확인
    assert not any(
        iu.cell == "E30" for iu in writer.inputs_used if iu.source and "contract" in iu.source
    ), "bonus contract 행에 값이 기록됨"
```

**최소 구현 위치**: `breakdown_sheet.py:64-67 "if row is not None:"`

**커밋 단위**: `test(exe-08): bonus contract=None 방어 실패테스트 → 통과`

---

## TASK-03: 이중 계상 방지 — 퇴직금·보험료 제외 (FR-003a, FR-003b)

**목표**: `costItems`에 퇴직금·보험료가 있어도 `budget_items`에 포함되지 않고, `conflict_type="자동계산중복"` 플래그가 추가된다.

**수용기준**:
- Given `costItems = [{"name": "퇴직금", "category": "labor", "executionAmount": 3_604_167}, {"name": "보험료", "category": "labor", "executionAmount": 4_914_670}]`일 때,
- When `build_sprint_contract(project_id, extracted_data)`를 호출하면,
- Then `contract.budget_items`에 `category` 값이 퇴직금·보험료에 해당하는 항목이 없고,  
  `contract.conflict_resolutions`에 `conflict_type="자동계산중복"`인 항목이 1건 이상 존재한다.

**실패 테스트**:
```python
def test_auto_calculated_excluded():
    data = make_extracted_data(cost_items=[
        {"name": "퇴직금", "category": "labor", "executionAmount": 3_604_167},
        {"name": "보험료", "category": "labor", "executionAmount": 4_914_670},
    ])
    contract = build_sprint_contract("proj-01", data)
    budget_names = [b.desc for b in contract.budget_items]
    assert not any("퇴직금" in (n or "") for n in budget_names), "퇴직금이 budget_items에 포함됨"
    conflicts = [c for c in contract.conflict_resolutions if c.conflict_type == "자동계산중복"]
    assert len(conflicts) >= 1, "자동계산중복 플래그 없음"
```

**최소 구현 위치**: `company_standards.py:43-50`, `contract_builder.py:377-382`

**커밋 단위**: `test(exe-08): 퇴직금/보험료 이중계상 방지 실패테스트 → 통과`

---

## TASK-04: VAT/부가세 항목 제외 (FR-004)

**목표**: `costItems`에 VAT·부가세 항목이 있어도 `budget_items`에 포함되지 않는다.

**수용기준**:
- Given `costItems = [{"name": "부가세(VAT)", "category": "etc", "executionAmount": 9_000_000}]`일 때,
- When `build_sprint_contract()`를 호출하면,
- Then `contract.budget_items`에 해당 항목이 없다.

**실패 테스트**:
```python
def test_vat_excluded_from_budget():
    data = make_extracted_data(cost_items=[
        {"name": "부가세(VAT)", "category": "etc", "executionAmount": 9_000_000}
    ])
    contract = build_sprint_contract("proj-01", data)
    assert all("VAT" not in (b.desc or "").upper() for b in contract.budget_items), "VAT 항목이 budget_items에 포함됨"
```

**최소 구현 위치**: `contract_builder.py:382-384`

**커밋 단위**: `test(exe-08): VAT/부가세 제외 실패테스트 → 통과`

---

## TASK-05: staff_plan fallback 급료 산출 (FR-005a, FR-005b)

**목표**: `budget_items`에 `category="labor"`가 없을 때 `staff_plan`에서 급료를 산출해 공통 시트에 기록하고, `conflict_type="급료확인"` 플래그가 추가된다.

**수용기준**:
- Given `budget_items=[]`이고 `staff_plan=[{"type":"직접","grade":"과장","months":[1,1,1],"monthlyRate":5_500_000}]`일 때,
- When `BreakdownSheetWriter._write()`를 실행하면,
- Then `공통!E25 == 16_500_000` (5,500,000 × 3)이고 `inputs_used[*].source == "staff_plan 급료합계"`이며,  
  `contract.conflict_resolutions`에 `conflict_type="급료확인"`이 포함된다.

**실패 테스트**:
```python
def test_staff_plan_fallback_salary():
    wb = load_template()
    contract = make_contract(
        budget_items=[],
        staff_plan=[StaffItem(type="직접", grade="과장", months=[1,1,1], monthly_rate=5_500_000)],
    )
    writer = BreakdownSheetWriter(wb, contract)
    writer.execute(step_id=3)
    assert wb["공통"]["E25"].value == 16_500_000
    assert any("staff_plan" in iu.source for iu in writer.inputs_used)
```

**최소 구현 위치**: `breakdown_sheet.py:69-88`

**커밋 단위**: `test(exe-08): staff_plan fallback 급료 실패테스트 → 통과`

---

## TASK-06: 다년도 당기/이후 배분 합계 보존 (FR-006, SC-002)

**목표**: 회계연도 경계 걸침 시 `current + next1 + next2 = execution_amount`를 1원 오차 이내로 충족한다.

**수용기준**:
- Given `project_period.start="2025-10-01"`, `project_period.end="2026-06-30"`, `fiscal_year=2025`, `budget_items=[BudgetItem(category="labor", execution_amount=39_000_000)]`일 때,
- When `BreakdownSheetWriter._write()`를 실행하면,
- Then `공통!E27 + 공통!E28 + 공통!E29 == 39_000_000` (1원 이내),  
  `공통!E27 > 0`이고 `공통!E28 > 0`이다.

**실패 테스트**:
```python
def test_multi_year_split_sum_preserved():
    wb = load_template()
    contract = make_contract(
        budget_items=[BudgetItem(category="labor", execution_amount=39_000_000,
                                  current_amount=0, next1_amount=0, next2_amount=0)],
        confirmed_fields=ConfirmedFields(project_period={"start":"2025-10-01","end":"2026-06-30"}, fiscal_year="2025"),
    )
    writer = BreakdownSheetWriter(wb, contract)
    writer.execute(step_id=3)
    ws = wb["공통"]
    cur = ws["E27"].value or 0
    nx1 = ws["E28"].value or 0
    nx2 = ws["E29"].value or 0
    assert abs(cur + nx1 + nx2 - 39_000_000) <= 1, f"배분 합계 오류: {cur}+{nx1}+{nx2}"
    assert cur > 0 and nx1 > 0, "당기·이후1 모두 0"
```

**최소 구현 위치**: `breakdown_sheet.py:79-88`, `contract_builder.py:193-201`

**검증 게이트**: SC-002

**커밋 단위**: `test(exe-08): 다년도 배분 합계 보존 실패테스트 → 통과`

---

## TASK-07: 셀 보호 — 파란 셀·수식 셀 미기록 (FR-008)

**목표**: 파란색(`FF0070C0`) 셀 또는 수식 셀에 값을 기록하지 않는다.

**수용기준**:
- Given 공통 시트에 파란 셀이 존재하고, `BreakdownSheetWriter._write()`를 실행할 때,
- When 해당 셀이 `write_cell()`의 대상이 되면,
- Then 셀 값이 변경되지 않고 `inputs_used`에 해당 셀이 포함되지 않는다.

**실패 테스트**:
```python
def test_blue_cell_not_overwritten():
    wb = load_template()
    ws = wb["공통"]
    # E5는 차수 표시 파란 셀(common_sheet.py:78 직접 write 처리 — 여기선 SheetWriter 방어 확인)
    from openpyxl.styles import PatternFill
    ws["E99"].fill = PatternFill(start_color="FF0070C0", end_color="FF0070C0", fill_type="solid")
    original_val = ws["E99"].value
    contract = make_contract(budget_items=[BudgetItem(category="safety", execution_amount=100_000)])
    writer = BreakdownSheetWriter(wb, contract)
    writer.execute(step_id=3)
    assert ws["E99"].value == original_val, "파란 셀이 덮어쓰여짐"
```

**최소 구현 위치**: `base.py:83-88 cell_type()`, `base.py:85-86 skip_cell 분기`

**커밋 단위**: `test(exe-08): 파란·수식 셀 보호 실패테스트 → 통과`

---

## TASK-08: inputs_used 소스 추적 완전성 (FR-002, SC-005)

**목표**: `write_cell()`이 기록한 모든 항목의 `inputs_used`에 `source` 필드가 비어 있지 않다.

**수용기준**:
- Given 임의 `budget_items` 3종을 포함한 `SprintContract`일 때,
- When `BreakdownSheetWriter.execute()`를 실행하면,
- Then `StepResult.constraint_compliance["소스_근거_명시"] == True`.

**실패 테스트**:
```python
def test_inputs_used_source_complete():
    wb = load_template()
    contract = make_contract(budget_items=[
        BudgetItem(category="labor", execution_amount=10_000_000),
        BudgetItem(category="travel", execution_amount=500_000),
        BudgetItem(category="etc", execution_amount=200_000),
    ])
    writer = BreakdownSheetWriter(wb, contract)
    result = writer.execute(step_id=3)
    assert result.constraint_compliance.get("소스_근거_명시") is True
    assert all(iu.source for iu in result.inputs_used), "source 없는 inputs_used 항목 있음"
```

**최소 구현 위치**: `base.py:106-108`

**커밋 단위**: `test(exe-08): inputs_used 소스 완전성 실패테스트 → 통과`

---

## TASK-09: CATEGORY_LABELS 에코 방지 (FR-010)

**목표**: `item.name`이 카테고리 라벨(예: "복리후생비")과 동일하면 `desc` 셀에 기록하지 않는다.

**수용기준**:
- Given `costItems = [{"name": "복리후생비", "category": "welfare", "executionAmount": 1_000_000}]`일 때,
- When `build_sprint_contract()`를 호출하면,
- Then `contract.budget_items`의 `welfare` 항목의 `desc`가 `None` 또는 `""`이다.

**실패 테스트**:
```python
def test_category_label_not_echoed_to_desc():
    data = make_extracted_data(cost_items=[
        {"name": "복리후생비", "category": "welfare", "executionAmount": 1_000_000}
    ])
    contract = build_sprint_contract("proj-01", data)
    welfare = next((b for b in contract.budget_items if b.category == "welfare"), None)
    assert welfare is not None, "welfare budget_item 없음"
    assert not welfare.desc, f"카테고리 라벨이 desc에 에코됨: {welfare.desc}"
```

**최소 구현 위치**: `contract_builder.py:26-33 CATEGORY_LABELS`, `contract_builder.py:389-390`

**커밋 단위**: `test(exe-08): CATEGORY_LABELS 에코 방지 실패테스트 → 통과`

---

## TASK-10: 통합 검증 — Reviewer _verify_breakdown 연동 (SC-001, SC-003, SC-004)

**목표**: `BreakdownSheetWriter`가 기록한 공통 시트를 `reviewer._verify_breakdown()`이 정상 검증한다.

**수용기준**:
- Given 완전한 `SprintContract`(budget_items + fee_items + rates)와 기록된 워크북일 때,
- When `_verify_breakdown(wb, contract, step_results)`를 호출하면,
- Then `result["labor_sum_ok"] == True`, `result["fee_cross_check_ok"] == True`, `result["errors"] == []`.

**실패 테스트**:
```python
def test_verify_breakdown_passes_after_write():
    wb, contract = make_complete_fixture()
    writer = BreakdownSheetWriter(wb, contract)
    step_result = writer.execute(step_id=3)
    vr = _verify_breakdown(wb, contract, {3: step_result})
    assert vr["errors"] == [], f"검증 오류: {vr['errors']}"
    assert vr["labor_sum_ok"] is True
    assert vr["fee_cross_check_ok"] is True
```

**최소 구현 위치**: `reviewer.py:300-405 _verify_breakdown()`

**커밋 단위**: `test(exe-08): Reviewer _verify_breakdown 연동 실패테스트 → 통과`

---

## 미결 사항 (tasks 수준)

아래 항목은 `[NEEDS CLARIFICATION]` 해소 후 별도 task로 추가한다.

| 항목 | 블로커 | 추가 예정 task |
|------|--------|----------------|
| 보험료 요율 기준 확정 | 집행/정산 요율 이원화 정책 결정 | TASK-11: 보험료 요율 SC-006 수치 반영 |
| 안전관리비 산출 기준 | "인원×5만" 코드 근거 확인 | TASK-12: safety 블록 자동 산출 또는 수식 위임 명확화 |
