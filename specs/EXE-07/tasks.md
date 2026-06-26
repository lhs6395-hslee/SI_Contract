# Tasks: EXE-07 수수료산출내역 (5-4)

**Created**: 2026-06-26  **Status**: Draft
**참고**: 이 tasks.md는 사람이 읽는 산출물이다. 자동 implement 비의존.
각 task는 "실패 테스트 작성 → 최소 구현 → 통과 확인 → 커밋" 순으로 진행한다.

---

## Task 1: 0차 시트 기본 열 기록 (FR-001, FR-002, FR-003a, FR-003b, FR-016, FR-017)

**수용기준 (SC-001 직결)**

- fee_items 3건(vendor 모두 제공)의 SprintContract로 FeeSheetWriter._write()를 실행하면,
  행 8~10에 D/E/F/G/H/I/K/L/Q/R/AJ 셀이 FeeItem 필드와 100% 일치한다(FR-003a).
- vendor=None인 FeeItem 1건으로 실행하면 AJ열에 값이 기록되지 않는다(FR-003a, vendor=None 케이스).
- revision=1인 SprintContract에서 vendor가 제공된 FeeItem의 vendor가 AQ열에 기록된다(FR-003b).
- fee_items=[]이면 시트를 수정하지 않고 즉시 반환한다.
- 자재코드(D열)가 1이다.

**실패 테스트 작성**

```python
# tests/test_fee_sheet.py
def test_base_rows_written_correctly():
    """FR-001/002/003/017: 0차 기본 열 매핑이 정확한지 검증."""
    items = [FeeItem(
        code=1, item_name="클라우드 마이그레이션", spec="AWS", unit="M/M",
        contract_qty=3.0, contract_unit_price=17_000_000, contract_amount=51_000_000,
        execution_qty=3.0, execution_unit_price=6_500_000, execution_amount=19_500_000,
        current_period_qty=3.0, current_period_amount=19_500_000, vendor="협력사A",
    )]
    contract = make_sprint_contract(fee_items=items, revision=0)
    wb = load_template()
    writer = FeeSheetWriter(wb, contract)
    writer._write()
    ws = wb["5-4. 수수료산출내역"]
    assert ws["H8"].value == 3.0        # contract_qty
    assert ws["I8"].value == 17_000_000 # contract_unit_price
    assert ws["K8"].value == 3.0        # execution_qty
    assert ws["L8"].value == 6_500_000  # execution_unit_price
    assert ws["Q8"].value == 3.0        # current_period_qty
    assert ws["R8"].value == 6_500_000  # current_period_qty단가
    assert ws["AJ8"].value == "협력사A" # vendor
    assert ws["D8"].value == 1           # code

def test_empty_fee_items_noop():
    """FR-016: fee_items=[]이면 시트 무수정."""
    contract = make_sprint_contract(fee_items=[], revision=0)
    wb = load_template()
    # 원본 셀 값 백업
    ws = wb["5-4. 수수료산출내역"]
    before = ws["H8"].value
    FeeSheetWriter(wb, contract)._write()
    assert ws["H8"].value == before
```

**최소 구현 확인 대상**

- `FeeSheetWriter._write_base_rows()` 가 FeeItem 필드를 올바른 열에 매핑하는지 확인.
  (`backend/services/excel/fee_sheet.py:68-95`)
- `CATEGORY_TO_CODE["fee"] == 1` 확인.
  (`backend/services/contract_builder.py:18`)

**커밋 단위**

```
test(exe-07): FR-001/002/003/016/017 기본 열 기록 실패 테스트
feat(exe-07): 0차 시트 기본 열 기록 통과
```

---

## Task 2: 수식 셀 강제 입력 / 수식 유지 (FR-004, FR-005, SC-008)

**수용기준 (SC-008 직결)**

- 금액이 수량×단가와 1원 이상 다를 때만 J/M/S 셀에 값을 강제 입력한다.
- 수식 셀이고 금액이 일치하면 셀 값을 덮어쓰지 않는다(수식 유지).

