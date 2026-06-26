# Tasks: EXE-10 — 갑지(0) 집계 (수식 레이어·종속)

**Feature Branch**: `EXE-10-cover-sheet-formula-layer`
**Created**: 2026-06-26
**Status**: Draft

> **중요**: 이 tasks.md는 사람이 읽는 산출물이다. 자동 implement 비의존(`/speckit-implement` 미실행). 각 task는 "실패 테스트 작성 → 최소 구현 확인 → 통과 → 커밋" 단위로 정의한다. EXE-10은 수식 레이어이므로 새 비즈니스 로직 구현보다 **수식 무결성 검증 테스트** 작성이 핵심이다.

---

## Task 1: 매출액·영업이익 천원 단위 기록 무결성 검증 (FR-002, FR-003, FR-007, FR-008, SC-001, SC-002)

**수용기준**: 0차 계약에서 F4(매출액)·P4(영업이익) 기록값이 확정값의 천원 변환과 1 이하 오차를 가진다. 검증 로직(FR-007, FR-008)이 1 초과 오차를 FAIL로 판정한다.

### Step 1-1: 실패 테스트 작성

테스트 파일 위치: `backend/tests/test_exe10_cover_formula.py`

```python
# 테스트: F4 천원 변환 정확성
def test_f4_revenue_thousand_unit():
    """FR-002: revenue=100_000_000원 → F4=100_000(천원), 오차 0"""
    contract = make_contract(revenue=100_000_000, profit=10_000_000, revision=0)
    wb = load_template()
    writer = CommonSheetWriter(wb, contract)
    writer._write()
    ws = wb["공통"]
    assert abs(ws["F4"].value - 100_000) <= 1  # SC-001

def test_f4_small_revenue_no_conversion():
    """FR-002: abs(revenue) < 1_000_000 → 변환 없이 원 단위 그대로"""
    contract = make_contract(revenue=500_000, revision=0)
    wb = load_template()
    writer = CommonSheetWriter(wb, contract)
    writer._write()
    ws = wb["공통"]
    assert ws["F4"].value == 500_000

def test_p4_profit_thousand_unit():
    """FR-003: profit=10_000_000원 → P4=10_000(천원)"""
    contract = make_contract(revenue=100_000_000, profit=10_000_000, revision=0)
    wb = load_template()
    writer = CommonSheetWriter(wb, contract)
    writer._write()
    ws = wb["공통"]
    assert abs(ws["P4"].value - 10_000) <= 1  # SC-002

def test_verify_cover_f4_fail_on_mismatch():
    """FR-007: F4 오차 > 1이면 검증 FAIL"""
    # F4에 틀린 값을 강제로 기록 후 _verify_cover_sheet 호출 → errors 비어있지 않음
    ...
```

*실행 시 현재 코드가 있으므로 pass가 예상됨. 실패 케이스는 의도적으로 오차 > 1인 값을 주입해 검증 로직 동작 확인.*

### Step 1-2: 현행 코드 확인

- `excel/common_sheet.py:119-126` `_thousand()` 함수와 `write_cell("F4", ...)`, `write_cell("P4", ...)` 이미 구현됨.
- `reviewer.py:423-447` F4·P4 검증 이미 구현됨.
- 추가 구현 불필요. 테스트로 현행 동작을 고정(regression guard).

### Step 1-3: 통과 기준

- `test_f4_revenue_thousand_unit`: PASS
- `test_p4_profit_thousand_unit`: PASS
- `test_f4_small_revenue_no_conversion`: PASS
- `test_verify_cover_f4_fail_on_mismatch`: 오류 목록에 "매출액" 포함됨 확인

### Step 1-4: 커밋

```
feat(test/exe10): F4/P4 천원 변환 무결성 검증 테스트 추가
```

---

## Task 2: 기간 날짜 기록 및 검증 무결성 (FR-004, FR-005, FR-012, SC-004)

**수용기준**: project_period.start·end가 존재하는 계약에서 공통 시트 col+125·col+126이 None이 아닌 datetime으로 기록된다. 미입력 시 검증 FAIL.

### Step 2-1: 실패 테스트 작성

