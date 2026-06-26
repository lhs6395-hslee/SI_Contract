# Feature Specification: EXE-10 — 갑지(0) 집계 (수식 레이어·종속)

**Feature Branch**: `EXE-10-cover-sheet-formula-layer`
**Created**: 2026-06-26
**Status**: Draft
**Input**: 공통 시트(CommonSheetWriter)·집계표(BreakdownSheetWriter)가 기록한 값을 갑지(0. 집행계획(갑지)) 수식 체인으로 집계·표현한다.

> **성격 명기 (설계 §3)**: EXE-10은 **수식 표현 레이어·종속** 기능이다. 독립적인 데이터 task(값 직접 입력)가 없으며, EXE-08(집행예산 산출내역서·집계표)이 기록한 공통 시트 값을 갑지 수식 체인이 참조·집계한다. 따라서 SC는 **수식 무결성 및 입력값 정합성**만을 대상으로 한다.

---

## User Scenarios & Testing

### User Story 1 — 갑지 매출액·영업이익 수식 집계 확인 (Priority: P1)

담당자는 파이프라인 완료 후 생성된 엑셀 파일의 갑지(0. 집행계획(갑지)) 시트에서, 공통 시트의 매출액·비목·영업이익이 수식 체인을 통해 올바르게 집계되어 있는지 확인한다. 갑지 셀은 직접 입력이 아닌 수식이므로, 검증은 공통 시트의 입력값과 SprintContract 확정값의 대조로 이루어진다.

- **Independent Test**: 단일 SprintContract(0차, revenue=1억, cost=8천만, profit=1천만)로 파이프라인 실행 → 공통 시트 F4(매출액 천원) == 100,000, P4(영업이익 천원) 오차 1원 이하 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** confirmed_fields.revenue=100,000,000(원)이고 revision=0인 SprintContract, **When** CommonSheetWriter._write()가 실행되면, **Then** 공통 시트 F4 == 100,000(천원, 오차 1원 이하).
  2. **Given** confirmed_fields.profit이 존재하고 abs(profit) >= 100,000(원), **When** CommonSheetWriter._write()가 실행되면, **Then** 공통 시트 P4 == round(profit / 1000)(천원, 오차 1원 이하).
  3. **Given** cf.revenue, cf.cost, cf.profit, contract.rates 모두 존재, **When** _verify_cover_sheet()가 실행되면, **Then** 영업이익 역산(revenue - cost - overhead)과 cf.profit의 차이가 `[잠정] max(abs(revenue)×0.01, 1,000)` 이하인 경우에만 검증 통과. (`[잠정, 코드 현행값]` — `reviewer.py:478`; 권위 출처 미확정 시 `[NEEDS CLARIFICATION]`)

### User Story 2 — 갑지 기간·사업명 참조원본 검증 (Priority: P1)

담당자는 갑지의 사업명·기간이 확정 정보와 일치하는지 확인하고자 한다. 갑지 셀은 수식이므로, 시스템은 공통 시트의 참조원본(E3, col+125/126)을 직접 대조한다.

- **Independent Test**: project_name="테스트사업", project_period={start:"2026-01-01", end:"2026-12-31"}인 계약으로 실행 → 공통!E3 == "테스트사업", 공통!E125/E126 비어있지 않음 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** confirmed_fields.project_name이 존재, **When** _verify_cover_sheet()가 실행되면, **Then** 공통!E3의 값이 cf.project_name과 완전 일치하지 않으면 오류를 보고한다.
  2. **Given** project_period.start와 project_period.end가 모두 존재, **When** CoverSheetWriter._write()가 실행되면, **Then** 공통 시트 col+125(시작일)·col+126(종료일)이 None이 아닌 datetime 값으로 기록된다.

### User Story 3 — 수정집행(revision>=1) 시 집계표 참조 수식 삽입 (Priority: P1)

수정집행 차수에서는 공통 시트의 해당 차수 열에 "(N차)" 집행예산집계표를 참조하는 수식이 삽입되어, 갑지가 정확한 차수의 집계표를 참조해야 한다.