**실패 테스트 작성**

```python
def test_force_write_on_mismatch():
    """FR-004: 금액 불일치 시 J셀 강제 입력."""
    # contract_amount=51_000_001 (수량×단가=51_000_000 + 1원 초과)
    item = FeeItem(
        contract_qty=3.0, contract_unit_price=17_000_000,
        contract_amount=51_000_001,  # 1원 불일치
        ...
    )
    writer = make_writer_with_items([item])
    writer._write()
    ws = writer.ws
    # J8은 수식 셀이었지만 강제 입력되어야 함
    assert ws["J8"].value == 51_000_001

def test_no_force_write_on_match():
    """FR-005: 금액 일치 시 수식 셀 유지."""
    item = FeeItem(
        contract_qty=3.0, contract_unit_price=17_000_000,
        contract_amount=51_000_000,  # 정확히 일치
        ...
    )
    writer = make_writer_with_items([item])
    # J8 셀을 수식으로 미리 설정
    writer.ws["J8"] = "=H8*I8"
    writer.ws["J8"].data_type = "f"
    writer._write()
    # 수식이 덮어써지지 않아야 함 (data_type 유지)
    assert writer.ws["J8"].data_type == "f"
```

**최소 구현 확인 대상**

- `_force_if_mismatch` 함수의 `round(amount) != round(qty * unit_price)` 조건.
  (`backend/services/excel/fee_sheet.py:137-142`)
- `_write_cell_direct`의 `data_type == "f"` 조건으로 수식 셀 스킵.
  (`backend/services/excel/fee_sheet.py:156-161`)

**커밋 단위**

```
test(exe-07): FR-004/005 수식 셀 강제입력/유지 실패 테스트
feat(exe-07): _force_if_mismatch / _write_cell_direct 수식 보호
```

---

## Task 3: 역마진 감지 (FR-006a, FR-006b, SC-002)

**수용기준 (SC-002 직결)**

- 집행단가 > 계약단가(계약단가 > 0)인 항목이 있을 때 _verify_fee_structure()는
  errors 목록에 "역마진" 문자열을 포함한 오류를 기록하고(FR-006a),
  margin_structure_ok=False를 반환한다(FR-006b).

**실패 테스트 작성**

```python
def test_reverse_margin_detected():
    """FR-006/SC-002: 역마진(집행단가 > 계약단가) 감지."""
    item = FeeItem(
        contract_qty=3.0, contract_unit_price=5_000_000, contract_amount=15_000_000,
        execution_qty=3.0, execution_unit_price=6_000_000, execution_amount=18_000_000,
        # 집행 6M > 계약 5M → 역마진
    )
    contract = make_sprint_contract(fee_items=[item])
    wb = write_fee_sheet(contract)
    result = _verify_fee_structure(wb, contract)
    assert result["margin_structure_ok"] is False
    assert any("역마진" in e for e in result["errors"])

def test_no_reverse_margin_ok():
    """FR-006: 집행 ≤ 계약이면 역마진 없음."""
    item = FeeItem(
        contract_unit_price=6_000_000, execution_unit_price=5_500_000, ...
    )
    result = _verify_fee_structure(wb, make_sprint_contract(fee_items=[item]))
    assert result["margin_structure_ok"] is True
```

**최소 구현 확인 대상**

- `reviewer.py:191-193` `if l_val > i_val and i_val > 0: errors.append(...)` 로직.

**커밋 단위**

```
test(exe-07): FR-006a/006b 역마진 감지 실패 테스트
feat(exe-07): _verify_fee_structure 역마진 감지 통과
```

---

## Task 4: 1원 정밀도 금액 검증 (FR-007a, FR-007b, FR-007c, SC-003)

**수용기준 (SC-003 직결)**

- 수량×단가와 금액의 차이가 1원 이상이면 errors 목록에 오류를 기록하고(FR-007a),
  계약금액 위반 시 contract_calc_ok=False(FR-007b), 집행금액 위반 시 execution_calc_ok=False(FR-007c).
