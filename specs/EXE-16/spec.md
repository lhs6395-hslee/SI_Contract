# Feature Specification: EXE-16 Reviewer AI 의미검증

**Feature Branch**: `EXE-16-ai-semantic-review`
**Created**: 2026-06-26
**Status**: Draft
**Input**: Reviewer 결정론 5단계(EXE-15) 완료 후, Bedrock Claude를 독립 Agent_Session으로 호출해 집행계획서의 논리적 의미 일관성을 검증한다.

---

## 범주 / 성격

**교차검증 — 백엔드 전용 (AI 비결정성·Bedrock 비용 분리).**
EXE-15(결정론 5단계)와 동일 `reviewer.py`에 구현되나, `_ai_semantic_review`는 별개 함수로 분리되며 결정론 점수 평균에 포함되지 않는다(`harness/verifier_rules.json:157` `"optional": true`). 수식 레이어·프론트 게이트 아님.

---

## User Scenarios & Testing

### User Story 1 — 의미 일관성 검증 (Priority: P1)

PM이 집행계획서 검토 결과를 받을 때, 수치 계산은 맞지만 매출-매입-영업이익 관계가 논리적으로 이상하거나 기간 대비 M/M 수량이 비현실적인 경우를 Bedrock AI가 별도 검증해 이슈를 추가로 보고받기 원한다.

- **Independent Test**: 결정론 5단계를 모두 통과한 SprintContract에 대해 `_ai_semantic_review`를 단독 호출해 반환 이슈 목록이 올바른 형태인지 확인한다.
- **Acceptance (Given/When/Then)**:
  1. **Given** 결정론 5단계 검증이 완료된 SprintContract와 step_results가 준비된 상태에서, **When** `run_review`가 Stage 6 `_ai_semantic_review`를 호출하면, **Then-a** `[AI검증]` 접두어를 가진 이슈 문자열 목록이 `ReviewResult.issues`에 추가된다. **Then-b** `run_review`의 반환값에 토큰 사용량 dict가 포함된다.
  2. **Given** 매출-매입 차이가 영업이익과 불일치하는 SprintContract가 입력될 때, **When** AI 의미검증이 수행되면, **Then** 해당 불일치를 명시한 이슈가 `ReviewResult.issues`에 포함된다.
  3. **Given** Bedrock 호출이 실패(예외 발생)할 때, **When** `_ai_semantic_review`가 실행되면, **Then-a** 빈 이슈 목록 `[]`과 `{"input": 0, "output": 0}`을 반환한다. **Then-b** 파이프라인을 중단하지 않고 계속 실행한다.

### User Story 2 — 정보 장벽 준수 (Priority: P1)

보안 감사자가 AI 의미검증이 Executor의 reasoning/notes를 참조하지 않고 확정 데이터와 inputs_used 요약만으로 독립 수행되었음을 확인하기 원한다.

- **Independent Test**: `_ai_semantic_review`에 전달되는 프롬프트를 캡처해 `StepResult.notes` 내용이 포함되지 않음을 검증한다.
- **Acceptance (Given/When/Then)**:
  1. **Given** StepResult에 notes 필드가 채워진 경우에도, **When** `_ai_semantic_review`가 프롬프트를 구성하면, **Then** `inputs_summary`는 `InputUsed.cell`·`InputUsed.value`·`InputUsed.source`만 포함한다.
  2. **Given** StepResult에 notes 필드가 채워진 경우에도, **When** `_ai_semantic_review`가 프롬프트를 구성하면, **Then** `StepResult.notes`는 프롬프트에 포함되지 않는다.
  3. **Given** `inputs_summary`가 30건을 초과하는 경우, **When** 프롬프트가 구성되면, **Then** 상위 30건만 전달된다(`reviewer.py:111` `inputs_summary[:30]`).

### Edge Cases

- Bedrock 스로틀링(`ThrottlingException`) 발생 시 `AIUnavailableError`가 raise되어 exception 블록에서 빈 결과로 처리된다.
- AI 응답이 JSON 배열로 시작하지 않으면(`text.startswith("[")` 미충족) 이슈 목록은 빈 배열로 처리된다(`reviewer.py:139`).
- `inputs_used.value`가 `None`인 항목은 `inputs_summary`에 포함되지 않는다(`reviewer.py:110`).
- verdict 판정(approved/needs_revision/rejected)은 결정론 1~5단계 평균 점수만으로 산정한다. AI 이슈는 `ReviewResult.issues`에 추가되지만 `avg_score` 계산에서 제외된다(`reviewer.py:579~599`).

---

## Functional Requirements (EARS)

