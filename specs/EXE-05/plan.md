# Implementation Plan: EXE-05 — 견적서 충돌 감지·해결

**Created**: 2026-06-26  **Status**: Draft
**설계 근거**: `docs/superpowers/specs/2026-06-26-집행서-SDD-design.md` §3 (코드 근거), §6 (빈칸 방침)

---

## 아키텍처 개요

EXE-05는 **두 레이어**에 걸쳐 구현된다.

```
[프론트엔드]
  업로드/추출 완료
       ↓
  apiValidate() → POST /api/validate
       ↓
[백엔드: main.py:675]
  require_auth (JWT)
       ↓
  USE_AI_SERVICE? → ai-service /validate (프록시)
                  → cross_validate(data)   ← ai_core.py:522
                        ↓
                   Bedrock (VALIDATE_PROMPT)
                        ↓
                   {"conflicts": [...]}
       ↓
[프론트엔드]
  conflictCount = conflicts.length   ← page.tsx:183,203
       ↓
  conflictCount > 0?
    YES → 충돌 알림 배너 + "충돌 해결 →" (review-page.tsx:706)
          ConflictsPage (other-pages.tsx:24)
          사용자 선택 → handleResolve → extractedData 업데이트
          conflicts = [], conflictCount = 0
    NO  → 정상 흐름
       ↓
[백엔드: 이후 export 단계]
  SprintContract.conflict_resolutions 보존
       ↓
  Reviewer Stage 2: _verify_conflict_resolution (reviewer.py:248)
```

**스택**:
- 백엔드: FastAPI (Python), Pydantic (`ConflictResolution`, `SprintContract`)
- AI 레이어: Amazon Bedrock (Claude) — `ai_core.py` `_call_claude` / `invoke_bedrock`
- 프론트엔드: Next.js (React) — `other-pages.tsx`, `review-page.tsx`, `page.tsx`, `lib/types.ts`, `lib/api.ts`
- 데이터 모델: `backend/models/sprint_contract.py`

---

## FR ↔ 컴포넌트 매핑

| FR | 동작 | 컴포넌트 | 파일:라인 |
|----|------|----------|-----------|
| FR-001 | 교차 검증 엔드포인트 수신 → cross_validate 호출 | `/api/validate` 엔드포인트 | `backend/main.py:675-684` |
| FR-001 | cross_validate 구현 — Bedrock 호출 + JSON 파싱 | `cross_validate()` 함수 | `backend/services/ai_core.py:522-527` |
| FR-001 | Bedrock 프롬프트 — mismatch/missing/warning 감지 | `VALIDATE_PROMPT` | `backend/services/ai_core.py:509-519` |
| FR-002 | 유형 A 감지 (동일 협력사 중복 견적) | `VALIDATE_PROMPT` (Bedrock) | `ai_core.py:509-519` |
| FR-003 | 유형 A' 감지 (완전 동일 중복, 자동 병합 금지) | `VALIDATE_PROMPT` (Bedrock) | `ai_core.py:509-519` |
| FR-004 | 유형 B 감지 (동일 품목 금액 불일치) | `VALIDATE_PROMPT` (Bedrock) | `ai_core.py:509-519` |
| FR-005 | 유형 C 감지 (견적서 내 품명 중복) | `VALIDATE_PROMPT` (Bedrock) | `ai_core.py:509-519` |
| FR-006 | 유형 D 감지 (행 합산 ≠ 명시 합계) | `VALIDATE_PROMPT` (Bedrock) | `ai_core.py:509-519` |
| FR-007 | conflictCount 설정 + 충돌 알림 배너 표시 | `page.tsx`, `review-page.tsx` | `frontend/app/page.tsx:183,203`, `frontend/components/pages/review-page.tsx:706-712` |
| FR-008 | 충돌 미해결 시 익스포트 차단 | `ConflictsPage`, review-page 익스포트 버튼 | `frontend/components/pages/other-pages.tsx:53-54` |
| FR-009 | 충돌 항목별 옵션 A/B/직접입력 UI | `ConflictsPage` | `frontend/components/pages/other-pages.tsx:94-155` |
| FR-010 | 미완료 시 "해결 완료" 버튼 비활성 | `ConflictsPage` | `frontend/components/pages/other-pages.tsx:53-54` |
| FR-011 | 해결 완료 → extractedData 업데이트 + conflicts 배열 초기화 | `handleResolve()` | `frontend/components/pages/other-pages.tsx:56-78` |
| FR-011b | conflicts 초기화 완료 후 conflictCount=0 + review 화면 이동 | `handleResolve()` | `frontend/components/pages/other-pages.tsx:75-77` |
| FR-012 | ConflictResolution 데이터 모델 보존 | `ConflictResolution`, `SprintContract` | `backend/models/sprint_contract.py:51-56,168` |
| FR-013a | Reviewer Stage 2 — user_choice 충족 여부 확인 | `_verify_conflict_resolution()` | `backend/services/reviewer.py:248-284` |
| FR-013b | Reviewer Stage 2 — resolved_value 존재 여부 확인 | `_verify_conflict_resolution()` | `backend/services/reviewer.py:248-284` |
| FR-014 | user_choice 미충족 시 FAIL 처리 | `_verify_conflict_resolution()` | `backend/services/reviewer.py:263-264` |

---

## 데이터 흐름 상세

### 1. 감지 흐름 (백엔드)

```
POST /api/validate
  body: dict  ← 추출 완료된 전체 ExtractedData JSON
  auth: JWT (require_auth)
  
  → cross_validate(data)
      VALIDATE_PROMPT.format(data_json=...)
      _call_claude(prompt, max_tokens=512, task_type="validate")
      _parse_json(raw, fallback=[])
      
  → return {"conflicts": [
      {"type": "mismatch|missing|warning",
       "field": "필드명",
       "message": "설명",
       "severity": "high|medium|low"}
    ]}
```