- 1원 미만 차이이면 OK로 처리한다.

**실패 테스트 작성**

```python
def test_amount_1won_mismatch_detected():
    """FR-007/SC-003: 1원 오차 감지."""
    item = FeeItem(
        contract_qty=3.0, contract_unit_price=5_500_000,
        contract_amount=16_500_001,  # 3×5.5M=16.5M, 1원 초과
    )
    result = _verify_fee_structure(wb, contract)
    assert result["contract_calc_ok"] is False
    assert any("계약:" in e for e in result["errors"])

def test_amount_exact_match_ok():
    """FR-007: 정확한 금액은 OK."""
    item = FeeItem(
        contract_qty=3.0, contract_unit_price=5_500_000,
        contract_amount=16_500_000,
    )
    result = _verify_fee_structure(wb, contract)
    assert result["contract_calc_ok"] is True
```

**최소 구현 확인 대상**

- `reviewer.py:169` `abs(j_val - item.contract_amount) > 1` 조건.
- `reviewer.py:173` `abs(expected_contract - item.contract_amount) > 1` 조건.

**커밋 단위**

```
test(exe-07): FR-007a/007b/007c 1원 정밀도 실패 테스트
feat(exe-07): _verify_fee_structure 1원 정밀도 검증 통과
```

---

## Task 5: 일할계산 (FR-008, FR-009)

**수용기준**

- 단위 "M/M", 시작일이 월 중간, 수량이 정수, contractAmount 미제공 → 일할계산된 수량(0.1 단위 반올림)이 FeeItem에 반영된다.
- contractAmount 명시 시 일할계산 없이 원래 수량과 금액이 그대로 사용된다.

**실패 테스트 작성**

```python
def test_prorated_qty_mid_month():
    """FR-008: 월 중간 시작 일할계산."""
    # 2025-10-15 시작, 2025-12-31 종료, M/M 3개월 요청
    # 10월: (31-15+1)/30 = 17/30 ≈ 0.567, 이후 11~12월 = 2개월
    # 계산: 0.6 + 2 = 2.6 M/M (0.1단위 반올림)
    extracted = {"startDate": {"value": "2025-10-15"}, "endDate": {"value": "2025-12-31"}}
    cost_items = [{"category": "fee", "unit": "M/M",
                   "contractQty": 3, "executionQty": 3,
                   "contractPrice": 5_500_000, "executionPrice": 5_500_000}]
    fee_items, _ = _build_fee_items(extracted, cost_items)
    assert fee_items[0].contract_qty == 2.6  # 일할계산 결과

def test_no_prorate_when_confirmed_amount():
    """FR-009: contractAmount 명시 시 일할계산 금지."""
    cost_items = [{"category": "fee", "unit": "M/M",
                   "contractQty": 3, "executionQty": 3,
                   "contractAmount": 16_500_000,  # 명시
                   "contractPrice": 5_500_000, "executionPrice": 5_500_000}]
    fee_items, _ = _build_fee_items(extracted_mid_month, cost_items)
    assert fee_items[0].contract_qty == 3.0  # 원래 수량 유지
    assert fee_items[0].contract_amount == 16_500_000
```

**최소 구현 확인 대상**

- `contract_builder.py:103-130` (_calc_prorated_qty)
- `contract_builder.py:228-231` (has_confirmed_amount 로직)

**커밋 단위**

```
test(exe-07): FR-008/009 일할계산/금지 실패 테스트
feat(exe-07): _build_fee_items 일할계산 통과
```

---

## Task 6: 다년도 당기 배분 + 플래그 (FR-010a, FR-010b, FR-011, FR-012, SC-006, SC-007)

**수용기준 (SC-006, SC-007 직결)**

- 다년도 사업(start_year ≠ end_year, fiscal_year 명시) → 당기수량 < 전체수량(FR-010a)이고,
  ConflictResolution conflict_type="연도배분확인"이 생성된다(FR-010b).