```python
def test_col125_126_not_none_when_period_exists():
    """FR-004, FR-005: 기간 존재 시 col+125·col+126 != None"""
    contract = make_contract(
        period={"start": "2026-01-01", "end": "2026-12-31"},
        revision=0
    )
    wb = load_template()
    writer = CoverSheetWriter(wb, contract)
    writer._write()
    ws = wb["공통"]
    assert ws["E125"].value is not None  # SC-004
    assert ws["E126"].value is not None  # SC-004

def test_verify_period_fail_when_cell_none():
    """FR-012: col+125=None이면 검증 오류"""
    # period 있는 계약으로 CoverSheetWriter 미실행 → _verify_cover_sheet 호출 → errors 포함
    ...

def test_to_date_parses_all_formats():
    """_to_date: %Y-%m-%d, %Y.%m.%d, %Y/%m/%d 모두 datetime 반환"""
    from services.excel.cover_sheet import _to_date
    from datetime import datetime
    assert isinstance(_to_date("2026-01-01"), datetime)
    assert isinstance(_to_date("2026.01.01"), datetime)
    assert isinstance(_to_date("2026/01/01"), datetime)
    assert _to_date("") is None
```

### Step 2-2: 현행 코드 확인

- `excel/cover_sheet.py:16-25` `_to_date()` 이미 구현됨.
- `excel/cover_sheet.py:38-44` 날짜 기록 이미 구현됨.
- `reviewer.py:458-470` 기간 검증 이미 구현됨.
- 추가 구현 불필요.

### Step 2-3: 통과 기준

- 모든 테스트 PASS.
- `_to_date("")` → None (빈 문자열 처리).

### Step 2-4: 커밋

```
feat(test/exe10): 기간 날짜 기록·검증 무결성 테스트 추가
```

---

## Task 3: 사업명 참조원본 검증 (FR-006)

**수용기준**: 공통 시트 E3이 confirmed_fields.project_name과 정확히 일치하지 않으면 _verify_cover_sheet()가 오류를 보고한다.

### Step 3-1: 실패 테스트 작성

```python
def test_e3_project_name_match():
    """FR-006: E3 == project_name이면 오류 없음"""
    contract = make_contract(project_name="테스트사업", revision=0)
    wb = load_template()
    # CommonSheetWriter가 E3 기록
    CommonSheetWriter(wb, contract)._write()
    result = _verify_cover_sheet(wb, contract, {})
    assert not any("사업명" in e for e in result["errors"])

def test_e3_project_name_mismatch_fails():
    """FR-006: E3 != project_name이면 오류 포함"""
    contract = make_contract(project_name="테스트사업", revision=0)
    wb = load_template()
    wb["공통"]["E3"].value = "다른사업명"  # 의도적 불일치
    result = _verify_cover_sheet(wb, contract, {})
    assert any("사업명" in e for e in result["errors"])
```

### Step 3-2: 현행 코드 확인

- `reviewer.py:449-456` E3 검증 이미 구현됨.

### Step 3-3: 통과 기준 / Step 3-4: 커밋

```
feat(test/exe10): 갑지 사업명 참조원본 검증 테스트 추가
```

---

## Task 4: 수정집행 시 집계표 참조 수식 삽입 (FR-010, FR-011, SC-003)

**수용기준**: revision >= 1인 계약에서 공통 시트의 수식 삽입 대상 셀들이 "=" 로 시작하는 수식 문자열로 기록된다. 숫자값 직접 기록 시 FAIL.

### Step 4-1: 실패 테스트 작성

