# Implementation Plan: EXE-01 문서분류

**Feature**: EXE-01 문서분류
**Created**: 2026-06-26
**Status**: Draft

---

## 아키텍처 개요

EXE-01은 백엔드 분류 엔진(FastAPI + Bedrock Claude Haiku)과 프론트엔드 분류 UI(Next.js)로 구성된다.
백엔드는 파일 텍스트를 AI에 전달해 6종 카테고리를 결정하고, 프론트엔드는 결과를 표시·폴백·수동재분류로 처리한다.

```
사용자 업로드
     │
     ▼
[Frontend: upload-page.tsx]
     │ apiClassify(file)
     ▼
[Next.js API Route: /api/classify/route.ts]  ← 프록시 레이어
     │ fetchBackend("/api/classify")
     ▼
[FastAPI: main.py:514 POST /api/classify]
     │ USE_AI_SERVICE=false → classify_document(filename, text)
     │ USE_AI_SERVICE=true  → _call_ai_service("/classify", ...)
     ▼
[ai_core.py:198 classify_document]
     │ CLASSIFY_PROMPT (6종 카테고리 정의)
     ▼
[invoke_bedrock → Bedrock Claude Haiku]
     │ TASK_TIER["classify"] = "haiku"  (ai_core.py:41)
     ▼
[_parse_json → ClassificationResult]
     │ {category, confidence, reason}
     ▼
[Frontend: 결과 처리]
     │ confidence < 0.5 + unknown → classifyFileFallback
     │ 오류 시 → classifyFileFallback (파일명 기반)
     ▼
[UI: 카테고리 레이블 표시 / 수동재분류 드롭다운]
```

---

## 기술 스택

| 레이어 | 기술 | 버전/위치 |
|--------|------|-----------|
| 백엔드 API | FastAPI | `main.py` |
| AI 추론 | AWS Bedrock (Claude Haiku) | `ai_core.py:40-43` |
| AI 코어 | `ai_core.py` (모놀리스·MSA 공유) | `backend/services/ai_core.py` |
| MSA 분리(선택) | ai-service (`USE_AI_SERVICE` 토글) | `main.py:521-523` |
| 프론트엔드 | Next.js (React) | `frontend/components/pages/upload-page.tsx` |
| 상태 관리 | React useState / useCallback | `upload-page.tsx` |
| 타입 정의 | TypeScript | `frontend/lib/types.ts:28` |

---

## FR ↔ 컴포넌트 매핑

| FR | 설명 | 담당 컴포넌트 | file:line |
|----|------|--------------|-----------|
| FR-001a | 파일 업로드 시 `/api/classify` 호출 | `apiClassify(file)` | `upload-page.tsx:184` |
| FR-001b | 6종 분류 + 신뢰도·사유 산출 반환 | `classify_document()` | `ai_core.py:198-205` |
| FR-001b | API 엔드포인트 진입점 | `classify_file()` | `main.py:514-526` |
| FR-001b | 분류 프롬프트(6종 카테고리 정의) | `CLASSIFY_PROMPT` | `ai_core.py:175-195` |
| FR-002a | 분류 결과 3필드 보존 | `_parse_json` 반환값 | `ai_core.py:205` |
| FR-002b | `reason` 필드 기록 경로 | `CLASSIFY_PROMPT` JSON 응답 형식 | `ai_core.py:194` |
| FR-003a | `unknown`+`confidence<0.5` 폴백 카테고리 재추정 | `classifyFileFallback()` | `upload-page.tsx:36-44` |
| FR-003b | 폴백 후 "키워드 기반 추정" 사유 표시 | 분류 결과 처리 블록 | `upload-page.tsx:185-187` |
| FR-004a | AI 호출 실패 시 파일명 폴백 적용 | `catch` 블록 | `upload-page.tsx:191-195` |
| FR-004b | AI 호출 실패 사유 "분석 실패 — 파일명 기반" 기록 | `catch` 블록 | `upload-page.tsx:191-195` |
| FR-005 | `unknown` 잔존 시 추출 차단 | `canStart` 계산식 | `upload-page.tsx:312` |
| FR-006 | 수동 재분류 — `category`/`confidence`/`manual` 갱신 | `reclassify()` | `upload-page.tsx:300-301` |
| FR-007a | 분류 중 "AI 분석 중…" 레이블 표시 | `FileRow` 컴포넌트 | `upload-page.tsx:523` |
| FR-007b | 분류 중 카테고리 드롭다운 비활성화 | `FileRow` 컴포넌트 | `upload-page.tsx:526` |
| FR-008 | 텍스트 추출 불가 시 파일명만 전달 + 프롬프트 신호 포함 | `classify_file()` → `_safe_extract_text()` | `main.py:519`, `ai_core.py:202` |
| FR-009 | MSA 프록시 (`USE_AI_SERVICE`) | `_call_ai_service("/classify", ...)` | `main.py:521-523` |

