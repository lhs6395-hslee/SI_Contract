# Feature Specification: EXE-12 — 템플릿 생성

**Feature Branch**: `EXE-12-template-generation`
**Created**: 2026-06-26
**Status**: Draft
**Input**: 집행계획서 엑셀 산출 시, 템플릿 xlsx를 로드하고 차수(0~11차) 열에 값을 기록하여 완성 파일을 생성한다.

**코드 근거 출처**:
- `backend/services/excel_writer.py` — `generate_excel`, `resolve_template_path`, `COMMON_MAPPING`
- `backend/services/excel/base.py` — `SheetWriter`, `load_template`, `write_cell`, `cell_type`
- `backend/services/excel/utils.py` — `rev_col`
- `backend/services/company_standards.py:12` — `MAX_REVISION = 11`
- `backend/services/orchestrator.py:86-115` — 파이프라인 진입점·워크북 생성 흐름
- `backend/services/excel/revision_sheets.py` — 수정집행 시트 ZIP 패칭 (EXE-13 전용 — EXE-12 경계 명기)

---

## User Scenarios & Testing

### User Story 1 — 0차 집행계획서 엑셀 생성 (Priority: P1)

운영자가 추출·확정된 계약 데이터를 기반으로 0차 집행계획서 엑셀 파일을 생성하고자 한다.
시스템은 `templates/템플릿.xlsx`를 로드하여, 공통 시트 E열(0차 열)을 포함한 각 시트에 값을 기록하고 완성 파일을 반환한다.

- **Independent Test**: SprintContract(revision=0) + ConfirmedFields 픽스처 → `orchestrator.run_pipeline_sync` 실행 → 결과 xlsx에서 공통 시트 E열 셀 값 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** `templates/템플릿.xlsx` 파일이 존재하고, revision=0인 SprintContract가 준비된 상태에서,
     **When** 파이프라인이 실행되면,
     **Then** 시스템은 템플릿을 로드하고 공통 시트 E5에 0을 기록하며, `results/` 폴더에 완성 xlsx 파일을 생성한다.

### User Story 2 — 한글 파일명 NFC/NFD 정규화 안전 해석 (Priority: P1)

macOS에서 docker 이미지 빌드 시 한글 파일명이 NFD 인코딩으로 저장되어, Linux 컨테이너에서 NFC 경로 조회가 실패할 수 있다. 시스템은 디렉토리 스캔을 통해 정규화 차이를 극복하고 템플릿을 찾아야 한다.

- **Independent Test**: 동일 templates_dir 내에 NFD 인코딩 파일명으로 `템플릿.xlsx`를 배치 → `resolve_template_path` 호출 → 파일 경로 반환 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** `templates/` 디렉토리에 NFD 인코딩 파일명 `템플릿.xlsx`가 있고 NFC 직접 경로(`templates/템플릿.xlsx`)가 존재하지 않는 상태에서,
     **When** `resolve_template_path`가 호출되면,
     **Then** 시스템은 디렉토리를 스캔하여 NFC 정규화로 일치하는 파일 경로를 반환한다.

### User Story 3 — 셀 색상 규칙에 따른 기록 선택 (Priority: P1)

집행계획서 엑셀 양식은 노란색(FFFFFFCC) 셀만 사용자/AI 입력 대상이며, 파란색(FF0070C0) 셀은 고정값(차수 등), 수식·라벨 셀은 기록하지 않는다. 시스템은 이 색상 규칙에 따라 값 기록 여부를 결정한다.

- **Independent Test**: 노란·파란·수식·라벨 셀이 포함된 테스트 워크시트 픽스처 생성 → `cell_type` + `write_cell` 실행 → 각 셀의 값 변경 여부 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** 파란색(FF0070C0) 셀과 수식 셀이 포함된 워크시트에서,
     **When** `write_cell`이 해당 셀에 값 기록을 시도하면,
     **Then** 시스템은 해당 셀의 값을 변경하지 않고 `inputs_used` 로그에도 기록하지 않는다.

### User Story 4 — 차수 열 결정 (Priority: P1)

차수(revision)에 따라 값이 기록될 열이 결정된다: 0차=E열, 1차=F열, ..., 11차=P열.

- **Independent Test**: revision 0..11 각각에 대해 `rev_col(revision)` 반환값 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** SprintContract의 revision이 0인 상태에서,
     **When** 공통 시트 라이터가 차수 열을 결정하면,
     **Then** 시스템은 E열(`rev_col(0) == 'E'`)을 차수 기준 열로 사용한다.
  2. **Given** revision이 11인 상태에서,
     **When** 공통 시트 라이터가 차수 열을 결정하면,
     **Then** 시스템은 P열(`rev_col(11) == 'P'`)을 차수 기준 열로 사용한다.

