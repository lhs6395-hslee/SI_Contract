# Feature Specification: EXE-06 — Sprint_Contract 생성

**Feature Branch**: `EXE-06-sprint-contract-build`
**Created**: 2026-06-26
**Status**: Draft
**Input**: 확정된 ExtractedData(추출+보정+충돌해결 완료)와 active_items 플래그를 받아, 파이프라인이 소비하는 SprintContract 객체를 결정론적으로 생성한다.

---

## User Scenarios & Testing

### User Story 1 — 단년도 사업 Sprint_Contract 생성 (Priority: P1)

프로젝트 관리자가 소스 추출·사내기준 보정·충돌 감지(EXE-02·03·05)를 완료한 확정 데이터를 제출하면, 시스템은 AI 호출 없이 결정론적으로 ConfirmedFields / FeeItem[] / BudgetItem[] / RateSet를 포함한 SprintContract를 생성하고, 파이프라인 Executor가 이를 수신해 집행계획서 시트를 채울 수 있는 상태여야 한다.

- **Independent Test**: `POST /api/pipeline/start` 에 단년도 extractedData를 전송 → 응답 status 200 + `sprint_contract.confirmed_fields.project_name` 값이 입력과 일치하는지 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 단년도 extractedData(costItems, staffPlan, rates 포함)와 revision=0이 제출된 상태, **When** `/api/pipeline/start`를 호출, **Then** SprintContract.revision=0, confirmed_fields에 projectName·projectPeriod·client 등이 매핑되고, active_items 딕셔너리가 costItems·staffPlan 존재 여부에 따라 true/false로 채워진다.

### User Story 2 — 다년도 사업 연도분리 적용 (Priority: P1)

회계연도를 걸치는 사업(예: 2025-09~2026-06)에서 costItems와 fee_items가 당기/이후1/이후2 비율로 배분되고, 관문 재확인 플래그(ConflictResolution.conflict_type="연도배분확인")가 생성되어야 한다.

- **Independent Test**: start_date=2025-09-01, end_date=2026-06-30, fiscalYear=2025인 데이터로 `build_sprint_contract` 직접 호출 → `fy_shares["current"]`·`next1`·`next2` 합이 1.0(±0.001), BudgetItem.current_amount+next1_amount+next2_amount=execution_amount.
- **Acceptance (Given/When/Then)**:
  1. **Given** 사업기간이 회계연도(2025)를 걸치는 extractedData, **When** SprintContract 생성, **Then** BudgetItem과 FeeItem 각 항목의 current_amount+next1_amount+next2_amount 합이 execution_amount와 일치(1원 오차도 FAIL)하고, conflict_resolutions에 "연도배분확인" 유형이 1건 이상 포함된다.

### User Story 3 — MAX_REVISION 초과 거부 (Priority: P1)

revision > 11 요청이 들어오면 시스템이 빌더 실행 전에 400 에러로 거부하여, 양식 열(E~P) 범위 밖 쓰기를 원천 차단해야 한다.

- **Independent Test**: revision=12로 `/api/pipeline/start` 호출 → HTTP 400, error 메시지에 "최대 11차"가 포함됨.
- **Acceptance (Given/When/Then)**:
  1. **Given** revision=12인 요청, **When** `/api/pipeline/start` 호출, **Then** HTTP 400 응답, SprintContract 생성 시도 없음, 에러 메시지에 MAX_REVISION(11) 값이 명시됨.

### User Story 4 — 급료 자동산출 및 관문 플래그 (Priority: P2)

staffPlan에 내부 인원이 있고 costItems에 labor 비목이 없을 때, 사내 직급단가표로 급료를 자동 산출하고 "급료확인" 플래그를 생성해야 한다.

- **Acceptance (Given/When/Then)**:
  1. **Given** staffPlan에 과장 1명(6M/M), costItems에 labor 없음, **When** SprintContract 생성, **Then** BudgetItem 중 category="labor"가 생성되고, conflict_resolutions에 conflict_type="급료확인"이 포함된다.

### User Story 5 — 요율 확인 플래그 무조건 생성 (Priority: P1)

