# Tasks: EXE-12 — 템플릿 생성

**Feature Branch**: `EXE-12-template-generation`
**Created**: 2026-06-26
**Status**: Draft
**작업 깊이**: 문서까지 — tasks.md는 사람이 읽는 구현 로드맵(자동 implement 비의존, constitution §VII)

각 task는 **실패 테스트 → 최소 구현 → 통과 → 커밋** 단위로 구성한다.
수용기준(Given/When/Then)은 spec.md에서 파생한다.

---

## Task T-01: `rev_col` 단위 테스트 통과 보장

**수용기준**: SC-002 — `rev_col(revision)`이 0~11 전체에 대해 'E'~'P'를 반환한다. 오차 0건.

**배경**: `excel/utils.py:6-8`에 이미 구현되어 있으나 단위 테스트가 없거나 불완전할 경우를 대비한 검증 task.

### 실패 테스트 (Red)

```python
# tests/test_rev_col.py
import pytest
from services.excel.utils import rev_col

@pytest.mark.parametrize("revision,expected_col", [
    (0, 'E'), (1, 'F'), (2, 'G'), (3, 'H'), (4, 'I'), (5, 'J'),
    (6, 'K'), (7, 'L'), (8, 'M'), (9, 'N'), (10, 'O'), (11, 'P'),
])
def test_rev_col_all_valid(revision, expected_col):
    assert rev_col(revision) == expected_col

def test_rev_col_max():
    assert rev_col(11) == 'P'  # MAX_REVISION 경계
```

### 최소 구현

`excel/utils.py:6-8`의 `rev_col` 구현을 그대로 사용. 신규 구현 불필요.
테스트 파일 `tests/test_rev_col.py` 생성.

### 통과 확인

```bash
pytest tests/test_rev_col.py -v
```
Expected: 12개 parametrize 케이스 PASS.

### 커밋

```bash
git add tests/test_rev_col.py
git commit -m "test(EXE-12): rev_col 차수→열 변환 단위 테스트"
```

---

## Task T-02: `resolve_template_path` NFC/NFD 안전 해석 테스트

**수용기준**: SC-003 — NFD 인코딩 파일명이 있을 때 `resolve_template_path`가 1회 스캔으로 경로를 반환한다. 예외 0건.

### 실패 테스트 (Red)

```python
# tests/test_resolve_template_path.py
import unicodedata
from pathlib import Path
import tempfile
import pytest
from services.excel_writer import resolve_template_path

def test_resolve_nfd_filename(tmp_path):
    """NFD 인코딩 파일명으로 저장된 템플릿을 NFC 조회로 찾는다."""
    nfd_name = unicodedata.normalize("NFD", "템플릿.xlsx")
    (tmp_path / nfd_name).write_bytes(b"dummy")

    result = resolve_template_path(tmp_path, "템플릿.xlsx")
    assert result.exists(), "NFD 파일을 NFC 조회로 찾지 못함"

def test_resolve_direct_path_first(tmp_path):
    """NFC 직접 경로가 있으면 스캔 없이 직접 반환한다."""
    nfc_path = tmp_path / "템플릿.xlsx"
    nfc_path.write_bytes(b"dummy")

    result = resolve_template_path(tmp_path, "템플릿.xlsx")
    assert result == nfc_path

def test_resolve_missing_returns_direct(tmp_path):
    """파일이 없으면 직접 경로를 반환(호출부에서 FileNotFoundError 처리)."""
    result = resolve_template_path(tmp_path, "없는파일.xlsx")
    assert result == tmp_path / "없는파일.xlsx"
    assert not result.exists()
```

### 최소 구현

`excel_writer.py:11-25`의 `resolve_template_path` 구현을 그대로 사용.
테스트 파일 `tests/test_resolve_template_path.py` 생성.

### 통과 확인

```bash
pytest tests/test_resolve_template_path.py -v
```
Expected: 3개 케이스 PASS.

### 커밋

```bash
git add tests/test_resolve_template_path.py
git commit -m "test(EXE-12): resolve_template_path NFC/NFD 해석 테스트"
```

---

## Task T-03: 셀 색상 기반 기록 규칙 테스트 (`cell_type`, `write_cell`)

**수용기준**: SC-004 — skip_cell(파란색) 및 formula_cell에 `write_cell` 호출 시 셀 값 변경 0건, `inputs_used` 추가 0건.