- 단년도 → 당기수량 = 전체 집행수량.
- currentQty 명시 시 자동 배분 없이 명시값 사용.
- 당기+이후1+이후2 금액 합 = 전체 금액 ±1원 이내.

**실패 테스트 작성**

```python
def test_multi_year_split_generates_conflict():
    """FR-010/SC-006: 다년도 사업 당기 배분 + 연도배분확인 플래그."""
    extracted = {
        "startDate": {"value": "2025-10-01"},
        "endDate": {"value": "2026-03-31"},
        "fiscalYear": {"value": "2025"},
    }
    cost_items = [{"category": "fee", "unit": "M/M",
                   "contractQty": 6, "executionQty": 6,
                   "contractPrice": 5_500_000, "executionPrice": 5_500_000}]
    fee_items, conflicts = _build_fee_items(extracted, cost_items)
    # 당기(2025년): 10~12월 = 3개월, 전체 6개월 → 비율 0.5
    assert fee_items[0].current_period_qty < 6.0
    assert any(c.conflict_type == "연도배분확인" for c in conflicts)

def test_single_year_full_qty_is_current():
    """FR-012: 단년도 → 당기수량 = 전체수량."""
    extracted = {
        "startDate": {"value": "2025-07-01"},
        "endDate": {"value": "2025-12-31"},
    }
    cost_items = [{"category": "fee", "unit": "M/M",
                   "contractQty": 6, "executionQty": 6,
                   "contractPrice": 5_500_000, "executionPrice": 5_500_000}]
    fee_items, conflicts = _build_fee_items(extracted, cost_items)
    assert fee_items[0].current_period_qty == 6.0
    assert not any(c.conflict_type == "연도배분확인" for c in conflicts)

def test_explicit_current_qty_not_overridden():
    """FR-011: currentQty 명시 시 자동 배분 금지."""
    cost_items = [{"category": "fee", "unit": "M/M",
                   "contractQty": 6, "executionQty": 6,
                   "currentQty": 2.5,  # 명시
                   "contractPrice": 5_500_000, "executionPrice": 5_500_000}]
    fee_items, _ = _build_fee_items(extracted_multi_year, cost_items)
    assert fee_items[0].current_period_qty == 2.5

def test_split_amount_sum_within_1won():
    """SC-007: 배분 합계가 전체 금액과 1원 이내."""
    amount = 33_000_000
    shares = {"current": 0.5, "next1": 0.5, "next2": 0.0, "prev": 0.0}
    cur, nx1, nx2 = _split_by_shares(amount, shares)
    assert abs(cur + nx1 + nx2 - amount) <= 1
```

**최소 구현 확인 대상**

- `contract_builder.py:160-190` (_fiscal_year_shares)
- `contract_builder.py:193-201` (_split_by_shares)
- `contract_builder.py:256-276` (currentQty 명시 / fy_shares / 단년도 분기)

**커밋 단위**

```
test(exe-07): FR-010a/010b/011/012 다년도 배분 실패 테스트
feat(exe-07): _build_fee_items 연도분리 배분 통과
```

---

## Task 7: 템플릿 행 확장 (FR-013a, FR-013b, SC-004)

**수용기준 (SC-004 직결)**

- fee_items가 9건을 초과하면 합계행 위에 초과분만큼 행이 삽입되고(FR-013a),
  삽입된 행에 이전 행의 셀 서식이 복사되며(FR-013b), 모든 항목이 누락 없이 기록된다.

**실패 테스트 작성**

```python
def test_row_insertion_for_overflow():
    """FR-013/SC-004: 9건 초과 시 행 삽입 + 모든 항목 기록."""
    items = [make_fee_item(name=f"항목{i}") for i in range(12)]
    contract = make_sprint_contract(fee_items=items, revision=0)
    wb = load_template()
    FeeSheetWriter(wb, contract)._write()
    ws = wb["5-4. 수수료산출내역"]
    # 행 8~19에 12개 항목 기록됨 (9건 기본 + 3행 삽입)
    for i, item in enumerate(items):
        assert ws.cell(row=8+i, column=5).value == item.item_name
```

