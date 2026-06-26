# Feature Specification: EXE-14 — import 역추출

**Feature Branch**: `EXE-14-import-reverse-extract`  **Created**: 2026-06-26  **Status**: Draft
**Input**: 완성된 집행계획서(PDF/xlsx) 단독 업로드 → 0차 ExtractedData 역추출 및 단위 확정 게이트 제어

---

## 성격 및 범위 선언

EXE-14는 **백엔드 도메인 기능 + 프론트 게이트 복합 기능**이다.

- **백엔드**: `POST /api/import` 엔드포인트가 Claude Bedrock을 호출해 집행계획서에서 0차 필드·비목·요율을 역추출한다.
- **프론트**: 역추출 결과에 `importMeta`가 존재할 때 단위 확정 게이트를 표시하고, `unitConfirmed=true`가 될 때까지 익스포트·1차 진행을 차단한다.

백엔드 게이트 전용 엔드포인트는 없다 — 단위 확정은 순수 클라이언트 상태(`unitConfirmed`)로 제어된다.  
[공식 코드: `frontend/lib/types.ts:114-115`, `frontend/components/pages/review-page.tsx:184`, `frontend/components/pages/other-pages.tsx:229`]

---

## User Scenarios & Testing

### User Story P1 — 완성 집행계획서 역추출 (Priority: P1)

사용자(FDE/PM)가 이미 작성된 집행계획서 PDF 또는 xlsx를 업로드하면, 시스템이 0차 ExtractedData(기본정보·비목·요율)를 자동으로 역추출하여 수정집행 진행을 빠르게 시작할 수 있게 한다. 견적서를 새로 올리는 정상 흐름과 달리, 이 경우 입력이 '결과물(완성 산출물)'이므로 별도 분기 처리가 필요하다.

- **Independent Test**: 집행계획서 PDF 1건만 업로드 → 추출 결과에 `projectName`, `revenue`, `costItems` 1건 이상, `importMeta` 존재 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** 사용자가 upload 화면에서 "집행계획서 가져오기"로 PDF/xlsx를 선택했을 때, **When** 파일을 POST `/api/import`로 전송하면, **Then** 응답에 `extracted`, `costItems`, `rates`, `importMeta` 키가 포함된 JSON이 반환된다.
  2. **Given** 반환된 `importMeta.unitGuessed=true`이거나 `importMeta`가 존재하면, **When** review 화면에 진입하면, **Then** 단위 확정 배너가 표시되고 `unitConfirmed=false` 상태에서 "이 단위로 금액 확정" 버튼이 활성화된다.
  3. **Given** 사용자가 단위를 "원"으로 선택하고 확정하면, **When** `confirmUnits()`가 실행되면, **Then** 모든 금액 필드에 `÷1000` factor가 적용되고 `unitConfirmed=true`로 전환된다.

### User Story P2 — 단위 미확정 상태 진행 차단 (Priority: P1)

단위 확정 전에 익스포트 또는 1차(파이프라인) 진행이 실행되면, 즉시 차단하고 review 화면으로 안내한다. 1000배 단위오류를 방지하는 핵심 안전장치다.

- **Independent Test**: `unitConfirmed=false` 상태에서 "집행계획서 생성" 버튼 클릭 → alert 표시 + `setRoute("review")` 호출 확인.
- **Acceptance (Given/When/Then)**:
  1. **Given** `extractedData.importMeta`가 존재하고 `unitConfirmed=false`인 상태에서, **When** 사용자가 1차 진행(파이프라인 실행) 또는 익스포트를 시도하면, **Then** THE FRONTEND SHALL 진행을 차단하고 review 화면으로 리디렉션한다.

### User Story P3 — 파일 없음 / 인가 실패 처리 (Priority: P2)

파일이 없거나 소유권 없는 저장 파일 참조 시 명확한 오류를 반환한다.