### 실패 테스트 (Red)

```python
# tests/test_write_cell.py
import openpyxl
from openpyxl.styles import PatternFill
import pytest
from services.excel.base import cell_type, CellType

def _make_ws_with_colored_cell(rgb: str):
    """지정 색상 셀을 포함한 단순 워크시트 생성."""
    wb = openpyxl.Workbook()
    ws = wb.active
    cell = ws["A1"]
    cell.fill = PatternFill(start_color=rgb, end_color=rgb, fill_type="solid")
    return ws, cell

def test_cell_type_input_yellow():
    _, cell = _make_ws_with_colored_cell("FFFFFFCC")
    assert cell_type(cell) == CellType.input_cell

def test_cell_type_skip_blue():
    _, cell = _make_ws_with_colored_cell("FF0070C0")
    assert cell_type(cell) == CellType.skip_cell

def test_write_cell_skips_blue(mocker):
    """파란색(skip_cell) 셀에는 값이 기록되지 않는다."""
    from models import SprintContract
    from services.excel.base import SheetWriter

    # 최소 픽스처 — SheetWriter는 추상이므로 서브클래스로 검사
    class _TestWriter(SheetWriter):
        sheet_name = "Sheet"
        def _write(self): pass

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws["A1"].fill = PatternFill(start_color="FF0070C0", end_color="FF0070C0", fill_type="solid")
    ws["A1"].value = "원래값"

    contract = mocker.MagicMock(spec=SprintContract)
    contract.revision = 0
    writer = _TestWriter(wb, contract)
    writer.write_cell("A1", "새값", source="test")

    assert ws["A1"].value == "원래값", "파란색 셀은 수정되면 안 됨"
    assert len(writer.inputs_used) == 0, "skip_cell은 inputs_used에 기록되면 안 됨"

def test_write_cell_skips_formula(mocker):
    """수식 셀에는 값이 기록되지 않는다."""
    from models import SprintContract
    from services.excel.base import SheetWriter

    class _TestWriter(SheetWriter):
        sheet_name = "Sheet"
        def _write(self): pass

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws["B1"].value = "=SUM(1,2)"
    ws["B1"].data_type = "f"

    contract = mocker.MagicMock(spec=SprintContract)
    contract.revision = 0
    writer = _TestWriter(wb, contract)
    writer.write_cell("B1", 999, source="test")

    assert len(writer.inputs_used) == 0, "formula_cell은 inputs_used에 기록되면 안 됨"
```

### 최소 구현

`base.py:35-97` 현행 구현 사용. 테스트 파일만 생성.
`pytest-mock` 의존 추가 필요 시 `requirements-dev.txt` 업데이트.

### 통과 확인

```bash
pytest tests/test_write_cell.py -v
```
Expected: 4개 케이스 PASS.

### 커밋

```bash
git add tests/test_write_cell.py
git commit -m "test(EXE-12): cell_type + write_cell 색상 규칙 테스트"
```

---

## Task T-04: `inputs_used` 소스 추적 테스트

**수용기준**: SC-005 — `constraint_compliance["소스_근거_명시"]`가 True이면 `inputs_used`의 모든 source가 비어있지 않다. 비어있는 항목 0건.

### 실패 테스트 (Red)

```python
# tests/test_inputs_used.py
import openpyxl
from openpyxl.styles import PatternFill
import pytest

def _make_yellow_wb():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws["A1"].fill = PatternFill(start_color="FFFFFFCC", end_color="FFFFFFCC", fill_type="solid")
    return wb

def test_inputs_used_has_source(mocker):
    from models import SprintContract
    from services.excel.base import SheetWriter

    class _TestWriter(SheetWriter):
        sheet_name = "Sheet"
        def _write(self):
            self.write_cell("A1", "테스트값", source="test_source")

    wb = _make_yellow_wb()
    contract = mocker.MagicMock(spec=SprintContract)
    contract.revision = 0
    writer = _TestWriter(wb, contract)
    result = writer.execute(step_id=1)

    assert result.constraint_compliance["소스_근거_명시"] is True
    for inp in result.inputs_used:
        assert inp.source, f"source가 비어있는 항목 발견: {inp}"

def test_inputs_used_empty_source_fails_compliance(mocker):
    """source가 빈 inputs_used가 있으면 소스_근거_명시가 False여야 한다."""
    from models import SprintContract
    from services.excel.base import SheetWriter

    class _TestWriter(SheetWriter):
        sheet_name = "Sheet"
        def _write(self):
            self.write_cell("A1", "테스트값", source="")  # 빈 source

    wb = _make_yellow_wb()
    contract = mocker.MagicMock(spec=SprintContract)
    contract.revision = 0
    writer = _TestWriter(wb, contract)
    result = writer.execute(step_id=1)

    assert result.constraint_compliance["소스_근거_명시"] is False
```

