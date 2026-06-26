# Implementation Plan: EXE-08 집행예산 산출내역서·집계표

**Created**: 2026-06-26  **Status**: Draft
**Spec**: `specs/EXE-08/spec.md`

---

## 1. 아키텍처 개요

EXE-08은 **공통 시트 입력 레이어**다. 외부 API 호출 없이, 메모리 내 `SprintContract` 데이터를  
openpyxl로 열린 워크북의 공통 시트 특정 셀에 쓴다. 5.집행예산산출내역서·4.집행예산집계표는  
수식 시트이므로 코드에서 직접 수정하지 않는다.

```
[EXE-06 build_sprint_contract]
          │ SprintContract(budget_items, active_items, staff_plan, revision, ...)
          ▼
[BreakdownSheetWriter._write()]   ← EXE-08 핵심
          │ write_cell("E25", 39_250_000, source="...")
          ▼
[wb["공통"] 차수열 E~P 셀 직접 기록]
          │ 수식 자동참조
          ▼
[5.집행예산산출내역서 수식 시트]  ← 값 읽기만 (EXE-10 갑지 수식도 여기 참조)
```

### 스택

| 계층 | 기술 | 비고 |
|------|------|------|
| 시트 기록 | openpyxl | `SheetWriter.write_cell()` — 셀 색상 방어 포함 |
| 비목 매핑 | Python dict `BUDGET_BLOCKS` | 하드코딩 상수 |
| 연도 배분 | `_fiscal_year_shares()` / `_split_by_shares()` | EXE-11 공유 함수 |
| 이중 계상 방지 | `is_auto_calculated()` | `company_standards.py` |
| 차수 열 변환 | `rev_col(revision)` | `utils.py` |

---

## 2. FR ↔ 컴포넌트 매핑

| FR | 동작 | 컴포넌트 (file:line) |
|----|------|---------------------|
| FR-001 | active_items 기준 비목 블록 기록 | `breakdown_sheet.py:52-67 BreakdownSheetWriter._write()` |
| FR-002 | inputs_used 출처 보존 | `base.py:82-97 SheetWriter.write_cell()` |
| FR-003a | 퇴직금·보험료 비목 입력 제외 | `company_standards.py:43-50 is_auto_calculated()` → `contract_builder.py:377-382` |
| FR-003b | 자동계산중복 플래그 기록 | `contract_builder.py:377-382` |
| FR-004 | VAT/부가세 제외 | `contract_builder.py:382-384` |
| FR-005a | 하위 호환 급료 산출 (staff_plan fallback 기록) | `breakdown_sheet.py:69-88`, `contract_builder.py:454-496` |
| FR-005b | 급료확인 관문 요청 | `breakdown_sheet.py:69-88`, `contract_builder.py:454-496` |
| FR-006 | 다년도 당기/이후 배분 | `breakdown_sheet.py:79-88` → `contract_builder.py:160-201 _fiscal_year_shares()/_split_by_shares()` |
| FR-007 | bonus contract 행=None → 기록 생략 | `breakdown_sheet.py:64-67 "if row is not None:"` |
| FR-008 | 파란 셀·수식 셀 덮어쓰기 방지 | `base.py:83-88 cell_type() 분기` |
| FR-009 | 차수 → 열 문자 변환 | `utils.py:6-8 rev_col()`, `breakdown_sheet.py:49` |
| FR-010 | CATEGORY_LABELS 에코 방지 (unwanted) | `contract_builder.py:26-33 CATEGORY_LABELS`, `contract_builder.py:389-390` |

---

## 3. 핵심 데이터 흐름

### 3-1. budget_items 경로 (주 경로)

```
costItems(프론트엔드) 
  → contract_builder.build_sprint_contract()
      → BUDGET_CATEGORIES 필터 (fee 제외)
      → is_auto_calculated() 필터 (퇴직금/보험료 제외)
      → VAT 필터
      → BudgetItem 집계(카테고리별 금액 누산)
      → fy_shares 연도 배분 (EXE-11 호출)
  → SprintContract.budget_items
  → BreakdownSheetWriter._write()
      → BUDGET_BLOCKS[category] → 행 번호
      → rev_col(revision) → 열 문자
      → write_cell(f"{col}{row}", amount)
```

### 3-2. staff_plan fallback 경로 (budget_items에 labor 없을 때)

```
SprintContract.staff_plan
  → [s for s if s.type=="직접"]
  → sum(monthly_rate × months)  [또는 standard_rate_for(grade)]
  → fy_shares → _split_by_shares()
  → write_cell(f"{col}{LABOR_SALARY['execution']}", total_salary)
```

> **spec/plan 정합성 주의**: `standard_rate_for(grade)` fallback 경로는 현재 이 plan에만 존재하며 spec.md FR-005a에 [NEEDS CLARIFICATION]으로 표시되어 있다. grade 기반 단가표 충돌(3중 출처: `company_standards.py` 과장 550만 / `executor.md:101` 600만 / `REPORT_eps_values.md:144` 650만 — 설계 §6-1 항목 1)이 해소되기 전까지, 이 경로의 구현은 보류한다.