요율(rates) 값이 업로드 문서에서 왔든 사내 기본값이든, conflict_resolutions에 "요율확인" 플래그가 반드시 생성되어야 한다.

- **Acceptance (Given/When/Then)**:
  1. **Given** rates 데이터 존재 여부에 무관하게, **When** SprintContract 생성, **Then** conflict_resolutions에 conflict_type="요율확인"이 정확히 1건 포함된다.

### Edge Cases

- staffPlan=[], costItems=[] 인 최소 데이터 → SprintContract 생성 성공(빈 budget_items/fee_items, active_items 전부 false).
- revision=0은 prev_revisions 빈 딕셔너리로 처리.
- fiscalYear 필드가 없을 때 startDate 연도를 fallback으로 사용 [`contract_builder.py:335 공식 코드`].
- `[NEEDS CLARIFICATION: revision > MAX_REVISION 시 main.py:729 HTTP 400과 contract_builder.py:307 ValueError 두 곳에서 각각 차단하는데, 어느 쪽이 단일 진입점(canonical gate)으로 확정되어야 하는가?]`

---

## Functional Requirements (EARS)

- **FR-001** (event): WHEN `/api/pipeline/start`에 extractedData와 revision을 수신하면, THE SYSTEM SHALL `build_sprint_contract(project_id, extracted_data, revision, prev_revisions)`를 호출하여 SprintContract를 생성한다.
  - 근거: `backend/main.py:745` [`공식 코드`]

- **FR-002** (unwanted): IF revision이 MAX_REVISION(11)을 초과하면, THEN THE SYSTEM SHALL HTTP 400을 반환하고 SprintContract 생성을 진행하지 않는다.
  - 근거: `backend/main.py:729-734`, `backend/services/company_standards.py:12 MAX_REVISION=11` [`공식 코드`]

- **FR-003** (event): WHEN extractedData의 extracted 딕셔너리를 수신하면, THE SYSTEM SHALL projectName / projectCode / projectPeriod / pm / salesOwner / writtenDate / fiscalYear / client / contractor / contractType / paymentTerms / revenue / cost / profit을 ConfirmedFields로 매핑한다.
  - 근거: `backend/services/contract_builder.py:327-349` [`공식 코드`]

- **FR-004a** (event): WHEN costItems를 수신하면, THE SYSTEM SHALL category="fee"인 항목을 FeeItem 목록으로 변환한다.
  - 근거: `backend/services/contract_builder.py:362` [`공식 코드`]

- **FR-004b** (event): WHEN costItems를 수신하면, THE SYSTEM SHALL category가 BUDGET_CATEGORIES에 속하는 항목을 BudgetItem 목록으로 집계한다.
  - 근거: `backend/services/contract_builder.py:373-409`, `contract_builder.py:21-24 BUDGET_CATEGORIES` [`공식 코드`]

- **FR-005** (unwanted): IF costItems 중 퇴직금·보험료에 해당하는 항목이 있으면, THEN THE SYSTEM SHALL 해당 항목을 BudgetItem 집계에서 제외하고 "자동계산중복" 플래그를 생성한다.
  - 근거: `backend/services/contract_builder.py:376-381` (is_auto_calculated 호출) [`공식 코드`]

- **FR-006** (unwanted): IF costItems 중 VAT/부가세 항목이 있으면, THEN THE SYSTEM SHALL 해당 항목을 BudgetItem 집계에서 제외한다.
  - 근거: `backend/services/contract_builder.py:382-384` [`공식 코드`]

- **FR-007** (state): WHILE 사업기간이 fiscal_year 회계연도 경계를 걸치는 동안, THE SYSTEM SHALL EXE-11 연도분리 엔진(`_fiscal_year_shares` / `_split_by_shares`)을 호출하여 BudgetItem과 FeeItem을 당기/이후1/이후2로 배분하고 "연도배분확인" ConflictResolution을 생성한다.
  - 근거: `backend/services/contract_builder.py:160 _fiscal_year_shares`, `:193 _split_by_shares`, `:366-406` [`공식 코드`]