### User Story 5 — 입력 추적 및 소스 명시 (Priority: P1)

각 셀 기록 시 해당 값의 출처(source)를 `inputs_used`에 보존하여 검증 가능성을 확보한다.

- **Independent Test**: `write_cell` 실행 후 `inputs_used` 목록에서 `source` 필드가 비어있지 않은지 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** SheetWriter가 노란색 입력 셀에 값을 기록할 때,
     **When** `write_cell`이 실행되면,
     **Then** 시스템은 `inputs_used` 목록에 `field`, `value`, `cell`, `source` 필드를 포함한 항목을 추가한다.

### Edge Cases

- 템플릿 파일이 존재하지 않으면 → `FileNotFoundError` 발생 (호출부에서 처리).
  - `excel_writer.py:47-48` 참조
- `templates_dir`가 디렉토리가 아니면 → `resolve_template_path`는 직접 경로를 반환하고 호출부에서 FileNotFoundError 처리.
- revision > 11이면 → `[NEEDS CLARIFICATION]` (MAX_REVISION=11 초과 처리 — EXE-13과 공유, 아래 명기)
- `data.get(key)` 결과가 `dict` 형태(예: `{"value": 금액}`)이면 → `.get("value")`로 내부값 추출 (`excel_writer.py:92-94`)

---

## Functional Requirements (EARS)

- **FR-001a** (complex): WHILE revision=0인 SprintContract가 처리 대상인 상태에서, WHEN `run_pipeline`이 SprintContract를 수신하면, THE SYSTEM SHALL `load_template()`으로 `templates/템플릿.xlsx`를 로드한다.
  - 근거: `orchestrator.py:114` `wb = load_template()`, `base.py:58-59`
  - 범위 주의: `orchestrator.py:114`의 `load_template()` 호출은 revision=0 경로에서만 실행된다. revision >= 1 경로의 템플릿 로드(`apply_revision_sheets` 이후 `openpyxl.load_workbook`)는 EXE-13 담당이며 EXE-12 비목표(non-goal)로 명시적 제외.

- **FR-001b** (complex): WHILE revision=0인 SprintContract가 처리 대상인 상태에서, WHEN `load_template()`이 파일 로드를 완료하면, THE SYSTEM SHALL openpyxl Workbook 객체를 생성하여 파이프라인에 전달한다.
  - 근거: `base.py:58-59`, `orchestrator.py:114`

- **FR-002a** (event): WHEN `resolve_template_path`가 호출되면, THE SYSTEM SHALL NFC 직접 경로(`templates_dir / "템플릿.xlsx"`)의 존재 여부를 조회한다.
  - 근거: `excel_writer.py:11-14`

- **FR-002b** (unwanted): IF `resolve_template_path`의 NFC 직접 경로 조회가 실패하면, THEN THE SYSTEM SHALL `templates_dir`를 스캔하여 NFC 정규화 일치 파일 경로를 반환한다.
  - 근거: `excel_writer.py:15-25`

- **FR-003a** (ubiquitous): THE SYSTEM SHALL `rev_col(revision)`을 사용하여 revision 정수를 `chr(ord('E') + revision)` 공식으로 열 문자로 변환한다.
  - 근거: `excel/utils.py:6-8` (`rev_col`)

- **FR-003b** (ubiquitous): THE SYSTEM SHALL `rev_col(revision)`이 반환한 열 문자에 해당하는 열에 차수 데이터를 기록한다.
  - 근거: `excel/common_sheet.py:75`

- **FR-004** (unwanted): IF `cell_type(cell)`이 `CellType.skip_cell`(파란색 FF0070C0)이면, THEN THE SYSTEM SHALL `write_cell`에서 해당 셀에 값을 기록하지 않는다.
  - 근거: `base.py:84-86`

- **FR-005** (unwanted): IF `cell_type(cell)`이 `CellType.formula_cell`(data_type='f')이면, THEN THE SYSTEM SHALL `write_cell`에서 해당 셀에 값을 기록하지 않는다.
  - 근거: `base.py:87-88`

- **FR-006** (event): WHEN `write_cell`이 노란색(FFFFFFCC) 셀에 값을 기록하면, THE SYSTEM SHALL `inputs_used` 목록에 `field`, `value`, `cell`, `source`, `calc_basis`를 포함한 `InputUsed` 항목을 추가한다.
  - 근거: `base.py:90-97`

