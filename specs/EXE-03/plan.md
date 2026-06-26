# Implementation Plan: EXE-03 사내기준보정

**Feature**: EXE-03 사내기준보정
**Created**: 2026-06-26
**Status**: Draft
**Spec**: `specs/EXE-03/spec.md`

---

## 아키텍처 개요

EXE-03은 **백엔드 순수 로직** 레이어이다. AI 호출 없음, 프론트 UI 없음.
`build_sprint_contract` 내의 "사내 기준 보정" 분기(`contract_builder.py:411-559`)와
상수 테이블 모듈(`company_standards.py`)로 구성된다.

```
ExtractedData (from EXE-02)
        │
        ▼
build_sprint_contract()          ← contract_builder.py:297
  │
  ├─ [FR-11] AUTO_CALCULATED 필터 ← company_standards.is_auto_calculated()  :48-50
  │
  ├─ [FR-01/02/03] 급료 보정
  │     ├─ labor 없음 → GRADE_RATES fallback        :454-496
  │     └─ labor 있음 + 불일치 → 재확인 플래그      :440-453
  │
  ├─ [FR-04/05] 상여 보정
  │     ├─ holidays_in_period(start, end)           company_standards.py:63-74
  │     └─ 기간 내 명절만 → 상여 BudgetItem          :512-559
  │
  ├─ [FR-08] DEFAULT_RATES fallback
  │     └─ rates 없으면 RateSet 채움                (EXE-06에서 RateSet 소비)
  │
  └─ [SC-03] 모든 자동산출 → ConflictResolution 부착
        └─ standards_conflicts list                  :415-559
        │
        ▼
SprintContract (EXE-06으로 전달)
  ├─ budget_items: list[BudgetItem]
  ├─ conflicts: list[ConflictResolution]   ← EXE-04 관문에서 사용자에게 표시
  └─ rate_set: RateSet                     ← EXE-09 노무비 산출에서 소비
```

---

## 기술 스택

| 계층 | 기술 | 역할 |
|------|------|------|
| 비즈니스 로직 | Python 3.11+ | 사내 기준 보정 연산 |
| 상수 테이블 | `company_standards.py` | GRADE_RATES / DEFAULT_RATES / HOLIDAYS |
| 보정 엔진 | `contract_builder.py:411-559` | fallback 분기·플래그 생성 |
| 데이터 모델 | `models.py` | BudgetItem / ConflictResolution / RateSet |
| HTTP 게이트 | `main.py` (FastAPI) | `/api/projects/{id}/save` — build_sprint_contract 호출점 |

---

## FR ↔ 컴포넌트 매핑

| FR | 동작 요약 | 구현 파일:라인 | 비고 |
|----|---------|--------------|------|
| FR-01 | labor 없음 → GRADE_RATES fallback | `contract_builder.py:454-496` | `standard_rate_for` 호출 |
| FR-02 | labor 있음 + 단가 불일치 → 플래그(입력값 보존) | `contract_builder.py:440-453` | `abs(std_total - labor_total) > 1` |
| FR-03 | 직급 완전 불일치 시 부분 일치 단가 사용 | `company_standards.py:53-60` | `standard_rate_for` 내 `g in grade` |
| FR-04 | 명절 기간 외 → 상여 미책정 | `company_standards.py:63-74` + `contract_builder.py:519` | `holidays_in_period` 반환값이 빈 리스트이면 bonus BudgetItem 미생성 |
| FR-05 | 기간 내 명절 → 상여 BudgetItem 자동 산출 + 플래그 | `contract_builder.py:512-559` | bonus 없을 때만 실행 |
| FR-08 | rates 없음 → DEFAULT_RATES fallback | `company_standards.py:27-34` | RateSet 초기값으로 사용 |
| FR-11 | AUTO_CALCULATED 이중 계상 방지 | `company_standards.py:44-50` + `contract_builder.py:378-384` | `is_auto_calculated()` 필터 |

> **삭제된 FR (Clarifications Retained으로 이동)**: FR-06(상여금 공식 충돌), FR-07(umbrella 플래그), FR-09(직급 단가 충돌), FR-10(보험요율 이원화), FR-12(간접/관리비율 근거) — 런타임 동작이 아닌 문서 상태 기술 또는 검증 기준 없는 umbrella FR이므로 EARS 준수를 위해 spec.md Clarifications Retained #1~4로 이동. 구현 추적은 spec.md Clarifications 항목의 "해소 후 SC 추가 예정"으로 관리.
>
> **모든 자동 산출 → ConflictResolution 부착 (구 FR-07)**: SC-03으로 달성 여부를 검증하며, 구현 경로는 `contract_builder.py:493-496`, `:556-559` `standards_conflicts` 리스트 append.

