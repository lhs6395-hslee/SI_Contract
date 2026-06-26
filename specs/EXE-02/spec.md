# Feature Specification: EXE-02 — 소스추출

**Feature Branch**: `EXE-02-source-extraction`  **Created**: 2026-06-26  **Status**: Draft  
**Input**: EXE-01이 분류한 소스 문서들로부터 집행계획서 6개 섹션(기본필드·비목·인원·일정·요율·조직)의 구조화 데이터를 추출한다.

---

## ⚙ 작성 규칙

헌법(`.specify/memory/constitution.md`) 제I~III원칙 준수.  
모든 코드 근거는 `backend/services/ai_core.py`(이하 `ai_core.py`) 및 `backend/main.py`(이하 `main.py`) 직접 확인.  
단일 출처 값만 인용; 출처 없음 또는 충돌 시 `[NEEDS CLARIFICATION]`.

---

## User Scenarios & Testing

### User Story 1 — 전체 필드 일괄 추출 (Priority: P1)

담당자가 계약서·내부 견적품의서·외주 견적서를 동시에 업로드하면 시스템이 한 번에 기본 필드를 추출해 검토 화면을 채워 준다. 수동 입력 없이 사업명·발주처·수행기간·매출 구조를 확인할 수 있다.

- **Independent Test**: 계약서 1건 + 내부 견적품의서 1건을 `/api/extract`에 POST → 응답 JSON에 `projectName.value`, `client.value`, `startDate.value` 가 모두 비null.
- **Acceptance (Given/When/Then)**:
  1. **Given** 계약서·내부견적품의서가 EXE-01로 분류된 상태, **When** `/api/extract`에 해당 파일을 업로드, **Then** `projectName/client/contractor/startDate/endDate/revenue` 필드가 `confidence: "verified"` 또는 `"guess"` 로 채워진 JSON을 반환한다.
  2. **Given** 문서에 수금조건이 명시되어 있음, **When** 추출 수행, **Then** `paymentTerms.value`가 해당 문구로 채워진다.
  3. **Given** 특정 필드(예: salesOwner)가 어떤 문서에도 없음, **When** 추출 수행, **Then** 해당 필드는 `{"value": null, "source": "", "confidence": "null"}` 로 반환된다.

### User Story 2 — 섹션별 탭 추출 (Priority: P1)

검토 화면의 각 탭(비목·인원·일정·요율·조직)에서 사용자가 새로고침 버튼을 누르면, 해당 섹션만 재추출해 탭 데이터를 갱신한다.

- **Independent Test**: 외주 견적서를 `/api/extract-costs`에 POST → 응답 `items` 배열에 `category`, `contractAmount`, `executionAmount` 가 채워진 항목 1건 이상.
- **Acceptance (Given/When/Then)**:
  1. **Given** 협력사 견적서 파일이 업로드됨, **When** `/api/extract-costs` 호출, **Then** 응답 `items`의 각 항목에 `category`(BUDGET_CATEGORIES 키 또는 `"fee"`), `name`, `executionAmount`가 있다.
  2. **Given** 투입 인원표가 있는 문서, **When** `/api/extract-people` 호출, **Then** `staffPlan` 배열에 `grade`, `totalMM`, `months`(길이 12 배열)가 채워진다.
  3. **Given** 요율이 문서에 명시되지 않음, **When** `/api/extract-rates` 호출, **Then** 각 요율 값은 `0`으로 반환된다(빌더 사내기준 fallback 대상).

### User Story 3 — Vision(스캔 PDF) 추출 (Priority: P2)

스캔 PDF(텍스트 레이어 없음)를 업로드하면 Vision 멀티모달로 페이지 이미지를 분석해 추출한다.

- **Independent Test**: 텍스트 없는 스캔 PDF를 `/api/extract`에 POST → 응답이 `{"error": "추출 실패"}` fallback이 아닌 실제 필드를 반환.
- **Acceptance (Given/When/Then)**:
  1. **Given** 스캔 PDF(이미지만 있음), **When** `/api/extract` 호출, **Then** 시스템은 페이지 이미지를 base64로 변환해 Bedrock 멀티모달 메시지에 포함하고, 텍스트 추출과 동일한 JSON 스키마로 결과를 반환한다.
  2. **Given** Vision 이미지가 9장 이상, **When** 추출 수행, **Then** 처음 8장만 전송하고 경고 로그를 기록한다(`ai_core.py:116` 상한).