**주의**: `VALIDATE_PROMPT`는 추출 데이터 교차 검증용 일반 프롬프트(`ai_core.py:509-519`)이다. 견적서 유형 A/A'/B/C/D 분류 코드를 명시적으로 반환하지 않는다. 프론트의 `Conflict.type`은 `"mismatch|missing|warning"` 값이고, 유형 A~D 코드는 `planner.md`/`PROJECT.md`의 파이프라인 수준 약속이다. — [추측] 두 체계의 정확한 연결 방식은 확인 필요.

⚠️ [추측 알람] 확인 필요
- 항목: VALIDATE_PROMPT가 감지 유형 A/A'/B/C/D를 구분해 반환하는지 여부
- 이유: `ai_core.py:509-519`의 프롬프트는 `"mismatch|missing|warning"` 분류만 지정하고 A/A'/B/C/D 코드 반환을 명시하지 않음
- 확인 방법: `ai_core.py:509-519` VALIDATE_PROMPT 전문 재검토 + 실제 Bedrock 응답 로그 확인
- 조치: 확인 후 FR-002~FR-006의 감지 메커니즘 기술 업데이트 필요

### 2. 해결 흐름 (프론트엔드)

```
conflictCount > 0
  → review-page.tsx:706 충돌 알림 배너 표시
  → "충돌 해결 →" 클릭 → setRoute("conflicts")
  → ConflictsPage (other-pages.tsx:24)
      rawConflicts = extractedData.conflicts
      picks: Record<number, "A"|"B"|"custom">
      customValues: Record<number, string>
      
      사용자 선택 (picks[i] = "A"|"B"|"custom")
      allResolved = resolvedCount === rawConflicts.length
      
      "해결 완료" (allResolved 시 활성)
      → handleResolve()
          resolvedValue = valueA | valueB | customValues[i]
          updated.extracted[field].value = resolvedValue
          updated.conflicts = []
          setExtractedData(updated)
          setConflictCount(0)
          setRoute("review")
```

### 3. 보존 및 검증 (백엔드)

```
SprintContract.conflict_resolutions: list[ConflictResolution]
  ConflictResolution:
    conflict_type: str      # "A"|"A'"|"B"|"C"|"D" 또는 내부 유형
    description: str
    options: list[str]
    user_choice: Optional[str]    # 사용자 선택 (필수)
    resolved_value: Optional[str] # 최종값 (필수)

Reviewer Stage 2: _verify_conflict_resolution(contract, step_results)
  → conflict_resolutions 순회
  → user_choice 미충족 → errors.append("미해결 충돌: ...")
  → resolved_value 누락 → errors.append("충돌 해결값 누락: ...")
  → score = ok_count / max(ok_count + len(errors), 1)
```

---

## 의존 관계

| 방향 | 의존 대상 | 내용 |
|------|-----------|------|
| EXE-05 → EXE-02 | 소스추출 | `cross_validate`의 입력은 EXE-02가 생성한 추출 데이터(ExtractedData) |
| EXE-05 → EXE-06 | Sprint_Contract 생성 | 충돌 해결 완료 후에만 EXE-06(`build_sprint_contract`)이 실행 가능. `planner.md:103` "충돌 해결 전 Executor 실행 금지" |
| EXE-15 → EXE-05 | Reviewer Stage 2 | `_verify_conflict_resolution`이 `SprintContract.conflict_resolutions`를 검증 — EXE-05의 해결 결과가 EXE-15의 입력 |
| EXE-04 ← EXE-05 | 병렬(순서 없음) | EXE-04(기본정보 확인 게이트)와 EXE-05는 같은 추출 데이터를 소비하나 순서 의존 없음 |

---

## 경계 명시 (non-goal)

- 파일 업로드/저장(CRUD) — EXE-05 범위 밖. `/api/files*`, `/api/projects*` 별개.
- 편집잠금(`/api/projects/{id}/lock*`) — 설계 §9 명시 제외.
- Reviewer AI 의미검증(`reviewer.py:97 _ai_semantic_review`) — EXE-16 분리.
- `CONTRACT_BUILDER` 내부 생성 충돌 (`"연도배분확인"`, `"자동계산중복"`, `"급료단가확인"`) — EXE-06/09 소관. EXE-05는 견적서 교차 충돌(유형 A~D)만 담당.

---

## 현행 코드 상태 메모 (잠정)

- `cross_validate`는 `ai_core.py`에 있으나 `main.py:682`에서 `from services.claude_api import cross_validate`로 임포트한다 — 모듈 경로가 `services/ai_core.py`와 `services/claude_api.py` 사이에 별칭이 있을 수 있음. 실제 파일 확인: `/backend/services/ai_core.py:522` = 정규 위치. [추측] `claude_api.py`는 별칭 또는 래퍼일 가능성 있음 — 추가 확인 권장.

⚠️ [추측 알람] 확인 필요
- 항목: `claude_api.py`가 `ai_core.py`의 별칭 또는 래퍼 모듈이라는 주장
- 이유: `main.py:682`의 `from services.claude_api import cross_validate` 임포트 경로를 실제 파일 시스템에서 직접 확인하지 않아 `claude_api.py`의 실체를 단정할 수 없음
- 확인 방법: `backend/services/claude_api.py` 파일 존재 여부 확인 및 내용 검토; `grep -r "cross_validate" backend/services/` 실행
- 조치: 확인 후 [공식 코드] 또는 내용 수정으로 태그 업데이트 필요
