# Tasks: EXE-13 — 수정집행 (차수별 7시트)

**Created**: 2026-06-26  **Status**: Draft
**주의**: 이 tasks.md는 사람이 읽는 산출물이다. 자동 implement 비의존.

각 task는 **실패 테스트 작성 → 최소 구현 → 통과 → 커밋** 사이클을 따른다.

---

## Task 1: 1차 수정집행 — 기본 7시트 생성 (FR-001, FR-002, FR-003)

**수용 기준**:
- `apply_revision_sheets(template, out, [1])` 후 xlsx에 `"(1차)"` suffix 시트 **7개** 존재.
- `"(수정집행)"` 원본 7시트는 `state="hidden"`.

**실패 테스트 (작성)**:
```python
def test_revision_1_creates_7_sheets(tmp_path):
    from pathlib import Path
    import openpyxl
    from backend.services.excel.revision_sheets import apply_revision_sheets

    template = Path("backend/templates/템플릿.xlsx")  # 실제 경로
    out = tmp_path / "rev1.xlsx"
    apply_revision_sheets(template, out, [1])

    wb = openpyxl.load_workbook(str(out))
    names = [s for s in wb.sheetnames if "(1차)" in s]
    assert len(names) == 7, f"(1차) 시트 수={len(names)}, 기대=7"

    hidden_tmpl = [s for s in wb.sheetnames if "(수정집행)" in s]
    # 모든 (수정집행) 시트가 숨겨져 있는지 확인
    for name in hidden_tmpl:
        ws = wb[name]
        assert ws.sheet_state == "hidden", f"{name}이 visible"
```

**최소 구현**:
- `_REV_SHEET_TEMPLATE_NAMES` 상수가 7개임을 확인 (`revision_sheets.py:21-29`).
- `apply_revision_sheets`의 `new_sheets` 루프가 단일 revision에 대해 7 항목을 생성하는지 검증.
- workbook.xml에 새 `<sheet>` 요소가 7개 추가, `"(수정집행)"` 시트에 `state="hidden"` 설정.

**커밋**: `test(exe-13): 1차 7시트 생성 + (수정집행) 숨김 테스트`

---

## Task 2: 공통!E5 → 고정 숫자 교체 (FR-004a, FR-004b)

**수용 기준**:
- 생성된 (1차) 시트 XML 전체에서 `공통!E5` 텍스트가 **0건** (모두 `1`로 교체됨).
- `공통!E5-1` 패턴은 `0`으로, `공통!E5` 단독은 `1`로 교체.

**실패 테스트 (작성)**:
```python
def test_e5_replaced_in_rev1(tmp_path):
    import zipfile
    from backend.services.excel.revision_sheets import apply_revision_sheets

    template = ...
    out = tmp_path / "rev1.xlsx"
    apply_revision_sheets(template, out, [1])

    with zipfile.ZipFile(out) as z:
        for name in z.namelist():
            if "worksheet" in name:
                content = z.read(name).decode("utf-8", errors="replace")
                assert "공통!E5" not in content, f"{name}에 공통!E5 잔존"
```

**최소 구현**:
- `_replace_e5_in_formula` 정규식이 `공통!E5-1` 패턴을 `공통!E5` 단독보다 먼저 처리하는지 확인 (`revision_sheets.py:63-74`).
- `_patch_sheet_xml`이 `공통` + `E5` 포함 수식에만 `_replace_e5_in_formula` 적용하는지 확인 (`:124-126`).

**커밋**: `test(exe-13): 공통!E5 정수 교체 단위 테스트`

---

## Task 3: 원본 7시트 (0차) rename + 숨김, 내부 참조 교체 (FR-006, FR-007a, FR-007b)

**수용 기준**:
- 산출 xlsx에 `"0. 집행계획(갑지) (0차)"` 등 원본 7시트가 `state="hidden"`으로 존재.
- 원본 시트 XML 내 `_ORIGINAL_SHEET_NAMES` 참조가 `"(0차)"` suffix로 교체됨.

**실패 테스트 (작성)**:
```python
def test_original_sheets_renamed_hidden(tmp_path):
    import openpyxl
    from backend.services.excel.revision_sheets import apply_revision_sheets, _ORIGINAL_SHEET_NAMES

    out = tmp_path / "rev1.xlsx"
    apply_revision_sheets(template, out, [1])
    wb = openpyxl.load_workbook(str(out))

    for orig in _ORIGINAL_SHEET_NAMES:
        renamed = orig + " (0차)"
        assert renamed in wb.sheetnames, f"{renamed} 미존재"
        assert wb[renamed].sheet_state == "hidden", f"{renamed} visible"
```

