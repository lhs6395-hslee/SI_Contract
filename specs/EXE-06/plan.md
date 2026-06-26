# Implementation Plan: EXE-06 — Sprint_Contract 생성

**Feature Branch**: `EXE-06-sprint-contract-build`
**Created**: 2026-06-26
**Status**: Draft

---

## 아키텍처 개요

EXE-06은 **결정론 변환 레이어**다. AI 호출이 없으며, EXE-02(소스추출)·EXE-03(사내기준보정)·EXE-05(충돌해결)를 통과한 확정 ExtractedData JSON을 SprintContract Pydantic 객체로 매핑한다. 이 객체는 이후 Executor(EXE-12/13)가 소비하는 계약이다.

```
[프론트엔드]
    │  POST /api/pipeline/start
    │  { extractedData, revision, projectId }
    ▼
[main.py:707] start_pipeline
    ├─ 인가 게이트 (_assert_project_access)          ← EXE-17 소비
    ├─ MAX_REVISION 체크 (main.py:729)               ← EXE-06 FR-002
    ├─ prev_revisions 로드 (DynamoDB)                ← EXE-13 의존
    │
    ▼
[contract_builder.py:297] build_sprint_contract
    ├─ ConfirmedFields 매핑 (:327-349)               ← FR-003
    ├─ FeeItem 변환 _build_fee_items (:204)          ← FR-004a, FR-014
    │    └─ _calc_prorated_qty 일할계산 (:103)
    ├─ BudgetItem 집계 (:373-409)                    ← FR-004b, FR-005, FR-006
    │    ├─ is_auto_calculated 필터 (:378)
    │    └─ _split_by_shares 연도배분 (:402)          ← EXE-11 엔진 소비
    ├─ _fiscal_year_shares 연도비율 (:160)            ← EXE-11 엔진 소비
    ├─ 급료 자동산출 (:454-496)                      ← FR-008, EXE-03 GRADE_RATES
    ├─ 급료단가 확인 플래그 (:440-453)               ← FR-009
    ├─ 계약배분 자동 처리 (:499-510)                 ← FR-013
    ├─ 상여 자동산출 (:512-559)                      ← EXE-09 도메인(공유 영역)
    ├─ RateSet 조립 (:622-629)                       ← EXE-03 DEFAULT_RATES
    ├─ 요율확인 플래그 (:630-633)                    ← FR-010
    └─ SprintContract 조립 (:643-660)                ← FR-001
         └─ active_items (:569-579)                  ← FR-012

    ▼
[orchestrator.py] run_pipeline(contract)             ← EXE-12/13/15/16 소비
```

---

## 스택

| 구성요소 | 기술 | 비고 |
|---------|------|------|
| API 진입점 | FastAPI (`main.py:707`) | Starlette Request, Depends(require_auth) |
| 빌더 | Pure Python 함수 (`contract_builder.py:297`) | AI 호출 없음, 결정론 |
| 데이터 모델 | Pydantic v2 (`models/sprint_contract.py`) | field_validator로 입력 방어 |
| 연도분리 엔진 | `_fiscal_year_shares` / `_split_by_shares` | EXE-11 공유 함수 |
| 사내기준 테이블 | `company_standards.py` | GRADE_RATES, DEFAULT_RATES, MAX_REVISION |
| 저장소 | DynamoDB (prev_revisions 로드) | `load_project` / `save_pipeline_state` |

---

## FR ↔ 컴포넌트 매핑

| FR | 동작 | 파일:라인 |
|----|------|-----------|
| FR-001 | build_sprint_contract 호출 | `backend/main.py:745` |
| FR-002 | MAX_REVISION 초과 HTTP 400 | `backend/main.py:729-734`, `backend/services/company_standards.py:12` |
| FR-003 | ConfirmedFields 매핑 | `backend/services/contract_builder.py:327-349` |
| FR-004a | FeeItem 변환 | `contract_builder.py:362` |
| FR-004b | BudgetItem 집계 | `contract_builder.py:373-409` |
| FR-005 | 퇴직금·보험료 이중계상 방어 | `contract_builder.py:376-381`, `company_standards.py:43-50 AUTO_CALCULATED_KEYWORDS` |
| FR-006 | VAT/부가세 제외 | `contract_builder.py:382-384` |
| FR-007 | 연도분리 엔진 소비 | `contract_builder.py:160 _fiscal_year_shares`, `:193 _split_by_shares`, `:366-406` |
| FR-008 | 급료 자동산출(GRADE_RATES) | `contract_builder.py:454-496`, `company_standards.py:16-22` |
| FR-009 | 급료단가 확인 플래그 | `contract_builder.py:440-453` |
| FR-010 | 요율확인 플래그 무조건 생성 | `contract_builder.py:630-633` |
| FR-011a | prev_revisions 로드 | `main.py:737-744` |
| FR-011b | prev_fee_items 생성 | `contract_builder.py:562-567` |
| FR-012 | active_items 결정론 산출 | `contract_builder.py:569-579` |
| FR-013 | 계약배분 자동 처리 | `contract_builder.py:499-510` |
| FR-014 | 일할계산 (M/M 단위, 월 중간 시작) | `contract_builder.py:103-130 _calc_prorated_qty`, `:222-250` |