- **FR-007a** (event): WHEN `generate_excel`이 완료되면, THE SYSTEM SHALL 임시 디렉토리에 `집행계획서.xlsx` 파일을 저장한다.
  - 근거: `excel_writer.py:61-63`

- **FR-007b** (event): WHEN `generate_excel`이 파일 저장을 완료하면, THE SYSTEM SHALL 저장된 파일의 경로를 반환한다.
  - 근거: `excel_writer.py:64`

- **FR-008** (ubiquitous): THE SYSTEM SHALL 공통 시트 `COMMON_MAPPING`에 정의된 행-키 쌍에 따라 E열(column=5) 셀에 data 딕셔너리에서 조회한 값을 기록한다.
  - 근거: `excel_writer.py:70-95`, `COMMON_MAPPING` 정의

- **FR-009** (event): WHEN `data` 딕셔너리의 값이 `dict` 형태(`{"value": ...}`)이면, THE SYSTEM SHALL `.get("value")`로 내부값을 추출하여 셀에 기록한다.
  - 근거: `excel_writer.py:92-94`

- **FR-010** (event): WHEN `SheetWriter.execute`가 완료되면, THE SYSTEM SHALL `StepResult`에 `status`, `inputs_used`, `constraint_compliance`("소스_근거_명시": all inputs have source)를 포함하여 반환한다.
  - 근거: `base.py:99-118`

- **FR-011** (unwanted): IF `SheetWriter._write`에서 예외가 발생하면, THEN THE SYSTEM SHALL `StepResult`의 `status`를 `StepStatus.failed`로 설정하고 `notes`에 예외 메시지를 기록한다.
  - 근거: `base.py:113-118`

- **FR-012a** (optional): WHERE `revision >= 1`인 수정집행 상황에서, THE SYSTEM SHALL `ws` 프로퍼티를 통해 `"{sheet_name} ({revision}차)"` 이름의 시트를 조회한다.
  - 근거: `base.py:74-78`
  - 주의: 수정집행 시트 XML 패칭 자체는 EXE-13(revision_sheets.py) 담당 — EXE-12는 이미 생성된 워크북에서 시트 조회·기록만 수행.

- **FR-012b** (unwanted): IF `"{sheet_name} ({revision}차)"` 이름의 시트가 존재하지 않으면, THEN THE SYSTEM SHALL 원본 `sheet_name`으로 폴백하여 시트를 반환한다.
  - 근거: `base.py:79-80`

---

## Success Criteria (측정형)

- **SC-001**: `generate_excel`이 유효한 data 딕셔너리를 수신한 경우, 공통 시트 `COMMON_MAPPING` 키 중 data에 존재하는 모든 항목이 E열 해당 행에 기록되어야 한다. 기록 누락률 0%.
  - 출처: `excel_writer.py:87-95`

- **SC-002**: `rev_col(revision)`의 반환값은 `revision` 0~11에 대해 각각 `'E'`~`'P'`(아스키 코드 연속 12자)와 정확히 일치해야 한다. 오차 0건.
  - 출처: `excel/utils.py:6-8`

- **SC-003**: `resolve_template_path`가 NFD 인코딩 파일명으로 저장된 `템플릿.xlsx`를 포함한 디렉토리에서 호출될 때, 1회 디렉토리 스캔으로 경로를 반환해야 한다(추가 예외 발생 0건).
  - 출처: `excel_writer.py:17-25`

- **SC-004**: `write_cell`이 `skip_cell` 또는 `formula_cell`에 호출될 때, 셀 값 변경 0건, `inputs_used` 추가 0건.
  - 출처: `base.py:84-88`

- **SC-005**: `SheetWriter.execute`의 `constraint_compliance["소스_근거_명시"]`가 `True`인 경우, `inputs_used` 내 모든 항목의 `source` 필드가 비어있지 않아야 한다(비어있는 항목 0건).
  - 출처: `base.py:107-108`

- **SC-006**: 파이프라인 성공 종료 시, `results/{project_id}_집행계획서.xlsx` 파일이 생성되어야 한다.
  - 출처: `orchestrator.py:153-169`

- **SC-007**: MAX_REVISION 초과 처리 시 동작 — `[NEEDS CLARIFICATION]`: revision > 11일 때 EXE-12 템플릿 로드 단계에서 어떤 오류를 반환해야 하는지 미정. EXE-13에서 ValueError를 발생시키지만 EXE-12 자체에서의 처리 기준이 명시되지 않음. 확인 필요.
  - 충돌 출처: `company_standards.py:12` MAX_REVISION=11, `orchestrator.py` revision 분기(EXE-13 담당) — EXE-12 수준 거부 기준 미명시