- **FR-008** (unwanted): IF BudgetItem에 labor 카테고리가 없고 staffPlan에 내부 인원이 있으면, THEN THE SYSTEM SHALL 사내 직급단가표(GRADE_RATES)를 기준으로 급료를 산출하여 BudgetItem(category="labor")을 추가하고 "급료확인" ConflictResolution을 생성한다.
  - 근거: `backend/services/contract_builder.py:454-496` [`공식 코드`]

- **FR-009** (unwanted): IF labor BudgetItem이 있고 staffPlan의 사내 직급단가표 기준 합계와 1원 이상 차이가 나면, THEN THE SYSTEM SHALL "급료단가확인" ConflictResolution을 생성한다(입력값은 변경하지 않는다).
  - 근거: `backend/services/contract_builder.py:440-453` [`공식 코드`]

- **FR-010** (ubiquitous): THE SYSTEM SHALL conflict_resolutions에 "요율확인" ConflictResolution을 반드시 1건 생성한다(요율 출처가 업로드 문서이든 사내 기본값이든 무조건 생성).
  - 근거: `backend/services/contract_builder.py:630-633` [`공식 코드`]

- **FR-011a** (unwanted): IF revision > 0이면, THEN THE SYSTEM SHALL DynamoDB에서 이전 차수 데이터를 로드하여 prev_revisions에 포함한다.
  - 근거: `backend/main.py:737-744` [`공식 코드`]

- **FR-011b** (unwanted): IF revision > 0이면, THEN THE SYSTEM SHALL 이전 차수 FeeItem 목록으로부터 prev_fee_items를 생성한다.
  - 근거: `contract_builder.py:562-567` [`공식 코드`]

- **FR-012** (ubiquitous): THE SYSTEM SHALL active_items 딕셔너리를 costItems 카테고리 존재 여부·staffPlan 유무·fee_items 유무에 따라 결정론적으로 산출한다.
  - 근거: `backend/services/contract_builder.py:569-579` [`공식 코드`]

- **FR-013** (unwanted): IF revenue가 있고 비목 계약금액 합계(contract_amount 전체)가 0이면, THEN THE SYSTEM SHALL 매출 전액을 labor BudgetItem의 contract_amount에 배분하고 "계약배분확인" ConflictResolution을 생성한다.
  - 근거: `backend/services/contract_builder.py:499-510` [`공식 코드`]

- **FR-014** (event): WHEN startDate가 월 중간이고 FeeItem 단위가 "M/M" 또는 "월"이며 수량이 정수이고 확정금액(contractAmount)이 없으면, THE SYSTEM SHALL 일할계산된 수량(0.1 단위 반올림)을 적용한다.
  - 근거: `backend/services/contract_builder.py:222-250`, `_calc_prorated_qty` [`공식 코드`]

---

## Success Criteria (측정형)

- **SC-001**: `build_sprint_contract` 호출 후 SprintContract 생성 소요 시간이 AI 호출 없음을 전제로 **1초 이내**여야 한다. (결정론 함수이므로 LLM 지연 없음. 절대 상한 `[NEEDS CLARIFICATION: 실측 베이스라인 후 확정]`)
- **SC-002**: 연도분리 적용 시 BudgetItem과 FeeItem의 current_amount + next1_amount + next2_amount 합이 execution_amount와 **1원 이하 오차**로 일치해야 한다. (1원 오차도 FAIL — constitution §IV)
- **SC-003**: revision > MAX_REVISION(11) 요청은 **100%** HTTP 400 거부되어야 한다.
- **SC-004**: 모든 SprintContract 생성 시 conflict_resolutions에 "요율확인"이 **정확히 1건** 포함되어야 한다.
- **SC-005**: SprintContract의 active_items 딕셔너리는 **9개 키** 전부 포함되어야 한다 (`"재료비"`, `"노무비"`, `"외주비"`, `"경비_복리후생비"`, `"경비_보험료"`, `"경비_수수료"`, `"경비_회선비"`, `"경비_소모품비"`, `"경비_여비교통비"` — `contract_builder.py:569-579` 기준 [`공식 코드`]).
- **SC-006**: VAT/부가세·퇴직금·보험료 항목은 BudgetItem 집계에서 **0건** 포함되어야 한다.

