# Implementation Plan: EXE-10 — 갑지(0) 집계 (수식 레이어·종속)

**Feature Branch**: `EXE-10-cover-sheet-formula-layer`
**Created**: 2026-06-26
**Status**: Draft

---

## 1. 아키텍처 개요

### 1-1. 성격·위치

EXE-10은 **수식 표현 레이어**다. 독립 비즈니스 데이터를 생성하지 않으며, EXE-08(집행예산 산출내역서·집계표)이 공통 시트에 기록한 비목별 금액을 갑지 수식 체인이 참조·집계한다. 코드 구현은 이미 존재하며, 이 plan은 구현 경계와 FR-컴포넌트 매핑을 정형화한다.

```
[SprintContract]
    │
    ├─[CommonSheetWriter]──────→ 공통 시트 F4(매출액), P4(영업이익)
    │   excel/common_sheet.py   col+6(년도), col+9~12(일자/PM)
    │                           col+13~16(기간비율), col+17~22(요율)
    │                           col+135~144(수식: 집계표 참조) [rev>=1]
    │                           col+148~149(영업이익 수식) [rev>=1]
    │
    ├─[CoverSheetWriter]───────→ 공통 시트 col+125(시작일), col+126(종료일)
    │   excel/cover_sheet.py    col+129(사업범위), col+134(특기사항)
    │                           이전 차수 prev_revisions 동일 행 기록
    │
    └─[_verify_cover_sheet()]──→ 검증: F4/P4/E3/기간/역산 오류 목록
        reviewer.py:408
```

### 1-2. 스택

| 계층 | 기술 | 역할 |
|------|------|------|
| Python 백엔드 | FastAPI + Python 3.x | 파이프라인 실행 |
| 시트 기록 | openpyxl (`SheetWriter` 베이스) | 셀 값·수식 기록 |
| 수식 체인 | 엑셀 수식 (템플릿 내장 + 동적 삽입) | 갑지 집계 표현 |
| 검증 | `reviewer.py` `_verify_cover_sheet()` | 입력값 정합성 게이트 |
| 차수-열 매핑 | `excel/utils.py:rev_col()` | E=0차 … P=11차 |

---

## 2. FR ↔ 컴포넌트 매핑

| FR | 설명 | 컴포넌트 | file:line |
|----|------|----------|-----------|
| FR-001 | 갑지 집계 셀 직접 입력 금지 (수식 전용) | `SheetWriter.write_cell()` — formula_cell 스킵 | `excel/base.py:87-88` |
| FR-002 | F4(매출액) 천원 기록 | `CommonSheetWriter._write()` `_thousand()` | `excel/common_sheet.py:119-124` |
| FR-003 | P4(영업이익) 천원 기록 | `CommonSheetWriter._write()` `_thousand()` | `excel/common_sheet.py:125-126` |
| FR-004 | col+125(시작일) datetime 기록 | `CoverSheetWriter._write()` `_to_date()` | `excel/cover_sheet.py:38-42` |
| FR-005 | col+126(종료일) datetime 기록 | `CoverSheetWriter._write()` `_to_date()` | `excel/cover_sheet.py:43-44` |
| FR-006 | E3(사업명) 불일치 오류 보고 | `_verify_cover_sheet()` E3 검증 | `reviewer.py:449-456` |
| FR-007 | F4(매출액) 1천원 초과 오류 | `_verify_cover_sheet()` F4 검증 | `reviewer.py:423-433` |
| FR-008 | P4(영업이익) 1천원 초과 오류 | `_verify_cover_sheet()` P4 검증 | `reviewer.py:436-447` |
| FR-009 | 영업이익 역산 불일치 오류 | `_verify_cover_sheet()` 역산 검증 | `reviewer.py:473-484` |
| FR-010 | rev>=1: 계약금액·집행계획 참조 수식 삽입 | `CommonSheetWriter._write()` 수식 삽입 루프 | `excel/common_sheet.py:334-348` |
| FR-011 | rev>=1: 영업이익·영업이익% 수식 삽입 | `CommonSheetWriter._write()` 수식 삽입 | `excel/common_sheet.py:349-353` |
| FR-012 | 기간 미입력 오류 보고 | `_verify_cover_sheet()` 기간 검증 | `reviewer.py:458-470` |
| FR-013 | 이전 차수 날짜·범위·특기사항 기록 | `CoverSheetWriter._write()` prev_revisions 루프 | `excel/cover_sheet.py:52-75` |

---

## 3. 의존 관계

### 3-1. 업스트림 의존

