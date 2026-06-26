# Implementation Plan: EXE-02 — 소스추출

**Feature**: EXE-02 소스추출  **Plan Date**: 2026-06-26  **Status**: Draft  
**Scope**: 문서(spec/plan/tasks)까지. 코드 구현/자동 implement 비대상(헌법 §VII).

---

## 1. 아키텍처 개요

EXE-02는 **백엔드 도메인 기능**이다. 프론트엔드는 각 섹션 탭의 API 호출 주체이나 추출 로직 자체는 백엔드에 있다.

```
[프론트엔드 탭 UI]
        │  multipart/form-data (files + stored_files)
        ▼
[FastAPI main.py — 인증 게이트(EXE-17)]
  /api/extract         → _doc_from_content → extract_all_fields
  /api/extract-costs   → _documents_from_request → _tab_extract("costs")
  /api/extract-people  → _documents_from_request → _tab_extract("people")
  /api/extract-schedule→ _documents_from_request → _tab_extract("schedule")
  /api/extract-rates   → _documents_from_request → _tab_extract("rates")
  /api/extract-org     → _documents_from_request → _tab_extract("org")
        │
        ├─ USE_AI_SERVICE=false (모놀리스 기본)
        │       └─ services/claude_api.py (re-export 레이어)
        │               └─ services/ai_core.py (실제 로직)
        │                       ├─ invoke_bedrock (Bedrock Claude)
        │                       ├─ _parse_json (균형괄호 파싱)
        │                       └─ _normalize_cost_category / _force_category_by_name
        │
        └─ USE_AI_SERVICE=true (MSA 경로)
                └─ ai-service/main.py → services/ai_core.py (동일 모듈 복사)
```

**스택**:
- 런타임: Python 3.14 / FastAPI (`backend/main.py`)
- AI: AWS Bedrock (`bedrock-runtime`), Claude Sonnet (`global.anthropic.claude-sonnet-4-6`)
- 파일 파싱: `services/file_parser.py` (텍스트 추출), Vision(스캔 PDF → base64 이미지)
- 저장 파일: `services/s3_storage.py` (`get_file`)
- 공유 AI 코어: `backend/services/ai_core.py` (backend·ai-service 양쪽 동일 파일)

---

## 2. FR ↔ 컴포넌트 매핑

| FR | 설명 | 파일 : 라인 | 컴포넌트 |
|----|------|-------------|----------|
| FR-001 | 전체 필드 일괄 추출 | `main.py:544-558`, `ai_core.py:259-268` | `extract_all_fields`, `EXTRACT_PROMPT` |
| FR-002 | 추출값 출처 보존 | `ai_core.py:216-236` | `EXTRACT_PROMPT` JSON 스키마 (`source`/`confidence` 필드) |
| FR-003 | 미발견 필드 null 처리 | `ai_core.py:254` | `EXTRACT_PROMPT` 규칙 (`{"value": null, "source": "", "confidence": "null"}`) |
| FR-004 | 비목 섹션 추출 | `main.py:605-608`, `ai_core.py:464-472` | `extract_costs_endpoint`, `extract_costs`, `COSTS_PROMPT` |
| FR-005a | 비목 카테고리 정규화 | `ai_core.py:329-385` | `_COST_CAT_ALIAS`, `_normalize_cost_category`, `_force_category_by_name` |
| FR-005b | 비목 카테고리 미매핑 → "etc" | `ai_core.py:349-359` | `_normalize_cost_category` |
| FR-005c | 비목 항목 보존 | `ai_core.py:466-471` | `extract_costs` |
| FR-006 | 자사 인력 추출 제외 | `ai_core.py:284-316` | `COSTS_PROMPT` 규칙 (프롬프트 레벨 제어) |
| FR-007 | 인원 섹션 추출 | `main.py:611-614`, `ai_core.py:475-477` | `extract_people_endpoint`, `extract_people`, `PEOPLE_PROMPT` |
| FR-008 | 매출 단가 인원 추출 제외 | `ai_core.py:396-397` | `PEOPLE_PROMPT` 규칙 |
| FR-009 | 일정 섹션 추출 | `main.py:617-620`, `ai_core.py:480-482` | `extract_schedule_endpoint`, `extract_schedule`, `SCHEDULE_PROMPT` |
| FR-010 | 요율 섹션 추출 | `main.py:623-626`, `ai_core.py:485-487` | `extract_rates_endpoint`, `extract_rates`, `RATES_PROMPT` |
| FR-011 | 요율 미명시 처리 | `ai_core.py:433-435` | `RATES_PROMPT` 규칙 (합산 표기→0 반환) |
| FR-012 | 조직 섹션 추출 | `main.py:629-632`, `ai_core.py:490-492` | `extract_org_endpoint`, `extract_org`, `ORG_PROMPT` |
| FR-013 | ai-service 위임 | `main.py:553-556`, `main.py:598-602` | `USE_AI_SERVICE` 환경 변수 분기, `_call_ai_service` |
| FR-014 | Vision 멀티모달 추출 | `ai_core.py:113-124`, `ai_core.py:165-170` | `invoke_bedrock` (images 파라미터), `_collect_images` |
| FR-015a | LLM JSON 파싱 실패 시 fallback 반환 | `ai_core.py:622-668` | `_parse_json` (균형괄호 알고리즘 + greedy fallback) |
| FR-015b | LLM JSON 파싱 실패 시 예외 비전파 | `ai_core.py:466-492` | 각 extract 함수 try/except |
| FR-016a | Bedrock 오류 내부 격리 (`AIUnavailableError`) | `ai_core.py:148-156` | `invoke_bedrock` 예외 처리 |
| FR-016b | Bedrock 오류 클라이언트 메시지 마스킹 | `ai_core.py:148-156` | `invoke_bedrock` 예외 처리 |
| FR-017 | 저장 파일 기반 추출 | `main.py:563-590` | `_documents_from_request` (S3 `get_file` 경로) |