**최소 구현**:
- `apply_revision_sheets` 내 workbook.xml 수정 부분 `:296-301`에서 `_ORIGINAL_SHEET_NAMES` 각 항목에 `" (0차)"` append + `state="hidden"` 설정.
- `_patch_sheet_refs_to_zero`의 lxml 수식 교체가 실제로 수식이 있는 원본 시트 XML에 적용되는지 검증 (`:83-108`).

**커밋**: `test(exe-13): 원본 시트 (0차) rename + 숨김 테스트`

---

## Task 4: N차 누적 체인 — 이전 차수 숨김, 최신만 visible (FR-009)

**수용 기준**:
- `apply_revision_sheets(template, out, [1, 2])` 시:
  - (1차) 7시트: `state="hidden"`
  - (2차) 7시트: visible (state 속성 없음)
- (2차) 시트 수식 내 `공통!E5-1`은 `1`, `공통!E5`는 `2`.

**실패 테스트 (작성)**:
```python
def test_chain_rev2_only_visible(tmp_path):
    import openpyxl
    from backend.services.excel.revision_sheets import apply_revision_sheets

    out = tmp_path / "rev12.xlsx"
    apply_revision_sheets(template, out, [1, 2])
    wb = openpyxl.load_workbook(str(out))
    names = wb.sheetnames

    rev1_sheets = [n for n in names if "(1차)" in n]
    rev2_sheets = [n for n in names if "(2차)" in n]
    assert len(rev1_sheets) == 7
    assert len(rev2_sheets) == 7
    for n in rev1_sheets:
        assert wb[n].sheet_state == "hidden"
    for n in rev2_sheets:
        assert wb[n].sheet_state == "visible"  # or != "hidden"
```

**최소 구현**:
- `is_visible = (revision == latest_revision)` 로직 확인 (`:243`).
- 이미 존재하는 이전 차수 시트(prev에 포함된 경우) 숨김 처리 `:309-317` 확인.
- (2차) E5 교체: `공통!E5-1` → `1`, `공통!E5` → `2` 검증.

**커밋**: `test(exe-13): 2차 누적 체인 — 이전 차수 숨김 테스트`

---

## Task 5: all_revisions=[] 시 단순 복사 (FR-001 경계)

**수용 기준**:
- `apply_revision_sheets(template, out, [])` 시 `out`이 `template`과 바이트 동일.

**실패 테스트 (작성)**:
```python
def test_empty_revisions_copies_template(tmp_path):
    from backend.services.excel.revision_sheets import apply_revision_sheets

    out = tmp_path / "copy.xlsx"
    apply_revision_sheets(template, out, [])
    assert out.read_bytes() == template.read_bytes()
```

**최소 구현**:
- `:169-171` `if not all_revisions: shutil.copy2(template_path, output_path); return` 확인.

**커밋**: `test(exe-13): 빈 차수 목록 → 단순 복사 테스트`

---

## Task 6: MAX_REVISION 초과 거부 게이트 구현 (FR-010) — 구현 갭

**수용 기준**:
- `revision=12`인 SprintContract로 `run_pipeline` 호출 시 `PipelineState.status == "escalated"` 또는 HTTP 422.
- 산출 xlsx 파일이 생성되지 않는다.

**배경**: 현행 `orchestrator.py`에 `revision > MAX_REVISION` 명시 거부 코드 없음(구현 갭). 이 task가 해당 게이트를 구현한다.

**실패 테스트 (작성)**:
```python
def test_max_revision_exceeded_rejected(tmp_path):
    import asyncio
    from backend.services.orchestrator import run_pipeline
    from backend.models.sprint_contract import SprintContract
    from backend.services.company_standards import MAX_REVISION

    contract = SprintContract(revision=MAX_REVISION + 1)
    state = asyncio.run(run_pipeline("test-proj", contract))
    assert state.status.value in ("escalated", "failed"), f"status={state.status}"
    assert state.output_file is None
```

**최소 구현**:
- `orchestrator.py run_pipeline` 상단에 `revision > MAX_REVISION` 체크 추가:
  ```python
  if revision > MAX_REVISION:
      state.status = PipelineStatus.escalated
      state.error = f"차수 상한 초과: revision={revision}, MAX_REVISION={MAX_REVISION}"
      return state
  ```
- `company_standards.py:12 MAX_REVISION = 11` import.

