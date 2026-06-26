# Implementation Plan: EXE-12 — 템플릿 생성

**Feature Branch**: `EXE-12-template-generation`
**Created**: 2026-06-26
**Status**: Draft
**작업 깊이**: 문서(spec/plan/tasks)까지 — 코드 구현 비대상(constitution §VII)

---

## 아키텍처 개요

EXE-12는 집행계획서 생성 파이프라인의 **파일 계층(xlsx 생성)**을 담당한다.
SprintContract(EXE-06 산출)를 받아, 템플릿 xlsx를 로드하고 각 SheetWriter가 시트별로 셀을 기록한다.

```
SprintContract (EXE-06 산출)
    │
    ▼
orchestrator.run_pipeline
    │
    ├─ [revision=0] load_template() → openpyxl.Workbook
    │
    ├─ [revision>=1] apply_revision_sheets() → openpyxl.Workbook   ← EXE-13 담당
    │
    ▼
SHEET_WRITERS 별 SheetWriter.execute(step_id)
    │
    ├─ CommonSheetWriter → 공통 시트 (차수 열 col=rev_col(revision))
    ├─ FeeSheetWriter → 5-4. 수수료산출내역                          ← EXE-07
    ├─ BreakdownSheetWriter → 5.집행예산산출내역서                    ← EXE-08
    ├─ CoverSheetWriter → 0. 집행계획(갑지)                          ← EXE-10
    ├─ StaffSheetWriter → 인원투입계획
    ├─ OrgSheetWriter → 1. 현장조직_업무분장
    └─ ScheduleSheetWriter → 3. 예정공정표
    │
    ▼
wb.save → results/{project_id}_집행계획서.xlsx + S3 업로드
```

**EXE-12 경계**: 템플릿 로드 → 셀 색상 기반 기록 규칙 → 입력 추적 → 결과 파일 저장.
수정집행 시트 ZIP 패칭(apply_revision_sheets)은 EXE-13에 위임.

---

## 기술 스택

| 계층 | 구현 |
|------|------|
| xlsx 조작 | `openpyxl` (load_workbook, Workbook, Worksheet, Cell) |
| 파일시스템 | `pathlib.Path`, `tempfile`, `unicodedata` (NFC/NFD 정규화) |
| 비동기 파이프라인 | `asyncio` (orchestrator — EXE-12는 내부 동기 로직) |
| 스토리지 | 로컬 `results/` + S3 선택적 업로드 (`s3_storage.py`) |
| 모델 | `SprintContract`, `StepResult`, `StepStatus`, `InputUsed` (`models.py`) |

---

## FR ↔ 실제 컴포넌트 매핑

| FR | 동작 | 파일:라인 |
|----|------|----------|
| FR-001a | `load_template()` — revision=0 경로에서 파일 로드 | `orchestrator.py:114`, `base.py:58-59` |
| FR-001b | `load_template()` 완료 후 openpyxl Workbook 객체 생성·전달 | `base.py:58-59` |
| FR-002a | `resolve_template_path` — NFC 직접 경로 조회 | `excel_writer.py:11-14` |
| FR-002b | NFC 직접 경로 실패 시 디렉토리 스캔·반환 | `excel_writer.py:15-25` |
| FR-003a | `rev_col(revision)` — revision 정수 → 열 문자 변환 | `excel/utils.py:6-8` |
| FR-003b | `rev_col` 반환 열에 차수 데이터 기록 | `common_sheet.py:75` |
| FR-004 | `write_cell` — skip_cell(파란색) 기록 건너뜀 | `base.py:84-86` |
| FR-005 | `write_cell` — formula_cell 기록 건너뜀 | `base.py:87-88` |
| FR-006 | `write_cell` — `inputs_used` 추적 항목 추가 | `base.py:90-97` |
| FR-007a | `generate_excel` 완료 시 임시 디렉토리에 파일 저장 | `excel_writer.py:61-63` |
| FR-007b | 파일 저장 완료 후 경로 반환 | `excel_writer.py:64` |
| FR-008 | `_fill_common_sheet` — COMMON_MAPPING 행→E열 기록 | `excel_writer.py:86-95` |
| FR-009 | dict 형태 값(`{"value": ...}`) 내부 추출 | `excel_writer.py:92-94` |
| FR-010 | `SheetWriter.execute` 완료 시 StepResult 반환(status·inputs·compliance) | `base.py:99-111` |
| FR-011 | `SheetWriter.execute` — 예외 시 StepStatus.failed + notes | `base.py:113-118` |
| FR-012a | `SheetWriter.ws` — revision>=1 시 "(N차)" 시트명 조회 | `base.py:74-78` |
| FR-012b | "(N차)" 시트 없으면 원본 시트명으로 폴백 | `base.py:79-80` |

---

## 핵심 로직 상세

### 템플릿 경로 해석 (`resolve_template_path`)