| 의존 기능 | 의존 내용 | 근거 |
|-----------|-----------|------|
| **EXE-08** (집행예산 산출내역서·집계표) | 공통 시트 비목 블록(행 23~112)에 값이 기록되어 있어야 갑지 수식이 올바른 합계를 참조할 수 있다. EXE-10은 EXE-08이 완료된 후 오케스트레이터가 의존성 레벨에 따라 실행한다. | `orchestrator.py:44-65` `compute_dependency_levels()` |
| **EXE-06** (Sprint_Contract 생성) | `SprintContract.confirmed_fields`, `.revision`, `.prev_revisions`, `.rates`가 확정되어 있어야 CommonSheetWriter·CoverSheetWriter가 값을 읽을 수 있다. | `contract_builder.py:297` `build_sprint_contract` |
| **EXE-13** (수정집행·차수별 7시트) | revision >= 1인 경우, "(N차)" 집행예산집계표 시트가 워크북에 존재해야 수식 참조가 유효하다. 시트 미존재 시 엑셀 #REF! 오류 발생. | `excel/common_sheet.py:340` `agg_sheet = f"'4. 집행예산집계표 ({rev}차)'"` |
| **EXE-15** (Reviewer 결정론 5단계) | `_verify_cover_sheet()`는 Reviewer 4단계로 호출된다. EXE-10의 FR-006~FR-012는 이 함수가 실행되어야 검증된다. | `reviewer.py:563` |

### 3-2. 공유 컴포넌트

| 컴포넌트 | 공유 소비자 | 근거 |
|----------|-----------|------|
| `excel/utils.py:rev_col()` | CommonSheetWriter, CoverSheetWriter, BreakdownSheetWriter, FeeSheetWriter, 수정집행 등 모든 시트 라이터 | `excel/utils.py:6-8` |
| `excel/base.py:SheetWriter` | 모든 시트 라이터의 베이스 클래스 | `excel/base.py:62` |
| `excel/base.py:CellType`, `cell_type()` | 수식 셀·입력 셀·스킵 셀 분류 — EXE-10 FR-001의 수식 셀 보호가 여기서 구현됨 | `excel/base.py:28-55` |

### 3-3. 다운스트림(Downstream)

EXE-10은 다른 기능이 소비하는 데이터를 직접 생성하지 않는다(수식 레이어이므로). 갑지 시트의 집계값은 엑셀 클라이언트에서 수식 계산 후 사용자가 읽는다.

---

## 4. 데이터 흐름 (0차 기준)

```
SprintContract
  .confirmed_fields.revenue     →  CommonSheetWriter  →  공통!F4 (천원)
  .confirmed_fields.profit      →  CommonSheetWriter  →  공통!P4 (천원)
  .confirmed_fields.project_name→  CommonSheetWriter  →  공통!E3
  .confirmed_fields.project_period.start → CoverSheetWriter → 공통!E125(datetime)
  .confirmed_fields.project_period.end   → CoverSheetWriter → 공통!E126(datetime)
  .confirmed_fields.scope       →  CoverSheetWriter  →  공통!E129
  .confirmed_fields.special_notes →CoverSheetWriter  →  공통!E134

  [템플릿 내장 수식] 갑지!집계셀  ←  공통!F4/P4/... (수식 참조)
```

```
수정집행(revision >= 1):
  CommonSheetWriter._write()
    → 공통!{col}135 = '4. 집행예산집계표 ({rev}차)'!H10*1000
    → 공통!{col}136 = '4. 집행예산집계표 ({rev}차)'!H13*1000
    → 공통!{col}137 = '4. 집행예산집계표 ({rev}차)'!H19*1000
    → 공통!{col}138 = '4. 집행예산집계표 ({rev}차)'!H22*1000
    → 공통!{col}141 = '4. 집행예산집계표 ({rev}차)'!L10*1000
    → 공통!{col}142 = '4. 집행예산집계표 ({rev}차)'!L13*1000
    → 공통!{col}143 = '4. 집행예산집계표 ({rev}차)'!L19*1000
    → 공통!{col}144 = '4. 집행예산집계표 ({rev}차)'!L22*1000
    → 공통!{col}148 = '4. 집행예산집계표 ({rev}차)'!L42*1000
    → 공통!{col}149 = '4. 집행예산집계표 ({rev}차)'!M42/100
```

---

## 5. 검증 흐름 (Reviewer 4단계)

```
reviewer.py:563 → _verify_cover_sheet(wb, contract, step_results)
  ├─ F4(매출액) 검증:    abs(actual - expected) > 1 → 오류
  ├─ P4(영업이익) 검증:  abs(actual - expected) > 1 → 오류
  ├─ E3(사업명) 검증:    actual_name != cf.project_name → 오류
  ├─ 기간 입력 검증:     col+125 or col+126 == None → 오류
  └─ 영업이익 역산:      |profit - (revenue-cost-overhead)| > max(rev*0.01, 1000) → 오류
```

---

## 6. 비고 — non-goal

- **갑지 시트 수식 내용 자체**: 엑셀 수식(예: `=HLOOKUP(...)`)은 템플릿 xlsx에 내장되어 있으며 Python 코드에서 작성하지 않는다. 본 스펙은 공통 시트 입력값의 정합성만 관리한다.
- **수식 셀 HLOOKUP 범위(E8:P149)**: EXE-12(템플릿 생성) 및 EXE-13(수정집행) 관할. EXE-10 범위 밖.
- **파일 CRUD·편집잠금·챗봇·OTEL/RateLimit**: 설계 §9 non-goal.
