# Implementation Plan: EXE-16 Reviewer AI 의미검증

**Created**: 2026-06-26
**Status**: Draft
**Feature**: `EXE-16-ai-semantic-review`

---

## 아키텍처 / 스택

| 계층 | 기술 | 비고 |
|------|------|------|
| 런타임 | Python 3.x + FastAPI | 백엔드 모놀리스 (`backend/`) |
| AI 호출 | AWS Bedrock (boto3 `bedrock-runtime`) | `ap-northeast-2`, `global.anthropic.claude-sonnet-4-6` |
| 공용 AI 로직 | `services/ai_core.py` | `invoke_bedrock`, `route_model`, 모델 티어 라우팅 |
| 검증 진입점 | `services/reviewer.py:545 run_review` | EXE-15·EXE-16 공동 진입점 |
| 선언적 규칙 | `harness/verifier_rules.json` | verdict_thresholds, stage 6 optional |
| 감사 기록 | `services/harness_loader.py record_run` | token_usage 포함 |
| 데이터 모델 | `models/sprint_contract.py` | SprintContract, StepResult, ReviewResult |

**EXE-15와 공유하는 진입점**: `run_review`(reviewer.py:545)는 Stage 1~5(EXE-15 결정론)와 Stage 6(EXE-16 AI 의미검증)을 순차 실행한다. 두 기능은 동일 파일 내에 구현되어 있으나, 기능적으로 분리되어 있다(`verifier_rules.json:157` `"optional": true`).

---

## 데이터 흐름

```
run_review(contract, step_results, wb)
    │
    ├── Stage 1~5: _verify_fee_structure/_verify_conflict_resolution/
    │              _verify_breakdown/_verify_cover_sheet/_verify_basic_info
    │              → fee_result, conflict_result, breakdown_result, cover_result, basic_result
    │
    ├── avg_score = mean(scores[1~5])   ← AI 점수 미포함
    │
    ├── Stage 6: _ai_semantic_review(contract, step_results)
    │              ├── inputs_summary 구성 (inputs_used[:30], value!=None만)
    │              ├── prompt 구성 (confirmed_fields + fee_items 건수 + inputs_summary)
    │              ├── invoke_bedrock(prompt, max_tokens=256, task_type="review")
    │              │       └── route_model("review") → Sonnet 티어
    │              └── 반환: ([이슈 문자열], {"input": N, "output": N})
    │
    ├── all_errors = [1~5 errors] + [AI 이슈]
    ├── verdict = approved(>=0.85) / needs_revision(>=0.60) / rejected(<0.60)
    │              (avg_score 기준, AI 이슈 미포함)
    └── record_run(token_usage=ai_tokens)
```

---

## FR ↔ 실제 컴포넌트 매핑

| FR | 구현 위치 (file:line) | 설명 |
|----|-----------------------|------|
| FR-001 (event) | `reviewer.py:97-144` `_ai_semantic_review` / `reviewer.py:567` `run_review` Stage 6 호출 | 결정론 완료 후 AI 호출 |
| FR-002 (ubiquitous) | `reviewer.py:141` `f"[AI검증] {i}"` | 이슈 접두어 부착 |
| FR-003 (ubiquitous) | `reviewer.py:125-131` 프롬프트 3개 항목 / `verifier_rules.json:161-171` | 검증 3-item 체크리스트 실행 |
| FR-004a (unwanted) | `reviewer.py:143-144` `except Exception: return ([], {"input": 0, "output": 0})` | Bedrock 예외 시 빈 결과 반환 |
| FR-004b (unwanted) | `reviewer.py:143-144` except 블록 후 `run_review` 계속 진행 | Bedrock 예외 시 파이프라인 계속 |
| FR-005 (unwanted) | `reviewer.py:139` `if text.startswith("[")` | JSON 배열 아닌 응답 무효화 |
| FR-006 (ubiquitous) | `ai_core.py:52` `TASK_TIER["review"] = "sonnet"` / `reviewer.py:135` `task_type="review"` | Sonnet 라우팅 |
| FR-007 (ubiquitous) | `reviewer.py:135` `invoke_bedrock(prompt, max_tokens=256, ...)` | 응답 토큰 상한 |
| FR-008a (ubiquitous) | `reviewer.py:567` `ai_issues, ai_tokens` 반환 | run_review 반환값에 토큰 포함 |
| FR-008b (ubiquitous) | `reviewer.py:635` `token_usage=ai_tokens` / `reviewer.py:627-636` `record_run` | record_run 감사 기록에 토큰 저장 |
| FR-009a (ubiquitous) | `reviewer.py:569-585` `all_errors` 합산 | AI 이슈 합산·반환 |
| FR-009b (ubiquitous) | `reviewer.py:578-585` `scores` 리스트 1~5단계만 | avg_score에 AI 이슈 미포함 |
| FR-010 (unwanted) | `reviewer.py:110` `if inp.value is not None` | None 필터링 |