---

## EXE-11 연도분리 엔진 의존 (공유 컴포넌트)

EXE-06은 EXE-11이 정의하는 두 함수를 **직접 호출**한다. 이 의존은 단일 파일(`contract_builder.py`) 내 함수 호출이며 별도 API 경계가 없다.

| 함수 | 위치 | EXE-06 호출 지점 |
|------|------|-----------------|
| `_fiscal_year_shares(start, end, fy)` | `contract_builder.py:160` | `:366` (BudgetItem 배분), `:209` (_build_fee_items) |
| `_split_by_shares(amount, shares)` | `contract_builder.py:193` | `:402` (BudgetItem), `:474` (급료 배분) |

**주의**: EXE-11 스펙 변경(연도분리 로직 수정)은 EXE-06 FR-007의 동작에 직접 영향을 준다. 두 스펙의 계약(shares 딕셔너리 구조: `{current, next1, next2, prev, total_mm}`)을 동기화해야 한다.

---

## EXE-03 사내기준보정 의존

EXE-06 빌더는 EXE-03이 관리하는 사내기준 테이블을 `company_standards.py`를 직접 import해 소비한다.

| 상수/함수 | 위치 | 용도 |
|-----------|------|------|
| `GRADE_RATES` | `company_standards.py:16` | 급료 자동산출 기준 단가 |
| `DEFAULT_RATES` | `company_standards.py:27` | 요율 fallback 기본값 |
| `MAX_REVISION` | `company_standards.py:12` | 차수 상한 게이트 |
| `is_auto_calculated()` | `company_standards.py:48` | 이중계상 방어 필터 |
| `standard_rate_for()` | `company_standards.py:53` | 직급 문자열 → 단가 조회 |
| `holidays_in_period()` | `company_standards.py:63` | 명절 in-period 필터 (상여 산출 — EXE-09 공유) |

---

## EXE-09 노무비 공유 영역

`contract_builder.py:512-559`(상여 자동산출)는 EXE-09(노무비 상세) 도메인과 공유 코드 영역이다. EXE-06 빌더 내에 인라인되어 있으나, **상여 공식 충돌**(설계 §6-1 항목 2)이 해소되면 EXE-09 스펙과 함께 재정렬이 필요하다.

---

## 데이터 흐름

```
입력: ExtractedData JSON
  extracted: { projectName, startDate, endDate, fiscalYear, ... }
  costItems: [ { category, name, contractPrice, executionPrice, ... }, ... ]
  staffPlan: [ { grade, totalMM, type, monthlyRate, ... }, ... ]
  rates: { indirectRate, healthInsurance, ... }
  conflicts: [ { type, message }, ... ]
  files: [ { category, name, vendor, ... }, ... ]
  schedule: [ { name, startMonth, endMonth }, ... ]
  organization: [ { role, name, scope, lead }, ... ]

출력: SprintContract
  confirmed_fields: ConfirmedFields
  fee_items: FeeItem[]          (5-4 시트용)
  budget_items: BudgetItem[]    (공통 시트 비목 블록용)
  staff_plan: StaffItem[]       (인원투입계획 시트용)
  schedule: ScheduleItem[]      (예정공정표 시트용)
  organization: OrgMember[]     (현장조직 시트용)
  rates: RateSet
  active_items: dict[str, bool]
  conflict_resolutions: ConflictResolution[]
  prev_revisions: dict
  prev_fee_items: dict
  steps: StepDef[]              (Executor 워크플로 7단계)
  acceptance_criteria: str[]
```

---

## 의존 관계 요약

| 방향 | 기능 | 관계 |
|------|------|------|
| EXE-06 → EXE-11 | 연도분리 엔진 소비 | 동일 파일 내 함수 호출 |
| EXE-06 → EXE-03 | 사내기준 테이블 소비 | company_standards.py import |
| EXE-02 → EXE-06 | ExtractedData 제공 | API 레이어(extractedData JSON) |
| EXE-05 → EXE-06 | ConflictResolution 포함 | conflicts 필드로 전달 |
| EXE-06 → EXE-12 | SprintContract 제공 | orchestrator를 통해 전달 |
| EXE-06 → EXE-13 | prev_fee_items 제공 | 수정집행 당초 데이터 |
| EXE-06 → EXE-15/16 | SprintContract 제공 | Reviewer 검증 대상 |
| EXE-06 → EXE-17 | 인가 게이트 통과 후 실행 | _assert_project_access (main.py:718) |
