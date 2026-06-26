# Feature Specification: EXE-01 문서분류

**Feature Branch**: `EXE-01-document-classification`
**Created**: 2026-06-26
**Status**: Draft
**Input**: 업로드된 파일을 6종 카테고리 중 하나로 분류하고 신뢰도·근거를 반환한다.

---

## 작성 규칙 준수 선언

- 모든 FR = EARS 5패턴. 수용기준 = Given/When/Then. SC = 측정형.
- 값 미창작: 출처 있는 단일 값만 인용 (`file:line` 명기). 2개+ 충돌 시 `[NEEDS CLARIFICATION]`.
- 모호어("should/적절히/가능하면") 0건, 한 FR = 한 동작.
- EXE-01 성격: **도메인 기능** (백엔드 분류 엔진 + 프론트 표시 및 폴백 포함).
- **SHALL 주어 확장**: EXE-01은 백엔드·프론트엔드 책임을 명시적으로 구분하기 위해 기본 `THE SYSTEM SHALL` 외에 `THE FRONTEND SHALL` / `THE BACKEND SHALL` 주어를 허용한다. `THE FRONTEND SHALL` = Next.js 클라이언트(upload-page.tsx 등) 책임. `THE BACKEND SHALL` = FastAPI 서버(main.py, ai_core.py 등) 책임. `THE SYSTEM SHALL` = 레이어 구분 불필요 또는 전체 시스템 책임.

---

## User Scenarios & Testing

### User Story 1 — 자동 문서분류 (Priority: P1)

담당자가 계약서·견적품의서·협력사 견적서 등 여러 파일을 한 번에 업로드했을 때,
AI가 각 파일의 종류를 자동으로 판별해 레이블(카테고리·신뢰도·사유)을 부여한다.
담당자는 레이블을 확인하고, 잘못 분류된 파일은 수동으로 카테고리를 수정할 수 있다.

- **Independent Test**: 단일 파일 업로드 후 `/api/classify` 응답의 `category`·`confidence`·`reason` 필드 존재 여부를 단독 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** 인증된 사용자가 `계약서.pdf`를 업로드했을 때,
     **When** `/api/classify` 엔드포인트를 호출하면,
     **Then** 응답이 `{"category": "contract", "confidence": <0.0~1.0>, "reason": "..."}` 구조이고 `category` 값이 6종 taxonomy 중 하나이다.
  2. **Given** 파일 업로드 직후 분류가 완료되기 전(classifying=true 상태)인 동안,
     **When** UI에서 해당 파일 행을 확인하면,
     **Then** "AI 분석 중…" 표시가 나타나고 카테고리 드롭다운이 비활성 상태이다.
  3. **Given** AI 분류 결과가 `category: "unknown"` + `confidence < 0.5` 인 파일이 있을 때,
     **When** 프론트엔드가 분류 결과를 수신하면,
     **Then** 파일명 기반 폴백 규칙(`classifyFileFallback`)을 적용해 카테고리를 재추정하고 "키워드 기반 추정" 사유를 표시한다.

### User Story 2 — 수동 재분류 (Priority: P2)

담당자가 AI 분류가 잘못된 파일의 카테고리를 드롭다운에서 직접 변경할 수 있다.
수동 지정된 파일은 신뢰도 1.0, `manual: true` 플래그로 표시된다.

- **Independent Test**: `reclassify(id, cat)` 호출 후 해당 파일의 `category`·`confidence`·`manual` 필드 검증.
- **Acceptance (Given/When/Then)**:
  1. **Given** AI가 `vendor`로 분류한 파일이 있을 때,
     **When** 담당자가 드롭다운에서 `contract`를 선택하면,
     **Then** 해당 파일의 `category`가 `"contract"`으로, `confidence`가 `1.0`으로, `manual`이 `true`로 갱신된다.

### User Story 3 — 미분류(unknown) 잔존 시 추출 차단 (Priority: P1)

`unknown` 카테고리 파일이 한 건이라도 남아 있으면 "추출 시작" 버튼이 비활성화된다.

- **Independent Test**: `unknown` 파일이 있는 상태와 없는 상태에서 `canStart` 계산값 비교.
- **Acceptance (Given/When/Then)**:
  1. **Given** 파일 목록에 `category: "unknown"` 파일이 1건 이상 존재할 때,
     **When** 추출 시작 버튼을 확인하면,
     **Then** 버튼이 비활성(`disabled`) 상태이다.

### Edge Cases