- **FR-001** (event): WHEN 결정론 5단계 검증이 완료되면, THE SYSTEM SHALL 정보 장벽(confirmed_fields + fee_items + inputs_used 상위 30건만, Executor reasoning/notes 미포함) 하에 Bedrock Claude를 호출해 AI 의미검증을 수행한다.
  `[공식 코드: reviewer.py:97-144 _ai_semantic_review, reviewer.py:567 run_review Stage 6 호출]`

- **FR-002** (ubiquitous): THE SYSTEM SHALL AI 의미검증 결과 이슈 목록에 `[AI검증]` 접두어를 붙여 결정론 이슈와 구별한다.
  `[공식 코드: reviewer.py:141 f"[AI검증] {i}"]`

- **FR-003** (ubiquitous): THE SYSTEM SHALL AI 의미검증에서 매출-매입-영업이익 논리 일관성, 기간 대비 M/M 수량 일치, 명백한 논리 오류의 3-item 체크리스트를 실행한다.
  `[공식 코드: reviewer.py:125-131 프롬프트 3개 항목, harness/verifier_rules.json:161-171]`

- **FR-004a** (unwanted): IF Bedrock 호출이 예외를 발생시키면, THEN THE SYSTEM SHALL 빈 이슈 목록 `[]`과 토큰 사용량 `{"input": 0, "output": 0}`을 반환한다.
  `[공식 코드: reviewer.py:143-144 except Exception 블록]`

- **FR-004b** (unwanted): IF Bedrock 호출이 예외를 발생시키면, THEN THE SYSTEM SHALL 파이프라인을 중단하지 않고 계속 실행한다.
  `[공식 코드: reviewer.py:143-144 except Exception 블록, run_review Stage 6 계속 진행]`

- **FR-005** (unwanted): IF AI 응답 텍스트가 JSON 배열 형식(`[`으로 시작)이 아니면, THEN THE SYSTEM SHALL 빈 이슈 목록을 반환한다.
  `[공식 코드: reviewer.py:139 text.startswith("[")]`

- **FR-006** (ubiquitous): THE SYSTEM SHALL `task_type="review"`로 모델 티어를 지정해 Sonnet 모델로 Bedrock을 호출한다.
  `[공식 코드: ai_core.py:52 TASK_TIER["review"] = "sonnet", reviewer.py:135 invoke_bedrock(..., task_type="review")]`

- **FR-007** (ubiquitous): THE SYSTEM SHALL Bedrock 호출 시 `max_tokens=256`으로 응답 길이를 제한한다.
  `[공식 코드: reviewer.py:135 invoke_bedrock(prompt, max_tokens=256, task_type="review")]`

- **FR-008a** (ubiquitous): THE SYSTEM SHALL AI 의미검증의 토큰 사용량(input/output)을 `run_review` 반환값에 포함한다.
  `[공식 코드: reviewer.py:567 ai_issues, ai_tokens 반환]`

- **FR-008b** (ubiquitous): THE SYSTEM SHALL AI 의미검증의 토큰 사용량(input/output)을 `record_run` 호출 시 감사 기록에 저장한다.
  `[공식 코드: reviewer.py:635 token_usage=ai_tokens]`

- **FR-009a** (ubiquitous): THE SYSTEM SHALL AI 의미검증 이슈를 결정론 1~5단계 이슈와 합산해 `ReviewResult.issues`로 반환한다.
  `[공식 코드: reviewer.py:569-585 all_errors 합산]`

- **FR-009b** (ubiquitous): THE SYSTEM SHALL avg_score 계산 시 AI 의미검증 이슈를 포함하지 않는다.
  `[공식 코드: reviewer.py:578-585 scores 리스트에 ai 미포함]`

- **FR-010** (unwanted): IF `inputs_used.value`가 `None`이면, THEN THE SYSTEM SHALL 해당 항목을 프롬프트의 inputs_summary에서 제외한다.
  `[공식 코드: reviewer.py:110 if inp.value is not None]`

---

## Success Criteria (측정형)