### User Story 4 — 자사 인력 추출 제외 (Priority: P1)

GS네오텍 직접 인력의 급료·임금 라인은 비목 추출에서 제외된다. 사내 직급단가표가 별도 계산하므로 이중 계상을 차단한다.

- **Independent Test**: GS네오텍 인력만 있는 EPS 견적서를 `/api/extract-costs`에 POST → 응답 `items`가 빈 배열(`[]`) 또는 `fee/bonus/welfare` 등 비노무 항목만 포함.
- **Acceptance (Given/When/Then)**:
  1. **Given** 공급자=GS네오텍인 견적서의 PM/SA 인력 라인, **When** 비목 추출, **Then** 해당 라인의 `category`가 `"labor"` 또는 `"wage"`로 추출되지 않는다.
  2. **Given** 원가명세에 별도 상여(bonus) 라인이 있음, **When** 비목 추출, **Then** 해당 라인은 `category: "bonus"`로 추출된다.

### Edge Cases

- 문서 전부를 읽어도 특정 필드를 찾을 수 없는 경우 → `null` 반환(임의값 추측 금지).
- 비목 category가 BUDGET_CATEGORIES 어휘 밖인 경우 → `"etc"` 로 정규화(`ai_core.py:358`).
- LLM이 JSON 뒤에 산문을 덧붙이는 경우 → `_parse_json` 균형괄호 알고리즘으로 유효 JSON만 추출(`ai_core.py:622-668`).
- Bedrock 호출 실패(ThrottlingException/ModelNotReadyException) → `AIUnavailableError` 발생, 클라이언트에 일반 오류 메시지만 노출(`ai_core.py:148-156`).
- Vision 이미지 변환 실패 → 경고 로그 후 텍스트 전용 추출 진행(`main.py:540`).

---

## Functional Requirements (EARS)

### FR-001 (event) — 전체 필드 일괄 추출
`WHEN` 인증된 사용자가 1개 이상의 문서 파일을 `/api/extract`에 업로드하면, `THE SYSTEM SHALL` `projectName·client·contractor·contractType·paymentTerms·pm·salesOwner·startDate·endDate·revenue·quoteMaterial·quoteLabor·quoteOutsourcing·cost·profit·profitRate·scope·specialNotes·fiscalYear·writtenDate` 필드를 포함한 JSON을 반환한다.  
*근거:* `ai_core.py:259 extract_all_fields`, `main.py:544-558 /api/extract`

### FR-002 (ubiquitous) — 추출값 출처 보존
`THE SYSTEM SHALL` 모든 추출 필드에 `source`(출처 문자열)와 `confidence`(`"verified"` | `"guess"` | `"null"`) 를 함께 반환한다.  
*근거:* `ai_core.py:216-236 EXTRACT_PROMPT JSON 스키마`

### FR-003 (unwanted) — 미발견 필드 null 처리
`IF` 문서 내 어떤 위치에서도 특정 필드 값을 찾을 수 없으면, `THEN THE SYSTEM SHALL` 해당 필드를 `{"value": null, "source": "", "confidence": "null"}` 로 반환하고 임의 값을 생성하지 않는다.  
*근거:* `ai_core.py:254 EXTRACT_PROMPT 규칙`

### FR-004 (event) — 비목 섹션 추출
`WHEN` 인증된 사용자가 `/api/extract-costs`를 호출하면, `THE SYSTEM SHALL` 비목 항목 배열(`items`)을 반환한다. 각 항목은 `category·name·spec·unit·contractQty·contractPrice·contractAmount·executionQty·executionPrice·executionAmount·vendor·source·confidence` 를 포함한다.  
*근거:* `ai_core.py:464 extract_costs`, `main.py:605-608 /api/extract-costs`

### FR-005a (unwanted) — 비목 카테고리 정규화
`IF` 추출된 `category` 값이 정의된 BUDGET_CATEGORIES 어휘 밖에 있으면, `THEN THE SYSTEM SHALL` 별칭 매핑을 적용해 표준 카테고리 키로 정규화한다.  
*근거:* `ai_core.py:329-359 _COST_CAT_ALIAS`, `ai_core.py:466-471 extract_costs`