### 3-3. 연도 배분 (EXE-11 공유)

```
_fiscal_year_shares(start_date, end_date, fiscal_year)
  → {"current": 비율, "next1": 비율, "next2": 비율, ...}
_split_by_shares(amount, shares)
  → (cur, nx1, nx2)  # cur + nx1 + nx2 = round(amount) [prev=0인 경우]
```

`breakdown_sheet.py:79-88`에서 동일 함수를 직접 import해 재사용한다.

---

## 4. BUDGET_BLOCKS 행 번호 상수

코드 근거: `breakdown_sheet.py:26-40`

| 카테고리 | desc | contract | execution | settled | current | next1 | next2 |
|----------|------|----------|-----------|---------|---------|-------|-------|
| labor    | 23   | 24       | 25        | 26      | 27      | 28    | 29    |
| bonus    | 30   | **None** | 31        | 32      | 33      | 34    | 35    |
| wage     | 36   | 37       | 38        | 39      | 40      | 41    | 42    |
| welfare  | 43   | 44       | 45        | 46      | 47      | 48    | 49    |
| travel   | 50   | 51       | 52        | 53      | 54      | 55    | 56    |
| vehicle  | 57   | 58       | 59        | 60      | 61      | 62    | 63    |
| equipment| 64   | 65       | 66        | 67      | 68      | 69    | 70    |
| rent     | 71   | 72       | 73        | 74      | 75      | 76    | 77    |
| transport| 78   | 79       | 80        | 81      | 82      | 83    | 84    |
| comm     | 85   | 86       | 87        | 88      | 89      | 90    | 91    |
| print    | 92   | 93       | 94        | 95      | 96      | 97    | 98    |
| safety   | 99   | 100      | 101       | 102     | 103     | 104   | 105   |
| etc      | 106  | 107      | 108       | 109     | 110     | 111   | 112   |

---

## 5. 의존 관계

| 방향 | 기능 | 의존 내용 |
|------|------|-----------|
| Consumes | **EXE-06** Sprint_Contract 생성 | `SprintContract.budget_items`, `active_items`, `revision` |
| Consumes | **EXE-11** 연도분리 엔진 | `_fiscal_year_shares()`, `_split_by_shares()` — 동일 함수 직접 import |
| Consumes | **EXE-09** 노무비 상세 | `budget_items.labor/bonus` 데이터 (급료·상여 산출은 EXE-09 소유) |
| Produces | **EXE-10** 갑지(0) 집계 | 공통 시트 셀값 → 갑지 수식이 참조 (EXE-10은 수식 레이어) |
| Shares | **EXE-07** 수수료산출내역 | `BUDGET_BLOCKS`의 `fee` 카테고리는 EXE-07이 별도 처리 (공통 시트 제외) |

**EXE-08과 EXE-09의 경계 (설계 §3)**:

- EXE-03(사내기준보정): 소스에 급료가 없을 때 사내 단가표를 fallback으로 적용하는 규칙 소유.
- EXE-09(노무비 상세): 급료·상여·퇴직·명절 금액을 `BudgetItem`으로 산출하는 규칙 소유.
- EXE-08(이 기능): 산출된 `BudgetItem`을 받아 공통 시트 행에 기록하는 입력 레이어.
- `contract_builder.py:434-560`은 EXE-03/09의 경계 영역이며 EXE-08은 그 출력만 소비한다.

---

## 6. 검증 연동 (EXE-15 결정론 검증)

`reviewer.py:300 _verify_breakdown()`이 이 기능의 출력을 검증한다.

| 검증 항목 | 검증 방법 | 허용 오차 |
|-----------|-----------|-----------|
| 노무비-급료 | `공통!{col}{LABOR_SALARY_ROW}` vs `staff_plan 합계` | 1원 |
| 수수료 교차 | `5-4 시트 집행합계` vs `SprintContract fee_items 합계` | 1원 |
| 보험료 요율 | 공통 시트 요율 셀 vs `contract.rates` | 0.0001 (%) |
| 비활성 비목 | `active_items=false` 비목 셀 = 0 | 0원 |

코드 근거: `reviewer.py:300-405`

---

## 7. 미결 사항 (plan 수준)

1. **보험료 요율 기준** — 집행/정산 이원화 해소 후 `DEFAULT_RATES` 업데이트 및 SC-006 수치 확정.  
   `[NEEDS CLARIFICATION — 설계 §6-1 항목 3]`

2. **안전관리비(`safety`) 산출 기준** — 코드에 별도 수식 없음. 양식 수식으로만 처리되는지 확인 필요.  
   `[NEEDS CLARIFICATION — 설계 §6-2 "인원×5만" 출처 미발견]`