---

## 의존 관계

### EXE-01이 제공하는 출력 (Produces)

| 출력 | 타입 | 소비 기능 |
|------|------|-----------|
| `ClassificationResult.category` | `FileCategory` | **EXE-02 소스추출** — 분류 결과에 따라 문서 역할을 구분해 추출 전략을 결정 |
| `ClassificationResult.category` | `FileCategory` | **EXE-14 import 역추출** — `execution_plan` 카테고리 파일을 역추출 대상으로 식별 |
| `UploadedFile.category` | `FileCategory` | **EXE-04 기본정보 확인 게이트** (간접) — `canStart` 충족(`unknown=0`)이 다음 단계 진입 조건 |

### EXE-01이 소비하는 입력 (Consumes)

| 입력 | 제공처 |
|------|--------|
| 파일 바이너리 (UploadFile) | 사용자 브라우저 업로드 |
| AWS Bedrock 자격증명 | 인프라 (EKS IRSA / 환경변수) |
| `USE_AI_SERVICE` 환경변수 | 배포 설정 |

### 외부 의존

- **AWS Bedrock (Claude Haiku)**: `HAIKU_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0` (`ai_core.py:36`). Bedrock VPC 엔드포인트 필요 (프로젝트 메모리 `project_dev_deploy.md` 참조).
- **`_safe_extract_text()`**: 파일 파서 — 텍스트 추출 실패 시 빈 문자열 반환, `ai_core.py:202`의 폴백 문자열로 대체.
- **`_parse_json()`**: JSON 균형괄호 추출 (`ai_core.py:622-672`) — 모델이 JSON 뒤에 산문을 붙이는 경우에도 안전하게 추출.

---

## 데이터 흐름 상세

### 백엔드 분류 흐름

1. `main.py:514` `POST /api/classify` 진입 — `require_auth` 의존성으로 인증 강제.
2. `main.py:517-519`: 파일 읽기 → `_check_upload_size()` → `_safe_extract_text()`.
3. `main.py:521-526`: `USE_AI_SERVICE` 분기 — 모놀리스 or MSA.
4. `ai_core.py:198-205`: `CLASSIFY_PROMPT` 포맷 → `_call_claude(max_tokens=[NEEDS CLARIFICATION: 256이 코드에 실제 기재된 값인지 `ai_core.py:198-205` 직접 확인 필요 — spec.md Assumptions에 미기재, 설계 §10 검증 로그에도 수치 근거 없음], task_type="classify")` → `_parse_json` 반환.
5. 반환값: `{"category": str, "confidence": float, "reason": str}`.

### 프론트엔드 분류 흐름

1. `upload-page.tsx:182-197`: 파일별 `classify(item)` 비동기 실행, 최대 3건 병렬 (`upload-page.tsx:199-212`).
2. 성공 시: `result.category === "unknown" && result.confidence < 0.5` 조건 평가 → 폴백 or 원본 적용.
3. 실패 시: `classifyFileFallback(item.name)` + 사유 "분석 실패 — 파일명 기반".
4. `canStart = name && hasContract && hasInternal && counts.unknown === 0` (`upload-page.tsx:312`).

---

## 경계 (비포함)

- 파일 저장소 CRUD (`/api/files*`) — non-goal (설계 §9).
- OTEL/RateLimit/Security 미들웨어 — non-goal (설계 §9).
- 분류 결과 DB 영속화 — EXE-01 범위 외 (현재 프론트 상태로만 유지).

> **Non-goal 추적 가능성 주의**: 위 목록은 설계 §9 참조를 기반으로 기술됨. constitution §범위밖(non-goal)과 설계 §9 목록이 실제로 일치하는지 cross-check가 이 문서 내에서 명시적으로 수행되지 않았다. 향후 설계 §9 개정 시 이 섹션과의 정합성을 수동으로 확인할 것.