---

## 정보 장벽 설계

`_ai_semantic_review`에서 프롬프트에 포함하는 데이터:
- `confirmed_fields`: project_name, client, revenue, cost, profit, project_period (`reviewer.py:105-119`)
- `fee_items` 건수: `len(contract.fee_items)` (금액 개별 값 미전달)
- `inputs_summary`: `InputUsed.cell` + `InputUsed.value` + `InputUsed.source` 상위 30건

프롬프트에서 **제외**하는 데이터:
- `StepResult.notes` (Executor reasoning)
- `StepResult.retry_fixes` / `StepResult.pending_confirmations`
- `contract.steps` / `contract.acceptance_criteria`

근거: `[공식 코드: reviewer.py:97-132 프롬프트 구성 전체]`

---

## 의존 관계

### 소비 (Consumes)
| 의존 | 소비 내용 | 의존 위치 |
|------|-----------|-----------|
| EXE-15 (Reviewer 결정론 5단계) | `run_review` 진입점 공유, Stage 1~5 완료 후 Stage 6 실행 | `reviewer.py:545-567` |
| EXE-06 (Sprint_Contract 생성) | `SprintContract` — confirmed_fields, fee_items, staff_plan, rates | `models/sprint_contract.py:159` |

### 제공 (Produces)
| 산출 | 소비자 | 비고 |
|------|--------|------|
| `ReviewResult.issues` 중 `[AI검증]` 항목 | 파이프라인 최종 응답, 프론트엔드 | AI 이슈 시각화 |
| `ai_tokens` dict (input/output) | `record_run` 감사 기록 | Bedrock 비용 추적 |

### 외부 의존
| 의존 | 용도 | 비고 |
|------|------|------|
| AWS Bedrock (`bedrock-runtime`) | AI 호출 | VPC 엔드포인트 필요 (project_dev_deploy 메모리) |
| `harness/verifier_rules.json` | `verdict_thresholds`, stage 6 `optional: true` | 하드코드 fallback: 0.85/0.60 |
| `services/harness_loader.py record_run` | 감사 로그 | 실패 시 비차단 + WARNING |

---

## 비결정성·비용 제어 설계

1. **verdict 격리**: AI 이슈는 `avg_score`에 포함되지 않아, Bedrock 응답 변동이 최종 판정에 영향을 주지 않는다.
2. **max_tokens=256**: 응답 길이·비용 상한.
3. **Graceful Degradation**: Bedrock 장애 시 AI 이슈 없이 결정론 결과만으로 verdict 확정.
4. **temperature=0.0**: invoke_bedrock 기본값. LLM 고유 비결정성은 남아 있음.

---

## 비범위 (non-goal)

- 파일 저장소 CRUD, 편집잠금, 챗봇, OTEL/RateLimit/Security 미들웨어 — 설계 §9
- AI 이슈를 verdict 강제 조정에 활용하는 정책 구현 — spec Clarifications Retained 항목 4
- AI 의미검증 프롬프트 커스터마이징 UI
- 코드 구현/TDD/자동 implement — constitution §VII
