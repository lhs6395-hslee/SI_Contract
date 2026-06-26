# Implementation Plan: EXE-11 — 연도분리 엔진 (공유)

**Feature**: EXE-11  **Created**: 2026-06-26  **Status**: Draft
**범위**: as-is 문서(spec/plan/tasks)까지. 코드 구현/TDD는 별도 사이클.

---

## 아키텍처 개요

EXE-11은 **공유 계산 엔진**이다. 독립적인 API 엔드포인트나 시트 라이터를 갖지 않으며, 아래 세 함수로 구성된다.

```
_fiscal_year_shares(start_date, end_date, fiscal_year)
    → {"current": float, "next1": float, "next2": float, "prev": float, "total_mm": float} | None

_split_by_shares(amount, shares)
    → (cur: int, nx1: int, nx2: int)

common_sheet.py:_calc_period_ratios(start_str, end_str, fiscal_year)
    → {13: float|None, 14: float|None, 15: float|None, 16: float|None}
```

이 함수들은 EXE-06·07·08·09가 직접 호출하는 **내부 라이브러리**이다. 외부 API 없음.

---

## 기술 스택

| 레이어 | 기술 | 비고 |
|--------|------|------|
| 언어 | Python 3.11+ | `datetime.date.fromisoformat` 사용 |
| 집계 단위 | `calendar.monthrange` (Python stdlib) | 일할 계산용 |
| 반올림 | `round()` (Python 내장) | 1원 정밀도 |
| 외부 의존 | 없음 | AI 호출 없는 결정론 함수 |

---

## FR ↔ 컴포넌트 매핑

| FR | 함수/클래스 | 파일:라인 | 설명 |
|----|------------|-----------|------|
| FR-001a | `_fiscal_year_shares` | `backend/services/contract_builder.py:176` | total_mm 환산 |
| FR-001b | `_fiscal_year_shares` | `backend/services/contract_builder.py:189-190` | 비율 딕셔너리 반환 |
| FR-002 | `_fiscal_year_shares` | `backend/services/contract_builder.py:174-178` | 단년도·범위 밖 → None |
| FR-003 | `_fiscal_year_shares` | `backend/services/contract_builder.py:169-173` | 파싱 실패 → None |
| FR-004a | `_fiscal_year_shares` / `_window` | `backend/services/contract_builder.py:185` | current 비율 산출 |
| FR-004b | `_fiscal_year_shares` / `_window` | `backend/services/contract_builder.py:186` | next1 비율 산출 |
| FR-004c | `_fiscal_year_shares` / `_window` | `backend/services/contract_builder.py:187` | next2 비율 산출 (3연도+ 합산) |
| FR-004d | `_fiscal_year_shares` / `_window` | `backend/services/contract_builder.py:188` | prev 비율 산출 |
| FR-005a | `_split_by_shares` | `backend/services/contract_builder.py:194` | cur 산출 |
| FR-005b | `_split_by_shares` | `backend/services/contract_builder.py:195` | nx1 산출 |
| FR-005c | `_split_by_shares` | `backend/services/contract_builder.py:197-199` | prev=0 잔여분 nx2 보정, 반환형 `(cur: int, nx1: int, nx2: int)` 튜플 |
| FR-006 | `_split_by_shares` | `backend/services/contract_builder.py:197-200` | prev>0 시 nx2 비율 산출 |
| FR-007a | `_mm_between` | `backend/services/contract_builder.py:153` | 시작일=1일이면 해당 월 1.0 |
| FR-007b | `_mm_between` | `backend/services/contract_builder.py:153-156` | 시작일≠1일이면 일할(분모 30) |
| FR-008a | `CommonSheetWriter._write` / `_calc_period_ratios` | `backend/services/excel/common_sheet.py:162-165` | _calc_period_ratios 호출 |
| FR-008b | `CommonSheetWriter._write` | `backend/services/excel/common_sheet.py:166-171` | D13~D16 셀 비율 기록 |
| FR-009 | `_calc_period_ratios` | `backend/services/excel/common_sheet.py:35-36` | 파싱 실패 → None 딕셔너리 |
| FR-010a | `_calc_period_ratios` | `backend/services/excel/common_sheet.py:54` | 비율 round 6자리 산출 |
| FR-010b | `_calc_period_ratios` | `backend/services/excel/common_sheet.py:55-56` | 비율 ≤0 → None |
| FR-011 | `_build_fee_items` | `backend/services/contract_builder.py:262-273` | FeeItem 당기금액·확인 플래그 |
| FR-012 | `_build_fee_items` | `backend/services/contract_builder.py:256-261` | 명시값 우선, 자동 배분 skip |

