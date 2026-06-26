# Implementation Plan: EXE-09 — 노무비 상세 (급료/상여/퇴직/명절)

**Feature Branch**: `EXE-09-labor-detail`  **Created**: 2026-06-26  **Status**: Draft
**작업 깊이**: 문서(spec/plan/tasks)까지. 코드 구현·TDD는 별도 사이클(설계 §9).

---

## 1. 아키텍처 개요

EXE-09는 **도메인 기능**(설계 §3 성격). 완전히 백엔드 서비스 레이어에서 동작하며,
프론트엔드는 BudgetItem 배열과 ConflictResolution 배열을 표시하기만 한다.
엑셀 시트의 퇴직금 셀(`=(G11+G21)/12`)은 수식 자동 계산이므로 본 기능에서 직접 산출하지 않는다.

```
[ExtractedData JSON]
       │
       ▼
contract_builder.py :: build_sprint_contract()   ← EXE-06 호출 진입점
       │
       ├─ (A) 급료 산출 블록  (line 434-496)
       │       ├─ has_labor_budget 체크  (line 436)
       │       ├─ 단가 불일치 감지  (line 440-453)
       │       └─ 자동 산출 + EXE-11 연도분리  (line 454-496)
       │
       ├─ (B) 상여 산출 블록  (line 512-559)
       │       ├─ has_bonus_budget 체크  (line 513)
       │       ├─ holidays_in_period() 호출  (line 519)  ← company_standards.py:63
       │       └─ rate × months_before / 9 산출  (line 540)
       │
       └─ [BudgetItem[], ConflictResolution[]] → SprintContract
```

퇴직금은 엑셀 레이어 수식(`excel/breakdown_sheet.py` → 셀 `=(G11+G21)/12`)이 자동 계산.
본 기능은 퇴직금 BudgetItem을 생성하지 않는다(이중계상 방지).

---

## 2. 기술 스택

| 레이어 | 기술 | 비고 |
|--------|------|------|
| 백엔드 언어 | Python 3.11+ | FastAPI 애플리케이션 |
| 핵심 서비스 | `backend/services/contract_builder.py` | EXE-09 산출 로직 전담 |
| 표준 테이블 | `backend/services/company_standards.py` | GRADE_RATES, HOLIDAYS, AUTO_CALCULATED_KEYWORDS |
| 연도분리 엔진 | `contract_builder.py:160 _fiscal_year_shares`, `:193 _split_by_shares` | EXE-11 공유 함수 |
| 엑셀 출력 | `excel/breakdown_sheet.py` | BudgetItem을 시트에 배치 (EXE-08 소비) |
| 인터페이스 | `main.py:544~ /api/projects/{id}/save` 등 | ExtractedData → SprintContract 변환 체인 |

---

## 3. FR ↔ 컴포넌트 매핑

| FR | 동작 요약 | 파일 : 라인 | 의존 |
|----|-----------|-----------|------|
| FR-001a | 급료 금액 산출 (GRADE_RATES × totalMM) | `contract_builder.py:454-491` | GRADE_RATES, standard_rate_for |
| FR-001b | 급료 BudgetItem 추가 | `contract_builder.py:488-496` | FR-001a 산출 결과 |
| FR-002 | 직급 부분일치 단가 조회 | `company_standards.py:53-60` | GRADE_RATES |
| FR-003 | 급료 단가 불일치 감지 + 플래그 | `contract_builder.py:440-453` | GRADE_RATES, standard_rate_for |
| FR-004a | 상여금 산출 (rate × months_before / 9) | `contract_builder.py:512-555, :540` | holidays_in_period, GRADE_RATES |
| FR-004b | 상여 BudgetItem 추가 | `contract_builder.py:555-559` | FR-004a 산출 결과 |
| FR-005 | holidays_in_period 경계 조건 | `company_standards.py:63-74` | HOLIDAYS 테이블 |
| FR-006 | 명절 없으면 상여 미생성 | `contract_builder.py:522` | holidays_in_period |
| FR-007 | 급료 BudgetItem 추가 시 확인 플래그 (event) | `contract_builder.py:493-496` | ConflictResolution, FR-001b |
| FR-008 | 상여 BudgetItem 추가 시 확인 플래그 (event) | `contract_builder.py:556-559` | ConflictResolution, FR-004b |
| FR-009 | AUTO_CALCULATED_KEYWORDS 이중계상 방지 (unwanted) | `company_standards.py:44-50` | is_auto_calculated |
| FR-010 | 급료 다년도 연도분리 | `contract_builder.py:473-484` | EXE-11 _split_by_shares |
| FR-011a | 상여 다년도 연도귀속 배분 (bonus_cur/bonus_nx1) | `contract_builder.py:542-551` | fiscal_year, EXE-11 공유 버킷 |
| FR-011b | 상여 잔액 next2_amount 설정 | `contract_builder.py:552-554` | FR-011a 배분 결과 |
| FR-012 | months_before ≤ 0 → 상여 0 처리 | `contract_builder.py:538-539` | — |