- **Independent Test**: revision=1, 이전 차수 prev_revisions={"0": {...}} 존재 → 공통 시트 F열(1차) 135행에 `='4. 집행예산집계표 (1차)'!H10*1000` 수식 삽입 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** revision >= 1인 SprintContract, **When** CommonSheetWriter._write()가 실행되면, **Then** 각 rev에 대해 공통 시트 col+135/136/137/138 셀에 `='4. 집행예산집계표 ({rev}차)'!H{ref_row}*1000` 형식의 수식이 삽입된다.
  2. **Given** revision >= 1인 SprintContract, **When** CommonSheetWriter._write()가 실행되면, **Then** 공통 시트 col+141/142/143/144 셀에 집행변경 집계표 참조 수식(`=...!L{ref_row}*1000`)이 삽입된다.
  3. **Given** revision >= 1인 SprintContract, **When** CommonSheetWriter._write()가 실행되면, **Then** 공통 시트 col+148에 `='4. 집행예산집계표 ({rev}차)'!L42*1000`, col+149에 `='4. 집행예산집계표 ({rev}차)'!M42/100` 수식이 삽입된다.

### Edge Cases

- revision=0인 경우: 집계표 참조 수식 삽입 로직이 실행되지 않는다(`all_revs`가 빈 리스트이거나 조건 미충족). 수식은 템플릿에 이미 존재한다.
- confirmed_fields.revenue가 None이면 F4 미기록 — 검증 단계에서 ok_count만 증가(오류 미발생).
- confirmed_fields.profit이 None이면 P4 미기록 — 검증 단계에서 ok_count만 증가.
- `[NEEDS CLARIFICATION: revision=0 시 집계표 참조 수식이 템플릿에 내장되어 있는지, 아니면 별도 삽입 로직이 필요한지 — cover_sheet.py 코드에서 `if revision >= 1` 조건으로 0차는 템플릿 수식을 그대로 사용함이 확인되나, 템플릿 내 수식이 올바른 셀을 참조하는지는 템플릿 파일 직접 확인이 필요하다]`
- 수정집행 시 원본 시트가 "(N차)"로 rename됨(`base.py:76-80`): SheetWriter.ws 프로퍼티가 revision >= 1이면 `"{sheet_name} ({revision}차)"` 시트를 사용한다.

---

## Functional Requirements (EARS)

> 모든 FR은 EARS 5패턴 중 하나. 한 FR = 한 동작. 모호어 없음.

- **FR-001** (ubiquitous): THE SYSTEM SHALL 갑지(0. 집행계획(갑지)) 시트의 집계 셀에 값을 직접 입력하지 않는다.
  - *근거*: `excel/cover_sheet.py:1-5` 주석 "갑지는 전부 수식 — 공통 시트와 집계표에서 참조"

- **FR-001b** (ubiquitous): THE SYSTEM SHALL 갑지 집계를 공통 시트→집계표 참조 수식 체인으로만 표현한다.
  - *근거*: `excel/cover_sheet.py:1-5` 주석 "갑지는 전부 수식 — 공통 시트와 집계표에서 참조"; `excel/base.py:87-88` formula_cell 스킵 구현

- **FR-002** (event): WHEN CommonSheetWriter._write()가 실행되고 confirmed_fields.revenue가 존재하며 abs(revenue) >= 1,000,000이면, THE SYSTEM SHALL `round(revenue / 1000)` 값을 공통 시트 F4에 기록한다(천원 단위).
  - *근거*: `excel/common_sheet.py:119-124` `_thousand()` + `write_cell("F4", ...)`

- **FR-002b** (unwanted): IF CommonSheetWriter._write()가 실행되고 confirmed_fields.revenue가 존재하는데 abs(revenue) < 1,000,000이면, THEN THE SYSTEM SHALL 변환 없이 revenue 원 단위 값 그대로 공통 시트 F4에 기록한다.
  - *근거*: `excel/common_sheet.py:119-121` `_thousand()` 임계값 분기 로직

- **FR-003** (event): WHEN CommonSheetWriter._write()가 실행되고 confirmed_fields.profit이 존재하며 abs(profit) >= 100,000이면, THE SYSTEM SHALL `round(profit / 1000)` 값을 공통 시트 P4에 기록한다(천원 단위).
  - *근거*: `excel/common_sheet.py:125-126` `write_cell("P4", _thousand(profit, 100_000), ...)`

