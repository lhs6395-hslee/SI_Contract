# Implementation Plan: EXE-14 — import 역추출

**Created**: 2026-06-26  **Status**: Draft
**기능 성격**: 백엔드 도메인(Bedrock 호출·JSON 파싱) + 프론트 게이트(단위 확정 UX)

---

## 아키텍처 개요

```
[프론트: upload-page.tsx]
  ↓ handleImportPlan() → apiImport(files)
  ↓ POST /api/import (Next.js Route: app/api/import/route.ts → proxy → FastAPI)

[백엔드: main.py POST /api/import]
  ↓ require_auth → _assert_project_access (stored_files 소유권)
  ↓ _documents_from_request(files, stored_files) → documents: [{filename, text, images}]
  ↓ USE_AI_SERVICE 분기
    ├── True  → _call_ai_service("/import", {documents}) → ai-service POST /import
    └── False → import_execution_plan(documents) [ai_core.py:599]
                  ↓ _call_claude(IMPORT_PROMPT, max_tokens=8192, images=_collect_images(docs))
                  ↓ _parse_json(raw, fallback) → {extracted, costItems, rates, importMeta}

[프론트: upload-page.tsx onComplete]
  ↓ ExtractedData 저장: importMeta, unitConfirmed=false
  ↓ setRoute("review")

[프론트: review-page.tsx]
  ↓ importPending = !!importMeta && !unitConfirmed
  ↓ 단위 확정 배너 렌더링 (importPending=true)
  ↓ confirmUnits() → factor 적용 → unitConfirmed=true

[프론트: other-pages.tsx doGenerate()]
  ↓ importMeta && !unitConfirmed → alert + setRoute("review") 차단
```

---

## 스택 및 컴포넌트

| 레이어 | 기술 | 역할 |
|--------|------|------|
| API 엔드포인트 | FastAPI POST `/api/import` | 인가·파일 수신·라우팅 |
| 역추출 로직 | `ai_core.py:599 import_execution_plan()` | Bedrock 호출 + JSON 파싱 |
| LLM | Bedrock Claude (모델 라우팅 `task_type="extract_full"`) | 0차 역추출 추론 |
| JSON 파싱 | `ai_core.py:622 _parse_json()` | 균형괄호 알고리즘 |
| Vision | `ai_core.py:165 _collect_images()` | 스캔 PDF base64 이미지 전송 |
| Next.js 프록시 | `frontend/app/api/import/route.ts` | 프론트→FastAPI 프록시 라우트 |
| 프론트 타입 | `frontend/lib/types.ts:111-115` | importMeta, unitConfirmed 타입 정의 |
| 프론트 API 래퍼 | `frontend/lib/api.ts:56 apiImport()` | FormData 구성 + fetch |
| upload UX | `frontend/components/pages/upload-page.tsx:76-118` | 파일 선택 → 역추출 실행 |
| 단위 확정 게이트 | `frontend/components/pages/review-page.tsx:181-227` | 배너·확정 로직 |
| 진행 차단 | `frontend/components/pages/other-pages.tsx:228-233` | 파이프라인 실행 전 게이트 |
| ai-service | `services/ai-service/main.py:119-121 POST /import` | MSA 분리 환경 처리 |

---

## FR별 컴포넌트 매핑

| FR | EARS 패턴 | 구현 컴포넌트 (file:line) |
|----|-----------|--------------------------|
| FR-001 | event | `ai_core.py:599-617 import_execution_plan()` + `main.py:637-670` |
| FR-002 | event | `ai_core.py:612 _call_claude(max_tokens=8192)` + `ai_core.py:622-672 _parse_json()` |
| FR-003 | ubiquitous | `IMPORT_PROMPT ai_core.py:551-554`, `types.ts:35-37,54-55` |
| FR-004 | ubiquitous | `main.py:647-648` 주석, `review-page.tsx:667-668` 자동확정 없음 |
| FR-005 | event | `ai_core.py:165-169 _collect_images()`, `ai_core.py:613` images 인자 |
| FR-006 | unwanted | `main.py:663-664` HTTPException 422 |
| FR-007 | unwanted | `main.py:650-660 _assert_project_access()` |
| FR-008 | unwanted | `ai_core.py:616-617 _parse_json fallback` |
| FR-009 | optional | `main.py:666-667 USE_AI_SERVICE` 분기, `ai-service/main.py:119-121` |
| FR-010a | state | `review-page.tsx:183-184 importPending`, `review-page.tsx:656-692 배너 JSX` |
| FR-010b | state | `other-pages.tsx:229-233 비활성화 게이트` |
| FR-011a | event | `review-page.tsx:202-227 confirmUnits() factor 적용` |
| FR-011b | event | `review-page.tsx:202-227 unitConfirmed=true 전환` |
| FR-011c | event | `review-page.tsx:183-184`, `other-pages.tsx:229-233 게이트 해제` |
| FR-012 | ubiquitous | `ai_core.py:613 limit=16000`, `ai_core.py:273-277 _doc_block()` |