- **Independent Test**: 빈 FormData로 POST `/api/import` → HTTP 422 응답 + 상세 메시지.
- **Acceptance (Given/When/Then)**:
  1. **Given** POST `/api/import`에 파일이 전혀 없을 때, **When** 요청이 처리되면, **Then** HTTP 422와 `"가져올 파일이 필요합니다 ..."` 상세가 반환된다.
  2. **Given** `stored_files`에 타 사용자 소유 `projectId`가 포함될 때, **When** 요청이 처리되면, **Then** `_assert_project_access` 가 차단하여 비인가 응답이 반환된다.

### Edge Cases

- 스캔본 PDF(텍스트 추출 불가): `_collect_images`로 Vision 이미지 전송. `doc_block` limit=16000으로 확장.
- JSON 응답 뒤에 모델이 산문·표를 덧붙인 경우: `_parse_json` 균형괄호 알고리즘으로 앞부분만 추출.
- 모든 필드가 추출 불가인 경우: fallback `{"extracted": {}, "costItems": [], "rates": null, "importMeta": {"unitGuessed": true, "missingFields": []}}` 반환. (게이트는 여전히 작동)
- 단위 라벨([단위:천원]) 존재 시: `unitConfidence="high"` 반환 — 그럼에도 프론트는 자동확정하지 않고 배너 표시 유지. [공식 코드: `review-page.tsx:667`]
- USE_AI_SERVICE=true 환경: `/api/import` 대신 ai-service `POST /import` 프록시 경유. [공식 코드: `main.py:666-667`, `services/ai-service/main.py:119-121`]

---

## Functional Requirements (EARS)

- **FR-001** (event): WHEN 사용자가 완성 집행계획서 파일(PDF/xlsx)을 `POST /api/import`로 전송하면, THE SYSTEM SHALL 해당 문서에서 `extracted`(기본정보 17필드)·`costItems`(비목 목록)·`rates`(요율 6종)·`importMeta`(단위추정 여부·누락필드)를 포함한 0차 역추출 결과를 반환한다.
  - 근거: `ai_core.py:599-617 import_execution_plan`, `main.py:637-670 /api/import`

- **FR-002** (event): WHEN 역추출 요청 처리 시, THE SYSTEM SHALL Bedrock Claude를 `max_tokens=8192`로 호출하고 응답에서 균형괄호 알고리즘으로 JSON 블록을 추출한다.
  - 근거: `ai_core.py:612-617`, `_parse_json` `ai_core.py:622-672`

- **FR-003** (ubiquitous): THE SYSTEM SHALL 모든 금액 필드에 `unitConfidence`("high"|"low") 값을 포함하여 반환한다. 단위 라벨([단위:천원] 등)이 문서에 명시되면 "high", 추정이면 "low"로 구분한다.
  - 근거: `IMPORT_PROMPT ai_core.py:551-554`, `types.ts:35-37`, `types.ts:54-55`

- **FR-004** (ubiquitous): THE SYSTEM SHALL 문서에서 단위 라벨 존재 여부에 관계없이 `importMeta.unitGuessed`를 반환하고, 호출측(프론트)이 사용자에게 단위 확정을 요청하도록 한다. 자동확정 금지.
  - 근거: `main.py:647-648`, `ai_core.py:604-605`, `review-page.tsx:667`

- **FR-005** (event): WHEN 스캔본 PDF가 포함된 경우, THE SYSTEM SHALL `_collect_images`로 base64 이미지를 수집하여 Bedrock Claude Vision 멀티모달 호출에 포함한다.
  - 근거: `ai_core.py:612-614`, `_collect_images ai_core.py:165-169`, `main.py:648`

- **FR-006** (unwanted): IF 요청 FormData에 파일이 없으면, THEN THE SYSTEM SHALL HTTP 422와 `"가져올 파일이 필요합니다 (집행계획서 PDF/xlsx 업로드 또는 저장 파일 선택)"` 상세를 반환한다.
  - 근거: `main.py:663-664`

- **FR-007** (unwanted): IF `stored_files`에 `projectId`가 포함되고 요청자가 해당 프로젝트의 소유자가 아니면, THEN THE SYSTEM SHALL `_assert_project_access` 게이트로 요청을 차단하고 비인가 응답을 반환한다.
  - 근거: `main.py:650-660`