- **FR-003b** (unwanted): IF CommonSheetWriter._write()가 실행되고 confirmed_fields.profit이 존재하는데 abs(profit) < 100,000이면, THEN THE SYSTEM SHALL 변환 없이 profit 원 단위 값 그대로 공통 시트 P4에 기록한다.
  - *근거*: `excel/common_sheet.py:119-121` `_thousand(val, threshold)` 임계값 분기 로직; threshold=100_000

- **FR-004** (event): WHEN CoverSheetWriter._write()가 실행되고 confirmed_fields.project_period.start가 존재하면, THE SYSTEM SHALL 시작일을 datetime 객체로 변환하여 공통 시트 col+125에 기록한다.
  - *근거*: `excel/cover_sheet.py:38-42` `write_cell(f"{col}125", _to_date(start), ...)`

- **FR-005** (event): WHEN CoverSheetWriter._write()가 실행되고 confirmed_fields.project_period.end가 존재하면, THE SYSTEM SHALL 종료일을 datetime 객체로 변환하여 공통 시트 col+126에 기록한다.
  - *근거*: `excel/cover_sheet.py:43-44` `write_cell(f"{col}126", _to_date(end), ...)`

- **FR-006** (unwanted): IF 공통 시트 E3(사업명)이 confirmed_fields.project_name과 불일치하면, THEN THE SYSTEM SHALL 검증 오류를 오류 목록에 추가하고 갑지 검증을 실패로 기록한다.
  - *근거*: `reviewer.py:449-456` `_verify_cover_sheet()` E3 검증 로직

- **FR-007** (unwanted): IF 공통 시트 F4(매출액)의 값이 confirmed_fields.revenue를 천원 단위로 변환한 값과 1(천원) 초과 차이가 있으면, THEN THE SYSTEM SHALL 검증 오류를 오류 목록에 추가한다.
  - *근거*: `reviewer.py:423-433` `abs(actual_revenue - expected_rev) > 1`

- **FR-008** (unwanted): IF 공통 시트 P4(영업이익)의 값이 confirmed_fields.profit을 천원 단위로 변환한 값과 1(천원) 초과 차이가 있으면, THEN THE SYSTEM SHALL 검증 오류를 오류 목록에 추가한다.
  - *근거*: `reviewer.py:436-447` `abs(actual_profit - expected_profit) > 1`

- **FR-009** (unwanted): IF confirmed_fields.revenue, cost, profit, contract.rates가 모두 존재하는데 영업이익 역산값(revenue - cost - overhead)과 cf.profit의 차이가 max(abs(revenue)×0.01, 1,000)을 초과하면, THEN THE SYSTEM SHALL 영업이익 역산 불일치 오류를 보고한다. 여기서 overhead는 revenue × (indirect_rate + admin_rate)로 산출한다(`[잠정, 코드 현행값]` — `reviewer.py:473-484`, `company_standards.py:28-29`).
  - *근거*: `reviewer.py:473-484` 영업이익 역산 검증 블록

- **FR-010** (state): WHILE contract.revision >= 1인 동안, THE SYSTEM SHALL 각 차수(0차~현재 차수 포함)에 대해 공통 시트의 계약금액 행(col+135~138)에 해당 "(N차)" 집행예산집계표를 참조하는 수식을 삽입한다.
  - *근거*: `excel/common_sheet.py:334-348` `if revision >= 1` 수식 삽입 루프 — H열 참조(계약금액)

- **FR-010b** (state): WHILE contract.revision >= 1인 동안, THE SYSTEM SHALL 각 차수(0차~현재 차수 포함)에 대해 공통 시트의 집행계획 행(col+141~144)에 해당 "(N차)" 집행예산집계표를 참조하는 수식을 삽입한다.
  - *근거*: `excel/common_sheet.py:334-348` `if revision >= 1` 수식 삽입 루프 — L열 참조(집행계획)

- **FR-011** (state): WHILE contract.revision >= 1인 동안, THE SYSTEM SHALL 공통 시트 col+148에 `='{N차}집행예산집계표'!L42*1000` 수식을 삽입한다.
  - *근거*: `excel/common_sheet.py:349-353` 영업이익 수식 삽입