- **SC-001**: Bedrock 호출 실패(예외) 시 파이프라인 중단율 = **0%** — `_ai_semantic_review` except 블록이 빈 결과를 반환해 `run_review`가 항상 완료된다. `[공식 코드: reviewer.py:143-144]`
- **SC-002**: AI 의미검증 이슈는 **100%** `[AI검증]` 접두어를 가진다. `[공식 코드: reviewer.py:141]`
- **SC-003**: inputs_summary 전달 건수 = **최대 30건** (30건 초과 시 상위 30건 한정). `[공식 코드: reviewer.py:111 [:30]]`
- **SC-004**: AI 의미검증 점수가 verdict 판정 임계(approved=0.85, needs_revision=0.60)에 **직접 영향 없음** — `avg_score`는 1~5단계 결과만 포함.  `[공식 코드: reviewer.py:578-585]`
- **SC-005**: `max_tokens` 제한 = **256 토큰** (AI 응답 길이 상한). `[공식 코드: reviewer.py:135]`
- **SC-006**: AI 이슈 탐지 정밀도 목표 — `[NEEDS CLARIFICATION]` (골든셋 검증 베이스라인 후 목표 수립 필요. 현재 정밀도·재현율 목표 수치 없음.)
- **SC-007**: Bedrock 응답 지연(p95) 목표 — `[NEEDS CLARIFICATION]` (SLA 수치 미정. read_timeout=60초 설정 있으나 p95 목표 미명시. `ai_core.py:26` 참조)

---

## Key Entities

| 엔티티 | 설명 | 출처 |
|--------|------|------|
| `SprintContract` | AI 검증 대상 — confirmed_fields(project_name, client, revenue, cost, profit, project_period), fee_items | `models/sprint_contract.py:159` |
| `StepResult` | Executor 출력 — `inputs_used`(cell, value, source) 제공, `notes`는 전달 금지 | `models/sprint_contract.py:200` |
| `InputUsed` | 셀-값-소스 레코드 — `field`, `value`, `cell`, `source`, `calc_basis` | `models/sprint_contract.py:184` |
| `ReviewResult` | AI 이슈 포함 최종 검증 결과 — `verdict`, `score`, `issues` | `models/sprint_contract.py:214` |
| `invoke_bedrock` | 공용 Bedrock 호출 함수 — 모델 티어 라우팅, Vision 멀티모달, 예외 처리 | `services/ai_core.py:97` |
| `verifier_rules` | 하네스 선언적 검증 규칙 — verdict_thresholds, stage 6 optional 설정 | `harness/verifier_rules.json:7,157` |
| `record_run` | 감사 기록 — project_id, verdict, score, errors, token_usage 포함 | `services/harness_loader.py` (호출: `reviewer.py:627`) |

---

## Assumptions

1. **Bedrock 모델**: `BEDROCK_MODEL_ID` 환경 변수 기본값 `global.anthropic.claude-sonnet-4-6`, 리전 `ap-northeast-2`. 코드 현행값=잠정. `[공식 코드: ai_core.py:20-21]`
2. **task_type "review" = Sonnet 티어**: `TASK_TIER["review"] = "sonnet"` → `MODEL_MAP["sonnet"] = DEFAULT_MODEL`. 코드 현행값=잠정. `[공식 코드: ai_core.py:52,57]`
3. **비결정성**: Bedrock LLM 응답은 비결정적이므로, 동일 입력에 대해 AI 이슈 목록이 실행 시마다 다를 수 있다. 이것은 설계 의도(EXE-15 결정론과 분리)이며 SC-004가 이를 통제.
4. **Bedrock 비용**: Sonnet 모델 호출당 토큰 비용이 발생하며, Haiku 대비 고비용. 토큰 상한(max_tokens=256)으로 응답 비용을 제한. 비용 기준은 `[NEEDS CLARIFICATION]` (단가표 미첨부).
5. **temperature=0.0**: `invoke_bedrock` 기본값 temperature=0.0. 단, LLM 고유 비결정성은 온도와 무관하게 존재. `[공식 코드: ai_core.py:106,130]`
6. **`record_run` 실패 비차단**: 감사 기록 실패 시 파이프라인을 차단하지 않고 WARNING만 로깅. `[공식 코드: reviewer.py:638-640]`

---

## Clarifications Retained

설계 §6-1 및 코드 대조로 확인된 미결 항목:

1. **AI 이슈 탐지 정밀도·재현율 목표** — 골든셋(정상/비정상 SprintContract 페어) 구성 후 측정치 기반 목표 수립 필요. 현재 수치 없음. (SC-006)
2. **Bedrock 응답 지연 SLA** — p95 목표 미정. 현재 `read_timeout=60`초만 설정(`ai_core.py:26`). (SC-007)
3. **Bedrock 비용 예산** — Sonnet 호출 단가 및 월간 허용 예산 미명시.
4. **AI 이슈가 verdict에 영향을 줘야 하는가** — 현재 코드는 avg_score 제외(`harness/verifier_rules.json:157` `"optional": true`). AI 이슈 심각도에 따라 verdict를 강제 조정하는 정책 미결.
5. **프롬프트 검증 항목 추가 가능성** — 현재 3개 항목 고정(매출-매입-이익, 기간-M/M, 논리오류). 추가 검증 항목 필요 여부 미결.