### FR-005b (unwanted) — 비목 카테고리 미매핑 처리
`IF` 별칭 매핑으로도 표준 카테고리 키를 결정할 수 없으면, `THEN THE SYSTEM SHALL` 해당 항목의 `category`를 `"etc"`로 설정한다.  
*근거:* `ai_core.py:349-359 _normalize_cost_category`

### FR-005c (unwanted) — 비목 항목 보존
`IF` `category` 값이 정의된 BUDGET_CATEGORIES 어휘 밖에 있으면, `THEN THE SYSTEM SHALL` 해당 항목을 응답에서 제거하지 않는다.  
*근거:* `ai_core.py:466-471 extract_costs`

### FR-006 (unwanted) — 자사 인력 비목 추출 제외
`IF` 공급자(을)가 GS네오텍인 견적서의 PM/SA 등 직접 인력 라인이면, `THEN THE SYSTEM SHALL` 해당 라인을 `"labor"` 또는 `"wage"` 카테고리로 비목에 포함하지 않는다.  
*근거:* `ai_core.py:284-316 COSTS_PROMPT 규칙`

### FR-007 (event) — 인원 섹션 추출
`WHEN` 인증된 사용자가 `/api/extract-people`를 호출하면, `THE SYSTEM SHALL` `staffPlan` 배열을 반환한다. 각 항목은 `name·role·grade·type·company·months(길이 12 배열)·totalMM·monthlyRate·source` 를 포함한다.  
*근거:* `ai_core.py:475 extract_people`, `main.py:611-614 /api/extract-people`

### FR-008 (unwanted) — 매출 단가 인원 추출 제외
`IF` 견적서에 매출 단가만 있고 원가 단가가 없으면, `THEN THE SYSTEM SHALL` 해당 인원의 `monthlyRate`를 `0`으로 반환한다.  
*근거:* `ai_core.py:396-397 PEOPLE_PROMPT 규칙`

### FR-009 (event) — 일정 섹션 추출
`WHEN` 인증된 사용자가 `/api/extract-schedule`를 호출하면, `THE SYSTEM SHALL` `schedule` 배열을 반환한다. 각 항목은 `name·startMonth·endMonth·source` 를 포함한다.  
*근거:* `ai_core.py:480 extract_schedule`, `main.py:617-620 /api/extract-schedule`

### FR-010 (event) — 요율 섹션 추출
`WHEN` 인증된 사용자가 `/api/extract-rates`를 호출하면, `THE SYSTEM SHALL` `rates` 객체를 반환한다. `rates`는 `indirectRate·adminRate·nationalPension·healthInsurance·employmentInsurance·industrialAccident` 각 필드에 `value`와 `source`를 포함한다.  
*근거:* `ai_core.py:485 extract_rates`, `main.py:623-626 /api/extract-rates`

### FR-011 (unwanted) — 요율 미명시 처리
`IF` 문서에 간접비율·일반관리비율이 합산으로만 표기되어 개별 분리가 불가하거나 전혀 명시되지 않으면, `THEN THE SYSTEM SHALL` 해당 항목을 `0`으로 반환한다(사내기준 fallback은 EXE-03 소관).  
*근거:* `ai_core.py:433-435 RATES_PROMPT 규칙`

### FR-012 (event) — 조직 섹션 추출
`WHEN` 인증된 사용자가 `/api/extract-org`를 호출하면, `THE SYSTEM SHALL` `organization` 배열을 반환한다. 각 항목은 `role·name·scope·lead` 를 포함한다.  
*근거:* `ai_core.py:490 extract_org`, `main.py:629-632 /api/extract-org`

### FR-013 (optional) — ai-service 위임
`WHERE` 환경 변수 `USE_AI_SERVICE=true`이면, `THE SYSTEM SHALL` 각 섹션 추출을 ai-service 엔드포인트(`/extract-{section}`)에 위임하고 모놀리스 `ai_core`를 직접 호출하지 않는다.  
*근거:* `main.py:593-602 _tab_extract`, `main.py:553-556 /api/extract`

