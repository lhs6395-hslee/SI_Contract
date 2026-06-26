# Tasks: EXE-14 — import 역추출

**Created**: 2026-06-26  **Status**: Draft
**주의**: 이 tasks.md는 사람이 읽는 구현 계획 산출물이다. 자동 implement 비의존.

---

## Task 1: 역추출 엔드포인트 기본 동작 검증

**수용기준**: SC-001 — 유효한 집행계획서 PDF 1건 전송 시 `extracted`, `costItems`, `rates`, `importMeta` 4개 키 포함 응답.

**대상 FR**: FR-001, FR-002, FR-012

### 1-1. 실패 테스트 작성

```
테스트: test_import_returns_required_keys
Given: 실제 집행계획서 PDF 파일 1건 (또는 텍스트 대역)
When:  POST /api/import (인증 토큰 포함, multipart/form-data)
Then:  HTTP 200, 응답 JSON에 "extracted", "costItems", "rates", "importMeta" 키 존재
```

현재 상태: 엔드포인트는 구현 완료 (`main.py:637`). 통합 테스트 스크립트(`run_all_suites.sh`)에 import 케이스 포함 여부 확인 필요.

### 1-2. 최소 구현 (이미 구현됨, 검증 초점)

- `ai_core.py:599-617 import_execution_plan()` — 코드 현행 확인
- `main.py:637-670` — 인가·파일없음·USE_AI_SERVICE 분기 현행 확인
- `_doc_block(documents, limit=16000)` 호출 확인 (`ai_core.py:613`)

### 1-3. 검증 체크리스트

- [ ] PDF(텍스트 추출 가능) 1건 → 응답 4개 키 존재
- [ ] `extracted.projectName.confidence` ∈ {"verified", "guess", "null"}
- [ ] `importMeta.unitGuessed` 타입 Boolean
- [ ] `costItems` 배열(빈 배열도 허용)
- [ ] `rates` null 또는 객체(6개 요율 키)

### 1-4. 커밋 단위

```
test(EXE-14): import 기본 응답 스키마 검증 통합테스트
```

---

## Task 2: JSON 트렁케이션 폴백 동작 검증

**수용기준**: SC-006 — Bedrock 응답 JSON 잘림 시 fallback 반환, HTTP 500 없음.

**대상 FR**: FR-002, FR-008

### 2-1. 실패 테스트 작성

```
테스트: test_import_fallback_on_truncated_json
Given: _call_claude가 잘린 JSON 문자열("{"project": "이름", "cost") 반환하도록 mock
When:  import_execution_plan([{"filename": "test.pdf", "text": "...", "images": []}]) 호출
Then:  반환값 = {"extracted": {}, "costItems": [], "rates": None, "importMeta": {"unitGuessed": True, "missingFields": []}}
       예외 발생 없음
```

### 2-2. 검증 포인트 (코드 경로)

1. `_parse_json` 균형괄호 알고리즘 실패 경로 (`ai_core.py:659-663`)
2. greedy 폴백 실패 경로 (`ai_core.py:666-671`)
3. 최종 `return fallback` (`ai_core.py:672`)

### 2-3. 체크리스트

- [ ] mock으로 잘린 JSON 주입 → fallback dict 반환 확인
- [ ] 완전히 빈 응답("") → fallback 반환 (`ai_core.py:631-632`)
- [ ] 유효 JSON 뒤에 산문 첨부된 경우 → 앞부분만 추출 (균형괄호 경로)

### 2-4. 커밋 단위

```
test(EXE-14): _parse_json 균형괄호 폴백 경로 단위테스트
```

---

## Task 3: 파일 없음 / 인가 오류 처리 검증

**수용기준**: SC-005 — 파일 없음 요청 HTTP 422. FR-006, FR-007 동작 확인.

**대상 FR**: FR-006, FR-007

### 3-1. 실패 테스트 작성

```
테스트 A: test_import_no_files_returns_422
Given: 빈 FormData (files 없음, stored_files 없음)
When:  POST /api/import (인증 토큰 포함)
Then:  HTTP 422, detail 포함 "가져올 파일이 필요합니다"

테스트 B: test_import_unauthorized_project_access
Given: stored_files에 타 사용자 소유 projectId 포함
When:  POST /api/import (본인 인증 토큰)
Then:  HTTP 403 또는 비인가 응답 (구체 코드는 _assert_project_access 구현 따름)
```

### 3-2. 코드 경로

- 파일 없음: `main.py:662-664` `HTTPException(422)`
- 인가: `main.py:650-660 _assert_project_access(pid, current_user)`

### 3-3. 체크리스트

- [ ] 빈 FormData → 422 + detail 문자열
- [ ] stored_files only (files=[]) + valid project → 정상 처리(files[]는 프론트가 안 보냄, stored_files로 처리 경로 확인)
- [ ] 타인 소유 projectId → 비인가 응답

### 3-4. 커밋 단위

```
test(EXE-14): import 파일없음 422 + 인가 게이트 통합테스트
```

---

## Task 4: 단위 확정 배너 렌더링 및 차단 동작 검증 (프론트)

**수용기준**: SC-002, SC-003 — 배너 표시 + 파이프라인 진행 차단.

**대상 FR**: FR-010a, FR-010b, FR-011a, FR-011b, FR-011c

### 4-1. 실패 테스트 작성 (프론트 단위 또는 E2E)

