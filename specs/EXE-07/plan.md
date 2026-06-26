# Implementation Plan: EXE-07 수수료산출내역 (5-4)

**Created**: 2026-06-26  **Status**: Draft
**Consumes**: EXE-06 (SprintContract, fee_items)
**Produces**: 5-4 수수료산출내역 시트 기록 (0차 및 수정집행 N차)

---

## 아키텍처 개요

EXE-07은 **쓰기 레이어(Write Layer)**이다. SprintContract.fee_items를 Excel 템플릿의
5-4 시트에 기록한다. 비즈니스 계산은 두 계층으로 분리된다.

```
EXE-06 SprintContract
    └── fee_items (FeeItem[])
            │
            ├─► _build_fee_items()         # contract_builder.py:204
            │       ├── _calc_prorated_qty()   # 일할계산
            │       ├── _fiscal_year_shares()  # 연도분리 (EXE-11 공유)
            │       └── _split_by_shares()     # 금액 배분
            │
            └─► FeeSheetWriter._write()    # excel/fee_sheet.py:41
                    ├── _write_base_rows() # revision=0
                    └── _write_rev_rows()  # revision>=1
```

EXE-11(연도분리 엔진)의 `_fiscal_year_shares`/`_split_by_shares` 함수를
`_build_fee_items`가 직접 호출하므로, EXE-07은 EXE-11에 대한 **런타임 의존**을 가진다.

---

## 기술 스택

| 계층 | 기술 | 역할 |
|------|------|------|
| 백엔드 | FastAPI (Python) | API 라우팅 |
| 데이터 모델 | Pydantic v2 (`models/sprint_contract.py`) | FeeItem 스키마 |
| Excel 라이터 | openpyxl (`excel/fee_sheet.py`) | 셀 직접 기록 |
| 계산 엔진 | `contract_builder.py` | 일할/연도분리 계산 |
| 검증 엔진 | `reviewer.py` | 역마진/1원 정밀도 검증 |
| 설정 | `harness/cell_map.json` | 행 번호 런타임 오버라이드 |

---

## FR ↔ 컴포넌트 매핑

| FR | 동작 요약 | 파일:라인 |
|----|-----------|-----------|
| FR-001 | 계약(H/I)/집행(K/L)/당기(Q/R) 컬럼 분리 기록 | `excel/fee_sheet.py:85-93` |
| FR-002 | D/E/F/G 열 기본정보 기록 | `excel/fee_sheet.py:81-84` |
| FR-003a | vendor 제공 + revision=0 → AJ열 협력사명 기록 | `excel/fee_sheet.py:94-95` |
| FR-003b | vendor 제공 + revision>=1 → AQ열 협력사명 기록 | `excel/fee_sheet.py:134-135` |
| FR-004 | J/M/S 수식 셀 금액 불일치 시 강제 입력 | `excel/fee_sheet.py:87`, `137-142` |
| FR-005 | 수식 셀(data_type="f") 값 일치 시 수식 유지 | `excel/fee_sheet.py:156-161` |
| FR-006a | 역마진 → errors 목록에 오류 기록 | `reviewer.py:191-192` |
| FR-006b | 역마진 → margin_structure_ok=False 반환 | `reviewer.py:193` |
| FR-007a | 금액 1원 초과 오차 → errors 목록에 오류 기록 | `reviewer.py:168-188` |
| FR-007b | 계약금액 1원 초과 오차 → contract_calc_ok=False 반환 | `reviewer.py:176` |
| FR-007c | 집행금액 1원 초과 오차 → execution_calc_ok=False 반환 | `reviewer.py:189` |
| FR-008 | M/M·월 단위 시작월 중간 시 일할계산 | `contract_builder.py:103-130`, `229-231` |
| FR-009 | contractAmount 명시 시 일할계산 금지 | `contract_builder.py:228` |
| FR-010a | 다년도 사업 회계연도 비율 배분 → 당기수량/금액 산출 | `contract_builder.py:160-190`, `262-268` |
| FR-010b | 다년도 사업 → 연도배분확인 ConflictResolution 생성 | `contract_builder.py:269-273` |
| FR-011 | currentQty/currentAmount 명시 시 자동 배분 금지 | `contract_builder.py:256-261` |
| FR-012 | 단년도 → 집행수량 전체를 당기수량으로 | `contract_builder.py:274-276` |
| FR-013a | 9건 초과 시 합계행 위에 초과분 행 삽입 | `excel/fee_sheet.py:70-73` (0차), `100-103` (수정집행) |
| FR-013b | 9건 초과 시 삽입 행에 직전 행 서식 복사 | `excel/fee_sheet.py:74-76` (0차), `104-106` (수정집행) |
| FR-014 | revision >= 1 당초/변경/당기 열 분리 | `excel/fee_sheet.py:97-135` |
| FR-015a | 이전 차수 항목 매칭: 품명+협력사명 일치 시 당초값 매핑 | `excel/fee_sheet.py:144-149` |
| FR-015b | 이전 차수 항목 매칭: 불일치 시 동일 순번 fallback | `excel/fee_sheet.py:150-153` |
| FR-016 | fee_items=[] 시 즉시 반환 | `excel/fee_sheet.py:43-44` |
| FR-017 | fee 범주 자재코드 = 1 | `contract_builder.py:18` |