---

## 3. 모듈 구조 상세

### 3-1. `backend/services/ai_core.py` (핵심)

EXE-02의 실제 추출 로직이 모두 여기에 있다. `claude_api.py`는 하위호환 re-export 레이어(`claude_api.py:8-30`).

| 함수/상수 | 라인 | 역할 |
|-----------|------|------|
| `EXTRACT_PROMPT` | 210~256 | 전체 필드 추출 프롬프트 (20 필드 JSON 스키마) |
| `extract_all_fields` | 259~268 | 전체 필드 추출 진입점 |
| `COSTS_PROMPT` | 280~325 | 비목 추출 프롬프트 (14종 category 정의) |
| `_COST_CAT_ALIAS` | 329~346 | category 정규화 매핑 (한글/영문 변형 → 표준 키) |
| `_normalize_cost_category` | 349~359 | 정규화 함수 (부분 일치 포함, 미지→"etc") |
| `_force_category_by_name` | 379~385 | 이름 키워드 강제 매핑 (재현성 보장) |
| `extract_costs` | 464~472 | 비목 추출 + 정규화 적용 |
| `PEOPLE_PROMPT` | 388~408 | 인원 추출 프롬프트 |
| `extract_people` | 475~477 | 인원 추출 |
| `SCHEDULE_PROMPT` | 411~424 | 일정 추출 프롬프트 |
| `extract_schedule` | 480~482 | 일정 추출 |
| `RATES_PROMPT` | 427~445 | 요율 추출 프롬프트 |
| `extract_rates` | 485~487 | 요율 추출 |
| `ORG_PROMPT` | 448~461 | 조직 추출 프롬프트 |
| `extract_org` | 490~492 | 조직 추출 |
| `extract_section` | 495~503 | 섹션 키 디스패치 (`_tab_extract`에서 호출) |
| `_parse_json` | 622~668 | 균형괄호 JSON 추출 + greedy fallback |
| `invoke_bedrock` | 97~156 | Bedrock 단일 호출 (Vision 멀티모달, 모델 라우팅, 오류 격리) |
| `_collect_images` | 165~170 | Vision용 base64 이미지 수집 |
| `TASK_TIER` | 40~53 | 작업별 모델 티어 라우팅 (`extract_costs/people/schedule/rates/org` → sonnet) |

### 3-2. `backend/main.py` — 엔드포인트 레이어

| 엔드포인트 | 라인 | 인증 | 역할 |
|-----------|------|------|------|
| `POST /api/extract` | 544~558 | `require_auth` | 전체 필드 추출 |
| `POST /api/extract-costs` | 605~608 | `require_auth` | 비목 추출 |
| `POST /api/extract-people` | 611~614 | `require_auth` | 인원 추출 |
| `POST /api/extract-schedule` | 617~620 | `require_auth` | 일정 추출 |
| `POST /api/extract-rates` | 623~626 | `require_auth` | 요율 추출 |
| `POST /api/extract-org` | 629~632 | `require_auth` | 조직 추출 |