### 최소 구현

`base.py:107-108` 현행 `constraint_compliance` 로직 사용. 테스트 파일만 생성.

### 통과 확인

```bash
pytest tests/test_inputs_used.py -v
```
Expected: 2개 케이스 PASS.

### 커밋

```bash
git add tests/test_inputs_used.py
git commit -m "test(EXE-12): inputs_used 소스 추적 + compliance 테스트"
```

---

## Task T-05: `COMMON_MAPPING` 기록 정확도 테스트

**수용기준**: SC-001 — `_fill_common_sheet`가 COMMON_MAPPING 키 중 data에 존재하는 모든 항목을 E열 해당 행에 기록한다. 기록 누락률 0%.

### 실패 테스트 (Red)

```python
# tests/test_fill_common_sheet.py
import openpyxl
from openpyxl.styles import PatternFill
import pytest
from services.excel_writer import COMMON_MAPPING, _fill_common_sheet

def _make_yellow_wb_with_mapping_cells():
    """COMMON_MAPPING 행을 노란색으로 채운 테스트 워크북."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "공통"
    for row in COMMON_MAPPING.keys():
        ws.cell(row=row, column=5).fill = PatternFill(
            start_color="FFFFFFCC", end_color="FFFFFFCC", fill_type="solid"
        )
    return wb

def test_fill_common_sheet_all_keys():
    """COMMON_MAPPING의 모든 키가 data에 있으면 E열에 기록된다."""
    wb = _make_yellow_wb_with_mapping_cells()
    ws = wb["공통"]

    data = {
        "projectName": "퀘이사존 유지보수",
        "client": "삼성SDS",
        "contractor": "GS네오텍",
        "contractType": "일반",
        "startDate": "2026.01.01",
        "endDate": "2026.12.31",
        "pm": "홍길동",
        "salesOwner": "김영희",
        "paymentTerms": "후불",
        "revenue": 156_600_000,
        "cost": 98_400_000,
    }

    _fill_common_sheet(ws, data)

    for row, key in COMMON_MAPPING.items():
        if key in data:
            cell_val = ws.cell(row=row, column=5).value
            assert cell_val is not None, f"row={row}, key={key}: 값이 기록되지 않음"

def test_fill_common_sheet_dict_value_extraction():
    """값이 dict 형태({'value': ...})일 때 내부값을 추출하여 기록한다."""
    wb = _make_yellow_wb_with_mapping_cells()
    ws = wb["공통"]

    data = {"projectName": {"value": "딕셔너리_사업명"}}
    _fill_common_sheet(ws, data)

    assert ws.cell(row=9, column=5).value == "딕셔너리_사업명"

def test_fill_common_sheet_missing_key_skipped():
    """data에 없는 키는 기록하지 않는다."""
    wb = _make_yellow_wb_with_mapping_cells()
    ws = wb["공통"]

    _fill_common_sheet(ws, {})  # 빈 data

    for row in COMMON_MAPPING.keys():
        assert ws.cell(row=row, column=5).value is None, f"row={row}: 비어있어야 함"
```

### 최소 구현

`excel_writer.py:86-95` 현행 구현 사용. 테스트 파일만 생성.
주의: 실제 템플릿 없이 openpyxl 순수 워크북으로 픽스처 구성 — 템플릿 파일 의존 없음.

### 통과 확인

```bash
pytest tests/test_fill_common_sheet.py -v
```
Expected: 3개 케이스 PASS.

### 커밋

```bash
git add tests/test_fill_common_sheet.py
git commit -m "test(EXE-12): COMMON_MAPPING 기록 정확도 테스트"
```

---

## Task T-06: 결과 파일 생성 통합 테스트 (smoke)

**수용기준**: SC-006 — 파이프라인 성공 종료 시 `results/{project_id}_집행계획서.xlsx`가 생성된다.

### 실패 테스트 (Red)