**커밋**: `feat(exe-13): MAX_REVISION 초과 거부 게이트 추가`

---

## Task 7: 공통 시트 E5 차수 기록 + rev_col 연결 (FR-013, FR-014)

**수용 기준**:
- `revision=1`로 파이프라인 실행 후 xlsx의 공통 시트 `E5` 값이 `1`.
- `rev_col(1)` == `"F"`, `rev_col(11)` == `"P"`.

**실패 테스트 (작성)**:
```python
def test_rev_col():
    from backend.services.excel.utils import rev_col
    assert rev_col(0) == "E"
    assert rev_col(1) == "F"
    assert rev_col(11) == "P"

def test_common_e5_written(tmp_path):
    import openpyxl
    # 파이프라인 통합 테스트 또는 CommonSheetWriter 단위 테스트
    # E5 셀에 revision 값이 기록됐는지 확인
    ...
```

**최소 구현**:
- `utils.py:6-8 rev_col` 함수 단위 테스트.
- `common_sheet.py:77-78` `self.ws["E5"].value = revision` 단위 테스트.

**커밋**: `test(exe-13): rev_col + E5 차수 기록 단위 테스트`

---

## Task 8: ZIP 메타 3파일 일관성 게이트 (FR-012)

**수용 기준**:
- N차 시트 추가 후 xlsx가 Excel/openpyxl에서 오류 없이 열린다.
- workbook.xml 시트 목록 수 = 기존 수 + (7 × len(all_revisions)).
- workbook.xml.rels에 추가된 rId 수 = 7 × len(all_revisions).
- Content_Types.xml Override 수 동일하게 추가.

**실패 테스트 (작성)**:
```python
def test_zip_meta_consistency(tmp_path):
    import zipfile
    from lxml import etree
    from backend.services.excel.revision_sheets import apply_revision_sheets

    out = tmp_path / "meta_check.xlsx"
    apply_revision_sheets(template, out, [1, 2])

    with zipfile.ZipFile(out) as z:
        wb_tree = etree.fromstring(z.read("xl/workbook.xml"))
        ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        sheets = wb_tree.find(f"{{{ns}}}sheets").findall(f"{{{ns}}}sheet")
        # 기존 시트 수는 템플릿에서 카운트 후 비교 (7×2=14 추가 기대)
        # 최소: 새 시트 이름이 등록되어 있고 rId가 rels에 존재
        ...
```

**최소 구현**:
- `apply_revision_sheets` 내 workbook.xml 시트 등록 (`:320-326`), rels 추가 (`:333-338`), ContentTypes 추가 (`:341-346`) 실행 후 openpyxl 로드 성공 자체가 주요 게이트.

**커밋**: `test(exe-13): ZIP 메타 3파일 일관성 테스트`

---

## Task 9: 6차 수정집행 체인 E2E (SC-006)

**수용 기준**:
- `test_revision_chain.py` 기준: rev 0~6 각 차수 파이프라인 완료, `"5-4. 수수료산출내역 (N차)"` H9/K9/X9 값이 검증 사례셋 기준값과 1% 미만 오차.
- 각 차수의 `"(N차)"` suffix 시트 7개 존재 + 이전 차수 보존 확인.

**실패 테스트 (작성)**:
- `.pipeline/tests/test_revision_chain.py` 기존 테스트를 신규 환경에서 실행.
- `PASS/FAIL` 출력 기준: `len(FAIL) == 0`.

**최소 구현**:
- Task 1~8 완료 후 체인 E2E 실행.
- 검증 사례셋(`golden_docs.json`)에서 `B2_6차수정` 체인 케이스 실행.
- 실패 시 H9(당초)/K9(변경)/X9(당기) wiring 디버깅.

**커밋**: `test(exe-13): 6차 수정집행 체인 E2E (검증 사례셋 검증)`

---

## 체크리스트

- [ ] Task 1: 1차 7시트 생성 + (수정집행) 숨김
- [ ] Task 2: 공통!E5 → 정수 교체
- [ ] Task 3: 원본 시트 (0차) rename + 숨김 + 내부 참조 교체
- [ ] Task 4: 누적 체인 이전 차수 숨김
- [ ] Task 5: 빈 차수 단순 복사
- [ ] Task 6: MAX_REVISION 초과 거부 게이트 (신규 구현)
- [ ] Task 7: rev_col + E5 단위 테스트
- [ ] Task 8: ZIP 메타 3파일 일관성
- [ ] Task 9: 6차 체인 E2E 검증 사례셋 검증
