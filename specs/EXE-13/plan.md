# Implementation Plan: EXE-13 — 수정집행 (차수별 7시트)

**Feature Branch**: `EXE-13-revision-sheets`  **Created**: 2026-06-26  **Status**: Draft

---

## 아키텍처 · 스택

| 계층 | 구성요소 | 역할 |
|------|----------|------|
| 오케스트레이터 | `backend/services/orchestrator.py` | `revision >= 1` 분기, `apply_revision_sheets` 호출 |
| 수정집행 라이터 | `backend/services/excel/revision_sheets.py` | xlsx ZIP 직접 조작 (lxml + zipfile) |
| 공통 시트 라이터 | `backend/services/excel/common_sheet.py` | E5 차수 기록, 차수 열 결정 |
| 유틸리티 | `backend/services/excel/utils.py` | `rev_col(revision)` |
| 모델 | `backend/models/sprint_contract.py` | `SprintContract.revision`, `SprintContract.prev_revisions` |
| 상수 | `backend/services/company_standards.py` | `MAX_REVISION = 11` |
| 테스트 | `.pipeline/tests/test_revision_chain.py` | 6차 체인 E2E |

**처리 방식**: openpyxl로는 시트 복사·이름 변경이 불완전하므로, xlsx를 ZIP 파일로 직접 열어 lxml로 XML 조작. 워크북 메타(workbook.xml, workbook.xml.rels, Content_Types.xml)를 원자적으로 수정.

---

## FR ↔ 컴포넌트 매핑

| FR | 구현 위치 | 코드 (file:line) |
|----|-----------|-----------------|
| FR-001 revision>=1 분기 | `orchestrator.py` | `:97-113` — revision/prev_revisions에서 `all_revisions` 구성 후 `apply_revision_sheets` 호출 |
| FR-002 7시트 목록 상수 | `revision_sheets.py` | `:21-29 _REV_SHEET_TEMPLATE_NAMES` |
| FR-003 시트명 치환 (N차) | `revision_sheets.py` | `:51-53 _revision_sheet_name` |
| FR-004a 공통!E5-1 → (N-1) 교체 | `revision_sheets.py` | `:56-74 _replace_e5_in_formula` |
| FR-004b 공통!E5 단독 → N 교체 | `revision_sheets.py` | `:56-74 _replace_e5_in_formula` |
| FR-005 (수정집행) 참조 → (N차) | `revision_sheets.py` | `:128-133 _patch_sheet_xml` |
| FR-006 원본 참조 → (0차) | `revision_sheets.py` | `:77-109 _patch_sheet_refs_to_zero` |
| FR-007a 원본 시트 (0차) rename | `revision_sheets.py` | `:296-301` |
| FR-007b 원본 시트 state=hidden 설정 | `revision_sheets.py` | `:296-301` |
| FR-008 (수정집행) 시트 state=hidden 설정 | `revision_sheets.py` | `:303-307` |
| FR-009 이전 차수 시트 state=hidden 설정 | `revision_sheets.py` | `:243 is_visible`, `:309-317` |
| FR-010 MAX_REVISION 초과 거부 | `company_standards.py` + `orchestrator.py` | `:12 MAX_REVISION=11` — **게이트 코드 미구현**, 구현 갭 |
| FR-011 revision==0 시 원본 템플릿 사용 | `orchestrator.py` | `:113-114 load_template()` |
| FR-012 ZIP 메타 3파일 갱신 | `revision_sheets.py` | `:329-348` |
| FR-013 E5 차수 기록 | `common_sheet.py` | `:77-78` |
| FR-014 rev_col 차수→열 변환 | `utils.py` | `:6-8` |

---

## 데이터 흐름

```
POST /api/pipeline/start
  ↓
orchestrator.run_pipeline(project_id, contract)
  ↓ (revision >= 1)
apply_revision_sheets(TEMPLATE_PATH, tmp_xlsx, all_revisions)
  ├─ zipfile.ZipFile(template_path, 'r') 읽기
  ├─ 각 revision × 7시트: _patch_sheet_xml(xml, revision) → 새 sheetN.xml
  ├─ 원본 시트: _patch_sheet_refs_to_zero(xml) → (0차) 참조 교체
  ├─ workbook.xml: 원본 rename + 숨김, (수정집행) 숨김, 새 시트 등록
  ├─ workbook.xml.rels: 새 rId 추가
  └─ [Content_Types].xml: 새 PartName 추가
  ↓
openpyxl.load_workbook(tmp_xlsx)  ← 수정집행 시트가 포함된 wb
  ↓
CommonSheetWriter.execute()       ← E5 = revision, col = rev_col(revision)
  ↓
FeeSheetWriter / BreakdownSheetWriter / ...  ← 차수 열에 값 기록
  ↓
wb.save(output_path)
```

---

## 의존 관계

| 소비/제공 방향 | 기능 | 비고 |
|---------------|------|------|
| **EXE-13이 소비** | EXE-12 (템플릿 생성) | `TEMPLATE_PATH` 가 존재해야 함 |
| **EXE-13이 소비** | EXE-06 (SprintContract 생성) | `contract.revision`, `contract.prev_revisions` 제공 |
| **EXE-07이 소비** | EXE-13 출력 | (N차) 시트가 생성된 wb에서 `"5-4. 수수료산출내역 (N차)"` 탭에 기록 |
| **EXE-08이 소비** | EXE-13 출력 | (N차) 시트의 `"5.집행예산산출내역서 (N차)"` 등에 기록 |
| **EXE-10이 소비** | EXE-13 출력 | (N차) 갑지 시트(`"0. 집행계획(갑지) (N차)"`)에 수식 기록 |

**EXE-13은 수정집행 시트 레이어를 담당하며 EXE-07/08/10과 물리적 시트를 공유한다.**
EXE-07/08/10은 차수가 0이면 원본 탭, 1 이상이면 `"(N차)"` suffix 탭에 기록해야 하므로,
시트 존재 보장은 EXE-13이, 값 기록은 각 라이터가 담당한다.

---

## 구현 갭 (현행 코드 기준)

| 갭 | 설명 | FR |
|----|------|----|
| MAX_REVISION 게이트 미구현 | `orchestrator.py`에 `revision > 11` 명시 거부 없음 | FR-010 |
| 임시 파일 정리 보장 | `tmp_xlsx.unlink()`가 `finally`로 처리되나 오류 시 wb 로드 전 삭제 → openpyxl 로드 실패 가능 (`orchestrator.py:106-112` try/finally 순서) | 운영 안정성 |

---

## 기술 제약

- **lxml 필수**: `revision_sheets.py`는 `from lxml import etree` 사용. 컨테이너 이미지에 lxml 포함 필수.
- **한글 시트명 NFC/NFD**: `test_revision_chain.py:23 nfc(s)` — openpyxl이 반환하는 시트명이 NFD일 수 있으므로 비교 시 NFC 정규화.
- **ZIP 직접 조작**: openpyxl의 시트 복사 API 한계로 ZIP 레벨 조작. `xl/worksheets/sheetN.xml` 번호는 기존 최대값+1부터 순차 할당.