---

## 의존 관계

### 소비(Consumes)

| 소비 대상 | 형태 | 출처 |
|----------|------|------|
| EXE-02 소스추출 결과 | `ExtractedData.extracted` / `.costItems` / `.staffPlan` | `contract_builder.py:312-319` |
| EXE-11 연도분리 엔진 | `_fiscal_year_shares` / `_split_by_shares` | `contract_builder.py:160,193` — 급료·상여 당기/이후 배분에 공용 |

### 생산(Produces)

| 생산 대상 | 형태 | 소비처 |
|---------|------|-------|
| 보정된 `budget_items` | `list[BudgetItem]` (category=labor/bonus) | EXE-06 Sprint_Contract 생성, EXE-09 노무비 산출 |
| `conflicts` (관문 플래그) | `list[ConflictResolution]` | EXE-04 기본정보 확인 게이트 (사용자 표시) |
| `rate_set` | `RateSet` | EXE-09 노무비 산출 (보험료 계산) |

### EXE-03 ↔ EXE-09 경계 (중요)

두 기능 모두 `contract_builder.py:434-559` 영역을 공유한다.

- **EXE-03 관할**: "소스에 값이 없을 때 사내 표준 테이블을 fallback으로 적용"하는 규칙과 관문 플래그 생성.
- **EXE-09 관할**: 급료/상여/퇴직/명절 노무비 항목의 **최종 금액 산출 및 시트 배치** 규칙.
- 동일 코드 블록(`contract_builder.py:434-559`)을 공유하므로 두 기능의 tasks.md 검증이 동일 코드 경로를 검증할 수 있다. 중복 수정 시 반드시 양쪽 spec을 함께 검토할 것.

---

## 데이터 흐름 상세

```
입력: ExtractedData
  .extracted.startDate, .endDate   → 명절 기간 판단
  .staffPlan[].grade, .totalMM     → GRADE_RATES 조회
  .staffPlan[].monthlyRate         → 문서 급여(단가표와 대조용)
  .costItems[].category="labor"    → labor 존재 여부
  .costItems[].category="bonus"    → bonus 존재 여부
  .rates                           → DEFAULT_RATES fallback 여부

처리:
  1. AUTO_CALCULATED 필터         → 이중 계상 방지
  2. labor 없음?
       YES → GRADE_RATES × totalMM → BudgetItem(category="labor")
             + ConflictResolution("급료확인")
       NO  → |입력값 - 단가표 기준| > 1?
               YES → ConflictResolution("급료단가확인"), 값 변경 없음
  3. bonus 없음?
       YES → holidays_in_period(start, end) → 기간 내 명절?
               YES → 상여 BudgetItem + ConflictResolution("상여확인")
               NO  → 상여 미생성
  4. rates 없음? → DEFAULT_RATES → RateSet

출력: SprintContract
  .budget_items (labor/bonus BudgetItem 포함)
  .conflicts     (관문 플래그 전체)
  .rate_set      (DEFAULT_RATES or 소스 요율)
```

---

## 미결 사항 (plan 단계에서 확인 필요)

| # | 항목 | 영향 컴포넌트 | 해소 경로 |
|---|------|------------|---------|
| P-1 | 직급 단가표 단가 3중 충돌 | `company_standards.py:16-22` | 사용자가 사내 기준 문서로 단일 출처 직접 확정 → GRADE_RATES 수정 |
| P-2 | 상여금 공식 3중 충돌 (`전액` vs `/9`) | `contract_builder.py:540` | 사용자가 사내 기준으로 적용 공식 직접 확정 |
| P-3 | 보험요율 집행/정산 이원화 | `company_standards.py:30-34` | 연도 기준 정책 공문 확보 |
| P-4 | 간접/관리비율 공문 경로 | `company_standards.py:28-29` | 담당자 경로 확인 |
| P-5 | 하도급노무비율 수치 | `executor.md:153` | 안전보건팀 공문 |
| P-6 | GRADE_RATES 미정의 직급 fallback | `company_standards.py:53-60` | 정책 결정(None 반환 → 건너뜀 vs 오류) |