---

## Key Entities

| 엔티티 | 정의 | 출처 |
|--------|------|------|
| `TEMPLATE_PATH` | `templates/템플릿.xlsx` 절대 경로. `resolve_template_path`로 NFC/NFD 안전 해석 | `excel_writer.py:29`, `base.py:22` |
| `COMMON_MAPPING` | 공통 시트 행번호 → data 키 매핑 dict (9~136행) | `excel_writer.py:70-83` |
| `CellType` | input_cell / formula_cell / label_cell / skip_cell | `base.py:28-31` |
| `INPUT_COLORS` | 노란색 `{"FFFFFFCC"}` — 기록 대상 | `base.py:24` |
| `SKIP_COLORS` | 파란색 `{"FF0070C0"}` — 기록 금지(고정값) | `base.py:25` |
| `SheetWriter` | 시트별 Executor 스텝 베이스 클래스. `wb`, `contract`, `inputs_used` 보유 | `base.py:62-121` |
| `rev_col(revision)` | 차수 정수 → 열 문자. `chr(ord('E') + revision)` | `excel/utils.py:6-8` |
| `MAX_REVISION` | 수정집행 최대 차수 = 11 (E~P열 12개, 0차 포함) | `company_standards.py:12` |
| `HLOOKUP $E$8:$P$149` | 공통 시트 차수 조회 HLOOKUP 범위 (E~P = 0~11차) | 메모리 `project_template_2026-06.md` |
| `InputUsed` | 셀 기록 추적: `field`, `value`, `cell`, `source`, `calc_basis` | `base.py:91-97` |
| `StepResult` | 시트 실행 결과: `step_id`, `sheet`, `status`, `inputs_used`, `constraint_compliance`, `notes` | `base.py:99-118` |

---

## Assumptions

(코드 현행값 = 잠정 — 권위 확정은 운영팀 인터뷰 후)

1. **HLOOKUP 범위**: 공통 시트 `$E$8:$P$149` — E열(0차)~P열(11차), 행 8~149. 메모리 `project_template_2026-06.md` 기술. 코드에서 직접 기록하지 않으며 양식 내장 수식으로 동작(잠정).
2. **차수 열 범위**: 0차=E열, 1차=F열, ..., 11차=P열(총 12열). `rev_col` 구현으로 확정 (`utils.py:6-8`).
3. **MAX_REVISION = 11**: `company_standards.py:12` 코드 확정값. 이 범위를 초과하는 차수는 양식 구조 한계.
4. **템플릿 단일 파일**: `templates/템플릿.xlsx` 단일 파일에 0차 16시트 + (수정집행) 7시트(hidden) 내장. 메모리 `project_template_2026-06.md` 기술(잠정).
5. **`generate_excel` vs `run_pipeline` 역할 분리**: `generate_excel`(`excel_writer.py`)은 공통 시트 E열 단순 기록 경로(레거시/단순 호출). `run_pipeline`(`orchestrator.py`)은 SheetWriter 기반 전체 파이프라인 실행 경로. 두 경로가 공존하며, 실제 운영은 `run_pipeline` 기준임을 코드에서 확인(잠정).
6. **수정집행 시트 패칭 분리**: revision >= 1 시 `apply_revision_sheets`(ZIP 패칭)는 EXE-13 담당. EXE-12는 패칭 완료 후 워크북에서 시트 조회·기록만 담당.
7. **결과 파일 저장**: `results/{project_id}_집행계획서.xlsx` 로컬 저장 + S3 업로드(S3 활성 시). S3 업로드 실패는 비치명적(경고만). `orchestrator.py:153-168` 기준.

---

## Clarifications Retained

- **[NEEDS CLARIFICATION] SC-007**: revision > 11(MAX_REVISION 초과) 시 EXE-12 템플릿 생성 단계에서의 거부/에러 처리 기준.
  - 충돌 출처 1: `company_standards.py:12` — MAX_REVISION=11 상수 정의만, EXE-12 수준 처리 미명시.
  - 충돌 출처 2: `orchestrator.py:104-113` — revision 분기는 EXE-13(apply_revision_sheets)에 위임. EXE-12 거부 시점 불명.
  - 확인 필요: EXE-12(템플릿 로드·기록)와 EXE-13(차수 시트 패칭) 중 어느 단계에서 MAX_REVISION 초과를 최초 거부해야 하는지 운영팀 확정 필요.