- AI 서비스 호출 실패 시: 파일명 기반 폴백 적용 (`upload-page.tsx:191-195`), 사유 = "분석 실패 — 파일명 기반".
- 텍스트 추출 불가(스캔 PDF 등): 파일명만으로 판단 — 프롬프트에 `"(텍스트 추출 불가 — 파일명만으로 판단)"` 전달 (`ai_core.py:202`).
- API 동시 분류: 최대 3건 병렬 처리 (`upload-page.tsx:199-212`). 4건 이상이면 배치 큐 대기.
- JSON 파싱 실패 시: `_parse_json` fallback 반환 — `{"category": "unknown", "confidence": 0.3, "reason": "파싱 실패"}` (`ai_core.py:205`).

---

## Functional Requirements (EARS)

- **FR-001a** (event): WHEN 사용자가 파일을 업로드하면, THE SYSTEM SHALL `POST /api/classify` 엔드포인트를 호출한다.

- **FR-001b** (event): WHEN `POST /api/classify` 가 호출되면, THE SYSTEM SHALL 파일 텍스트와 파일명을 6종 카테고리(contract/internal/vendor/insurance/execution_plan/unknown) 중 하나와 신뢰도(0.0~1.0), 사유(reason) 문자열로 분류한 결과를 반환한다.

- **FR-002a** (ubiquitous): THE SYSTEM SHALL 분류 결과에 `category`·`confidence`·`reason` 세 필드를 보존한다.

- **FR-002b** (ubiquitous): THE SYSTEM SHALL 분류 근거(파일명·문서 내용 신호)를 `reason` 필드에 기록한다.

- **FR-003a** (unwanted): IF AI 분류 결과가 `category: "unknown"` 이고 `confidence < 0.5` 이면, THEN THE FRONTEND SHALL 파일명 키워드 기반 폴백 규칙(`classifyFileFallback`)을 적용해 카테고리를 재추정한다.

- **FR-003b** (unwanted): IF AI 분류 결과가 `category: "unknown"` 이고 `confidence < 0.5` 이면, THEN THE FRONTEND SHALL 해당 사유를 "키워드 기반 추정"으로 표시한다.

- **FR-004a** (unwanted): IF `POST /api/classify` 호출이 실패(예외 발생)하면, THEN THE FRONTEND SHALL 파일명 기반 폴백 분류(`classifyFileFallback`)를 적용한다.

- **FR-004b** (unwanted): IF `POST /api/classify` 호출이 실패(예외 발생)하면, THEN THE FRONTEND SHALL 사유를 "분석 실패 — 파일명 기반"으로 기록한다.

- **FR-005** (unwanted): IF 파일 목록에 `category: "unknown"` 항목이 1건 이상 존재하면, THEN THE FRONTEND SHALL 추출 시작 동작(startExtract)을 차단한다.

- **FR-006** (event): WHEN 담당자가 드롭다운에서 카테고리를 수동으로 지정하면, THE FRONTEND SHALL 해당 파일의 `category`를 선택값으로, `confidence`를 `1.0`으로, `manual`을 `true`로 갱신한다.

- **FR-007a** (state): WHILE 파일 분류가 진행 중(`classifying: true`)인 동안, THE FRONTEND SHALL 해당 파일 행에 "AI 분석 중…" 레이블을 표시한다.

- **FR-007b** (state): WHILE 파일 분류가 진행 중(`classifying: true`)인 동안, THE FRONTEND SHALL 카테고리 수동 선택 UI를 비활성화한다.

- **FR-008** (ubiquitous): THE SYSTEM SHALL 텍스트 추출이 불가능한 파일(스캔 PDF 등)에 대해 파일명만으로 분류를 시도하고, 프롬프트에 `"(텍스트 추출 불가 — 파일명만으로 판단)"` 신호를 포함한다.

- **FR-009** (optional): WHERE `USE_AI_SERVICE` 환경변수가 활성화된 경우, THE SYSTEM SHALL 분류 요청을 `ai-service` MSA의 `/classify` 엔드포인트로 프록시한다.

---

## Success Criteria (측정형)