### FR-014 (optional) — Vision 멀티모달 추출
`WHERE` 업로드 문서에 스캔 PDF 이미지가 포함되면, `THE SYSTEM SHALL` 최대 8장의 페이지 이미지를 멀티모달 메시지에 포함해 기본 필드 추출 JSON 스키마와 동일한 형식으로 결과를 반환한다.  
*근거:* `ai_core.py:114-116 Vision 상한`, `ai_core.py:165-170 _collect_images`

### FR-015a (unwanted) — LLM 응답 JSON 파싱 실패 시 fallback 반환
`IF` LLM 응답에서 유효 JSON 추출에 실패하면, `THEN THE SYSTEM SHALL` 섹션별 fallback 값(`{"error":"추출 실패"}` / `{"items":[]}` / `{"staffPlan":[]}` 등)을 반환한다.  
*근거:* `ai_core.py:622-668 _parse_json`, `ai_core.py:466-492 각 extract 함수 fallback`

### FR-015b (unwanted) — LLM 응답 JSON 파싱 실패 시 예외 비전파
`IF` LLM 응답에서 유효 JSON 추출에 실패하면, `THEN THE SYSTEM SHALL` 파싱 예외를 호출자에게 전파하지 않는다.  
*근거:* `ai_core.py:622-668 _parse_json`, `ai_core.py:466-492 각 extract 함수 fallback`

### FR-016a (unwanted) — Bedrock 호출 오류 내부 격리
`IF` Bedrock 호출 중 `ThrottlingException` 또는 `ModelNotReadyException`이 발생하면, `THEN THE SYSTEM SHALL` `AIUnavailableError`를 발생시킨다.  
*근거:* `ai_core.py:148-156 invoke_bedrock 예외 처리`

### FR-016b (unwanted) — Bedrock 호출 오류 클라이언트 메시지 마스킹
`IF` Bedrock 호출 중 `ThrottlingException` 또는 `ModelNotReadyException`이 발생하면, `THEN THE SYSTEM SHALL` 클라이언트에 일반 오류 메시지만 반환하고 내부 예외 상세를 노출하지 않는다.  
*근거:* `ai_core.py:148-156 invoke_bedrock 예외 처리`

### FR-017 (optional) — 저장 파일 기반 추출
`WHERE` 요청에 `stored_files` 파라미터가 포함되면, `THE SYSTEM SHALL` S3에서 해당 파일을 로드해 업로드 파일과 합산하여 추출 입력으로 사용한다.  
*근거:* `main.py:563-590 _documents_from_request`

---

## Success Criteria (측정형)

- **SC-001**: **골든셋(정상 LLM 응답이 보장된 테스트 문서 집합) 기준**으로, `/api/extract` 호출 시 응답 HTTP 상태 코드가 `200`이고 반환 JSON에 `projectName` 키가 존재하는 비율이 **100%** (fallback `{"error":"추출 실패"}` 반환 비율 0%). 깨진 LLM 응답이 입력인 경우는 FR-015a/b 범위이므로 이 기준 집합에서 제외한다.
- **SC-002**: 비목 추출 시 `items` 각 항목의 `category`가 BUDGET_CATEGORIES 어휘(`fee/labor/bonus/wage/welfare/travel/vehicle/equipment/rent/transport/comm/print/safety/etc`) 중 하나인 비율 **100%** (정규화 후).
- **SC-003**: 전체 필드 추출 시 `source`·`confidence` 가 모든 필드에 존재하는 비율 **100%**.
- **SC-004a**: Vision 이미지가 8장 초과 시 처음 8장만 Bedrock 요청에 전송되는 비율 **100%**.
- **SC-004b**: Vision 이미지가 8장 초과 시 나머지 이미지 누락에 대한 경고 로그가 기록되는 비율 **100%**.
- **SC-005**: 추출 정확도(골든셋 대비 필드 정확 일치율) 목표 — `[NEEDS CLARIFICATION: 베이스라인 측정 후 목표 수치 확정. 현재 단일 출처 없음.]`
- **SC-006**: `/api/extract-costs` 응답 시간(P95) — `[NEEDS CLARIFICATION: 부하 테스트 기준선 미정.]`

---

## Key Entities