```python
# tests/test_pipeline_output.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

def test_output_file_created(tmp_path, mocker):
    """run_pipeline_sync 실행 후 results 폴더에 xlsx가 생성된다."""
    # TEMPLATE_PATH를 실제 템플릿 경로로 교체(CI 환경에서 실 템플릿 없는 경우 skip)
    template = Path(__file__).parent.parent / "templates" / "템플릿.xlsx"
    if not template.exists():
        pytest.skip("템플릿 파일 없음 — 통합 테스트 skip")

    # RESULTS_DIR은 orchestrator.py에서 import — SC-006의 'results/{project_id}_집행계획서.xlsx'와
    # 동일 경로여야 한다. orchestrator.py에서 RESULTS_DIR = Path("results") 또는 절대경로로
    # 정의하는지 확인 필요(SC-006 정렬 보장). import 경로가 달라 경로 불일치 시 테스트 실패.
    from services.orchestrator import run_pipeline_sync, RESULTS_DIR
    from models import SprintContract, ConfirmedFields, StepDef

    cf = ConfirmedFields(
        project_name="테스트사업",
        client="테스트발주처",
        contractor="GS네오텍",
        contract_type="일반",
        payment_terms="후불",
        pm="테스트PM",
        fiscal_year=2026,
    )
    contract = SprintContract(
        confirmed_fields=cf,
        revision=0,
        steps=[
            StepDef(id=1, sheet="공통", dependencies=[]),
        ],
    )

    state = run_pipeline_sync("smoke_test_001", contract)

    out_file = RESULTS_DIR / "smoke_test_001_집행계획서.xlsx"
    assert out_file.exists(), f"결과 파일 미생성: {out_file}"
    # 정리
    out_file.unlink(missing_ok=True)
```

### 최소 구현

`orchestrator.py:86-175` 현행 구현 사용. 테스트 파일만 생성.
CI 환경에서 실 템플릿 없을 경우 `pytest.skip` 처리.

### 통과 확인

```bash
pytest tests/test_pipeline_output.py -v -s
```
Expected: 실 템플릿 있으면 PASS, 없으면 SKIP.

### 커밋

```bash
git add tests/test_pipeline_output.py
git commit -m "test(EXE-12): 파이프라인 결과 파일 생성 smoke 테스트"
```

---

## Task T-07: `[NEEDS CLARIFICATION]` 해소 후 MAX_REVISION 초과 처리 구현

**수용기준**: SC-007 (현재 `[NEEDS CLARIFICATION]`) — revision > 11 시 EXE-12 수준에서의 처리 기준.

**현재 상태**: 미정. 사용자 직접 확정 후 진행.

### 대기 항목

- [ ] 사용자가 EXE-12 vs EXE-13 중 어느 계층에서 MAX_REVISION 초과를 최초 거부할지 사내 기준으로 직접 확정.
- [ ] 확정 후 본 task에 실패 테스트 추가.

### 후보 구현 방향 (확정 전 — 값 미창작 원칙으로 구현 미결정)

- 방향 A: `orchestrator.py`의 `run_pipeline` 진입 시 revision > MAX_REVISION이면 즉시 PipelineStatus.escalated 반환.
- 방향 B: EXE-13 `apply_revision_sheets` 내 validation으로 ValueError 발생.
- 방향 C: EXE-12 `load_template` 이전 단계에서 거부하고 HTTP 400 반환.

**확정 전 커밋 금지** — 이 task는 NEEDS CLARIFICATION 해소 후 착수.

---

## 완료 기준 체크리스트

- [ ] T-01: rev_col 0~11 전범위 단위 테스트 PASS
- [ ] T-02: resolve_template_path NFC/NFD 3케이스 PASS
- [ ] T-03: cell_type + write_cell 색상 규칙 4케이스 PASS
- [ ] T-04: inputs_used source 추적 + compliance 2케이스 PASS
- [ ] T-05: COMMON_MAPPING 기록 정확도 3케이스 PASS
- [ ] T-06: 결과 파일 생성 smoke PASS (또는 SKIP — 템플릿 없는 경우)
- [ ] T-07: NEEDS CLARIFICATION 해소 후 MAX_REVISION 초과 처리 테스트 PASS

전체 완료 후:

```bash
git add specs/EXE-12
git commit -m "feat(sdd): EXE-12 템플릿 생성 spec/plan/tasks"
```