- **FR-008** (unwanted): IF Bedrock 응답 JSON 파싱이 균형괄호 알고리즘으로도 실패하면, THEN THE SYSTEM SHALL `fallback={"extracted": {}, "costItems": [], "rates": null, "importMeta": {"unitGuessed": true, "missingFields": []}}` 를 반환한다.
  - 근거: `ai_core.py:616-617`

- **FR-009** (optional): WHERE `USE_AI_SERVICE=true`로 설정된 경우, THE SYSTEM SHALL `/api/import` 요청을 ai-service `POST /import`로 프록시하여 처리한다.
  - 근거: `main.py:666-667`, `services/ai-service/main.py:119-121`

- **FR-010a** (state): WHILE `extractedData.importMeta`가 존재하고 `unitConfirmed=false`인 동안, THE FRONTEND SHALL review 화면 상단에 단위 확정 배너를 표시한다.
  - 근거: `review-page.tsx:183-184`, `review-page.tsx:656-692`

- **FR-010b** (state): WHILE `extractedData.importMeta`가 존재하고 `unitConfirmed=false`인 동안, THE FRONTEND SHALL 익스포트 버튼 및 1차(파이프라인) 진행을 비활성화한다.
  - 근거: `other-pages.tsx:229-233`

- **FR-011a** (event): WHEN 사용자가 단위(천원/원)를 선택하고 "이 단위로 금액 확정"을 실행하면, THE FRONTEND SHALL 선택 단위에 따라 `factor`(원 선택 시 `÷1000`)를 모든 금액 필드와 비목 금액에 일괄 적용한다.
  - 근거: `review-page.tsx:202-227`

- **FR-011b** (event): WHEN 사용자가 단위(천원/원)를 선택하고 "이 단위로 금액 확정"을 실행하면, THE FRONTEND SHALL `unitConfirmed=true`로 전환한다.
  - 근거: `review-page.tsx:202-227`

- **FR-011c** (event): WHEN `unitConfirmed=true`로 전환되면, THE FRONTEND SHALL 단위 확정 배너 및 진행 차단 게이트를 해제한다.
  - 근거: `review-page.tsx:183-184`, `other-pages.tsx:229-233`

- **FR-012** (ubiquitous): THE SYSTEM SHALL 역추출 문서 블록을 `limit=16000` 자로 잘라 IMPORT_PROMPT에 삽입하고, 단일 문서(집행계획서)의 모든 시트(산출내역·요율·공정표 등)가 프롬프트 범위 안에 포함되도록 한다.
  - 근거: `ai_core.py:613`, `_doc_block ai_core.py:273-277`

---

## Success Criteria (측정형)

- **SC-001**: `POST /api/import`에 유효한 집행계획서 PDF 1건을 전송했을 때 응답 JSON에 `extracted`, `costItems`, `rates`, `importMeta` 4개 키가 모두 존재해야 한다. (100% 필수)
- **SC-002**: `importMeta.unitGuessed=true`이거나 `importMeta`가 존재하는 경우, review 화면 진입 시 단위 확정 배너가 렌더링되어야 한다. (100% 필수)
- **SC-003**: `unitConfirmed=false` 상태에서 파이프라인 실행 버튼 클릭 시 alert이 발생하고 `setRoute("review")`가 호출되어야 한다. (100% 필수)
- **SC-004**: 단위를 "원"으로 확정했을 때, factor `÷1000`이 `revenue`, `cost`, `profit`, `indirectCost`(추출된 경우에 한함) 및 모든 costItems의 금액 필드에 적용되어야 한다. (100% 필수, 1원 정밀도)
  - 주의: `indirectCost`는 IMPORT_PROMPT 추출 스키마(`ai_core.py:558-576`)에 명시적 필드가 없으므로 import 후 null/미추출 상태일 수 있다. 해당 필드가 null인 경우 factor 적용은 no-op이며 SC-004 위반이 아니다.