- **SC-001**: 정상 파일 업로드 시 `/api/classify` 응답에 `category`·`confidence`·`reason` 3개 필드가 **100%** 존재한다.
- **SC-002**: 반환된 `category` 값이 6종 taxonomy(`contract|internal|vendor|insurance|execution_plan|unknown`) 중 하나에 해당하는 비율 = **100%** (taxonomy 외 값 0건).
- **SC-003**: `category: "unknown"` + `confidence < 0.5` 인 경우 프론트엔드 폴백 적용 후 `category` 값이 `"unknown"` 이외의 값으로 갱신되는 비율 — [NEEDS CLARIFICATION: 파일명에 키워드가 없는 경우 폴백도 "unknown"을 반환할 수 있음. 목표 커버리지 수치 미정].
- **SC-004**: `unknown` 파일 잔존 시 추출 시작 버튼 비활성화 — `canStart` 조건 충족률 **100%** (`upload-page.tsx:312`).
- **SC-005**: AI 호출 실패 시 폴백 분류 결과 반환까지 소요 시간 ≤ [NEEDS CLARIFICATION: 타임아웃 상한 미명시. `ai_core.py`의 Bedrock `read_timeout=60` (`ai_core.py:26`) 이후 fallback 반환].
- **SC-006**: 동시 분류 처리 수 최대 **3건** 병렬 유지 (`upload-page.tsx:199-212`).

---

## Key Entities

- **ClassificationResult**: `{category: FileCategory, confidence: float(0.0~1.0), reason: string}` — `POST /api/classify` 응답 스키마 (`ai_core.py:194-195`).
- **FileCategory**: `"contract" | "internal" | "vendor" | "insurance" | "execution_plan" | "unknown"` (`frontend/lib/types.ts:28`).
- **UploadedFile**: `{id, file?, name, size, type, category: FileCategory, confidence, classifying, reason, manual?}` (`frontend/lib/types.ts:15-26`).
- **CLASSIFY_PROMPT**: AI에 전달되는 분류 프롬프트 — 6종 카테고리 정의 포함 (`ai_core.py:175-195`).
- **classifyFileFallback**: 파일명 키워드 기반 폴백 함수 (`upload-page.tsx:36-44`).
- **LLM 모델 티어**: `classify` 작업은 `haiku` 티어 라우팅 (`ai_core.py:41`, `TASK_TIER["classify"]`).

---

## Assumptions

- **6종 taxonomy 정의**: `ai_core.py:184-192`에 프롬프트 내 정의가 있음 (코드 현행값=잠정). 공식 운영정책 문서(기획서) 미존재.
- **신뢰도 임계값 0.5**: `upload-page.tsx:185`에서 `confidence < 0.5` 조건 사용 — 코드 현행값=잠정. 해당 임계값 설정 근거 문서 없음.
- **폴백 confidence 상수** (`upload-page.tsx:38-43`): `execution_plan=0.68`, `contract=0.65`, `internal=0.62`, `insurance=0.70`, `vendor=0.55`, `unknown=0.30` — 코드 현행값=잠정.
- **파싱 실패 fallback confidence**: `0.3` (`ai_core.py:205`) — 코드 현행값=잠정.
- **텍스트 앞 2000자만 전달**: `ai_core.py:202` `text[:2000]` — 코드 현행값=잠정 (긴 문서의 후반부 신호 누락 가능).
- **`USE_AI_SERVICE` MSA 전환**: `main.py:521-526`에 토글 구현됨. 테스트 환경에서는 모놀리스 경로 사용.

---

## Clarifications Retained

1. **[NEEDS CLARIFICATION] 신뢰도 임계값 결정 근거**: `upload-page.tsx:185`의 `confidence < 0.5` 임계값은 코드에서 임의로 설정된 것으로 보이며, 설계 문서·운영 정책 내 수치 근거 없음. 사용자가 사내 기준으로 직접 확정 필요.
   - 출처 A: `upload-page.tsx:185` — `confidence < 0.5`
   - 출처 B: 설계 §6 및 `constitution.md` — 해당 임계값 불기재

2. **[NEEDS CLARIFICATION] 6종 taxonomy 공식 운영 정의**: 현재 6종(`contract/internal/vendor/insurance/execution_plan/unknown`) 정의는 AI 프롬프트 내 자연어 설명만 존재 (`ai_core.py:184-192`). 기획서·공식 운영 정책 문서의 별도 정의 여부 미확인.
   - 출처 A: `ai_core.py:184-192` (프롬프트 자연어 정의)
   - 출처 B: `frontend/lib/types.ts:28` (TypeScript 타입 — 6종 열거)
   - 두 출처는 taxonomy 목록 자체는 일치하나, 카테고리별 판단 기준의 공식 문서 없음.

3. **[NEEDS CLARIFICATION] 분류 정확도 SC 목표 수치**: SC-003의 폴백 커버리지, SC-005의 타임아웃 상한이 미정. 베이스라인 측정 후 목표 수치 결정 필요.