```python
def test_formula_inserted_for_rev1():
    """FR-010, FR-011: revision=1 시 수식(= 시작) 삽입"""
    contract = make_contract(revision=1, prev_revisions={"0": {...}})
    wb = load_template()
    # revision >= 1: 워크북에 "(1차)" 시트 필요
    wb.create_sheet("4. 집행예산집계표 (1차)")
    CommonSheetWriter(wb, contract)._write()
    ws = wb["공통 (1차)"] if "공통 (1차)" in wb.sheetnames else wb["공통"]
    # col = 'F' (1차)
    assert str(ws["F135"].value).startswith("=")  # SC-003
    assert str(ws["F141"].value).startswith("=")  # SC-003
    assert str(ws["F148"].value).startswith("=")  # SC-003
    assert str(ws["F149"].value).startswith("=")  # SC-003

def test_formula_contains_correct_sheet_name():
    """FR-010: 수식이 올바른 집계표 시트명을 참조"""
    contract = make_contract(revision=1, prev_revisions={"0": {...}})
    wb = load_template()
    wb.create_sheet("4. 집행예산집계표 (1차)")
    CommonSheetWriter(wb, contract)._write()
    ws = wb["공통"]
    assert "집행예산집계표 (1차)" in str(ws["F135"].value)

def test_no_formula_inserted_for_rev0():
    """FR-001: revision=0에서 집계표 수식 삽입 루프 미실행"""
    contract = make_contract(revision=0)
    wb = load_template()
    CommonSheetWriter(wb, contract)._write()
    ws = wb["공통"]
    # E135는 템플릿 수식 또는 빈 셀이어야 함 (숫자 직접 기록 아님)
    val = ws["E135"].value
    assert val is None or (isinstance(val, str) and val.startswith("=")) or val == 0
```

### Step 4-2: 현행 코드 확인

- `excel/common_sheet.py:327-353` revision >= 1 수식 삽입 루프 이미 구현됨.
- `excel/common_sheet.py:340` `agg_sheet = f"'4. 집행예산집계표 ({rev}차)'"` 시트명 패턴 확인.

### Step 4-3: 통과 기준

- `test_formula_inserted_for_rev1`: F135, F141, F148, F149 모두 "=" 시작 PASS.
- `test_formula_contains_correct_sheet_name`: 시트명 포함 PASS.
- `test_no_formula_inserted_for_rev0`: E135가 숫자값 직접 기록이 아님 PASS.

### Step 4-4: 커밋

```
feat(test/exe10): 수정집행 집계표 참조 수식 삽입 무결성 테스트 추가
```

---

## Task 5: 영업이익 역산 검증 (FR-009, SC-005)

**수용기준**: revenue·cost·profit·rates가 모두 존재하는 계약에서 역산 오차가 `max(abs(revenue)×0.01, 1,000)` 이내이면 통과, 초과하면 FAIL.

### Step 5-1: 실패 테스트 작성

```python
def test_profit_reverse_calc_within_tolerance():
    """FR-009: 역산 오차 허용 범위 내 → 오류 없음"""
    # revenue=100_000_000, cost=80_000_000, indirect+admin=4.9%
    # overhead=4_900_000, expected_profit=15_100_000
    # cf.profit=15_100_000 → 오차 0
    contract = make_contract_with_rates(
        revenue=100_000_000, cost=80_000_000, profit=15_100_000,
        indirect_rate=1.9, admin_rate=3.0
    )
    wb = load_template()
    CommonSheetWriter(wb, contract)._write()
    result = _verify_cover_sheet(wb, contract, {})
    assert not any("역산" in e for e in result.get("errors", []))

def test_profit_reverse_calc_exceeds_tolerance():
    """FR-009: 역산 오차 > max(rev*0.01, 1000) → 오류"""
    contract = make_contract_with_rates(
        revenue=100_000_000, cost=80_000_000,
        profit=5_000_000,  # 의도적 오류: 실제 역산값 15_100_000과 크게 차이
        indirect_rate=1.9, admin_rate=3.0
    )
    wb = load_template()
    CommonSheetWriter(wb, contract)._write()
    result = _verify_cover_sheet(wb, contract, {})
    assert any("역산" in e for e in result.get("errors", []))
```

### Step 5-2: 현행 코드 확인

- `reviewer.py:473-484` 영업이익 역산 검증 이미 구현됨.
- `[NEEDS CLARIFICATION]`: 간접·일반관리비율(1.9%·3.0%)이 실제 운영 기준인지 권위 출처 미확정(`company_standards.py:28-29`·주석만). 테스트는 코드 현행값을 입력으로 사용한다.

### Step 5-3: 통과 기준

두 테스트 PASS.

### Step 5-4: 커밋

```
feat(test/exe10): 갑지 영업이익 역산 검증 테스트 추가
```

---

## Task 6: 이전 차수 날짜·범위·특기사항 기록 (FR-013)

**수용기준**: prev_revisions가 있는 계약에서 각 이전 차수의 날짜·사업범위·특기사항이 해당 차수 열에 기록된다.

### Step 6-1: 실패 테스트 작성