- **SC-005**: `POST /api/import` 파일 없음 요청 → HTTP 422. (100% 필수)
- **SC-006**: Bedrock 호출 응답 JSON이 잘린 경우(트렁케이션), fallback 구조가 반환되어야 하며 서버가 500 오류를 발생시키지 않아야 한다. (100% 필수)
- **SC-007**: `/api/import` 응답 latency — [NEEDS CLARIFICATION: 현행 Bedrock 호출 실측 기준 목표값 미정. 베이스라인 측정 후 SLA 확정 필요]

---

## Key Entities

| 엔티티 | 위치 | 설명 |
|--------|------|------|
| `ImportResult` | `frontend/lib/api.ts:48-53` | 프론트가 수신하는 역추출 결과 타입 |
| `importMeta` | `frontend/lib/types.ts:113` | 단위 추정 여부·누락 필드 메타 |
| `unitConfirmed` | `frontend/lib/types.ts:115` | 사용자가 단위를 확정했는지 여부 (Boolean 상태) |
| `unitConfidence` | `frontend/lib/types.ts:37,55` | 개별 금액 필드의 단위 신뢰도 ("high"|"low") |
| `IMPORT_PROMPT` | `ai_core.py:543` | 역추출 전용 프롬프트 — 17필드·비목·요율 지시 |
| `import_execution_plan()` | `ai_core.py:599` | 역추출 코어 함수 |
| `_parse_json()` | `ai_core.py:622` | 균형괄호 JSON 추출 유틸 |
| `_collect_images()` | `ai_core.py:165` | Vision 이미지 수집 (스캔 PDF 지원) |
| `_doc_block()` | `ai_core.py:273` | 문서 텍스트 블록 조합 (limit=16000) |
| `apiImport()` | `frontend/lib/api.ts:56` | 프론트 → 백엔드 /api/import 호출 함수 |
| `confirmUnits()` | `frontend/components/pages/review-page.tsx:202` | 단위 확정 실행 함수 |

---

## Assumptions

- 역추출 입력 문서는 GS네오텍 양식 집행계획서 단 1건이다. 복수 문서가 전달되면 첫 번째 문서를 기준으로 처리된다(단일 양식 가정). [잠정, 코드 현행값: `_doc_block` 복수 문서도 병합하나 집행계획서는 단일 업로드 UX 설계]
- Bedrock Claude 호출 `max_tokens=8192`는 코드 현행값이며 환경 제약에 따라 변경될 수 있다. [잠정, `ai_core.py:612`]
- 단위 기본 추정은 "천원"이다. 백엔드는 `unitConfidence="high"`인 경우에도 ×1000 환산을 수행하므로, 프론트 `factor=1`(천원 선택)이 기본경로다. [공식 코드: `ai_core.py:551-554`, `review-page.tsx:203`]
- Vision 이미지 전송 상한은 8장이다. 초과 분은 경고 로그 후 누락된다. [공식 코드: `ai_core.py:115-117`]
- `USE_AI_SERVICE` 환경변수의 기본값은 [NEEDS CLARIFICATION: 현행 배포 환경에서의 실제 기본값 미확인 — `main.py` 상단 및 `.env` 확인 필요].

---

## Clarifications Retained

아래 항목은 단일 출처가 없거나 출처 충돌로 확정 불가하여 운영팀 인터뷰로 해소한다.

1. **SC-007 응답 latency SLA**: 현행 Bedrock 호출은 실측 기준으로 수 초~수십 초 범위로 추정되나, 목표 SLA 수치가 설계 문서 또는 코드에 명시되어 있지 않다 → 베이스라인 측정 후 확정 필요.
2. **USE_AI_SERVICE 기본값**: `main.py` 배포 환경 `.env`에서 확인 필요.
3. **단위 게이트 UX 위치 확정**: 현재 review-page.tsx에만 구현되어 있으나, upload-page 완료 직후 모달 형태로 이동 가능한지 여부가 미정. [공식 코드 현행: `review-page.tsx:656-692`]