- **FR-011b** (state): WHILE contract.revision >= 1인 동안, THE SYSTEM SHALL 공통 시트 col+149에 `='{N차}집행예산집계표'!M42/100` 수식을 삽입한다.
  - *근거*: `excel/common_sheet.py:349-353` 영업이익% 수식 삽입

- **FR-012** (unwanted): IF project_period.start 또는 project_period.end 중 하나라도 존재하는데 해당 공통 시트 셀(col+125 또는 col+126)이 None이면, THEN THE SYSTEM SHALL 기간 미입력 오류를 보고한다.
  - *근거*: `reviewer.py:458-470` 기간 입력 여부 검증

- **FR-013** (event): WHEN CoverSheetWriter._write()가 이전 차수(prev_revisions) 데이터와 함께 실행되면, THE SYSTEM SHALL 각 이전 차수의 시작일·종료일·사업범위·특기사항을 해당 차수 열(prev_col+125, +126, +129, +134)에 기록한다.
  - *근거*: `excel/cover_sheet.py:52-75` prev_revisions 루프

---

## Success Criteria (측정형)

- **SC-001**: confirmed_fields.revenue가 존재하는 모든 계약에서, 공통 시트 F4의 값이 `round(revenue / 1000)`(천원)과의 차이가 **1 이하**이어야 한다(1원 정밀도 검증, 천원 단위 내 오차 허용 없음).
  - *근거*: `reviewer.py:427` `abs(actual_revenue - expected_rev) > 1` 임계

- **SC-002**: confirmed_fields.profit이 존재하는 모든 계약에서, 공통 시트 P4의 값이 `round(profit / 1000)`(천원)과의 차이가 **1 이하**이어야 한다.
  - *근거*: `reviewer.py:440` `abs(actual_profit - expected_profit) > 1` 임계

- **SC-003**: revision >= 1인 계약에서, 공통 시트의 수식 삽입 셀(col+135~138, col+141~144, col+148~149)은 **100%** 수식 문자열(= 로 시작)로 기록되어야 한다. 숫자값 직접 기록 시 FAIL.
  - *근거*: `excel/common_sheet.py:343-353` 수식 삽입 패턴

- **SC-004**: project_period.start·end가 모두 존재하는 계약에서, 공통 시트 col+125·col+126은 **None이 아닌** datetime 값으로 기록되어야 한다.
  - *근거*: `excel/cover_sheet.py:39-44`, `reviewer.py:461-467`

- **SC-005**: 영업이익 역산 검증(FR-009)에서, revenue·cost·profit·rates 모두 존재하는 경우 역산 오차가 `[잠정, 코드 현행값] max(abs(revenue) × 0.01, 1,000)` 이내이어야 한다. 해당 임계값은 `reviewer.py:478` 코드 현행값을 단일 출처로 하며, 별도 권위 문서 미확정.
  - *근거*: `reviewer.py:478` 임계값 표현식


---

## Key Entities

| 엔티티 | 정의 | 코드 근거 |
|--------|------|-----------|
| `SprintContract.confirmed_fields` | 사업명·기간·매출액·영업이익 등 확정 필드 | `models.py` |
| `SprintContract.revision` | 현재 차수(0=0차, 1=1차 …) | `models.py` |
| `SprintContract.prev_revisions` | 이전 차수 데이터 dict | `models.py` |
| `SprintContract.rates` | 간접비·일반관리비·보험 요율 집합 | `models.py` |
| `CommonSheetWriter` | 공통 시트 마스터 데이터 기록 — F4/P4/col+n 셀 | `excel/common_sheet.py:69` |
| `CoverSheetWriter` | 갑지용 공통 시트 날짜·범위·특기사항 기록 | `excel/cover_sheet.py:28` |
| `_verify_cover_sheet()` | Reviewer 4단계: 갑지 집계 무결성 검증 | `reviewer.py:408` |
| `rev_col(revision)` | 차수 → 열 문자 변환 (E=0차, F=1차, …, P=11차) | `excel/utils.py:6-8` |
| `_thousand(val, threshold)` | 원 단위 → 천원 단위 변환 | `excel/common_sheet.py:119-121` |
| `_calc_period_ratios()` | 공사 기간 → 정산누계/당기/이후 비율 산출 | `excel/common_sheet.py:16-63` |