**최소 구현 확인 대상**

- `fee_sheet.py:70-76` (insert_rows + _copy_row_style)
- `fee_sheet.py:25-36` (_copy_row_style 서식 복사)

**커밋 단위**

```
test(exe-07): FR-013a/013b 행 확장 실패 테스트
feat(exe-07): 9건 초과 insert_rows + 서식 복사 통과
```

---

## Task 8: 수정집행 차수 열 분리 (FR-014, FR-015a, FR-015b, SC-005)

**수용기준 (SC-005 직결)**

- revision=1 시 현재 차수 시트의 H/I(당초 계약), K/L(변경 계약), N/O(당초 집행), Q/R(변경 집행), X/Y(당기) 열이 올바르게 채워진다.
- 이전 차수 항목은 품명+협력사명 일치로 매핑되고(FR-015a), 일치 항목이 없으면 동일 순번으로 fallback 된다(FR-015b).

**실패 테스트 작성**

```python
def test_revision_columns_split():
    """FR-014/SC-005: revision=1 당초/변경/당기 열 분리."""
    prev_item = FeeItem(
        item_name="클라우드 마이그레이션", vendor="협력사A",
        contract_qty=3.0, contract_unit_price=5_000_000,
        execution_qty=3.0, execution_unit_price=4_500_000,
        current_period_qty=3.0,
    )
    curr_item = FeeItem(
        item_name="클라우드 마이그레이션", vendor="협력사A",
        contract_qty=4.0, contract_unit_price=5_000_000,
        execution_qty=4.0, execution_unit_price=4_500_000,
        current_period_qty=1.5,
    )
    contract = make_sprint_contract(
        fee_items=[curr_item], revision=1,
        prev_fee_items={"0": [prev_item]},
    )
    FeeSheetWriter(wb, contract)._write()
    ws = wb["5-4. 수수료산출내역"]
    row = 9  # REV_DATA_START_ROW
    assert ws[f"H{row}"].value == 3.0          # 당초 contract_qty
    assert ws[f"I{row}"].value == 5_000_000    # 당초 contract_unit_price
    assert ws[f"K{row}"].value == 4.0          # 변경 contract_qty
    assert ws[f"N{row}"].value == 3.0          # 당초 execution_qty
    assert ws[f"Q{row}"].value == 4.0          # 변경 execution_qty
    assert ws[f"X{row}"].value == 1.5          # 당기 수량

def test_prev_item_fallback_by_index():
    """FR-015: 품명 불일치 시 순번 fallback."""
    prev_item = FeeItem(item_name="구항목", vendor="B사", contract_qty=2.0, ...)
    curr_item = FeeItem(item_name="신항목", vendor="A사", contract_qty=3.0, ...)
    # _match_item이 품명/협력사 불일치 → index=0 fallback
    result = FeeSheetWriter._match_item([prev_item], curr_item, 0)
    assert result.item_name == "구항목"
```

**최소 구현 확인 대상**

- `fee_sheet.py:97-135` (_write_rev_rows)
- `fee_sheet.py:144-153` (_match_item)
- `fee_sheet.py:19` (REV_DATA_START_ROW=9)

**커밋 단위**

```
test(exe-07): FR-014/015a/015b 수정집행 차수 열 분리 실패 테스트
feat(exe-07): _write_rev_rows 당초/변경/당기 열 분리 통과
```

---

## Task 9: 연도분리 검증 (SC-006 Reviewer 연동)

**수용기준 (SC-006 직결)**

- 다년도 프로젝트에서 Q열(당기수량)이 전체 집행수량 이상이면 fiscal_year_split_ok=False.
- 단년도 프로젝트에서 Q열(당기수량)이 전체 집행수량보다 작으면 FAIL.

**실패 테스트 작성**

