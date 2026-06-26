# 집행서 도메인 SDD 스펙 스위트 — 설계 문서

**작성일**: 2026-06-26 **상태**: Draft (사용자 리뷰 대기) **대상 repo**: `/Users/toule/Documents/kiro/SI_ Contract`
**방법론 출처**: `/Users/toule/Documents/Works/2026/업무용/솔루션/SDD` (GS네오텍 확정 SDD 방법론)

> **태그 규칙**: 본 문서의 모든 사실 주장은 `[공식]`(1차 출처·URL 또는 file:line 직접 확인) / `[외부]` / `[추측]`(+알람) 으로 표기한다. 본 설계의 모든 핵심 사실은 작성자가 직접 1차 출처/코드를 열어 확인했다(§10 검증 로그).

---

## 0. 목적

집행계획서 자동작성 시스템(이하 "집행서")의 도메인 지식이 현재 `PROJECT.md` 산문 + 메모리 + 코드 + 부분적 Kiro 스펙에 흩어져 있다. 이를 **GS네오텍 확정 SDD 방법론**(Spec Kit 골격 + FR만 EARS + Superpowers 검증, 값 미창작)으로 정형화하여, 검증 가능한 spec/plan/tasks 풀세트로 만든다.

- **범위**: 집행서 도메인 전체 (17개 기능, §3)
- **산출 형식**: Spec Kit 표준 (`specs/EXE-NN/{spec,plan,tasks}.md`), **Kiro 형식 미사용**
- **대상 에이전트**: Claude Code(슬래시 커맨드) + Codex CLI(skills 모드) — Kiro 제외
- **이번 작업 깊이**: 문서(spec/plan/tasks)까지. 코드 구현/TDD는 별도 사이클(§9)

## 1. 방법론 기반 (검증됨)

확정 방법론 = **Spec Kit(WHAT·저작/통일) + EARS(FR 섹션만) + Superpowers(HOW·검증)**, 값 미창작 원칙. 파이프라인:
`0 프리셋 → 1 /specify → 2 /clarify → 3 /plan → 4 /tasks → 5 /analyze·checklist → 6 Superpowers(implement 대체) → 7 머지 → 8 /converge`