공용 헬퍼:
- `_documents_from_request` (`main.py:563-590`): 업로드 파일 + S3 저장 파일 합산 로드
- `_tab_extract` (`main.py:593-602`): USE_AI_SERVICE 분기

---

## 4. 데이터 흐름

```
업로드 파일 (multipart)
  └─ _check_upload_size → _doc_from_content
        ├─ file_parser → text 추출
        └─ Vision 변환 → base64 images []
                │
                ▼
        DocumentBlock { filename, text, images }
                │
                ▼
        _documents_from_request (S3 stored_files 병합)
                │
         ┌──────┴──────────────────────────────────┐
         │                                          │
  extract_all_fields                        _tab_extract(section)
  (EXTRACT_PROMPT, max_tokens=2048)         (COSTS_PROMPT 등, max_tokens=512~2048)
         │                                          │
         └──────────────┬───────────────────────────┘
                        │
                 invoke_bedrock(temperature=0.0)
                        │
                 _parse_json (균형괄호)
                        │
                 category 정규화 (비목만)
                        │
                 JSON 응답 반환
```

---

## 5. 의존 관계

### 5-1. 이 기능이 소비하는 것 (Upstream)

| 기능 | 근거 |
|------|------|
| **EXE-01 문서분류** | EXE-01이 분류 결과를 제공한다. 단, 현재 코드에서 추출 엔드포인트가 분류 결과를 직접 읽어 필터링하는 로직은 없음 — 프론트엔드가 분류 후 추출을 호출하는 흐름으로 운용. |
| **EXE-17 인증·인가** | 모든 추출 엔드포인트가 `require_auth` 의존 (`main.py:544, 605, 611, 617, 623, 629`). |

### 5-2. 이 기능이 생산하는 것 (Downstream)

| 기능 | 소비 데이터 |
|------|------------|
| **EXE-03 사내기준보정** | `RatesObject` (요율 0 반환 시 fallback 적용) + `StaffEntry.grade` (직급 기반 단가 보정) |
| **EXE-04 기본정보 확인 게이트** | `ExtractedFields` (6개 기본정보 탭 표시) |
| **EXE-05 견적서 충돌 감지·해결** | `CostItem[]` (다중 견적서 교차 비교) |
| **EXE-06 Sprint_Contract 생성** | `ExtractedFields` + `CostItem[]` + `StaffEntry[]` + `ScheduleEntry[]` + `RatesObject` + `OrgEntry[]` 전부 |

### 5-3. 공유 모듈

| 모듈 | 공유 방식 |
|------|----------|
| `backend/services/ai_core.py` | backend(모놀리스)와 `services/ai-service/`가 **동일 파일**을 사용 (MSA 경로 드리프트 차단) |
| `backend/services/claude_api.py` | ai_core re-export 레이어 (기존 import 경로 하위호환) |

---

## 6. 설계 제약 및 경계

### EXE-02가 하지 않는 것

- **사내기준 fallback 적용 안 함**: 요율=0 반환 시 EXE-03이 처리. 추출은 "소스에서 읽는 것"만.
- **충돌 감지 안 함**: 다중 문서 교차 검증은 EXE-05.
- **역추출 안 함**: 완성 집행계획서로부터 역방향 추출은 EXE-14.
- **분류 수행 안 함**: 문서 분류는 EXE-01. 추출은 분류 결과를 전제로 실행.
- **데이터 저장 안 함**: 추출 결과 영속화는 EXE-06(Sprint_Contract 생성) 이후 단계.

### 추출 결정론 한계

추출은 LLM 기반이므로 동일 입력에도 결과가 다를 수 있다. `temperature=0.0`으로 결정론을 목표로 하나, 프롬프트/모델 변경 시 재보정 필요.  
비목 category는 `_force_category_by_name`으로 이름 키워드 강제 매핑해 재현성을 보완한다 (`ai_core.py:379-385`).

---

## 7. 비기능 고려사항

- **Bedrock retry**: `max_attempts=3`, `mode=adaptive` (`ai_core.py:23-26`).
- **Vision 이미지 상한**: 8장 (`ai_core.py:115-116`). 초과 시 경고 로그, 조용한 누락 방지.
- **파일 크기 상한**: `_check_upload_size` (`main.py:550`). 수치는 `[NEEDS CLARIFICATION]` (spec.md Assumptions 참조).
- **토큰 상한**: 섹션별 max_tokens가 다름(512~2048). Vision 추출은 JSON 잘림 방지를 위해 여유 상한 적용 (`ai_core.py:267 주석`).
