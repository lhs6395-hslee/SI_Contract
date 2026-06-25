# Requirements Document

## Introduction

SI 집행계획서 자동화 시스템에서 다년도 사업(2개 이상의 회계연도에 걸치는 사업)의 이월 로직을 구현한다. 현재 시스템은 단년도 사업만 처리 가능하며, 사업 기간이 2025.09~2026.09처럼 복수 년도에 걸칠 때 연도별 M/M 분배, 정산누계/당기계획/당기이후 컬럼 자동 계산, 이월 차수 추가 시 데이터 이동 로직이 필요하다.

## Glossary

- **Carryover_Engine**: 다년도 사업의 연도별 금액/수량 분배 및 이월 처리를 수행하는 백엔드 모듈
- **FeeItem**: 수수료산출내역 시트의 개별 항목 (품명, 수량, 단가, 금액 포함)
- **SprintContract**: 집행계획서 전체 데이터를 담는 최상위 모델
- **Fiscal_Year**: 회계연도 (1월~12월 기준)
- **Settlement_Cumulative**: 정산누계 — 전년도까지 완료된 실적 금액/수량
- **Current_Period**: 당기계획 — 현재 회계연도에 집행할 금액/수량
- **Post_Current**: 당기이후 — 내년 이후에 집행 예정인 금액/수량
- **MM_Distribution**: 사업 기간을 월 단위로 분할하여 각 회계연도에 속하는 M/M(Man-Month)을 산출하는 계산
- **Carryover_Revision**: 이월 차수 — 동일 사업이 다음 회계연도로 넘어갈 때 생성되는 새로운 차수
- **Fee_Sheet_Writer**: 수수료산출내역 시트에 데이터를 기록하는 Excel 라이터 모듈
- **Breakdown_Sheet_Writer**: 집행예산산출내역서(공통 시트 비목별 행)에 데이터를 기록하는 Excel 라이터 모듈
- **Common_Sheet_Writer**: 공통 시트에 마스터 데이터를 기록하는 Excel 라이터 모듈

## Requirements

### Requirement 1: 다년도 사업 판별

**User Story:** As a 집행계획서 작성자, I want 시스템이 사업 기간을 분석하여 다년도 여부를 자동 판별하도록, so that 이월 로직 적용 여부를 수동으로 지정하지 않아도 된다.

#### Acceptance Criteria

1. WHEN SprintContract의 project_period.start와 project_period.end가 서로 다른 회계연도에 속할 때, THE Carryover_Engine SHALL 해당 사업을 다년도 사업으로 분류한다
2. WHEN 사업이 다년도로 분류될 때, THE Carryover_Engine SHALL 사업 기간에 포함되는 모든 회계연도 목록을 산출한다
3. WHEN 사업 기간이 단일 회계연도 내에 있을 때, THE Carryover_Engine SHALL 기존 단년도 로직을 그대로 적용한다

### Requirement 2: 연도별 M/M 자동 분배

**User Story:** As a 집행계획서 작성자, I want 다년도 사업의 총 수량(M/M)이 각 회계연도에 자동으로 비례 분배되도록, so that 수동 계산 없이 연도별 계획을 수립할 수 있다.

#### Acceptance Criteria

1. WHEN 다년도 사업의 FeeItem에 execution_qty가 설정될 때, THE Carryover_Engine SHALL 각 회계연도에 속하는 월수 비율에 따라 수량을 분배한다
2. THE Carryover_Engine SHALL 분배된 각 연도별 수량의 합이 원래 execution_qty와 동일하도록 보장한다
3. WHEN 분배 결과에 소수점 이하 잔여분이 발생할 때, THE Carryover_Engine SHALL 마지막 연도에 잔여분을 할당하여 합계 정합성을 유지한다
4. WHEN StaffItem의 months 배열이 설정될 때, THE Carryover_Engine SHALL 각 월이 속하는 회계연도를 기준으로 연도별 M/M 합계를 산출한다

### Requirement 3: FeeItem 모델 확장

**User Story:** As a 개발자, I want FeeItem 모델에 정산누계와 당기이후 필드가 추가되도록, so that 다년도 사업의 연도별 금액을 데이터 모델에서 표현할 수 있다.