---

## 소비 기능과의 의존 관계

```
EXE-11 (연도분리 엔진)
  ├── EXE-06 (Sprint_Contract 생성)
  │     _build_fee_items → _fiscal_year_shares / _split_by_shares 호출
  │     [공식 코드] contract_builder.py:204-294, 297-...
  │
  ├── EXE-07 (수수료산출내역 5-4)
  │     FeeItem.current_period_qty/amount 사용 (EXE-11 배분 결과 소비)
  │     [공식 코드] excel/fee_sheet.py
  │
  ├── EXE-08 (집행예산 산출내역서·집계표)
  │     BudgetItem.current_amount/next1_amount/next2_amount 사용
  │     → EXE-09(노무비)의 bonus_cur/bonus_nx1 도 동일 경로
  │     [공식 코드] excel/breakdown_sheet.py, contract_builder.py:542-554
  │
  └── EXE-09 (노무비 상세)
        상여금 bonus_cur/bonus_nx1 = `hday.year <= fiscal_year` 조건으로 연도 귀속
        [공식 코드] contract_builder.py:542-545
```

**EXE-11은 피의존 방향으로 다른 기능에 영향을 준다. EXE-11 자체는 EXE-02·03의 데이터를 간접 소비하나(SprintContract 인수), EXE-02·03의 완료가 EXE-11 함수 실행의 전제다.**

---

## 데이터 흐름

```
ExtractedData(start_date, end_date, fiscal_year)
    │
    ▼ _fiscal_year_shares()
fiscal_year_shares: {current, next1, next2, prev, total_mm}
    │
    ├─▶ _split_by_shares(fee_amount, shares)
    │       → (cur, nx1, nx2)  ─▶  FeeItem.current_period_amount  [EXE-07 소비]
    │
    ├─▶ BudgetItem 생성 시 직접 배분 (상여금 bonus_cur/nx1/nx2)   [EXE-09 소비]
    │       contract_builder.py:542-554
    │
    └─▶ _calc_period_ratios(start, end, fiscal_year)
            → {13, 14, 15, 16}  ─▶  CommonSheetWriter D13~D16    [EXE-08 소비]
```

---

## 경계 (as-is 기준)

| 포함 | 제외 |
|------|------|
| `_fiscal_year_shares` 비율 계산 | 이월 차수 생성 API (미구현 TO-BE) |
| `_split_by_shares` 금액 배분 | `settlement_cumulative_qty/amount` 모델 확장 (미구현) |
| `_calc_period_ratios` 공통 시트 비율 | `SprintContract.is_multi_year` 필드 추가 (미구현) |
| FeeItem 당기 분리·확인 플래그 | Fee_Sheet_Writer col14~20 정산누계 기록 (미구현) |
| 노무비 상여금 연도 귀속 로직 | 이월 정산누계 자동 누적 (미구현) |

---

## 미해결 설계 이슈 (구현 전 확인 필요)

1. **비율 계산 이원화** (NC-01): `_fiscal_year_shares`(개월수 기반)와 `_calc_period_ratios`(일수 기반)의 방법론이 다름. 단일화 또는 사용 시나리오 분리 기준 확인 필요.
2. **일할 분모 30** (NC-02): `_mm_between` 분모가 30 고정. 양식 또는 계약 규정과의 정합성 확인 필요.
3. **prev 구간 귀속** (NC-03): 이월 차수 작성 시 prev 금액이 어느 필드로 처리되는지 미정.
