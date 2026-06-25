# 집행서 SDD Constitution

> 본 헌법은 집행서 도메인 SDD 스펙 스위트(specs/EXE-*)의 모든 산출물이 준수하는 원칙이다.
> 근거: `CLAUDE.md`/`AGENTS.md` 실효 규칙 승계 + GS네오텍 SDD 방법론(값 미창작).
> 설계 근거: `docs/superpowers/specs/2026-06-26-집행서-SDD-design.md`

## I. 값 미창작 (NON-NEGOTIABLE)

출처가 repo에 있는 **단일 값**만 인용해 채운다. 출처가 **2개 이상 충돌**하면 무조건
`[NEEDS CLARIFICATION]`으로 표기하고 충돌 출처를 전부 나열한다. 임의 수치 생성 금지.
(예: 직급단가표 550/600/650만 충돌, 상여공식 전액 vs /9 충돌 → 강제 NEEDS CLARIFICATION)

## II. 근거 태깅

모든 사실 주장에 `[공식]`/`[외부]`/`[추측]`. `[추측]`엔 알람 블록 필수.
도구 사실(버전·플래그·이슈 상태)은 1차 출처(공식 문서/GitHub API/코드 file:line)를
**직접 확인한 뒤에만** `[공식]`. sub-agent/웹 요약 전달값은 미확인 시 `[추측]`.

## III. EARS 하이브리드 형식

Functional Requirements는 **EARS 5패턴**(Ubiquitous / Event WHEN / State WHILE /
Unwanted IF-THEN / Optional WHERE + SHALL)으로만 작성. 수용기준은 **Given/When/Then**,
Success Criteria는 **측정형**(숫자/시간). 모호어("should/적절히/가능하면") 금지, 한 요구=한 동작.

## IV. 금액·검증 규율

모든 금액 검증은 **1원 정밀도**(1원 오차도 FAIL). **역마진**(집행단가 > 계약단가) = critical FAIL.
보험료 검증 오차 1,000원 이상 FAIL. Reviewer 판정 임계: 0.85↑ approved / 0.60↑ needs_revision / 0.60↓ rejected.

## V. 인간 게이트 · 자동처리 금지

3관문(기본정보·견적서 충돌·추출결과) 사용자 확인 필수. 충돌·추측 항목 자동 확정 금지.
완전 동일 견적서(유형 A') 자동 병합 금지.

## VI. 에이전트 규율

Executor는 **자신의 step 정보만** 수신(전체 Sprint_Contract 전달 금지).
병렬→순차 전환은 사용자 동의 없이 금지. MCP 불가 항목 즉시 보고(무단 대체 금지).

## VII. 도구·버전 거버넌스

spec-kit `@v0.11.8` 핀 고정. PyPI `specify-cli`(동명 비공식) 사용 금지 — git 소스만.
EARS는 spec-kit 네이티브 미지원(Issue #1356 OPEN)이라 로컬 자작
(`.specify/templates/overrides/spec-template.md`, resolution priority 1). 업그레이드 시 재병합 검토.
본 SDD는 문서(spec/plan/tasks)까지 — 코드 구현/`/speckit-implement` 자동실행 비대상.

## VIII. Hooks (실제 settings.json 기준)

`.claude/settings.json` 실효 hook = `PreToolUse(Edit|Write) → .claude/hooks/harness_check.py` 단일.
(CLAUDE.md 문서의 `guardian.sh`/`kairos.sh`는 repo에 실재하지 않으므로 승계 금지 — 드리프트 답습 방지.)

## 범위 밖 (non-goal)

- **작업 깊이**: 코드 구현·TDD·자동 implement 비대상(문서까지).
- **도메인 범위**: 파일 CRUD·편집잠금·챗봇·OTEL/RateLimit/Security 미들웨어 제외(별개 운영·인프라 관심사).

**Version**: 1.0.0 | **Ratified**: 2026-06-26 | **Source**: CLAUDE.md/AGENTS.md + SDD 방법론
