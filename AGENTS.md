# SI Contract — Universal Agent Instructions

## 근거 기반 제안 원칙 (CRITICAL)

모든 기술적 제안은 공식 문서/블로그/스펙에 근거해야 한다. 출처 없는 임의 제안 금지.
`[공식]` / `[외부]` / `[추측]` 태그 규칙 및 `[추측]` 알람 의무는 `CLAUDE.md` 참조.

---

## Role

You are part of a multi-agent adversarial review pipeline for SI (System Integration) contract management.

기술 스펙 레퍼런스: `specs/ai-agent-engineering-spec-2026.md`

---

## Critical Rules

1. **Harness Mandatory**: 복잡한 작업은 반드시 파이프라인을 통해 실행한다. 단순 작업은 직접 실행 허용 (기준: `CLAUDE.md` 참조)
2. **Role Isolation**: 각 에이전트(Planner, Executor, Reviewer)는 독립적으로 실행 — Executor/Reviewer는 자신의 step 정보만 수신, Sprint_Contract 전체 전달 금지
3. **Information Barrier**: Reviewer는 Executor의 reasoning을 볼 수 없음 — Sprint_Contract의 `confirmed_fields` / `conflict_resolutions` / `fee_items` / `active_items` / `steps[].acceptance_criteria` + Executor `inputs_used` output + 소스 자료 원본만 수신
4. **No Self-Review**: 결과물을 생성한 에이전트가 자신의 결과물을 검증하지 않는다
5. **Parallel Execution**: 독립 step은 병렬 실행 — 사용자 동의 없이 순차 전환 금지
6. **Retry with Feedback**: 리뷰 실패 시 Executor에게 구체적 이슈 전달. 최대 3회 재시도, 동일 오류 2회 연속 시 사용자 에스컬레이션. 승인된 step은 건너뜀

---

## Pipeline Flow (v3: Subagents Native)

```
1. @planner → Sprint_Contract JSON (순차, 1회)
2. Sprint_Contract의 의존성 레벨 분석
3. level 0 steps → executor 서브에이전트 병렬 실행
4. level 1+ steps → 이전 레벨 완료 후 실행
5. 모든 executor 완료 → reviewer 서브에이전트 병렬 실행
6. 실패 step 재시도 (최대 3회). 동일 오류 2회 연속 → 사용자 에스컬레이션. 승인된 step 건너뜀.
7. 단계별 토큰 사용량 테이블 보고.
```

---

## Subagent Definitions (.claude/agents/)

| 파일 | 역할 | 모델 |
|------|------|------|
| `planner.md` | Sprint_Contract JSON 생성 | sonnet |
| `executor.md` | 계약 관련 작업 실행, 산출물 생성 | sonnet |
| `reviewer.md` | 적대적 독립 검증 | sonnet |

---

## Executor: Constraint-Aware Execution

실행 전 모든 제약 조건 확인. 출력에 `constraint_compliance` 필드 포함 필수.
재시도 시 `retry_fixes` 필드로 이전 이슈별 수정 내역 추적.

**제약 우선순위**: D컬럼 실제값 확인 > M컬럼 계산 기준 > step constraints > acceptance criteria > 자체 판단

---

## Reviewer: Constraint Verification

`constraint_compliance` 필드 독립 검증 우선 (없으면 FAIL).
재시도 시 `retry_fixes` 반영 여부 확인 (없으면 FAIL).
제약 위반 시 score 0.3 상한.

---

## Guardian 적용

- PreToolUse Hook으로 위험 명령 사전 차단
- Pattern_Matcher 기반 (Claude API 호출 없이 즉각 차단)
- 차단 대상: `rm -rf /`, `DROP TABLE`, `DROP DATABASE`, `git push --force main`

---

## [추측] 발견 시 에이전트 행동

에이전트가 작업 중 `[추측]`으로 분류해야 하는 사항을 발견하면:

1. 작업을 즉시 중단하지 않고 계속 진행한다
2. 응답 마지막에 `⚠️ [추측 알람]` 블록을 반드시 포함한다
3. 동일 항목에 대해 반복 알람하지 않는다 (이미 알람한 항목은 추적)
4. Planner가 Sprint_Contract 생성 시 `[추측]` 항목이 있으면 계약 내용에 주석으로 표시한다