| 엔티티 | 설명 | 출처 |
|--------|------|------|
| `ExtractedFields` | `extract_all_fields` 반환 — 기본 필드 20종, 각 필드에 `value/source/confidence` | `ai_core.py:216-236` |
| `CostItem` | 비목 단위 — `category/name/spec/unit/contractQty~Amount/executionQty~Amount/vendor/source/confidence` | `ai_core.py:319-324` |
| `StaffEntry` | 인원 단위 — `name/role/grade/type/company/months[12]/totalMM/monthlyRate/source` | `ai_core.py:404-407` |
| `ScheduleEntry` | 일정 단위 — `name/startMonth/endMonth/source` (startMonth는 사업 시작월 기준 1-index) | `ai_core.py:420-423` |
| `RatesObject` | 요율 객체 — `indirectRate/adminRate/nationalPension/healthInsurance/employmentInsurance/industrialAccident` 각 `{value, source}` | `ai_core.py:437-444` |
| `OrgEntry` | 조직 단위 — `role/name/scope/lead(bool)` | `ai_core.py:457-460` |
| `DocumentBlock` | 추출 입력 — `filename/text/images(base64 list)` | `main.py:530-541` |

---

## Assumptions

- **모델 라우팅 (코드 현행값=잠정)**: `extract_full` → `"sonnet"` 티어(`BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-6`), 전체 추출은 Sonnet, 섹션별(`extract_costs/people/schedule/rates/org`) 모두 `"sonnet"` 티어 사용 (`ai_core.py:40-53 TASK_TIER`). 실환경 모델 ID는 `BEDROCK_MODEL_ID` 환경 변수로 재정의 가능.
- **max_tokens 상한 (코드 현행값=잠정)**: `extract_full` 2048 토큰, 비목/인원 2048 토큰, 일정 1024 토큰, 요율 512 토큰, 조직 1024 토큰 (`ai_core.py:267, 465-491`). Vision 추출은 JSON 잘림 방지를 위해 2048 사용.
- **temperature 0**: 모든 추출 호출이 `temperature=0.0`으로 결정론적 출력을 목표로 한다 (`ai_core.py:130`).
- **문서 텍스트 상한 (코드 현행값=잠정)**: 섹션 추출 `_doc_block` 기본 limit=4000자, 전체 추출은 `doc[:2000]` (`ai_core.py:273, 261`). 초과분은 잘림.
- **Vision 이미지 상한 (코드 현행값=잠정)**: 최대 8장. 초과 시 경고 로그 후 처음 8장만 전송 (`ai_core.py:115-116`).
- **클라이언트 파일 크기 제한**: `_check_upload_size` 적용 (`main.py:550`). 제한 수치는 `[NEEDS CLARIFICATION: main.py의 상한값 직접 확인 필요 — 이 spec 작성 범위에서 해당 라인 미읽음]`.
- **인증 의존**: 모든 추출 엔드포인트는 `require_auth` 의존성이 적용되어 있음 (`main.py:544, 605, 611, 617, 623, 629`). 인증 상세는 EXE-17 소관.
- **EXE-01 소비**: 이 기능은 EXE-01이 분류한 문서를 입력으로 받는다. 분류 결과를 추출 시 직접 필터링하는 로직은 현 코드에 없음 — 업로드된 파일 전체를 추출 대상으로 삼는다.

---

## Clarifications Retained

이 기능에 `[NEEDS CLARIFICATION]` 강제 항목(설계 §6-1)은 없다. 추출 동작은 코드로 확정됨.  
단, 아래 미정 항목은 배포·운영 전 확인이 필요하다:

1. **추출 정확도 SC 목표** (SC-005): 골든셋 기반 베이스라인 측정 후 수치 확정 필요. 현재 단일 기준 출처 없음.
2. **응답 시간 SC** (SC-006): 부하 테스트 기준선 미정. Bedrock 호출 latency가 지배적.
3. **업로드 파일 크기 상한**: `_check_upload_size` 구현 내 수치 미확인. 운영 정책과 함께 확정 필요.
4. **`USE_AI_SERVICE` 기본값**: 배포 환경에서 모놀리스 vs ai-service 경로 중 어느 것이 기본인지 배포 설정 확인 필요.