```python
def test_multiyear_current_qty_not_split():
    """SC-006: 다년도인데 당기=전체면 연도분리 FAIL."""
    item = FeeItem(execution_qty=6.0, current_period_qty=6.0, ...)
    contract = make_multiyear_contract(fee_items=[item])  # start≠end year
    wb = write_fee_sheet(contract)
    result = _verify_fee_structure(wb, contract)
    assert result["fiscal_year_split_ok"] is False
    assert any("연도분리" in e for e in result["errors"])

def test_singleyear_current_qty_less_than_total():
    """SC-006: 단년도인데 당기<전체면 연도분리 FAIL."""
    item = FeeItem(execution_qty=6.0, current_period_qty=4.0, ...)
    contract = make_singleyear_contract(fee_items=[item])
    wb = write_fee_sheet(contract)
    result = _verify_fee_structure(wb, contract)
    assert result["fiscal_year_split_ok"] is False
```

**최소 구현 확인 대상**

- `reviewer.py:203-212` (연도분리 검증 분기)

**커밋 단위**

```
test(exe-07): SC-006 연도분리 Reviewer 검증 실패 테스트
feat(exe-07): _verify_fee_structure 연도분리 검증 통과
```

---

## Task 10: 통합 검증 + 커밋

**수용기준 (전체 SC 통합)**

모든 Task 1~9의 테스트가 통과하며, 아래 조합 시나리오도 통과한다.

**통합 시나리오**

```python
def test_integration_full_fee_sheet():
    """전체 파이프라인: EXE-06 데이터 → FeeSheetWriter → _verify_fee_structure."""
    # 1. SprintContract 생성 (다년도, 10건 항목, revision=0)
    contract = make_full_sprint_contract(...)
    # 2. 0차 시트 기록
    wb = load_template()
    FeeSheetWriter(wb, contract)._write()
    # 3. Reviewer 검증
    result = _verify_fee_structure(wb, contract)
    # 4. 전체 SC 통과
    assert result["contract_calc_ok"] is True
    assert result["execution_calc_ok"] is True
    assert result["margin_structure_ok"] is True
    assert result["fiscal_year_split_ok"] is True
    assert result["score"] > 0.0
```

**체크리스트**

- [ ] FR-001, FR-002, FR-003a, FR-003b, FR-004, FR-005, FR-006a, FR-006b, FR-007a, FR-007b, FR-007c, FR-008, FR-009, FR-010a, FR-010b, FR-011, FR-012, FR-013a, FR-013b, FR-014, FR-015a, FR-015b, FR-016, FR-017 모두 대응하는 테스트가 존재하고 통과한다
- [ ] SC-001~008 수치 기준이 테스트에서 검증된다
- [ ] [NEEDS CLARIFICATION] NC-01~04 항목은 테스트에 하드코딩하지 않고 파라미터화하거나 skip 처리한다
- [ ] 역마진 FAIL이 Reviewer 반환값에 명시적으로 표시된다
- [ ] 다년도 배분 결과가 ConflictResolution에 기록된다

**최종 커밋**

```
feat(sdd): EXE-07 수수료산출내역 spec/plan/tasks
```

---

## [NEEDS CLARIFICATION] 항목 처리 지침

아래 항목은 사용자가 사내 기준으로 직접 확정하기 전까지 테스트에서 확정값을 단정하지 않는다.

| NC | 항목 | 처리 방법 |
|----|------|-----------|
| NC-01 | 수수료 코드 1/2/3 판단 기준 | 코드=1 단일값만 테스트. 2/3 분기 테스트는 skip |
| NC-02 | cell_map.json 런타임 오버라이드 기본값 보장 | cell_map.json 없는 환경에서 기본값(8/16/17) 테스트만 수행 |
| NC-03 | 일할계산 0.1 단위 반올림 정책 | 현행 코드 그대로 테스트. 정책 변경 시 spec 재검토 |
| NC-04 | Z열 강제 입력 허용 오차 기준 | round() 비교 테스트만 수행. 명시적 > N원 기준은 미정 |