---

## 4. 경계 및 의존 관계

### EXE-09 ↔ EXE-03 경계 (CRITICAL)

두 기능 모두 `contract_builder.py:434-560` 코드 영역을 공유한다(설계 §3 경계 명기).

| 구분 | EXE-03 (사내기준보정) | EXE-09 (노무비 상세) |
|------|----------------------|---------------------|
| 역할 | 소스에 값이 없을 때 적용할 fallback 표준값 결정 | 급료/상여/퇴직 항목의 실제 산출·배치 규칙 |
| 산출물 | GRADE_RATES, DEFAULT_RATES, 명절 fallback 규칙 | BudgetItem(labor/bonus), ConflictResolution |
| 충돌값 귀속 | 직급 단가표 3중 충돌, 요율 이원화 — EXE-03에 귀속 | 상여 공식 3중 충돌 — EXE-09에 귀속 |

### EXE-09 → EXE-08 경계

EXE-09가 생성한 `BudgetItem(category="labor")` / `BudgetItem(category="bonus")`는
EXE-08(`excel/breakdown_sheet.py`)이 BUDGET_BLOCKS에 배치한다. 퇴직금은 시트 수식 레이어(EXE-10)가 담당.

### EXE-09 → EXE-11 의존

- `_fiscal_year_shares` (`contract_builder.py:160`): 다년도 비율 산출
- `_split_by_shares` (`contract_builder.py:193`): 금액 분할

EXE-11은 공유 함수이므로 EXE-09 변경이 EXE-06/07/08/11 결과에 영향을 미치지 않음을 확인 후 커밋.

### EXE-09 → EXE-06 (소비자)

`build_sprint_contract` (`contract_builder.py:297`)가 EXE-09 로직의 진입점이다.
EXE-06이 SprintContract를 생성하는 과정에서 EXE-09 산출 블록이 실행된다.

---

## 5. 데이터 흐름

```
ExtractedData.staffPlan[]          ExtractedData.costItems[]
        │                                    │
        ▼                                    ▼
internal_staff 필터(type="직접")    has_labor_budget / has_bonus_budget 체크
        │
        ├── 급료 자동 산출 (FR-001)
        │   GRADE_RATES[grade] × totalMM
        │   → BudgetItem(category="labor")
        │   → ConflictResolution("급료확인")
        │
        ├── 급료 단가 불일치 감지 (FR-003)
        │   abs(std_total - labor_total) > 1
        │   → ConflictResolution("급료단가확인"), 원본 유지
        │
        └── 상여 산출 (FR-004)
            holidays_in_period(start, end)
            → 명절별 인원별 round(rate × months_before / 9)
            → BudgetItem(category="bonus")
            → ConflictResolution("상여확인")

모든 BudgetItem → SprintContract.budget_items[]
모든 ConflictResolution → SprintContract.standards_conflicts[]
```

---

## 6. [NEEDS CLARIFICATION] 항목이 미치는 영향

| 충돌 항목 | 현재 잠정 적용 | 확정 시 변경 범위 |
|----------|--------------|----------------|
| 직급 단가표 | `company_standards.py:16-22 GRADE_RATES` 과장 5,500,000원 | GRADE_RATES 수정 → FR-001·FR-004 산출값 변경 |
| 상여 공식 | `rate × months_before / 9` (`contract_builder.py:540`) | 공식 변경 시 FR-004 산출 로직·테스트 전면 업데이트 |

두 항목이 확정될 때까지 관문(ConflictResolution 플래그)에서 사용자 재확인 운용.

---

## 7. non-goal (범위 밖)

- 퇴직금 직접 산출 — 엑셀 수식 레이어(EXE-10) 전담.
- 현장사원(type != "직접") 임금 산출 — 별도 처리(본 기능 범위 밖).
- 보험료 요율 적용 — EXE-08 산출내역서 수식 레이어.
- 파일 CRUD, 편집잠금, 챗봇, OTEL/Security 미들웨어 (설계 §9 범위 밖).