```
테스트 A: test_unit_gate_banner_shown_when_import_pending
Given: ExtractedData에 importMeta={unitGuessed: true} 설정, unitConfirmed=false
When:  review-page 렌더링
Then:  "PDF 추출 결과 — 금액·단위 확인 필수" Alert 컴포넌트 존재

테스트 B: test_pipeline_blocked_when_unit_not_confirmed
Given: importMeta 존재, unitConfirmed=false
When:  doGenerate() 호출 (other-pages.tsx)
Then:  alert 호출 + setRoute("review") 호출
       apiStartPipeline 호출 없음

테스트 C: test_unit_gate_hidden_after_confirmation
Given: importMeta 존재, unitConfirmed=false 상태에서 confirmUnits() 실행
When:  단위 선택 "천원", "이 단위로 금액 확정" 클릭
Then:  unitConfirmed=true, importPending=false, 배너 사라짐
```

### 4-2. 코드 경로

- `review-page.tsx:183-184` importPending 계산
- `review-page.tsx:202-227 confirmUnits()`
- `other-pages.tsx:228-233 doGenerate()` 차단
- `review-page.tsx:656-692` 배너 JSX

### 4-3. 체크리스트

- [ ] `importMeta=undefined` → 배너 없음 (일반 추출 경로)
- [ ] `importMeta` 존재 + `unitConfirmed=false` → 배너 표시
- [ ] `importMeta` 존재 + `unitConfirmed=true` → 배너 없음
- [ ] 단위 "원" 선택 후 확정 → revenue ÷1000, costItems 모든 금액 ÷1000 (1원 정밀도)
- [ ] 단위 "천원" 선택 후 확정 → 값 그대로 유지 (factor=1)
- [ ] 미확인 금액 건수(`unconfirmedAmountCount`) 배너에 정확히 표시

### 4-4. 커밋 단위

```
test(EXE-14): 단위 확정 게이트 프론트 동작 (배너·차단·확정 후 해제)
```

---

## Task 5: Vision 멀티모달 경로 검증

**수용기준**: 스캔본 PDF(텍스트 없음) 처리 시 이미지 전송 경로 활성화.

**대상 FR**: FR-005

### 5-1. 테스트 시나리오

```
테스트: test_import_collects_images_for_vision
Given: 문서 중 images 리스트가 있는 항목 포함 (base64 png mock)
When:  import_execution_plan(documents) 호출
Then:  _call_claude 호출 시 images 인자에 해당 base64 포함
       이미지 9장 이상이면 경고 로그 발생 + 8장만 전송
```

### 5-2. 코드 경로

- `ai_core.py:165-169 _collect_images()`
- `ai_core.py:613` `images=_collect_images(documents)` 인자
- `ai_core.py:104-118 invoke_bedrock()` Vision 분기

### 5-3. 체크리스트

- [ ] images=[] 인 경우 → 텍스트 단독 호출 (Vision 미사용 경로)
- [ ] images 8장 → 8장 전송
- [ ] images 9장 → 경고 로그 + 8장 전송, 1장 누락 로그

### 5-4. 커밋 단위

```
test(EXE-14): Vision 이미지 수집 및 8장 상한 경로 검증
```

---

## Task 6: USE_AI_SERVICE 프록시 경로 검증

**수용기준**: USE_AI_SERVICE=true 환경에서 ai-service POST /import 호출.

**대상 FR**: FR-009

### 6-1. 테스트 시나리오

```
테스트: test_import_proxied_to_ai_service_when_flag_true
Given: USE_AI_SERVICE=True 환경변수 설정, _call_ai_service mock
When:  POST /api/import (파일 포함)
Then:  _call_ai_service("/import", {"documents": ...}) 호출
       import_execution_plan() 직접 호출 없음
```

### 6-2. 코드 경로

- `main.py:666-667 USE_AI_SERVICE` 분기
- `services/ai-service/main.py:119-121 POST /import`

### 6-3. 체크리스트

- [ ] USE_AI_SERVICE=False → `import_execution_plan()` 직접 호출
- [ ] USE_AI_SERVICE=True → `_call_ai_service("/import", ...)` 호출
- [ ] ai-service 엔드포인트 반환값이 `main.py` 응답과 동일 스키마

### 6-4. 커밋 단위

```
test(EXE-14): USE_AI_SERVICE 프록시 분기 검증
```

---

## 완료 기준 요약

| Task | SC 커버 | 상태 |
|------|---------|------|
| Task 1: 역추출 기본 동작 | SC-001 | 구현 완료(코드), 테스트 작성 필요 |
| Task 2: JSON 폴백 | SC-006 | 구현 완료(코드), 단위테스트 작성 필요 |
| Task 3: 파일없음 422 + 인가 | SC-005 | 구현 완료(코드), 통합테스트 작성 필요 |
| Task 4: 단위 게이트 프론트 | SC-002, SC-003, SC-004 | 구현 완료(코드), 프론트 테스트 작성 필요 |
| Task 5: Vision 경로 | SC-001 일부 | 구현 완료(코드), mock 테스트 필요 |
| Task 6: ai-service 프록시 | - | 구현 완료(코드), mock 분기 테스트 필요 |

**미결 수용기준**: SC-007(latency SLA)은 [NEEDS CLARIFICATION] — 베이스라인 측정 후 별도 성능 task 추가.

---

## 주의사항

- 모든 금액 검증은 **1원 정밀도**(Math.round 결과 정수 일치). 소수점 발생 시 FAIL.
- 단위 게이트는 `importMeta` 존재 여부로만 판단한다. `unitConfirmed`가 `true`이면 `importMeta`가 있어도 게이트 해제.
- 테스트에서 실제 Bedrock 호출은 mock으로 대체. 실측 통합테스트는 `run_all_suites.sh` 별도 스위트로 분리.