#### Acceptance Criteria

1. THE FeeItem SHALL settlement_cumulative_qty(정산누계 수량) 필드를 포함한다
2. THE FeeItem SHALL settlement_cumulative_amount(정산누계 금액) 필드를 포함한다
3. THE FeeItem SHALL post_current_qty(당기이후 수량) 필드를 포함한다
4. THE FeeItem SHALL post_current_amount(당기이후 금액) 필드를 포함한다
5. THE FeeItem SHALL 각 신규 필드의 기본값을 0으로 설정한다
6. WHEN 단년도 사업일 때, THE Carryover_Engine SHALL settlement_cumulative 및 post_current 필드를 0으로 유지한다

### Requirement 4: 수수료산출내역 시트 연도 분리 기록

**User Story:** As a 집행계획서 작성자, I want 수수료산출내역 시트에 정산누계/당기계획/당기이후 컬럼이 자동으로 채워지도록, so that 엑셀 템플릿의 연도별 컬럼이 정확히 반영된다.

#### Acceptance Criteria

1. WHEN 다년도 사업의 FeeItem을 시트에 기록할 때, THE Fee_Sheet_Writer SHALL col14~16(N~P열)에 정산누계 수량/단가/금액을 기록한다
2. WHEN 다년도 사업의 FeeItem을 시트에 기록할 때, THE Fee_Sheet_Writer SHALL col17~19(Q~S열)에 당기계획 수량/단가/금액을 기록한다
3. WHEN 다년도 사업의 FeeItem을 시트에 기록할 때, THE Fee_Sheet_Writer SHALL col20 이후에 당기이후 수량/단가/금액을 기록한다
4. THE Fee_Sheet_Writer SHALL 정산누계 금액 + 당기계획 금액 + 당기이후 금액이 집행 총액과 일치하도록 검증한다

### Requirement 5: 집행예산집계표 연도 분리 기록

**User Story:** As a 집행계획서 작성자, I want 집행예산산출내역서의 비목별 금액이 정산누계/당기/당기이후로 분리 기록되도록, so that 비목별 연도 구분이 엑셀에 정확히 반영된다.

#### Acceptance Criteria

1. WHEN 다년도 사업의 비목별 금액을 공통 시트에 기록할 때, THE Breakdown_Sheet_Writer SHALL settled 행에 정산누계 금액을 기록한다
2. WHEN 다년도 사업의 비목별 금액을 공통 시트에 기록할 때, THE Breakdown_Sheet_Writer SHALL current 행에 당기계획 금액을 기록한다
3. WHEN 다년도 사업의 비목별 금액을 공통 시트에 기록할 때, THE Breakdown_Sheet_Writer SHALL next1 행에 당기이후(내년) 금액을 기록한다
4. WHEN 다년도 사업의 비목별 금액을 공통 시트에 기록할 때, THE Breakdown_Sheet_Writer SHALL next2 행에 당기이후(내후년 이후) 금액을 기록한다
5. THE Breakdown_Sheet_Writer SHALL settled + current + next1 + next2 금액 합계가 execution 금액과 일치하도록 보장한다

### Requirement 6: 공통 시트 연도 구분 기록

**User Story:** As a 집행계획서 작성자, I want 공통 시트의 R13~R16 셀에 연도별 구분 정보가 기록되도록, so that 정산누계/당기/당기이후 기간이 명확히 표시된다.

#### Acceptance Criteria

1. WHEN 다년도 사업일 때, THE Common_Sheet_Writer SHALL R13 셀에 정산누계 기간(시작년도~전년도)을 기록한다
2. WHEN 다년도 사업일 때, THE Common_Sheet_Writer SHALL R14 셀에 당기계획 기간(현재 회계연도)을 기록한다
3. WHEN 다년도 사업일 때, THE Common_Sheet_Writer SHALL R15 셀에 당기이후 내년 기간을 기록한다
4. WHEN 다년도 사업일 때, THE Common_Sheet_Writer SHALL R16 셀에 당기이후 내후년 이후 기간을 기록한다
5. WHEN 단년도 사업일 때, THE Common_Sheet_Writer SHALL R13~R16 셀을 비워둔다

