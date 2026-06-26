# Feature Specification: Reviewer 결정론 5단계

**Feature Branch**: `EXE-15-reviewer-deterministic`  **Created**: 2026-06-26  **Status**: Draft
**Input**: 집행계획서 워크북과 SprintContract를 입력받아 5단계 결정론적 금액 검증을 수행하고, 단계별 pass/fail + 종합 verdict를 반환한다.

---

## 작성 규칙 준수 선언

- 모든 FR: EARS 5패턴 중 하나, 한 FR = 한 동작
- 모든 수치: 단일 출처 명기. 충돌 시 [NEEDS CLARIFICATION]
- 모호어("should/적절히/가능하면") 금지
- 범위 밖(파일 CRUD·편집잠금·챗봇·AI 의미검증 EXE-16·관측성) 미포함

---

## User Scenarios & Testing

### User Story P1 — Executor 입력값의 1원 정밀도 자동 교차검증 (Priority: P1)

집행계획서 작성 파이프라인에서 Executor가 xlsx 워크북에 값을 기입한 직후, Reviewer는 그 결과를 독립적으로 교차 검증해야 한다. Reviewer는 Executor의 reasoning/notes를 받지 않고, SprintContract 데이터 + 워크북 셀 값만으로 수수료구조·충돌해결·산출내역서·갑지·기본정보의 5단계를 순서대로 결정론적으로 검증한다. 어느 단계에서든 1원 초과 오차 또는 역마진이 발견되면 해당 단계는 FAIL로 기록된다.

- **Independent Test**: 알려진 오류(역마진 행, 1원 초과 오차)를 포함한 테스트 워크북으로 `run_review()`를 호출해 verdict가 `needs_revision` 또는 `rejected`이고 오류 목록에 해당 행 정보가 포함되는지 확인한다.
- **Acceptance (Given/When/Then)**:
  1. **Given** 유효한 SprintContract와 Executor가 기입을 완료한 openpyxl Workbook이 있고, **When** `run_review(contract, step_results, wb)`가 호출되면, **Then** ReviewResult가 반환되고 `verdict`는 `"approved"` / `"needs_revision"` / `"rejected"` 중 하나이다.
  2. **Given** 수수료 시트 행에서 집행단가(L열) > 계약단가(I열)인 역마진이 존재할 때, **When** `run_review()`가 호출되면, **Then** `constraint_violations`에 해당 행과 "역마진" 메시지가 포함되고 `margin_structure_ok`가 `False`이다.
  3. **Given** constraint_violations가 0건이고 avg_score가 0.85 이상일 때, **When** `run_review()`가 호출되면, **Then** `verdict`가 `"approved"`이다. [공식 코드: `reviewer.py:594`, `harness/verifier_rules.json: verdict_thresholds.approved=0.85`] (커버 FR: FR-022b)
  4. **Given** 평균 점수가 0.60 이상 0.85 미만일 때, **When** `run_review()`가 호출되면, **Then** `verdict`가 `"needs_revision"`이다. [공식 코드: `harness/verifier_rules.json: verdict_thresholds.needs_revision=0.60`]
  5. **Given** 평균 점수가 0.60 미만일 때, **When** `run_review()`가 호출되면, **Then** `verdict`가 `"rejected"`이다.

### User Story P2 — 수정집행(차수 시트)에서도 동일 검증 적용 (Priority: P2)

차수가 1 이상인 수정집행 워크북에서는 "5-4. 수수료산출내역 (N차)" 형식의 시트명이 사용된다. Reviewer는 차수 접미사를 인식해 최신 차수 시트를 선택하고 동일한 5단계 검증을 수행해야 한다.

- **Independent Test**: 차수=1인 워크북(`"5-4. 수수료산출내역 (1차)"` 시트 존재)으로 `run_review()`를 호출해 오류 없이 Stage 1 검증이 완료되는지 확인한다.
- **Acceptance (Given/When/Then)**:
  1. **Given** 워크북에 `"5-4. 수수료산출내역 (N차)"` 시트만 존재하고 SprintContract.revision이 N일 때, **When** `_resolve_sheet(wb, "5-4. 수수료산출내역", contract)`가 호출되면, **Then** 해당 차수 시트가 반환되고 오류 없이 셀 값을 읽는다. [공식 코드: `reviewer.py:43-67 _resolve_sheet`]

### User Story P3 — 충돌 미해결 시 검증 FAIL (Priority: P1)