---

## Key Entities

| 엔티티 | 위치 | 역할 |
|--------|------|------|
| `SprintContract` | `backend/models/sprint_contract.py:159` | 파이프라인 교환 형식 최상위 객체 |
| `ConfirmedFields` | `backend/models/sprint_contract.py:16` | 기본정보 필드 집합 (프로젝트명·기간·계약정보 등) |
| `FeeItem` | `backend/models/sprint_contract.py:59` | 5-4 수수료 시트 행 단위 (계약/집행/당기 분리) |
| `BudgetItem` | `backend/models/sprint_contract.py:76` | 공통 시트 비목 블록 행 (category 기준, 원 단위) |
| `RateSet` | `backend/models/sprint_contract.py:129` | 간접비/관리비/4대보험 요율 집합 |
| `ConflictResolution` | `backend/models/sprint_contract.py:51` | 빌더가 생성한 관문 플래그 (type·description·options) |
| `StaffItem` | `backend/models/sprint_contract.py:88` | 인원투입계획 행 (이름·직급·월별M/M) |
| `ScheduleItem` | `backend/models/sprint_contract.py:107` | 예정공정표 행 (공종·시작월·종료월) |
| `OrgMember` | `backend/models/sprint_contract.py:122` | 현장조직·업무분장 행 |
| `active_items` | `contract_builder.py:569-579` | 비목 활성화 플래그 딕셔너리 (9개 키) |
| `GRADE_RATES` | `company_standards.py:16` | 직급 단가표 (급료 자동산출 기준) |
| `DEFAULT_RATES` | `company_standards.py:27` | 기본 요율 (문서 추출 실패 시 fallback) |
| `MAX_REVISION` | `company_standards.py:12` | 수정집행 최대 차수 = 11 (양식 열 E~P 한계) |

---

## Assumptions

모든 항목은 코드 현행값=잠정 기재이며, 권위 출처(공문·계약서·양식 정본) 미확정 시 사용자 확인 후 재정립 필요.

1. **결정론 보장**: `build_sprint_contract`는 AI 호출이 없으며 동일 입력에 동일 출력을 보장한다. (`contract_builder.py:1` 모듈 주석 "AI 호출 없음" [`공식 코드`])
2. **MAX_REVISION = 11** (잠정): 집행계획서 양식의 차수 열 E~P = 0~11차, HLOOKUP 범위 $E$8:$P$149. (`company_standards.py:12` [`공식 코드`])
3. **작성일 기본값 = 오늘**: writtenDate 필드가 소스에 없으면 생성 당일 날짜를 사용한다. (`contract_builder.py:325` [`공식 코드`])
4. **GRADE_RATES(잠정)**: 과장 550만은 Clarifications Retained 항목 1에서 3중 충돌로 `[NEEDS CLARIFICATION]` 지정됨. 나머지 4개 직급도 동일 출처 쌍(company_standards.py vs executor.md) 간 2-way 충돌이 확인되므로 모두 `[NEEDS CLARIFICATION]` 대상이다.
   - 부장: company_standards.py=750만 vs executor.md=800만 `[NEEDS CLARIFICATION]`
   - 차장: company_standards.py=650만 vs executor.md=700만 `[NEEDS CLARIFICATION]`
   - 대리: company_standards.py=450만 vs executor.md=500만 / REPORT=550만 `[NEEDS CLARIFICATION]`
   - 사원: company_standards.py=350만 vs executor.md=450만 `[NEEDS CLARIFICATION]`
   - 현행 코드 적용값: company_standards.py 기준(잠정). 운영팀 확정 전까지 임의값 생성 금지.