검증된 도구 사실 (작성자 직접 확인, §10):
- `[공식]` Spec Kit 최신 **v0.11.8** (2026-06-24). 설치: `uvx --from git+https://github.com/github/spec-kit.git@v0.11.8 specify init`
- `[공식]` Codex 지원됨 — **skills 모드**: `specify init . --integration codex --integration-options="--skills"` (`$speckit-*`로 호출). Issue #454("codex args")는 **CLOSED**.
- `[공식]` EARS는 Spec Kit **네이티브 미지원** (Issue #1356 **OPEN**) → **조직 표준 프리셋**(방법론 권장)으로 자작·자가유지 (§5)
- `[공식]` init 플래그는 `--integration`(≠`--ai`), `--here`/`.`. **멀티 에이전트는 에이전트별 개별 init** 실행.
- `[공식]` `--force`는 `.claude/commands/`·`.specify/{scripts,templates,memory}`를 덮어씀. **`specs/`는 보호**(템플릿 패키지에서 제외).

## 2. 산출 구조 (repo 레이아웃)

```
SI_ Contract/
├── .specify/
│   ├── presets/templates/spec-template.md      # EARS 프리셋 (방법론 권장, §5)
│   ├── templates/{plan,tasks}-template.md      # Spec Kit 기본
│   ├── scripts/  memory/constitution.md        # Spec Kit + 우리 헌법 (§7)
├── .claude/skills/speckit-*/SKILL.md           # Claude 통합 = 스킬(/speckit-* 하이픈) (신규, 검증)
├── .agents/skills/speckit-*/SKILL.md           # Codex 통합 = skills($speckit-*) (신규, 검증)
├── CLAUDE.md / AGENTS.md                        # 기존 — SPECKIT 마커 블록만 append(덮어쓰기 X)
├── .claude/agents/{planner,executor,reviewer}.md  # 기존 — 보존
├── specs/
│   ├── ai-agent-engineering-spec-2026.md       # 기존 하네스 스펙 — 별개, 보존
│   └── EXE-01 … EXE-17/{spec.md, plan.md, tasks.md}   # 신규 (17×3 = 51 문서)
└── _archive/kiro-specs/multi-year-carryover/   # 기존 Kiro 스펙 이관 (§3 EXE-11)
```

산출 본문은 작성자가 EARS 템플릿대로 **직접 저작**(슬래시 커맨드 결과물과 동치). 하네스는 설치해 두어 이후 신규 기능·`/converge`가 Claude·Codex에서 동작.

## 3. 기능 분해 (EXE-01~17) — 코드 근거로 정밀화

당초 14개를 실제 코드 스캔/대조로 17개로 정밀화(경계가 실제 모듈과 1:1 대응).

| # | 기능 | 성격 | 코드 근거 `[공식 코드]` |
|---|------|------|----------|
| EXE-01 | 문서분류 | 도메인 | `ai_core.py:198 classify_document`, `main.py:514 /api/classify` (6종) |
| EXE-02 | 소스추출 | 도메인 | `ai_core.py` extract_all_fields(259)/costs(464)/people(475)/schedule(480)/rates(485)/org(490) |
| EXE-03 | 사내기준보정 | 도메인 | `company_standards.py`(단가표·요율·명절) + `contract_builder.py:434-560` 보정 |
| EXE-04 | 기본정보 확인 게이트 | **프론트 전용** | `frontend/lib/types.ts:106 confirmedTabs`, `review-page.tsx:114` — 백엔드 게이트 엔드포인트 없음 |
| EXE-05 | 견적서 충돌 감지·해결 | 도메인 | `ai_core.py:522 cross_validate`, `main.py:675 /api/validate`, 유형 A/A'/B/C/D |
| EXE-06 | Sprint_Contract 생성 | 도메인 | `contract_builder.py:297 build_sprint_contract` (EXE-11 엔진 소비) |
| EXE-07 | 수수료산출내역 5-4 | 도메인 | `excel/fee_sheet.py`, `contract_builder.py:204 _build_fee_items` |
| EXE-08 | 집행예산 산출내역서·집계표 | 도메인 | `excel/breakdown_sheet.py` (BUDGET_BLOCKS) |
| EXE-09 | 노무비 상세(급료/상여/퇴직/명절) | 도메인 | `contract_builder.py:434-558`, `company_standards.py:63 holidays_in_period` |
| EXE-10 | 갑지(0) 집계 | **수식 레이어·종속** | `excel/cover_sheet.py` + `excel/common_sheet.py` (직접입력 셀 거의 없음) |
| EXE-11 | 연도분리 엔진 | **공유** (← .kiro 흡수) | `contract_builder.py:160 _fiscal_year_shares`, `:193 _split_by_shares` |
| EXE-12 | 템플릿 생성 | 도메인 | `excel_writer.py`, `excel/base.py`, `excel/utils.py rev_col` |
| EXE-13 | 수정집행(차수별 7시트) | 도메인 | `excel/revision_sheets.py`, MAX_REVISION=11(`company_standards.py:12`) |
| EXE-14 | import 역추출 | 도메인 | `ai_core.py:599 import_execution_plan`, `main.py:637 /api/import` |
| EXE-15 | Reviewer 결정론 5단계 | 교차검증 | `reviewer.py` _verify_fee_structure(147)/conflict(248)/breakdown(300)/cover(408)/basic(500) |
| EXE-16 | Reviewer AI 의미검증 | 교차검증 | `reviewer.py:97 _ai_semantic_review` (Bedrock — 비용·비결정성 분리) |
| EXE-17 | 계정 격리·인가 | 플랫폼 | `cognito_auth.py`, `main.py _project_owner/_assert_project_access` |

의존 관계·경계 명시 (plan.md에 반영):
- EXE-06(Sprint_Contract)이 EXE-11(연도분리 엔진)을 소비 — 동일 함수 공유 1곳 명문화.
- EXE-10(갑지)은 EXE-08 집계의 수식 표현(독립 데이터 task 없음, 수식 무결성 SC만).
- EXE-09(노무비 상세)는 EXE-08의 비목 하위 영역이나 상여/명절 등 규칙 밀도가 높아 분리.
- **EXE-03 ↔ EXE-09 경계** (둘 다 `contract_builder.py:434-560` 영역): EXE-03 = "소스에 값이 없을 때 적용하는 사내 표준 테이블·fallback 규칙"(충돌값 §6-1이 여기 귀속), EXE-09 = "급료/상여/퇴직/명절 노무비 항목의 산출·시트 배치 규칙". 공유 코드 영역임을 plan.md에 명기.

## 4. 기능별 문서 형식

각 EXE-NN은 Spec Kit 표준 3종:
- **spec.md**: User Scenarios(Given/When/Then) + **Functional Requirements = EARS 5패턴** + 측정형 Success Criteria + Key Entities + Assumptions + `[NEEDS CLARIFICATION]`
- **plan.md**: 아키텍처/스택(FastAPI·openpyxl·xlsx ZIP 패칭·Next.js)/데이터 흐름 + **각 FR↔실제 컴포넌트(file) 매핑**(§3 코드 근거 사용)
- **tasks.md**: 수용기준→task(실패테스트→최소구현→통과→커밋 단위). 단, 이번 작업은 문서까지 — tasks.md는 사람이 읽는 산출물(자동 implement 비의존, §9)

## 5. EARS 적용 — 프리셋 (방법론 권장) `[방법론]`

- 방식: EARS spec-template을 **조직 표준 프리셋**으로 패키징 (`.specify/presets/templates/spec-template.md`). `[공식 방법론]` ears-template 헤더 "조직 표준(권장): 프리셋", 방법론_구조 §8(`specify preset add`).
- 근거: 집행서뿐 아니라 GS 다(多)프로젝트에서 재사용 — "다인·다프로젝트 spec 통일" 의도(의사결정_히스토리 ①)에 부합.
- 검증 `[공식, CLI help 직접 확인]`: v0.11.8 `specify preset add --dev <dir> --priority N` 존재 (`--dev`=로컬 디렉토리 등록, README엔 없으나 CLI help에 있음). resolution stack: overrides(1)>presets(2)>extensions(3)>core(4), `specify preset resolve spec-template`로 적용 확인. 기본 spec-template은 비EARS(검증). **Claude 통합은 `.claude/skills/speckit-*`(슬래시 `/speckit-*` 하이픈), Codex는 `.agents/skills`+`$speckit-*`** — 방법론 문서의 `/speckit.specify`(점)는 구버전 표기.
- 출처: 방법론 폴더 `ears-spec-template.md` 이식.
- 유지 규칙(헌법에 명문화): Spec Kit 업그레이드 시 spec-template 변경분과 **재병합 검토 필수**(#1356 미해결 → 자가유지 부담). EARS 5패턴 규약 문서를 `specs/` 하위에 독립 보관해 도구 미설치 시에도 규약 성립.
- 대안(방법론 "프로젝트 일회성"): 단일 repo만 쓸 경우 `.specify/templates/overrides/`(우선순위 1) — 단 다프로젝트 재사용 불가.

## 6. `[NEEDS CLARIFICATION]` 방침

원칙: **단일 출처일 때만 인용 충전. 출처 2개+가 충돌하면 무조건 `[NEEDS CLARIFICATION]`** 으로 표기하고 충돌 출처를 모두 나열. (출처 있음 ≠ 확정)

### 6-1. 강제 `[NEEDS CLARIFICATION]` (충돌 확정, §10 검증)
1. **직급 단가표 3중 충돌** — `company_standards.py:16` 과장 550만 / `executor.md:101` 600만 / `REPORT_eps_values.md:144` 실양식 650만
2. **상여금 공식 충돌** — `executor.md:109` "1M/M 전액·비율없음" / `contract_builder.py:540` `rate*months/9` / `REPORT_eps_values.md:155` `=6500000*3/9`. (audit 메모리 "/9 사양충돌 미답"과 일치)
3. **보험 요율 이원화** — 집행 4.75/4.0674/0.796% vs 정산 4.5/4.0041/0.766% (`REPORT_eps_values.md:174-180`); 적용 기준연도/갱신정책도 미정
4. 간접·일반관리비율 **문서 근거** ("윤지민과장 25년 기준" 주석만, 공문 경로 없음)
5. 수수료 코드 1/2/3 **정량 판단 기준** (planner.md "[추측] 가능"으로만)
6. **하도급노무비율** 수치 (`executor.md:153` 공식엔 등장하나 % 미명시)

### 6-2. 채울 수 있는 값 (단일/일치 출처, 인용)
간접 1.9%·관리 3.0% (`company_standards.py:28-29` + `REPORT:97-98` 일치), MAX_REVISION 11, 재수정 3회(`orchestrator.py:125`), 동일오류 2회 에스컬레이션, 마진 무결성(집행단가≤계약단가, 역전 FAIL `reviewer.py:191`), 1원 정밀도, 충돌유형 A/A'/B/C/D 정의(PROJECT.md=planner.md 일치), 퇴직금 (급료+상여)/12, 명절 in-period 규칙, 안전관리비 인원×5만, Reviewer 임계 0.85/0.60, 명절 날짜 상수(2025~2027) 등. (각 spec.md Assumptions에 "코드 현행값=잠정, 권위 출처 미확정" 명기)

## 7. constitution (`.specify/memory/constitution.md`) `[우리결정 — 방법론은 "(선택) 프로젝트 원칙" 슬롯만 제공, 내용은 repo 분석]`

기존 `CLAUDE.md`/`AGENTS.md`의 **실효 규칙 승계** + 방법론 원칙:
- 제1원칙: **값 미창작 / 충돌값 = `[NEEDS CLARIFICATION]`**
- 근거 태깅(`[공식]`/`[외부]`/`[추측]`+알람), 추측 알람 의무
- 1원 정밀도, 역마진(집행>계약 단가) = critical FAIL
- 인간 확인 3관문(기본정보·견적서 충돌·추출결과), 자동 처리 금지
- Executor step-only, 병렬→순차 전환 금지
- hooks 기술은 **실제 settings.json 기준**(`PreToolUse(Edit|Write)→harness_check.py` 단일). `[공식]` CLAUDE.md의 guardian.sh/kairos.sh는 실재하지 않으므로 **승계 금지**(드리프트 답습 방지).
- PyPI `specify-cli`(동명 비공식) 금지, `git+...@v0.11.8` 핀 고정.

## 8. 설치 안전 절차 (specify init) `[우리결정 — 방법론 외 추가, 운영 repo 보호]`

`[공식 upgrade.md]` `--force`가 `.claude/commands/`·`.specify/*`를 덮어쓰므로:
1. 전용 브랜치 생성 (예: `feat/sdd-spec-suite`)
2. 현재 `.claude/`·`AGENTS.md`·`specs/` 클린 커밋으로 고정 + 별도 백업
3. `--force` **미사용**, 기본 모드로 init (Claude → Codex 개별)
4. `git diff`로 `.claude/agents/`·`.claude/settings.json`·`AGENTS.md` **변경 0건** 검증. 변경 발생 시 즉시 복원
5. Spec Kit이 `AGENTS.md`를 점유하면 우리 가이드는 별 파일명/`specs/` 격리로 회피

## 9. non-goal (2축 분리) `[우리결정 — critique 기반 범위 정의]`

- **(작업 깊이)** 코드 구현·TDD·실제 `/speckit.implement` 자동실행 **안 함**. 산출은 spec/plan/tasks 문서까지. 구현·검증(방법론 6단계 Superpowers)은 별도 사이클.
- **(도메인 범위)** 다음은 본 SDD 범위 외(확인된 별개 엔드포인트, 운영·인프라 횡단): 파일 저장소 CRUD(`/api/files*`, `/api/projects*`), 편집잠금(`/api/projects/{id}/lock*`), 챗봇(`/api/chat`), OTEL/RateLimit/Security 미들웨어. (결함 아님 — 의도적 제외)
- 기존 하네스 스펙(`specs/ai-agent-engineering-spec-2026.md`)·planner/executor/reviewer 에이전트 미수정.

## 10. 검증 로그 (작성자 직접 확인)

> 본 설계는 sub-agent 리서치 결과를 그대로 채택하지 않고, 작성자가 1차 출처/코드를 직접 열어 재확인했다. (1차 위임 검증에서 Issue #454 상태 오독이 있었기에 전수 재확인)

**웹 1차 출처 (WebFetch/GitHub API 직접):**
- spec-kit README — Codex CLI + skills 모드, 지원 에이전트 목록
- spec-kit README(preset) — `specify preset search`/`add <name>` 존재, resolution stack(overrides>presets>extensions>core). `--dev` 플래그는 README에 없음(로컬 프리셋 생성법 설치 시 확인)
- GitHub API issues/454 → `state: closed`; issues/1356 → `state: open` (EARS Integration)
- GitHub API releases/latest → `tag_name: v0.11.8`
- docs/upgrade.md — `--here`/`--force` 덮어쓰기 대상, `specs/` 보호, 백업 권고
- OpenAI Codex Custom Prompts — `$ARGUMENTS`/`$1..$9` 인수 지원

**실제 코드 (Read/grep 직접):**
- `company_standards.py` GRADE_RATES/DEFAULT_RATES/HOLIDAYS/MAX_REVISION, `holidays_in_period`
- `contract_builder.py:160/193/204/297/533-546` 연도분리 엔진·상여 /9·build_sprint_contract
- `reviewer.py` 5 verify + `_ai_semantic_review`(97) = 6단계
- `ai_core.py` classify(198)·extract 6종·cross_validate(522)·import(599)
- `main.py` 엔드포인트 전수 (게이트 엔드포인트 부재 확인)
- `excel/` 11개 라이터 모듈 존재
- `frontend` confirmedTabs(types.ts:106, review-page.tsx:114) — 게이트 프론트 전용
- `.claude/settings.json` hooks = harness_check.py 단일 (guardian/kairos 부재 확인)
- `.claude/agents/executor.md`, `.pipeline/analysis/REPORT_eps_values.md` — 충돌값 양측 대조

## 11. 미해결 명확화 항목 (사용자 직접 확정 대상)

§6-1의 6건은 `/clarify` 단계에서 **사용자가 사내 기준(사규·공문·단가표 등)으로 직접 확정**한다. 본 SDD는 지어내지 않고 `[NEEDS CLARIFICATION]`으로 표면화만 한다. (방법론은 도구·프로세스만 차용하고 예시 도메인 어휘는 쓰지 않는다.)

## 12. 다음 단계

1. 본 설계 사용자 리뷰·승인
2. `writing-plans`로 구현 계획 작성 (설치 → EARS 오버라이드 → 17개 spec → plan → tasks → analyze)
3. 양산: 전체 일괄(승인됨). 규모(51문서)상 ultracode 워크플로로 기능별 병렬 생성 가능(별도 옵트인)