---

## 의존 관계

### EXE-14가 소비하는 기능

| 의존 | 근거 |
|------|------|
| **EXE-01 (문서분류)**: 업로드 파일의 category가 `execution_plan`임을 UI 레벨에서 마킹 | `upload-page.tsx:97`: `category: "execution_plan"` 하드코딩. 역추출 전용 분기이므로 EXE-01 분류 결과를 소비하지 않고 직접 분기 |
| **인가 시스템 (EXE-17)**: `require_auth`, `_assert_project_access` | `main.py:641,660` |

### EXE-14를 소비하는 기능

| 소비자 | 근거 |
|--------|------|
| **EXE-04 (기본정보 확인 게이트)**: import 0차 결과가 review-page의 `ExtractedData`로 진입해 EXE-04의 confirmedTabs 흐름에 합류 | `upload-page.tsx:99 unitConfirmed=false`, `review-page.tsx:106 confirmedTabs` |
| **EXE-06 (Sprint_Contract 생성)**: 단위 확정 후 `ExtractedData`가 파이프라인 입력으로 사용 | `other-pages.tsx:239 apiStartPipeline` |

### 비의존 (명시 분리)

- EXE-02(소스추출): 견적서 기반 추출. EXE-14는 별도 엔드포인트·별도 프롬프트. 동일 `_parse_json` 유틸만 공유.
- EXE-05(충돌 감지): 역추출 0차는 단일 문서이므로 충돌 감지 대상 아님.

---

## 데이터 흐름 상세

### 1. 입력 문서 조합 (`_doc_block`, limit=16000)

```
[문서 1: 집행계획서.pdf]
<텍스트 최대 16000자>
```

일반 추출(`extract_all_fields`)의 기본 limit=4000과 달리 16000으로 확장된 이유:  
산출내역·요율·영업담당 시트가 4000자 이후에 위치해 누락되는 실측 문제를 해결.  
[공식 코드: `ai_core.py:606-611` 주석]

### 2. 응답 스키마

```json
{
  "extracted": {
    "projectName":  {"value": "...", "source": "...", "confidence": "verified|guess|null"},
    "revenue":      {"value": 0, "unit": "원", "unitConfidence": "high|low", "source": "...", "confidence": "..."},
    ...17개 필드
  },
  "costItems": [
    {"category": "fee|labor|...", "name": "...",
     "contractQty": 0, "contractPrice": 0, "contractAmount": 0,
     "executionQty": 0, "executionPrice": 0, "executionAmount": 0,
     "unitConfidence": "high|low", "source": "...", "confidence": "..."}
  ],
  "rates": {
    "indirectRate": {"value": 0, "source": "..."},
    ...6종
  },
  "importMeta": {"unitGuessed": true, "missingFields": ["..."]}
}
```

[공식 코드: `ai_core.py:557-596 IMPORT_PROMPT`, `ai_core.py:616 fallback`]

### 3. 단위 확정 factor 적용

| 사용자 선택 | factor | 처리 |
|------------|--------|------|
| 천원 (기본) | 1 | 백엔드 환산값 그대로 사용 |
| 원 | 1/1000 | `Math.round(value * factor)` |

대상 필드: `revenue`, `cost`, `profit`, `indirectCost` + 모든 `costItems`의 `contractPrice`, `contractAmount`, `executionPrice`, `executionAmount`.  
[공식 코드: `review-page.tsx:186,202-227`]

---

## 비기능 고려사항

- **Bedrock 비용**: `max_tokens=8192` × 단일 문서 1회 호출. 일반 추출의 2048 대비 4배. 집행계획서 역추출은 빈도가 낮으므로 허용.
- **Vision 이미지 상한**: 최대 8장 전송. 초과 시 `_logger.warning` 후 누락. [공식 코드: `ai_core.py:115-117`]
- **JSON 트렁케이션 대응**: `_parse_json` 균형괄호 알고리즘 + greedy 폴백 + dict fallback. 3단계 방어.
- **프론트 상태 비영속**: `unitConfirmed`는 React 상태이므로 페이지 새로고침 시 초기화된다. 저장된 프로젝트는 DynamoDB의 `importMeta`로 재판단한다. [NEEDS CLARIFICATION: `importMeta`가 DynamoDB에 별도 명시 저장되는 경로 미확인 — `apiSaveProject`가 전체 project blob을 전송하므로 포함될 수 있으나 명시적 저장 코드 없음. 실제 저장 경로 확인 후 업데이트 필요]