5. **DEFAULT_RATES(잠정)**: 간접 1.9%/관리 3.0%/국민연금 4.5%(집행기준 4.75%와 충돌)/건강보험 4.0041%(집행기준 4.0674%와 충돌)/산재 0.766%(집행기준 0.796%와 충돌)/고용보험 1.75%. (`company_standards.py:27-34` [`공식 코드`]) — 현행값은 정산 기준 추정이나 집행 기준과 충돌. Clarifications Retained 항목 4 참조 `[NEEDS CLARIFICATION]`. "윤지민과장 문의 25년 기준" 주석 근거, 공문 경로 미확정.
6. **일할계산 분모 30일**: 시작월이 월 중간인 경우 잔여일 / 30 고정(업계 관행). (`contract_builder.py:117` 주석 [`공식 코드`])
7. **fiscalYear fallback**: extracted에 fiscalYear 없으면 startDate 연도를 사용. (`contract_builder.py:335` [`공식 코드`])
8. **VAT 방어**: 공급가액 기준 원칙. 모든 금액에서 VAT/부가세 항목 자동 제외. (`contract_builder.py:382-384` [`공식 코드`])

---

## Clarifications Retained

아래 항목은 설계 §6-1(강제 `[NEEDS CLARIFICATION]`)에서 이월한 미해결 충돌로, 운영팀(FDE) 인터뷰로 확정 전까지 임의값 생성 금지.

1. **직급 단가표 2중 이상 충돌 (전 직급)** `[NEEDS CLARIFICATION]`
   - 과장 3중 충돌:
     - 출처 A: `backend/services/company_standards.py:19` — 5,500,000원/월
     - 출처 B: `.claude/agents/executor.md:101` — 6,000,000원/월
     - 출처 C: `.pipeline/analysis/REPORT_eps_values.md:144` — 6,500,000원/월(실양식)
   - 부장 2중 충돌:
     - 출처 A: `company_standards.py` — 7,500,000원/월
     - 출처 B: `executor.md:101` — 8,000,000원/월
   - 차장 2중 충돌:
     - 출처 A: `company_standards.py` — 6,500,000원/월
     - 출처 B: `executor.md:101` — 7,000,000원/월
   - 대리 3중 충돌:
     - 출처 A: `company_standards.py` — 4,500,000원/월
     - 출처 B: `executor.md:101` — 5,000,000원/월
     - 출처 C: `REPORT_eps_values.md:145` — 5,500,000원/월
   - 사원 2중 충돌:
     - 출처 A: `company_standards.py` — 3,500,000원/월
     - 출처 B: `executor.md:101` — 4,500,000원/월
   - 현재 코드 적용값: company_standards.py 기준(전 직급 잠정). 운영팀 확정 전까지 잠정.

2. **MAX_REVISION 초과 처리 이원화**
   - `main.py:729-734`: HTTP 400 반환 (API 레이어)
   - `contract_builder.py:307`: ValueError raise (빌더 레이어)
   - 단일 진입점(canonical gate) 확정 필요 — 현재 두 곳 모두 막고 있음.

3. **간접·일반관리비율 문서 근거 미확보**
   - 현행 코드: indirect_rate=1.9%, admin_rate=3.0% (`company_standards.py:28-29`)
   - 근거: "윤지민과장 25년 기준" 주석만, 공문 경로/문서 없음 → `[NEEDS CLARIFICATION]`

4. **보험 요율 이원화 및 기준연도 미정**
   - 집행 요율: 4.75/4.0674/0.796% vs 정산 요율: 4.5/4.0041/0.766% (`REPORT_eps_values.md:174-180`)
   - DEFAULT_RATES의 현행 코드값이 어느 기준연도인지, 갱신 정책이 없음 → `[NEEDS CLARIFICATION]`

5. **상여금 산출 공식 충돌** `[NEEDS CLARIFICATION]`
   - 출처 A: `.claude/agents/executor.md:109` — 1M/M 전액 (월 단가 × M/M)
   - 출처 B: `backend/services/contract_builder.py:540` — rate × months / 9
   - 출처 C: `.pipeline/analysis/REPORT_eps_values.md:155` — 6,500,000 × 3 / 9 (실양식 예시)
   - `contract_builder.py:512-559`(build_sprint_contract 내 상여 자동산출)가 실행되나, EXE-06 Functional Requirements에 상여 산출 FR이 없음. EXE-09 스펙과 함께 재정렬이 필요하며, 공식 확정 전까지 임의 구현 금지. (설계 §6-1 강제 `[NEEDS CLARIFICATION]` 이월)