---

## Assumptions

- **[잠정] 천원 단위 변환 임계**: `abs(val) >= 1,000,000(원)`이면 천원 변환, 미만이면 원 단위 그대로. `[잠정, 코드 현행값]` — `excel/common_sheet.py:119-121`. 영업이익 임계는 `100,000(원)`.
- **[잠정] 차수-열 매핑**: E=0차, F=1차, …, P=11차(최대 12차수). `[잠정, 코드 현행값]` — `excel/utils.py:7`.
- **[잠정] 갑지 시트명**: "0. 집행계획(갑지)". `[잠정, 코드 현행값]` — `orchestrator.py:37`.
- **[잠정] 공통 시트명**: "공통". `[잠정, 코드 현행값]` — `excel/common_sheet.py:70`, `excel/cover_sheet.py:29`.
- **[잠정] 견적품의 고정 규칙**: revision >= 1에서 매출액(F4)·영업이익(P4)은 0차 prev_revisions 값으로 고정. `[잠정, 코드 현행값]` — `excel/common_sheet.py:91-132` 주석 "견적품의는 최초 1회".
- **[잠정] 수정집행 집계표 행 매핑**: 계약금액 rows {135:10, 136:13, 137:19, 138:22}, 집행계획 rows {141:10, 142:13, 143:19, 144:22}. `[잠정, 코드 현행값]` — `excel/common_sheet.py:342-347`.
- **[잠정] 수식 셀 보호**: SheetWriter.write_cell()은 data_type=="f"인 셀(수식 셀)은 덮어쓰지 않는다. `[잠정, 코드 현행값]` — `excel/base.py:87-88`.
- 갑지 셀(0. 집행계획(갑지) 시트)은 수식으로만 표현되어 있어 Python 코드에서 직접 값 읽기 불가. Reviewer는 공통 시트 원본값 대조로 검증한다 — `reviewer.py:415` 주석.

---

## Clarifications Retained

> 설계 §6-1 기준으로 EXE-10에 직접 해당하는 충돌 항목.

1. **간접·일반관리비율 문서 근거** (설계 §6-1 항목 4): 영업이익 역산(FR-009) 시 사용되는 `contract.rates.indirect_rate + admin_rate`의 값이 코드에서 `company_standards.py:28-29` 기본값(간접 1.9%·관리 3.0%)으로 초기화되나, 공문 근거가 "윤지민과장 25년 기준" 주석뿐. 해당 요율의 권위 출처 미확정이므로 `[NEEDS CLARIFICATION]`.
   - 충돌 출처: `company_standards.py:28-29` 1.9%/3.0% / 공문 없음(주석만)

2. **보험 요율 이원화** (설계 §6-1 항목 3): `contract.rates`에 포함되는 국민연금·건강보험·산재보험·고용보험 요율이 `excel/common_sheet.py:194-208` 요율 행(17~22)에 기록되나, 집행 vs 정산 이원화(`REPORT_eps_values.md:174-180`)로 적용 기준연도·갱신정책 미확정. `[NEEDS CLARIFICATION]`.
   - 충돌 출처: `REPORT_eps_values.md:174-180` 집행 4.75/4.0674/0.796% vs 정산 4.5/4.0041/0.766%

3. **갑지 수식 셀 목록 완전성**: `cover_sheet.py` 주석 "E127/E128 수식이 참조"가 언급되나 해당 행의 수식 내용이 코드에서 직접 확인되지 않음. 템플릿 xlsx 열람으로 확인 필요. `[NEEDS CLARIFICATION]`.

4. **갑지 수식 체인 검증 대상 셀 범위** (구 SC-006): 행 127~149 중 수식 셀과 입력 셀의 정확한 분류, 및 수식 체인 전체 단계 수 — `cover_sheet.py` 주석에 "E127/E128 수식이 참조"가 언급되나 E127·E128의 수식 내용이 코드에서 직접 확인되지 않음. 측정형 SC 확정 전 템플릿 xlsx 파일 직접 열람 필요. `[NEEDS CLARIFICATION]`.
