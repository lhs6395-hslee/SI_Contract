<!--
  EARS Spec Template — GitHub Spec Kit 프리셋/오버라이드용
  설치 위치(둘 중 하나):
    · 프로젝트 일회성:  .specify/templates/overrides/spec-template.md
    · 조직 표준(권장):  프리셋으로 패키징 → .specify/presets/<id>/templates/spec-template.md
  근거: spec-kit 템플릿 resolution stack(overrides>presets>extensions>core), 프리셋=조직 표준 spec 형식.
  EARS 출처: Alistair Mavin 외, Rolls-Royce / IEEE RE'09.  모든 수치 잠정·추후 재정립.
-->
# Feature Specification: [FEATURE NAME]

**Feature Branch**: `[NNN-slug]`  **Created**: [YYYY-MM-DD]  **Status**: Draft
**Input**: [한 줄 의도]

---

## ⚙ 작성 규칙 (이 템플릿의 핵심 — 에이전트는 반드시 준수)

모든 Functional Requirement는 **EARS 표기 5패턴 중 하나**로만 쓴다. 한 요구 = 한 동작 = 검증가능.
값을 모르면 임의로 정하지 말고 `[NEEDS CLARIFICATION: 무엇을 확인해야 하나]`.

| 패턴 | 틀 | 쓰는 때 |
|---|---|---|
| **Ubiquitous** | `THE SYSTEM SHALL <응답>.` | 항상 참인 불변 요구 |
| **Event (WHEN)** | `WHEN <트리거>, THE SYSTEM SHALL <응답>.` | 이벤트 발생 시 |
| **State (WHILE)** | `WHILE <상태>, THE SYSTEM SHALL <응답>.` | 특정 상태가 지속되는 동안 |
| **Unwanted (IF-THEN)** | `IF <비정상 조건>, THEN THE SYSTEM SHALL <응답>.` | 오류·예외·금지 동작 |
| **Optional (WHERE)** | `WHERE <기능이 포함되면>, THE SYSTEM SHALL <응답>.` | 특정 구성·옵션일 때 |
| **Complex** | `WHILE <상태>, WHEN <트리거>, THE SYSTEM SHALL <응답>.` | 위 조합 |

> 금지: "should/가능하면/적절히" 같은 모호어, 한 문장에 동작 2개("and"), 측정 불가 표현.

---

## User Scenarios & Testing

### User Story 1 — [제목] (Priority: P1)
[운영자가 무엇을 원하는지 한 문단]
- **Independent Test**: [이 스토리만으로 단독 검증하는 방법]
- **Acceptance (Given/When/Then)**:
  1. **Given** [맥락], **When** [행동], **Then** [기대].

### Edge Cases
- [엣지/예외 케이스] · 불명확 시 `[NEEDS CLARIFICATION: ...]`

---

## Functional Requirements (EARS)

각 FR은 `(패턴)` 태그 + EARS 문장. 아래는 **FinOps MVP 실예시**(최성우 분석·merged spec 기반, 그대로 사용 가능).

- **FR-001** (event): WHEN 비용 티켓이 인입되면, THE SYSTEM SHALL 티켓을 L1/L2/L3 후보·신뢰도·위험도·필수 증거 템플릿으로 분류한다.
- **FR-002** (ubiquitous): THE SYSTEM SHALL 모든 분류·출력 claim에 대해 source reference(참조 티켓·근거)를 보존한다.
- **FR-003** (unwanted): IF 근거가 confident classification에 부족하면, THEN THE SYSTEM SHALL 자동 확정하지 않고 human triage 또는 `[NEEDS CLARIFICATION: insufficient evidence]`로 표시한다.
- **FR-004** (event): WHEN F3 비용 설명 또는 F2 readiness 출력을 생성하기 전이면, THE SYSTEM SHALL 먼저 F1 Data Readiness Gate를 실행한다.
- **FR-005** (state): WHILE readiness 상태가 `STALE`·`MISSING_TAG`·`MAPPING_UNKNOWN`·`RECONCILIATION_FAILED`·`UNKNOWN` 중 하나인 동안, THE SYSTEM SHALL 확정 고객 설명 대신 checklist·missing-evidence 요청·verification plan만 생성한다.
- **FR-006** (unwanted): IF CloudTrail principal 증거가 없으면, THEN THE SYSTEM SHALL caller-specific API attribution을 차단한다.
- **FR-007** (unwanted): IF private/internal note가 존재하면, THEN THE SYSTEM SHALL 그 내용을 customer-facing draft 본문에 복사하지 않는다.
- **FR-008** (optional): WHERE 비용 급증이 key 유출·비정상 사용을 시사하면, THE SYSTEM SHALL 보안 인시던트로 escalate한다.
- **FR-009** (ubiquitous): THE SYSTEM SHALL 실제 고객 발송·RI/SP 구매·리소스 변경·태그 변경을 자동 실행하지 않는다. (감사 역할)
- **FR-010** (event): WHEN 외부 LLM을 호출하기 전이면, THE SYSTEM SHALL 고객 계정·개인정보를 마스킹한다.

### Key Entities
- TicketEvidence, FinOpsClassification(category·confidence·risk·evidence), DataReadinessResult(statuses·source_of_truth), FinOpsOutput(claims·blocked_claims·evidence_refs)

---

## Success Criteria (측정형)

- **SC-001**: 대표 골든셋 티켓의 **≥ [NEEDS CLARIFICATION: 베이스라인 측정 후 목표]%** 가 reviewer 수용 scenario·action mode를 받는다.
- **SC-002**: material output claim의 **100%** 가 evidence reference 또는 verification marker를 가진다.
- **SC-003**: F1 reviewed case의 **100%** 가 1개 이상의 명시적 readiness 상태를 가진다.
- **SC-004**: 운영자가 한 티켓의 분류·증거·출력 제약을 **2분 이내** 리뷰할 수 있다. (베이스라인 후 재정립)

---

## Assumptions
- AWS·EC2 기반, 솔루션은 **감사(Auditor)** — 발송·실행·책임은 인간.
- 준비된 대표 티켓 패키지가 이 draft의 authoritative local evidence.

## Clarifications Retained
- 최종 taxonomy label·action mode 정의 · 신뢰도 임계값 수치 · source-of-truth 우선순위 · 마스킹/발송 승인 정책 — 운영팀 인터뷰로 확정.