견적서 충돌(유형 A/A'/B/C/D) 중 user_choice가 설정되지 않은 항목이 있으면 Reviewer는 해당 충돌을 FAIL로 기록해야 한다.

- **Acceptance (Given/When/Then)**:
  1. **Given** SprintContract.conflict_resolutions에 `user_choice=None`인 항목이 있을 때, **When** `run_review()`가 호출되면, **Then** Stage 2 결과의 `resolved_ok`가 `False`이고 "미해결 충돌" 메시지가 오류 목록에 포함된다. [공식 코드: `reviewer.py:264-265`]

### Edge Cases

- 워크북에서 수식 셀은 data_only=False 모드에서 값이 None임 — 산출내역서 시트 직접 합산 대신 공통 시트 원본값과 SprintContract 데이터를 대조한다. [공식 코드: `reviewer.py:306-316` 주석]
- 수수료 항목이 0건인 경우 Stage 1 ok_count/total 계산에서 ZeroDivisionError 방지 — `max(ok_count + len(errors), 1)` 처리. [공식 코드: `reviewer.py:226`]
- 영업이익 역산 오차 허용: `max(abs(revenue) * 0.01, 1000)` — [NEEDS CLARIFICATION: 1% 또는 1,000원 허용의 기준 문서 출처 없음. 코드 단일 출처: `reviewer.py:478`]
- 한글 NFC 정규화: 시트명 분해/결합 차이를 `unicodedata.normalize("NFC")` 로 흡수한다. [공식 코드: `reviewer.py:49-52`]

---

## Functional Requirements (EARS)

### Stage 1: 수수료 구조 검증

- **FR-001a** (ubiquitous): THE SYSTEM SHALL 수수료 시트의 각 행에 대해 계약금액(H열×I열 또는 J열 직접입력)과 SprintContract.fee_items[i].contract_amount의 차이를 계산한다. [공식 코드: `reviewer.py:169-175`, `harness/verifier_rules.json: stages.1_fee_structure.checks[0].tolerance=1`]

- **FR-001b** (unwanted): IF 수수료 시트 행의 계산된 계약금액 차이가 1원을 초과하면, THEN THE SYSTEM SHALL 해당 행을 계약금액 오류로 기록한다. [공식 코드: `reviewer.py:169-175`, `harness/verifier_rules.json: stages.1_fee_structure.checks[0].tolerance=1`]

- **FR-002a** (ubiquitous): THE SYSTEM SHALL 수수료 시트의 각 행에 대해 집행금액(K열×L열 또는 M열 직접입력)과 SprintContract.fee_items[i].execution_amount의 차이를 계산한다. [공식 코드: `reviewer.py:179-188`, `harness/verifier_rules.json: stages.1_fee_structure.checks[1].tolerance=1`]

- **FR-002b** (unwanted): IF 수수료 시트 행의 계산된 집행금액 차이가 1원을 초과하면, THEN THE SYSTEM SHALL 해당 행을 집행금액 오류로 기록한다. [공식 코드: `reviewer.py:179-188`, `harness/verifier_rules.json: stages.1_fee_structure.checks[1].tolerance=1`]

- **FR-003** (unwanted): IF 수수료 시트 행의 집행단가(L열)가 계약단가(I열)보다 크고 계약단가가 0보다 클 때, THEN THE SYSTEM SHALL 해당 행을 역마진 오류로 기록한다. [공식 코드: `reviewer.py:192-193`]

- **FR-004** (optional): WHERE SprintContract.fee_items[i].current_period_qty가 0보다 클 때, THE SYSTEM SHALL Q열 당기수량과 SprintContract 값의 차이가 0.01을 초과하면 오류로 기록한다. [공식 코드: `reviewer.py:196-199`, `harness/verifier_rules.json: stages.1_fee_structure.checks[3].tolerance=0.01`]

- **FR-005** (unwanted): IF 프로젝트 시작연도와 종료연도가 다른 다년도 사업인데 당기수량(Q열)이 전체수량(execution_qty)과 같거나 크면, THEN THE SYSTEM SHALL 연도분리 오류로 기록한다. [공식 코드: `reviewer.py:202-209`]

- **FR-006** (unwanted): IF 단년도 사업인데 당기수량(Q열)이 전체수량(execution_qty)보다 작으면, THEN THE SYSTEM SHALL 연도분리 오류로 기록한다. [공식 코드: `reviewer.py:210-212`]

- **FR-007** (unwanted): IF SprintContract.fee_items[i].contract_qty와 수수료 시트 H열 셀값의 차이가 0.01을 초과하면, THEN THE SYSTEM SHALL 계약수량 불일치 오류로 기록한다. [공식 코드: `reviewer.py:221-223`]

- **FR-008** (unwanted): IF SprintContract.fee_items[i].contract_unit_price와 수수료 시트 I열 셀값의 차이가 1원을 초과하면, THEN THE SYSTEM SHALL 계약단가 불일치 오류로 기록한다. [공식 코드: `reviewer.py:224`]

### Stage 2: 충돌 해결 검증

- **FR-009** (unwanted): IF SprintContract.conflict_resolutions에 user_choice가 None인 항목이 있으면, THEN THE SYSTEM SHALL 해당 항목을 "미해결 충돌" 오류로 기록한다. [공식 코드: `reviewer.py:263-265`]

- **FR-010** (unwanted): IF SprintContract.conflict_resolutions에 user_choice가 있으나 resolved_value가 None인 항목이 있으면, THEN THE SYSTEM SHALL "충돌 해결값 누락" 오류로 기록한다. [공식 코드: `reviewer.py:267-269`]

### Stage 3: 산출내역서 교차 검증

- **FR-011a** (ubiquitous): THE SYSTEM SHALL staff_plan에서 type="직접"인 인원의 monthly_rate×월별 M/M 합계를 expected_salary로 산출한다. [공식 코드: `reviewer.py:315-328`, `harness/verifier_rules.json: stages.3_breakdown.checks[0].tolerance=1`]

- **FR-011b** (unwanted): IF expected_salary와 공통 시트 급료 행의 셀값의 차이가 1원을 초과하면, THEN THE SYSTEM SHALL 급료 합계 오류로 기록한다. [공식 코드: `reviewer.py:315-328`, `harness/verifier_rules.json: stages.3_breakdown.checks[0].tolerance=1`]

- **FR-012a** (ubiquitous): THE SYSTEM SHALL 수수료 시트 집행금액(M열 직접입력 또는 K×L) 합계와 SprintContract.fee_items 합계의 차이를 계산한다. [공식 코드: `reviewer.py:331-354`, `harness/verifier_rules.json: stages.3_breakdown.checks[1].tolerance=1`]

- **FR-012b** (unwanted): IF 수수료 교차검증의 차이가 1원을 초과하면, THEN THE SYSTEM SHALL 수수료 교차검증 오류로 기록한다. [공식 코드: `reviewer.py:331-354`, `harness/verifier_rules.json: stages.3_breakdown.checks[1].tolerance=1`]

- **FR-013** (optional): WHERE SprintContract.rates가 존재하고 expected_salary가 0보다 클 때, THE SYSTEM SHALL 공통 시트 보험료 요율 셀(국민연금·건강보험·산재보험·고용보험)과 contract.rates의 차이가 0.0001을 초과하면 보험료 오류로 기록한다. [공식 코드: `reviewer.py:359-388`, `harness/verifier_rules.json: stages.3_breakdown.checks[2].tolerance=0.0001`] [NEEDS CLARIFICATION: 헌법 §IV는 '보험료 검증 오차 1,000원 이상 FAIL'(금액 단위)로 정의하나, 본 FR-013은 '요율 차이 0.0001 초과 시 FAIL'(소수점 요율 단위)을 정의한다. 동일 보험료 검증 대상에 대해 단위·접근방식·임계가 상이하여 충돌 발생. 충돌 출처: constitution.md §IV vs harness/verifier_rules.json stages.3_breakdown.checks[2].tolerance. 운영팀/FDE 확인 필요.]

- **FR-014** (unwanted): IF active_items에서 비활성(False)인 비목의 공통 시트 셀값이 0이 아니면, THEN THE SYSTEM SHALL 비활성 비목 오류로 기록한다. [공식 코드: `reviewer.py:391-394`]

### Stage 4: 갑지 검증

- **FR-015** (unwanted): IF 공통 시트 F4(매출액, 천원)와 confirmed_fields.revenue의 차이가 1원을 초과하면, THEN THE SYSTEM SHALL 매출액 오류로 기록한다. [공식 코드: `reviewer.py:425-432`]

- **FR-016** (unwanted): IF 공통 시트 P4(영업이익, 천원)와 confirmed_fields.profit의 차이가 1원을 초과하면, THEN THE SYSTEM SHALL 영업이익 오류로 기록한다. [공식 코드: `reviewer.py:436-444`] [NEEDS CLARIFICATION: SC-008 및 Edge Cases는 'max(abs(revenue)*0.01, 1000) 이내 차이는 WARN 처리, FAIL 아님'으로 더 넓은 허용 임계를 정의한다. 본 FR-016의 1원 임계와 SC-008의 동적 임계가 동일 검증 대상(영업이익)에 대해 충돌. 충돌 출처: FR-016(1원 임계) vs SC-008/reviewer.py:478(max 공식). 운영팀/FDE 확인 필요.]

- **FR-016b** (unwanted): IF 공통 시트 P4(영업이익, 천원)와 confirmed_fields.profit의 차이가 `max(abs(revenue) * 0.01, 1000)` 이하이면, THEN THE SYSTEM SHALL 해당 차이를 FAIL로 기록하지 않는다. [NEEDS CLARIFICATION: 허용 공식의 기준 문서 출처 없음. 단일 코드 출처: `reviewer.py:478`. FR-016의 1원 임계와 본 FR-016b의 동적 임계가 충돌. 충돌 출처: FR-016(1원) vs FR-016b/reviewer.py:478(max 공식). 권위 문서 확인 필요.]

- **FR-017** (unwanted): IF 공통 시트 E3(사업명)이 confirmed_fields.project_name과 일치하지 않으면, THEN THE SYSTEM SHALL 갑지 참조원본-사업명 오류로 기록한다. [공식 코드: `reviewer.py:450-456`]

- **FR-018** (unwanted): IF confirmed_fields.project_period.start와 end가 존재하는데 공통 시트 {col}125 또는 {col}126 셀이 None이면, THEN THE SYSTEM SHALL 기간 미입력 오류로 기록한다. [공식 코드: `reviewer.py:460-469`]

### Stage 5: 기본정보 검증

- **FR-019a** (ubiquitous): THE SYSTEM SHALL project_name·client·contractor·contract_type·pm·sales_owner·written_date의 7개 필드에 대해 공통 시트 셀값과 confirmed_fields 값을 정규화 후 문자열 비교한다. [공식 코드: `reviewer.py:507-530`, `harness/verifier_rules.json: stages.5_basic_info.checks[0].fields`]

- **FR-019b** (unwanted): IF 정규화 후 문자열 비교에서 불일치가 있으면, THEN THE SYSTEM SHALL 해당 필드명과 함께 오류로 기록한다. [공식 코드: `reviewer.py:507-530`, `harness/verifier_rules.json: stages.5_basic_info.checks[0].fields`]

### 판정 및 공통

- **FR-020** (ubiquitous): THE SYSTEM SHALL 5단계 각 스테이지의 점수(ok_count/total)를 산술평균하여 avg_score를 산출한다. [공식 코드: `reviewer.py:578-585`]

- **FR-021** (unwanted): IF avg_score가 0.85 미만이고 0.60 이상이면, THEN THE SYSTEM SHALL verdict를 `"needs_revision"`으로 설정한다. [공식 코드: `reviewer.py:594-599`, `harness/verifier_rules.json: verdict_thresholds`]

- **FR-021b** (unwanted): IF constraint_violations가 1건 이상이면, THEN THE SYSTEM SHALL verdict를 `"approved"`로 설정하지 않는다. [공식 코드: `reviewer.py:594`, `harness/verifier_rules.json: verdict_thresholds`]

- **FR-022** (unwanted): IF avg_score가 0.60 미만이면, THEN THE SYSTEM SHALL verdict를 `"rejected"`로 설정한다. [공식 코드: `reviewer.py:597-599`]

- **FR-022b** (unwanted): IF constraint_violations가 0건이고 avg_score가 0.85 이상이면, THEN THE SYSTEM SHALL verdict를 `"approved"`로 설정한다. [공식 코드: `reviewer.py:594`, `harness/verifier_rules.json: verdict_thresholds.approved=0.85`]

- **FR-023a** (ubiquitous): THE SYSTEM SHALL 5단계 검증을 Stage 1→2→3→4→5 순서대로 실행한다. [공식 코드: `reviewer.py:560-564 run_review`]

- **FR-023b** (ubiquitous): THE SYSTEM SHALL 이전 단계 실패와 무관하게 5단계 전체를 완료한다. [공식 코드: `reviewer.py:560-564 run_review`]

- **FR-024** (ubiquitous): THE SYSTEM SHALL Executor의 reasoning/notes를 검증 입력으로 사용하지 않고, SprintContract의 confirmed_fields·fee_items·rates·staff_plan·conflict_resolutions와 xlsx 셀값만을 검증 근거로 사용한다. [공식 코드: `reviewer.py:1-17` 모듈 docstring]

- **FR-025** (optional): WHERE 차수(revision)가 1 이상인 수정집행이면, THE SYSTEM SHALL `_resolve_sheet(wb, base_name, contract)`로 "base_name (N차)" 형식의 시트명을 NFC 정규화 후 선택한다. [공식 코드: `reviewer.py:43-67`]

---

## Success Criteria (측정형)

- **SC-001**: Stage 1 역마진 검출 — 집행단가 > 계약단가인 행을 **100%** 오류로 기록한다. (허용 누락 0건) [공식 코드: `reviewer.py:192-193`]

- **SC-002**: 1원 정밀도 — 계약금액·집행금액·급료합계·수수료 교차 금액 검증의 허용 오차는 **1원** 이하. 1원 초과 시 FAIL. [공식 코드: `harness/verifier_rules.json: precision=1`]

- **SC-003**: 보험료 요율 검증 허용 오차 — 요율(소수점 표현) 차이 **0.0001 이하**. 초과 시 FAIL. [공식 코드: `harness/verifier_rules.json: stages.3_breakdown.checks[2].tolerance=0.0001`] [NEEDS CLARIFICATION: 헌법 §IV는 '보험료 검증 오차 1,000원 이상 FAIL'(금액 단위)로 정의하나, 본 SC-003은 요율 단위(0.0001) 임계를 사용한다. 동일 보험료 검증 대상에 대해 단위·임계가 상이하여 충돌. 충돌 출처: constitution.md §IV vs SC-003/FR-013. 운영팀/FDE 확인 필요.]

- **SC-004**: 당기수량 검증 허용 오차 — **0.01** 이하. 초과 시 FAIL. [공식 코드: `harness/verifier_rules.json: stages.1_fee_structure.checks[3].tolerance=0.01`]

- **SC-005**: verdict 임계 — avg_score **≥ 0.85** → `"approved"`, **≥ 0.60** → `"needs_revision"`, **< 0.60** → `"rejected"`. [공식 코드: `harness/verifier_rules.json: verdict_thresholds`]

- **SC-006**: 차수 시트 해석 — 차수가 1~11인 수정집행 워크북에서 `_resolve_sheet()`가 정확한 최신 차수 시트를 **100%** 선택한다. [공식 코드: `reviewer.py:43-67`]

- **SC-007**: 정보 장벽 — `run_review()` 호출 시 Executor reasoning/notes 필드를 검증 입력으로 사용하는 코드 경로가 **0건**이어야 한다(코드 정적 검증). [공식 코드: `reviewer.py:97-104` `_ai_semantic_review` 주석]

- **SC-008**: (FR-016b 참조) 영업이익 역산 WARN 허용 임계는 FR-016b에서 정의한다.

---

## Key Entities

| 엔티티 | 정의 | 출처 |
|--------|------|------|
| `SprintContract` | 검증 대상 계약 데이터 (ConfirmedFields·fee_items·rates·staff_plan·conflict_resolutions 포함) | `backend/models/sprint_contract.py:159` |
| `ReviewResult` | verdict·score·amount_verification·basic_info_verification·constraint_violations·issues 포함 반환값 | `backend/models/sprint_contract.py` (models) |
| `StepResult` | Executor 각 단계 출력 (inputs_used 목록 포함) | `backend/models/sprint_contract.py` |
| `InputUsed` | 셀 좌표·값·소스·계산 근거를 가지는 입력 추적 레코드 | `backend/models/sprint_contract.py:184` |
| `FeeItem` | 수수료 행 1건(계약/집행 수량·단가·금액·당기수량 포함) | `backend/models/sprint_contract.py:59` |
| `RateSet` | 보험료·간접·관리비 요율 집합 | `backend/models/sprint_contract.py:129` |
| `ConfirmedFields` | 사용자 확정 기본정보(사업명·발주처·기간·수익성 등) | `backend/models/sprint_contract.py:16` |
| `ConflictResolution` | 견적서 충돌 1건(type·description·user_choice·resolved_value) | `backend/models/sprint_contract.py:51` |
| `verifier_rules.json` | 검증 임계·허용 오차 선언 (`harness/` 디렉토리) | `harness/verifier_rules.json` |
| `cell_map.json` | 공통 시트 셀 행번호 상수 (labor.salary_row 등) | `harness/cell_map.json` |

---

## Assumptions

- 간접비율 **1.9%**·일반관리비율 **3.0%** (코드 현행값=잠정, 권위 문서 미확정) [공식 코드: `backend/services/company_standards.py:28-29`]
- 수수료 시트 데이터 행 범위 기본값: DATA_START_ROW=8, DATA_END_ROW=16, FEE_TOTAL_ROW=17 (`harness/cell_map.json` 없을 때 fallback) [공식 코드: `reviewer.py:37`]
- 공통 시트 노무비 행 기본값: LABOR_SALARY_ROW=25, LABOR_BONUS_ROW=31, LABOR_WAGE_ROW=38 (fallback) [공식 코드: `reviewer.py:294`]
- 보험료 요율 행 기본값: 국민연금=19, 건강보험=20, 산재보험=21, 고용보험=22 (fallback) [공식 코드: `reviewer.py:371-374`]
- 매출액·영업이익 단위 변환: `value >= 1,000,000`이면 천원 단위로 `round(value/1000)` 적용 [공식 코드: `reviewer.py:426-427`]
- MAX_REVISION=11 (집행서 템플릿 양식 한계) [공식 코드: `backend/services/company_standards.py:12`]
- EXE-15는 결정론적 검증만 담당하며, AI 의미 검증(Bedrock 호출)은 EXE-16으로 분리된다. [공식 설계: `docs/superpowers/specs/2026-06-26-집행서-SDD-design.md §3`]

---

## Clarifications Retained

[NEEDS CLARIFICATION] 항목(강제):

1. **영업이익 역산 WARN 허용 공식 + FR-016 임계 충돌** — 코드 `reviewer.py:478`의 `max(abs(revenue) * 0.01, 1000)` 기준(1% 또는 1,000원 중 큰 값)의 권위 문서 출처가 없음. FR-016의 1원 임계와 FR-016b의 동적 임계가 동일 검증 대상에서 충돌. 충돌 출처: FR-016(1원) vs FR-016b/reviewer.py:478(max 공식). 운영팀 확인 필요.
   - 현재 코드 단일 출처: `reviewer.py:478` (WARN 처리, FAIL 아님)
   - 확인 방법: 집행계획서 작성 규칙 문서 또는 FDE 인터뷰

2. **수수료 코드 1/2/3 정량 판단 기준** — 설계 §6-1 항목 5번. `planner.md`에 "[추측] 가능"으로만 표현됨. 코드 `sprint_contract.py:61 FeeItem.code` 기본값=1이나 판단 기준 미명시.
   - 충돌 출처: `planner.md` (추측 표기) vs 코드 기본값 1
   - 확인 방법: 수수료 코드 분류 기준 문서 또는 FDE 인터뷰

3. **보험료 요율 갱신 정책·적용 연도** — 집행 4.75/4.0674/0.796% vs 정산 4.5/4.0041/0.766% (설계 §6-1 항목 3번)
   - 충돌 출처: `REPORT_eps_values.md:174-180` 이원화 데이터
   - 확인 방법: 연도별 보험요율 고시 문서 또는 FDE 인터뷰
   - 본 EXE-15 스펙에서는 "contract.rates에서 넘어온 값을 그대로 검증에 사용"하는 구조로 처리. 요율값 자체는 EXE-03 스펙 권역.

4. **보험료 검증 단위 충돌 (FR-013/SC-003 vs 헌법 §IV)** — 헌법 §IV: '보험료 검증 오차 1,000원 이상 FAIL'(금액 단위). FR-013·SC-003: '요율 차이 0.0001 초과 시 FAIL'(소수점 요율 단위). 동일 보험료 검증 대상에 대해 헌법과 스펙이 서로 다른 단위·임계를 정의.
   - 충돌 출처: `constitution.md §IV` vs `spec.md FR-013/SC-003`
   - 확인 방법: 운영팀/FDE 인터뷰 또는 헌법 §IV 개정
   - 해소 전까지 FR-013 및 SC-003 본문에 [NEEDS CLARIFICATION] 유지.