### Requirement 7: 이월 차수 생성

**User Story:** As a 집행계획서 작성자, I want 이월 버튼을 클릭하면 새로운 차수가 자동 생성되고 회계연도가 변경되도록, so that 다음 년도 집행계획을 별도 차수로 관리할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 이월 차수 추가를 요청할 때, THE Carryover_Engine SHALL SprintContract의 revision을 1 증가시킨다
2. WHEN 이월 차수가 생성될 때, THE Carryover_Engine SHALL fiscal_year를 다음 회계연도로 변경한다
3. WHEN 이월 차수가 생성될 때, THE Carryover_Engine SHALL 현재 차수의 데이터를 prev_revisions에 저장한다
4. WHEN 이월 차수가 생성될 때, THE Carryover_Engine SHALL 이전 차수의 당기계획 금액을 새 차수의 정산누계에 누적한다
5. WHEN 이월 차수가 생성될 때, THE Carryover_Engine SHALL 이전 차수의 당기이후(내년) 금액을 새 차수의 당기계획으로 이동한다
6. WHEN 이월 차수가 생성될 때, THE Carryover_Engine SHALL 이전 차수의 당기이후(내후년~) 금액을 새 차수의 당기이후로 이동한다

### Requirement 8: 정산누계 자동 계산

**User Story:** As a 집행계획서 작성자, I want 이월 시 정산누계가 이전 차수 데이터를 기반으로 자동 계산되도록, so that 수동 입력 오류 없이 누적 실적이 반영된다.

#### Acceptance Criteria

1. WHEN 이월 차수가 생성될 때, THE Carryover_Engine SHALL 이전 차수의 settlement_cumulative_amount + 이전 차수의 current_period_amount를 새 차수의 settlement_cumulative_amount로 계산한다
2. WHEN 이월 차수가 생성될 때, THE Carryover_Engine SHALL 이전 차수의 settlement_cumulative_qty + 이전 차수의 current_period_qty를 새 차수의 settlement_cumulative_qty로 계산한다
3. THE Carryover_Engine SHALL 새 차수의 settlement_cumulative_amount + current_period_amount + post_current_amount가 execution_amount와 동일하도록 검증한다
4. IF 정산누계 + 당기 + 당기이후 합계가 집행 총액과 불일치할 때, THEN THE Carryover_Engine SHALL 불일치 내역을 오류로 보고한다

### Requirement 9: SprintContract 모델 확장

**User Story:** As a 개발자, I want SprintContract 모델에 다년도 사업 관련 메타데이터가 추가되도록, so that 이월 상태와 연도 정보를 추적할 수 있다.

#### Acceptance Criteria

1. THE SprintContract SHALL is_multi_year(다년도 여부) 필드를 포함한다
2. THE SprintContract SHALL fiscal_years(사업에 포함되는 회계연도 목록) 필드를 포함한다
3. THE SprintContract SHALL carryover_source_revision(이월 원본 차수 번호) 필드를 포함한다
4. WHEN is_multi_year가 false일 때, THE Carryover_Engine SHALL 이월 관련 로직을 실행하지 않는다

### Requirement 10: UI 이월 모달 연동 API

**User Story:** As a 프론트엔드 개발자, I want 이월 차수 생성을 위한 API 엔드포인트가 제공되도록, so that UI의 이월 모달에서 백엔드 이월 로직을 호출할 수 있다.

#### Acceptance Criteria

1. WHEN 프론트엔드가 이월 요청 API를 호출할 때, THE Carryover_Engine SHALL 현재 프로젝트의 최신 차수 데이터를 기반으로 이월 차수를 생성한다
2. THE Carryover_Engine SHALL 이월 결과로 새 SprintContract(갱신된 revision, fiscal_year, 분배된 금액)를 반환한다
3. IF 현재 사업이 단년도 사업일 때, THEN THE Carryover_Engine SHALL 이월 요청을 거부하고 사유를 반환한다
4. WHEN 이월 API 호출 시 선택적으로 실적 금액 수정값이 포함될 때, THE Carryover_Engine SHALL 수정된 실적을 정산누계에 반영한다