---

## 데이터 흐름 상세

### 0차 시트 열 매핑 (revision=0)

```
FeeItem 필드              → Excel 셀(행 8~16)
──────────────────────────────────────────────
code                      → D열  (자재코드)
item_name                 → E열  (품명)
spec                      → F열  (규격)
unit                      → G열  (단위)
contract_qty              → H열  (계약 수량)
contract_unit_price       → I열  (계약 단가)
[수식 또는 강제입력]      → J열  (계약 금액 = H×I)
execution_qty             → K열  (집행 수량)
execution_unit_price      → L열  (집행 단가)
[수식 또는 강제입력]      → M열  (집행 금액 = K×L)
current_period_qty        → Q열  (당기 수량)
execution_unit_price      → R열  (당기 단가 = 집행단가 재사용)
[수식 또는 강제입력]      → S열  (당기 금액 = Q×R)
vendor                    → AJ열 (비고: 협력사명)
```

코드 근거: `backend/services/excel/fee_sheet.py:81-95`

### 수정집행 시트 열 매핑 (revision >= 1)

```
이전 차수 FeeItem (당초)  → H열(계약수량 당초), I열(계약단가 당초)
                            N열(집행수량 당초), O열(집행단가 당초)
현재 차수 FeeItem (변경)  → K열(계약수량 변경), L열(계약단가 변경)
                            Q열(집행수량 변경), R열(집행단가 변경)
current_period_qty        → X열  (당기 수량)
execution_unit_price      → Y열  (당기 단가)
[수식 또는 강제입력]      → Z열  (당기 금액 = X×Y)
vendor                    → AQ열 (비고: 협력사명)
금액 셀 J/M/P/S/Z         ← 템플릿 수식이 계산 (수량×단가)
```

코드 근거: `backend/services/excel/fee_sheet.py:108-135`

---

## 의존 관계

### EXE-11 (연도분리 엔진) — 런타임 공유

EXE-07의 `_build_fee_items`는 EXE-11의 두 함수를 직접 호출한다.

| 함수 | 목적 | 파일:라인 |
|------|------|-----------|
| `_fiscal_year_shares(start, end, fiscal_year)` | 당기/이후1/이후2 비율 계산 | `contract_builder.py:160` |
| `_split_by_shares(amount, shares)` | 금액을 (당기, 이후1, 이후2)로 배분 | `contract_builder.py:193` |

이 두 함수는 EXE-06, EXE-08, EXE-09도 소비한다. EXE-11 스펙의 변경은 EXE-07에 직접 영향을 준다.

### EXE-06 (Sprint_Contract 생성) — 데이터 공급

EXE-06의 `build_sprint_contract`가 생성한 `SprintContract.fee_items`를 소비한다.
fee_items가 없으면 EXE-07은 시트를 수정하지 않는다.

코드 근거: `contract_builder.py:297` (build_sprint_contract)

### EXE-15 (Reviewer 결정론 5단계) — 검증 소비

EXE-15의 Stage 1이 `_verify_fee_structure`를 통해 EXE-07의 산출 결과를 검증한다.
역마진(FR-006)과 1원 정밀도(FR-007)는 EXE-15 Stage 1의 검증 항목이다.

코드 근거: `reviewer.py:147` (_verify_fee_structure)

---

## 검증 컴포넌트 (EXE-15 Stage 1)

`_verify_fee_structure` 함수가 수행하는 검증 항목과 결과 키:

| 검증 항목 | 결과 키 | 기준 | 파일:라인 |
|-----------|---------|------|-----------|
| 계약 수량×단가=금액 | `contract_calc_ok` | 오차 1원 미만 | `reviewer.py:168-176` |
| 집행 수량×단가=금액 | `execution_calc_ok` | 오차 1원 미만 | `reviewer.py:178-189` |
| 역마진 | `margin_structure_ok` | 집행단가 ≤ 계약단가 | `reviewer.py:191-193` |
| 연도분리 | `fiscal_year_split_ok` | 다년도 시 당기 < 전체 | `reviewer.py:203-212` |
| 계약 소스 교차 | `cross_check_contract_source` | 셀 ↔ FeeItem 수량/단가 일치 | `reviewer.py:219-224` |
| 집행 소스 교차 | `cross_check_estimate_source` | 집행 불일치 없음 | `reviewer.py:228-231` |

---

## 설정 오버라이드

DATA_START_ROW/DATA_END_ROW/FEE_TOTAL_ROW는 `harness/cell_map.json`의
`fee_sheet` 섹션에서 런타임에 로드된다. 파일이 없거나 로드 실패 시 기본값(8/16/17)이 사용된다.

코드 근거: `backend/services/reviewer.py:30-37` (_load_fee_constants)

---

## 비범위 (EXE-07에 포함되지 않는 항목)

- 노무비(급료/상여/퇴직/명절) 산출 → EXE-09
- 공통 시트 비목 블록 기록 → EXE-08
- 갑지 집계 수식 체인 → EXE-10
- 연도분리 비율 계산 알고리즘 자체 → EXE-11
- 파일 저장소 CRUD, 편집잠금, 챗봇, OTEL → 설계 §9 비범위