```
1. templates_dir / "템플릿.xlsx" 직접 존재 확인
2. 없으면 os.listdir(templates_dir) 스캔
3. 각 항목을 unicodedata.normalize("NFC", name)으로 정규화
4. NFC 일치 항목 반환 (없으면 직접 경로 반환 — 호출부에서 FileNotFoundError)
```

근거: `excel_writer.py:11-25`

### 차수 열 변환 (`rev_col`)

```python
def rev_col(revision: int) -> str:
    return chr(ord("E") + revision)
# revision 0 → 'E', 1 → 'F', ..., 11 → 'P'
```

근거: `excel/utils.py:6-8`

### 셀 색상 기반 기록 규칙 (`cell_type`, `write_cell`)

- `_get_rgb(cell)` → RGB 문자열 추출 (예외·투명·흰색 제외)
- `INPUT_COLORS = {"FFFFFFCC"}` → input_cell (기록 대상)
- `SKIP_COLORS = {"FF0070C0"}` → skip_cell (기록 금지)
- `data_type == 'f'` → formula_cell (기록 금지)
- 그 외 → label_cell (기록 금지)

근거: `base.py:35-55`, `base.py:82-97`

### 수정집행 시트 조회 (`SheetWriter.ws`)

revision >= 1이면 `"{sheet_name} ({revision}차)"` 시트명으로 조회.
해당 시트가 없으면 원본 sheet_name으로 폴백.

근거: `base.py:74-80`

### HLOOKUP 범위

공통 시트 `$E$8:$P$149` — E열(0차)~P열(11차), MAX_REVISION=11.
시스템이 직접 수식을 삽입하지 않고, 양식 내장 수식이 이 범위를 참조함.

근거: 메모리 `project_template_2026-06.md`(HLOOKUP 범위 $E$8:$P$149 — 잠정, Assumption 1 참조). `company_standards.py:12`는 MAX_REVISION=11 상수만 정의하며 HLOOKUP 행 범위(8~149)의 직접 근거가 아님.

---

## 의존 관계

### 소비 (Consumes)

| 기능 | 역할 | 인터페이스 |
|------|------|-----------|
| EXE-06 (Sprint_Contract 생성) | SprintContract 공급 | `contract_builder.py:297 build_sprint_contract` |

### 생산 (Produces)

| 기능 | 역할 | 인터페이스 |
|------|------|-----------|
| EXE-07 (수수료산출내역) | FeeSheetWriter가 EXE-12 SheetWriter 베이스 상속 | `base.py:SheetWriter` |
| EXE-08 (집행예산 산출내역서) | BreakdownSheetWriter가 EXE-12 SheetWriter 베이스 상속 | `base.py:SheetWriter` |
| EXE-09 (노무비 상세) | 노무비 BudgetItem → BreakdownSheetWriter 경유 (EXE-08) | — |
| EXE-10 (갑지 집계) | CoverSheetWriter가 EXE-12 SheetWriter 베이스 상속 | `base.py:SheetWriter` |
| EXE-13 (수정집행 차수별 7시트) | apply_revision_sheets 전처리 결과 워크북을 EXE-12가 수신 | `revision_sheets.py:apply_revision_sheets` |
| EXE-15 (Reviewer 결정론) | `inputs_used` 기록을 Reviewer가 검증에 활용 | `StepResult.inputs_used` |

### EXE-13과의 경계

EXE-13은 revision >= 1 시 템플릿 ZIP을 패칭하여 `(N차)` 시트를 생성한다.
EXE-12는 패칭 완료 후 워크북에서 `SheetWriter.ws`를 통해 시트를 조회하고 값을 기록한다.
두 기능은 `orchestrator.py:104-115`에서 순차 실행: apply_revision_sheets → wb 로드 → SheetWriter.

---

## 파일 목록 (코드 근거 파일)

| 파일 | 역할 |
|------|------|
| `backend/services/excel_writer.py` | `generate_excel`, `resolve_template_path`, `COMMON_MAPPING`, `_fill_common_sheet` |
| `backend/services/excel/base.py` | `SheetWriter`, `load_template`, `TEMPLATE_PATH`, `cell_type`, `write_cell`, `CellType` |
| `backend/services/excel/utils.py` | `rev_col` |
| `backend/services/orchestrator.py` | `run_pipeline`, `SHEET_WRITERS`, `compute_dependency_levels`, `_execute_step` |
| `backend/services/company_standards.py` | `MAX_REVISION = 11` |
| `backend/services/excel/common_sheet.py` | `CommonSheetWriter._write`, `_calc_period_ratios`, `_rev_col` 사용 |

---

## 미해결 항목

- **MAX_REVISION 초과 처리 계층**: EXE-12(로드 단계)가 거부해야 하는지 EXE-13(패칭 단계)이 거부해야 하는지 미정. `[NEEDS CLARIFICATION]` (spec.md SC-007 참조).