```python
def test_prev_revision_dates_written():
    """FR-013: prev_revisions[0] 날짜가 E열(0차)에 기록됨"""
    contract = make_contract(
        revision=1,
        prev_revisions={
            "0": {
                "extracted": {
                    "startDate": {"value": "2026-01-01"},
                    "endDate": {"value": "2026-06-30"},
                    "scope": {"value": "1단계"},
                    "specialNotes": {"value": "비고A"},
                }
            }
        }
    )
    wb = load_template()
    CoverSheetWriter(wb, contract)._write()
    ws = wb["공통 (1차)"] if "공통 (1차)" in wb.sheetnames else wb["공통"]
    # 0차 = E열
    assert ws["E125"].value is not None  # startDate
    assert ws["E126"].value is not None  # endDate
    assert ws["E129"].value == "1단계"   # scope
    assert ws["E134"].value == "비고A"   # specialNotes
```

### Step 6-2: 현행 코드 확인

- `excel/cover_sheet.py:52-75` prev_revisions 루프 이미 구현됨.

### Step 6-3: 통과 기준

테스트 PASS.

### Step 6-4: 커밋

```
feat(test/exe10): 이전 차수 날짜·범위·특기사항 기록 무결성 테스트 추가
```

---

## Task 7: 수식 셀 보호 — formula_cell 스킵 (FR-001)

**수용기준**: SheetWriter.write_cell()이 data_type=="f"인 셀(수식 셀)을 건드리지 않는다.

### Step 7-1: 실패 테스트 작성

```python
def test_formula_cell_not_overwritten():
    """FR-001: data_type='f' 셀에 write_cell 호출 시 값 변경 없음"""
    from services.excel.base import SheetWriter, cell_type, CellType
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "=1+1"  # 수식 셀 (실제 파일 저장 후 읽어야 data_type='f' 인식)
    # 또는 직접 data_type 설정
    ws["A1"].data_type = "f"
    original_value = ws["A1"].value

    class _DummyWriter(SheetWriter):
        sheet_name = ws.title
        def _write(self): pass

    writer = _DummyWriter(wb, make_minimal_contract())
    writer.write_cell("A1", 9999, source="test")
    assert ws["A1"].value == original_value  # 변경 없음
```

### Step 7-2: 현행 코드 확인

- `excel/base.py:87-88`: `if ct == CellType.formula_cell: return` 이미 구현됨.

### Step 7-3: 통과 기준

테스트 PASS (수식 셀 값 불변).

### Step 7-4: 커밋

```
feat(test/exe10): 수식 셀 write_cell 스킵 보호 테스트 추가
```

---

## 전체 커밋 순서 (의존성 없음 — 병렬 가능)

| Task | 커밋 메시지 요약 | 의존 |
|------|----------------|------|
| Task 1 | F4/P4 천원 변환 무결성 | 없음 |
| Task 2 | 기간 날짜 기록·검증 | 없음 |
| Task 3 | 사업명 참조원본 검증 | 없음 |
| Task 4 | 수정집행 수식 삽입 | 없음 |
| Task 5 | 영업이익 역산 검증 | 없음 |
| Task 6 | 이전 차수 날짜 기록 | 없음 |
| Task 7 | 수식 셀 보호 | 없음 |
| 최종 | `feat(sdd): EXE-10 갑지 집계 spec/plan/tasks` | 전체 |

---

## 미해결 항목 (구현 전 확인 필요)

| 항목 | 현황 | 확인 방법 |
|------|------|-----------|
| 간접·일반관리비율 권위 출처 | `company_standards.py:28-29` 코드값 1.9%/3.0%, 공문 없음 | 사용자가 사내 기준 문서(공문·사규)로 직접 확정 |
| 보험 요율 집행 vs 정산 이원화 | `REPORT_eps_values.md:174-180` 두 버전 충돌 | 사용자가 사내 기준 문서로 직접 확정 |
| 갑지 수식 셀 목록 완전성 (E127·E128) | cover_sheet.py 주석 언급, 코드 미확인 | 템플릿 xlsx 직접 열람 |
| revision=0 시 집계표 수식 템플릿 내장 여부 | 코드에서 0차 수식 삽입 로직 없음 | 템플릿 xlsx 직접 열람 |
