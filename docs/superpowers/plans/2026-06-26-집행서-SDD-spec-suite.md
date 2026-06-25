# 집행서 도메인 SDD 스펙 스위트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 집행서 도메인을 GS네오텍 확정 SDD 방법론(Spec Kit + FR만 EARS + Superpowers, 값 미창작)으로 정형화해, 17개 기능의 `spec/plan/tasks` 풀세트(51문서) + Spec Kit 하네스(Claude·Codex)를 산출한다.

**Architecture:** SI Contract repo 루트에 Spec Kit v0.11.8 설치(Claude 슬래시 + Codex skills) → EARS를 조직 표준 **프리셋**으로 패키징 → constitution 작성 → `specs/EXE-01..17/`에 기능별 3종 문서 저작 → `/analyze`·`/checklist`로 교차 일관성 게이트. 코드 구현은 비대상(문서까지).

**Tech Stack:** GitHub Spec Kit v0.11.8 (`uvx`/`specify`), EARS 5패턴, Superpowers(검증 단계, 본 계획 비대상), Markdown.

**설계 근거 문서:** `docs/superpowers/specs/2026-06-26-집행서-SDD-design.md` (이하 "설계 §N"). 기능별 코드 근거·빈칸값은 설계 §3·§6 참조.

## Global Constraints

각 task의 요구사항에 아래가 암묵적으로 모두 포함된다 (설계 문서에서 verbatim):

- **값 미창작**: 출처가 repo에 있는 단일 값만 인용 충전. **출처 2개+ 충돌 시 무조건 `[NEEDS CLARIFICATION]`** + 충돌 출처 전부 나열. (설계 §6)
- **FR = EARS 5패턴**(Ubiquitous/Event WHEN/State WHILE/Unwanted IF-THEN/Optional WHERE + SHALL). **수용기준 = Given/When/Then**, **SC = 측정형**(숫자 목표). (방법론 하이브리드_가이드)
- **Kiro 형식 미사용.** 산출은 Spec Kit 형식만.
- **코드 구현/TDD/`/speckit.implement` 자동실행 안 함** — 산출은 spec/plan/tasks 문서까지. (설계 §9 작업깊이 축)
- **범위 밖 도메인**: 파일 CRUD·편집잠금·챗봇·OTEL/RateLimit/Security 미들웨어. (설계 §9 도메인 축)
- **근거 태깅** `[공식]`/`[외부]`/`[추측]`(+알람) 유지. 도구 사실은 1차 출처 직접 확인 후에만 `[공식]`.
- **설치 안전**: spec-kit `@v0.11.8` 핀 고정, PyPI `specify-cli`(비공식) 금지. `--force` 금지. 설치 후 `.claude/agents/`·`.claude/settings.json`·`AGENTS.md` **변경 0건** git diff 검증. (설계 §8, `[공식 upgrade.md]`)
- **기존 자산 보존**: `specs/ai-agent-engineering-spec-2026.md`, `.claude/agents/{planner,executor,reviewer}.md` 미수정.

---

## Phase 0 — 하네스 셋업

### Task 0: 전용 브랜치 + 기존 자산 백업

**Files:**
- 변경 없음 (git 작업)

**Interfaces:**
- Produces: 클린 베이스 브랜치 `feat/sdd-spec-suite`, 백업 디렉토리

- [ ] **Step 1: 현재 상태 커밋(또는 stash)으로 워킹트리 클린화**

```bash
cd "/Users/toule/Documents/kiro/SI_ Contract"
git status --short   # 미커밋 변경 확인 (harness/long_term_memory.json 등)
git stash push -u -m "pre-sdd-stash" || true
```

- [ ] **Step 2: 전용 브랜치 생성**

```bash
git checkout -b feat/sdd-spec-suite
```
Expected: `Switched to a new branch 'feat/sdd-spec-suite'`

- [ ] **Step 3: 보호 대상 자산 백업 (덮어쓰기 대비)**

```bash
mkdir -p .sdd-backup
cp -R .claude .sdd-backup/claude
cp AGENTS.md .sdd-backup/AGENTS.md 2>/dev/null || true
cp -R specs .sdd-backup/specs
ls -la .sdd-backup
```
Expected: `.sdd-backup/{claude, AGENTS.md, specs}` 존재

- [ ] **Step 4: 백업 무결성 게이트**

Run: `diff -rq .claude .sdd-backup/claude && echo OK`
Expected: `OK` (차이 없음)

- [ ] **Step 5: Commit (백업 트래킹 제외)**

```bash
echo ".sdd-backup/" >> .gitignore
git add .gitignore
git commit -m "chore(sdd): branch + gitignore for spec-kit install backup"
```

---

### Task 1: Spec Kit 설치 (Claude Code) + 검증

**Files:**
- Create: `.specify/` (templates/scripts/memory), `.claude/commands/speckit.*.md`

**Interfaces:**
- Produces: `specify` 실행 가능 상태, `/speckit.*` 슬래시 커맨드(Claude)

- [ ] **Step 1: specify CLI 가용성 확인 (버전 핀)**

Run: `uvx --from git+https://github.com/github/spec-kit.git@v0.11.8 specify --help`
Expected: specify CLI 도움말 출력 (PyPI `specify-cli` 사용 금지 — git 소스만)

- [ ] **Step 2: 현재 디렉토리에 init (Claude, --force 금지)**

```bash
uvx --from git+https://github.com/github/spec-kit.git@v0.11.8 specify init . --integration claude
```
Expected: 덮어쓰기 확인 프롬프트가 뜨면 기존 `.claude/agents`·`settings.json`·`AGENTS.md`를 건드리는지 확인 후 진행. `.specify/`·`.claude/commands/speckit.*` 생성.

- [ ] **Step 3: 보호 자산 변경 0건 게이트 (CRITICAL)**

```bash
git add -A && git status --short
diff -rq .claude/agents .sdd-backup/claude/agents && echo "agents OK"
diff .claude/settings.json .sdd-backup/claude/settings.json && echo "settings OK"
diff AGENTS.md .sdd-backup/AGENTS.md && echo "AGENTS OK"
```
Expected: `agents OK` / `settings OK` / `AGENTS OK`.
**FAIL 시**: `cp -R .sdd-backup/claude/agents .claude/ && cp .sdd-backup/claude/settings.json .claude/ && cp .sdd-backup/AGENTS.md AGENTS.md` 로 즉시 복원 후, 충돌 파일을 spec-kit이 점유하면 우리 자산을 다른 경로로 격리하는 방안 재검토.

- [ ] **Step 4: Commit**

```bash
git add .specify .claude/commands
git commit -m "chore(sdd): install spec-kit v0.11.8 (claude integration)"
```

---

### Task 2: Codex 통합 추가 (skills 모드)

**Files:**
- Create: `.codex/` 또는 spec-kit이 codex용으로 생성하는 prompts/skills 경로

**Interfaces:**
- Consumes: Task 1의 `.specify/`
- Produces: Codex에서 `$speckit-*` 호출 가능 상태

- [ ] **Step 1: Codex 통합 init (skills 모드)**

```bash
uvx --from git+https://github.com/github/spec-kit.git@v0.11.8 specify init . --integration codex --integration-options="--skills"
```
Expected: Codex용 커맨드/skills 생성. **참고**: `--integration-options="--skills"`는 설계 §1에서 README로 확인한 형태. 실거동이 다르면 `specify --help`/`specify init --help`로 현행 플래그 재확인 후 조정(지어내지 말 것).

- [ ] **Step 2: 보호 자산 변경 0건 재게이트**

```bash
diff -rq .claude/agents .sdd-backup/claude/agents && echo "agents OK"
diff .claude/settings.json .sdd-backup/claude/settings.json && echo "settings OK"
```
Expected: 둘 다 OK

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore(sdd): add codex integration (skills mode)"
```

---

### Task 3: EARS 조직 표준 프리셋 패키징

**Files:**
- Create: `.specify/presets/templates/spec-template.md` (EARS)
- Source: `/Users/toule/Documents/Works/2026/업무용/솔루션/SDD/03_방법론_확정/ears-spec-template.md`

**Interfaces:**
- Consumes: Task 1의 `.specify/`
- Produces: `/speckit.specify`가 FR=EARS 템플릿으로 spec 생성

- [ ] **Step 1: 로컬 프리셋 생성법 실거동 확인 (지어내지 말 것)**

Run: `uvx --from git+https://github.com/github/spec-kit.git@v0.11.8 specify preset --help`
확인 사항: 로컬 커스텀 프리셋 등록 방법 — (a) `specify preset add` 로컬 경로/`--dev` 지원 여부, (b) 아니면 `.specify/presets/templates/`에 파일 직접 배치.
**근거**: 설계 §5 — `--dev`는 현행 README 미기재. resolution stack은 overrides>presets>extensions>core (presets=우선순위 2).

- [ ] **Step 2: EARS spec-template 배치**

```bash
mkdir -p .specify/presets/templates
cp "/Users/toule/Documents/Works/2026/업무용/솔루션/SDD/03_방법론_확정/ears-spec-template.md" .specify/presets/templates/spec-template.md
```
(Step 1에서 `specify preset add`가 로컬을 지원하면 그 방식 사용. 미지원이면 위 직접 배치 + resolution stack으로 적용.)

- [ ] **Step 3: 프리셋 해석 게이트**

Run: `uvx --from git+https://github.com/github/spec-kit.git@v0.11.8 specify preset search` (및 가능하면 resolve 류 확인)
Expected: 배치한 EARS 템플릿이 spec-template 해석에 반영됨. **검증 불가 시**: 더미 `specs/_smoke/`에 `/speckit.specify` 1회 실행해 산출 spec의 FR 섹션이 EARS 5패턴 안내를 포함하는지 육안 확인 후 더미 삭제.

- [ ] **Step 4: Commit**

```bash
git add .specify/presets
git commit -m "feat(sdd): add EARS org-standard preset (spec-template override)"
```

---

### Task 4: constitution 작성 `[우리결정 — 내용은 repo 규칙 승계]`

**Files:**
- Create/Modify: `.specify/memory/constitution.md`

**Interfaces:**
- Produces: 프로젝트 헌법 (이후 모든 spec이 준수)

- [ ] **Step 1: constitution 작성** (설계 §7 내용)

`.specify/memory/constitution.md`에 아래 원칙 기재 (각 항목 1~2줄):

```markdown
# 집행서 SDD Constitution

## 제1원칙: 값 미창작
출처가 repo에 있는 단일 값만 인용. 출처 2개+ 충돌 시 [NEEDS CLARIFICATION] + 충돌 출처 전부 나열. 임의 수치 생성 금지.

## 근거 태깅
모든 사실 주장에 [공식]/[외부]/[추측]. [추측]엔 알람 블록. 도구 사실은 1차 출처 직접 확인 후에만 [공식].

## 금액·검증 규율
1원 정밀도(모든 금액 검증 1원 오차도 FAIL). 역마진(집행단가 > 계약단가) = critical FAIL.

## 인간 게이트
3관문(기본정보·견적서 충돌·추출결과) 사용자 확인 필수. 충돌·추측 자동 처리 금지.

## 에이전트 규율
Executor는 step 정보만 수신(전체 계약 금지). 병렬→순차 전환 사용자 동의 없이 금지.

## 도구·버전
spec-kit @v0.11.8 핀. PyPI specify-cli(동명 비공식) 금지. 업그레이드 시 EARS 프리셋 재병합 검토(#1356 미해결).

## Hooks (실제 settings.json 기준)
PreToolUse(Edit|Write) → .claude/hooks/harness_check.py 단일. (CLAUDE.md의 guardian.sh/kairos.sh는 실재하지 않으므로 승계 금지.)
```

- [ ] **Step 2: hooks 기술 정확성 게이트**

Run: `python3 -c "import json; h=json.load(open('.claude/settings.json'))['hooks']; print(list(h.keys()))"`
Expected: `['PreToolUse']` (constitution의 hooks 서술과 일치 — guardian/kairos 미기재 확인)

- [ ] **Step 3: Commit**

```bash
git add .specify/memory/constitution.md
git commit -m "feat(sdd): add project constitution (repo rules + 값 미창작)"
```

---

### Task 5: 기존 Kiro 스펙 아카이브

**Files:**
- Move: `.kiro/specs/multi-year-carryover/` → `_archive/kiro-specs/multi-year-carryover/`

**Interfaces:**
- Produces: Kiro 형식 운영 제거 (내용은 EXE-11로 변환 예정)

- [ ] **Step 1: 아카이브 이동**

```bash
mkdir -p _archive/kiro-specs
git mv .kiro/specs/multi-year-carryover _archive/kiro-specs/multi-year-carryover
ls _archive/kiro-specs/multi-year-carryover
```
Expected: `requirements.md`, `.config.kiro` 존재

- [ ] **Step 2: Commit**

```bash
git commit -m "chore(sdd): archive kiro multi-year-carryover spec (→ EXE-11)"
```

---

## Phase 1 — 기능별 SDD 저작 (EXE-01 ~ EXE-17)

### 공통 저작 절차 (모든 EXE-NN task가 따르는 표준 — 반복 대신 참조)

각 기능 task는 아래 5스텝 사이클을 수행한다. "테스트" = 게이트 체크리스트.

**저작 입력**: 설계 §3(코드 근거)·§6(채울 값/충돌). **금지**: 코드를 새로 읽어 값을 창작 — 설계 §3/§6과 실제 file:line만 근거로.

1. **spec.md 저작** — 섹션: `## User Scenarios & Testing`(User Story + Given/When/Then) → `## Functional Requirements`(각 FR `(패턴)` 태그 + EARS 문장) → `## Success Criteria`(측정형, 출처 없으면 `[NEEDS CLARIFICATION]`) → `## Key Entities` → `## Assumptions`(코드 현행값=잠정 명기) → `## Clarifications Retained`(해당 기능의 §6-1 충돌 항목).
2. **spec 게이트** — 체크리스트:
   - [ ] 모든 FR이 EARS 5패턴 중 하나 (모호어 "should/적절히" 0건, 한 문장 1동작)
   - [ ] 충돌값(설계 §6-1 해당분)이 `[NEEDS CLARIFICATION]` + 충돌 출처 나열
   - [ ] SC가 측정형(숫자/시간), 미정 목표는 `[NEEDS CLARIFICATION]`
   - [ ] 범위 밖 도메인(설계 §9) 미포함
3. **plan.md 저작** — 아키텍처/스택 + **각 FR ↔ 실제 컴포넌트(file:line) 매핑**(설계 §3 코드 근거 사용) + 의존(설계 §3 의존관계).
4. **tasks.md 저작** — 각 수용기준→task(실패테스트→최소구현→통과→커밋 단위). **사람이 읽는 산출물**(자동 implement 비의존).
5. **커밋** — `git add specs/EXE-NN && git commit -m "feat(sdd): EXE-NN <기능> spec/plan/tasks"`.

> 실행 방식: `/speckit.specify`(Claude) 또는 직접 저작 둘 다 가능. EARS 프리셋이 FR 섹션을 강제하므로 슬래시 커맨드 사용 권장. Codex에선 `$speckit-specify`.

---

### Task EXE-01: 문서분류

**Files:** Create `specs/EXE-01/{spec.md,plan.md,tasks.md}`
**Interfaces:** Produces 분류 결과 스키마(category·confidence) — EXE-02·EXE-14가 소비
**저작 입력(코드 근거):** `ai_core.py:198 classify_document`, `main.py:514 /api/classify`. 6종 문서 분류.
**FR로 인코딩할 동작:**
- (event) WHEN 문서 업로드 시, THE SYSTEM SHALL 계약서/견적서/집행계획서 등 6종으로 분류하고 신뢰도를 산출한다.
- (unwanted) IF 분류 신뢰도가 임계값 미만이면, THEN THE SYSTEM SHALL 자동 확정 대신 사용자 확인을 요청한다.
- (ubiquitous) THE SYSTEM SHALL 분류 결과에 근거(파일명/내용 신호)를 보존한다.
**`[NEEDS CLARIFICATION]`:** 분류 신뢰도 임계값 수치, 6종 taxonomy 정확 정의(코드 확인 필요·미명시면 빈칸).

- [ ] **Step 1: spec.md** (공통 절차 1 + 위 FR)
- [ ] **Step 2: spec 게이트** (공통 절차 2)
- [ ] **Step 3: plan.md** (FR↔`ai_core.py:198`/`main.py:514` 매핑)
- [ ] **Step 4: tasks.md** (공통 절차 4)
- [ ] **Step 5: Commit**

---

### Task EXE-02: 소스추출

**Files:** Create `specs/EXE-02/{spec,plan,tasks}.md`
**Interfaces:** Consumes EXE-01 분류; Produces ExtractedData(필드/costItems/people/rates) — EXE-05·06 소비
**코드 근거:** `ai_core.py` extract_all_fields(259)/costs(464)/people(475)/schedule(480)/rates(485)/org(490); `main.py:544~629`
**FR 동작:** WHEN 분류된 소스 수신, THE SYSTEM SHALL 섹션별(필드/원가/인력/일정/요율/조직) 추출을 수행한다 / (unwanted) IF 필드 근거가 소스에 없으면 THEN `[추측]` 표기 + 빈칸 / (ubiquitous) 각 추출값에 출처(문서·위치) 보존.
**`[NEEDS CLARIFICATION]`:** 없음(추출 동작은 코드로 확정). 추출 정확도 SC 목표는 베이스라인 후.

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-03: 사내기준보정

**Files:** Create `specs/EXE-03/{spec,plan,tasks}.md`
**Interfaces:** Consumes EXE-02; Produces 보정된 단가/요율/명절 — EXE-06·09 소비
**코드 근거:** `company_standards.py`(GRADE_RATES·DEFAULT_RATES·HOLIDAYS), `contract_builder.py:434-560` 보정. 경계: 설계 §3(EXE-03=fallback 표준 규칙).
**FR 동작:** (unwanted) IF 급료/요율이 소스에 없으면 THEN THE SYSTEM SHALL 사내 표준 테이블 값을 fallback 적용하고 관문 재확인 플래그를 단다 / (state) WHILE 명절이 투입기간 [start,end] 밖이면 THE SYSTEM SHALL 해당 상여를 책정하지 않는다.
**`[NEEDS CLARIFICATION]` (설계 §6-1, 강제):**
- 직급 단가표 3중 충돌: `company_standards.py:16` 과장 550만 / `executor.md:101` 600만 / `REPORT_eps_values.md:144` 650만
- 간접·일반관리비율 문서 근거(주석만), 보험요율 적용 기준연도·갱신정책, 하도급노무비율 수치
**채울 값(단일 출처):** 명절 in-period 규칙, 명절 날짜 상수(2025~2027), 간접 1.9%/관리 3.0%(코드+REPORT 일치, "잠정" 명기).

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-04: 기본정보 확인 게이트 (프론트 전용)

**Files:** Create `specs/EXE-04/{spec,plan,tasks}.md`
**Interfaces:** Consumes EXE-02; Produces confirmedTabs 상태
**코드 근거:** `frontend/lib/types.ts:106 confirmedTabs`, `review-page.tsx:114`. **백엔드 게이트 엔드포인트 없음.**
**범주화(설계 §3):** 프론트 UX 제약. SC를 "UI 상태/확정 게이트 동작"으로 측정.
**FR 동작:** (event) WHEN 6개 기본정보 추출 완료 시, THE FRONTEND SHALL 사용자에게 확인 UI를 제시한다 / (unwanted) IF 사용자가 미확인 상태면 THEN THE FRONTEND SHALL 다음 단계 진행을 차단한다.
**주의:** spec.md에 "백엔드 비즈니스 로직 아님(프론트 전용)" 명기.

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-05: 견적서 충돌 감지·해결

**Files:** Create `specs/EXE-05/{spec,plan,tasks}.md`
**Interfaces:** Consumes EXE-02; Produces ConflictResolution[]
**코드 근거:** `ai_core.py:522 cross_validate`, `main.py:675 /api/validate`; 유형 정의 `PROJECT.md:44-48`=`planner.md:109-113`(일치).
**FR 동작:** WHEN 다중 견적서 수신, THE SYSTEM SHALL 충돌 유형 A/A'/B/C/D를 감지한다 / IF 충돌 발견 THEN 사용자 선택을 요청하고 자동 병합하지 않는다(특히 A' 완전동일 자동병합 금지).
**채울 값:** 유형 A/A'/B/C/D 정의(단일 일치 출처).

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-06: Sprint_Contract 생성

**Files:** Create `specs/EXE-06/{spec,plan,tasks}.md`
**Interfaces:** Consumes EXE-02·03·05 + **EXE-11(연도분리 엔진)**; Produces SprintContract
**코드 근거:** `contract_builder.py:297 build_sprint_contract`. **EXE-11 공유**: `_fiscal_year_shares(160)`/`_split_by_shares(193)` 호출.
**FR 동작:** WHEN 확정 데이터·active_items 수신, THE SYSTEM SHALL ConfirmedFields/FeeItem/BudgetItem/RateSet를 포함한 SprintContract를 생성한다 / WHERE 다년도 사업이면 THE SYSTEM SHALL EXE-11 연도분리 엔진으로 당기/이후 배분한다.
**plan.md:** EXE-11 공유 의존 1곳 명문화.
**`[NEEDS CLARIFICATION]`:** MAX_REVISION 초과 처리(채울 값=11).

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-07: 수수료산출내역 (5-4)

**Files:** Create `specs/EXE-07/{spec,plan,tasks}.md`
**Interfaces:** Consumes EXE-06; Produces 5-4 시트 기록
**코드 근거:** `excel/fee_sheet.py`, `contract_builder.py:204 _build_fee_items`.
**FR 동작:** THE SYSTEM SHALL 계약 컬럼(매출, 발주처 계약서)과 집행 컬럼(매입, 협력사 견적서)을 분리 기록한다 / (unwanted) IF 집행단가 > 계약단가면 THEN 역마진 critical FAIL / 행별 수량×단가=금액(1원 정밀도).
**채울 값:** 마진 무결성 규칙, 1원 정밀도, 당기/차기 J/M/O 열 의미.

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-08: 집행예산 산출내역서·집계표

**Files:** Create `specs/EXE-08/{spec,plan,tasks}.md`
**Interfaces:** Consumes EXE-06; Produces 공통 시트 비목 기록
**코드 근거:** `excel/breakdown_sheet.py`(BUDGET_BLOCKS rows 23-112).
**FR 동작:** WHEN active_items=true인 비목, THE SYSTEM SHALL 해당 비목 블록에 금액을 기록한다 / 보험료=기준액×요율(자동 계산, 이중계상 방지).
**채울 값:** 간접 1.9%/관리 3.0%(잠정), 안전관리비 인원×5만. **`[NEEDS CLARIFICATION]`:** 보험요율 적용연도(EXE-03과 공유).
**경계:** EXE-09(노무비)와 BUDGET_BLOCKS 공유 — 설계 §3 경계 명기.

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-09: 노무비 상세 (급료/상여/퇴직/명절)

**Files:** Create `specs/EXE-09/{spec,plan,tasks}.md`
**Interfaces:** Consumes EXE-03; Produces 노무비 BudgetItem
**코드 근거:** `contract_builder.py:434-558`, `company_standards.py:63 holidays_in_period`. 경계: 설계 §3(EXE-09=노무비 산출/배치).
**FR 동작:** THE SYSTEM SHALL 급료=직급단가×M/M, 퇴직금=(급료+상여)/12로 산출한다 / WHERE 명절이 투입기간 내면 명절상여를 책정한다.
**`[NEEDS CLARIFICATION]` (설계 §6-1, 강제):**
- 상여 공식: `executor.md:109` 1M/M 전액 / `contract_builder.py:540` rate×months/9 / `REPORT_eps_values.md:155` (3/9)×단가
- 직급 단가표 3중 충돌(EXE-03과 공유)
**채울 값:** 퇴직금 (급료+상여)/12, 퇴직공제부금 0 고정.

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-10: 갑지(0) 집계 (수식 레이어·종속)

**Files:** Create `specs/EXE-10/{spec,plan,tasks}.md`
**Interfaces:** Consumes EXE-08 집계
**코드 근거:** `excel/cover_sheet.py` + `excel/common_sheet.py`. 직접입력 셀 거의 없음(수식 체인).
**범주화(설계 §3):** EXE-08 집계의 **수식 표현 레이어** — 독립 데이터 task 없음. **SC = 수식 무결성만**(예: 영업이익A = 매출액-(노무+재료+외주+경비), 1원 오차 FAIL).
**FR 동작:** THE SYSTEM SHALL 갑지 매출액/비목/영업이익을 집계표→공통 수식 체인으로 표현한다.

- [ ] **Step 1~5** (공통 절차, 단 tasks.md는 수식 검증 중심)

---

### Task EXE-11: 연도분리 엔진 (공유) ← .kiro 흡수

**Files:** Create `specs/EXE-11/{spec,plan,tasks}.md`
**Interfaces:** Produces _fiscal_year_shares/_split_by_shares — EXE-06·07·08·09가 소비(공유)
**코드 근거:** `contract_builder.py:160 _fiscal_year_shares`, `:193 _split_by_shares`, `common_sheet.py:16-63`.
**소스 흡수:** `_archive/kiro-specs/multi-year-carryover/requirements.md`(10 요구) → EARS로 변환.
**FR 동작:** WHEN 사업기간이 회계연도 경계를 걸치면, THE SYSTEM SHALL 당기/이후1/이후2 비율로 금액·수량을 배분하고 합계 정합성을 보존한다(잔여분 마지막 버킷).
**중요(설계 §6, critique medium):** .kiro 요구 중 **미구현 모델 확장**(settlement_cumulative_qty 등 신규 필드)은 "to-be, 코드 미구현"으로 라벨 분리 — as-is 코드 스펙과 섞지 말 것. 미구현분은 `[NEEDS CLARIFICATION]` 또는 별도 to-be 표기.

- [ ] **Step 1~5** (공통 절차, + .kiro 요구 10건 매핑 시 as-is/to-be 분리)

---

### Task EXE-12: 템플릿 생성

**Files:** Create `specs/EXE-12/{spec,plan,tasks}.md`
**코드 근거:** `excel_writer.py generate_excel/resolve_template_path`, `excel/base.py`, `excel/utils.py rev_col`.
**FR 동작:** THE SYSTEM SHALL 템플릿을 로드해 차수 열(E~P=0~11차)에 값을 기록하고 수식 캐시를 제거한다 / 빈 셀·시트 삭제·HLOOKUP 범위 규칙 적용.
**채울 값:** MAX_REVISION 11, HLOOKUP $E$8:$P$149.

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-13: 수정집행 (차수별 7시트)

**Files:** Create `specs/EXE-13/{spec,plan,tasks}.md`
**코드 근거:** `excel/revision_sheets.py apply_revision_sheets`, `orchestrator.py:104-113`(revision>=1 분기).
**FR 동작:** WHEN revision>=1, THE SYSTEM SHALL 차수별 7시트를 동적 생성하고 E5 차수·차수 열을 갱신한다 / (unwanted) IF revision > 11 THEN 거부(양식 한계).
**채울 값:** 7시트 목록, MAX_REVISION 11, HLOOKUP F8:P→E8:P 수정.

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-14: import 역추출

**Files:** Create `specs/EXE-14/{spec,plan,tasks}.md`
**Interfaces:** Consumes EXE-01 분류
**코드 근거:** `ai_core.py:599 import_execution_plan`, `main.py:637 /api/import`, 프론트 단위 게이트.
**FR 동작:** WHEN 완성 집행계획서(PDF/xlsx) 단독 업로드, THE SYSTEM SHALL 0차 역추출을 수행한다 / (unwanted) IF 단위(천원/원) 미확정이면 THEN 사용자 확정 게이트로 1000배 오류를 차단한다.
**채울 값:** 단위 확정 게이트, _parse_json 균형괄호 규칙.

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-15: Reviewer 결정론 5단계

**Files:** Create `specs/EXE-15/{spec,plan,tasks}.md`
**코드 근거:** `reviewer.py` _verify_fee_structure(147)/conflict(248)/breakdown(300)/cover(408)/basic(500).
**FR 동작:** THE SYSTEM SHALL 5단계(수수료구조·충돌해결·산출내역서교차·갑지·기본정보)를 결정론적으로 검증한다 / 1원 오차도 FAIL / 집행단가>계약단가 역마진 FAIL.
**채울 값:** 1원 정밀도, 보험료 오차 1000원 FAIL, Reviewer 임계 0.85/0.60.
**경계:** AI 의미검증은 EXE-16(분리).

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-16: Reviewer AI 의미검증

**Files:** Create `specs/EXE-16/{spec,plan,tasks}.md`
**코드 근거:** `reviewer.py:97 _ai_semantic_review` (Bedrock 호출).
**FR 동작:** WHEN 결정론 검증 후, THE SYSTEM SHALL 정보장벽(confirmed_fields+inputs_used만, Executor reasoning 미전달) 하에 AI 의미 일관성을 검증한다.
**SC:** 점수 임계 0.85(approved)/0.60(needs_revision). 비결정성·Bedrock 비용 명기.

- [ ] **Step 1~5** (공통 절차)

---

### Task EXE-17: 계정 격리·인가

**Files:** Create `specs/EXE-17/{spec,plan,tasks}.md`
**코드 근거:** `cognito_auth.py require_auth/resolve_role`, `main.py _project_owner/_assert_project_access`.
**FR 동작:** THE SYSTEM SHALL owner 필드·scan 필터·인가 게이트로 계정 간 데이터를 격리한다 / IF 비소유자 접근 THEN 거부.
**범위 주의:** 편집잠금(lock/unlock)은 설계 §9 범위 밖(별개 도메인) — 미포함.

- [ ] **Step 1~5** (공통 절차)

---

## Phase 2 — 교차 일관성 게이트 + 빈칸 집계

### Task 6: /analyze · /checklist 교차 검증

**Files:** 변경 없음 (검증) — 필요 시 spec 수정 커밋

- [ ] **Step 1: 일관성 분석**

Claude에서 `/speckit.analyze` 실행 (17개 spec↔plan↔tasks 누락·모순·중복 검사). 또는 수동: 각 EXE의 FR이 plan 컴포넌트로 매핑되고, 수용기준이 task로 커버되는지 표 점검.
Expected: 불일치 0건. 발견 시 해당 EXE로 돌아가 수정.

- [ ] **Step 2: 품질 체크리스트**

`/speckit.checklist` 또는 수동: 전 spec에서 EARS 비준수 FR·모호어·미표기 충돌값 0건 확인.

- [ ] **Step 3: Commit (수정분 있으면)**

```bash
git add specs && git commit -m "fix(sdd): cross-spec consistency (analyze/checklist)"
```

---

### Task 7: [NEEDS CLARIFICATION] 집계 → 인터뷰 질문지

**Files:** Create `specs/CLARIFICATIONS.md`

- [ ] **Step 1: 전 spec의 `[NEEDS CLARIFICATION]` 수집**

```bash
grep -rn "NEEDS CLARIFICATION" specs/EXE-* | tee specs/_nc_raw.txt
wc -l specs/_nc_raw.txt
```

- [ ] **Step 2: 9-카테고리 인터뷰 질문지 작성**

`specs/CLARIFICATIONS.md`에 수집 항목을 카테고리별로 정리 (설계 §6-1 6대 충돌 포함: 직급단가표·상여공식·보험요율·간접/관리비율 근거·수수료코드·하도급노무비율). 방법론 §12(9-카테고리) 형식.

- [ ] **Step 3: Commit**

```bash
rm specs/_nc_raw.txt
git add specs/CLARIFICATIONS.md
git commit -m "docs(sdd): aggregate NEEDS CLARIFICATION → interview questionnaire"
```

---

## Self-Review (작성자 체크)

**1. Spec coverage:** 설계 §3 17개 기능 → Task EXE-01~17 1:1 대응 ✓. 설계 §0~§12 각 항목: 방법론기반(Phase0 Task1-4)·구조(Phase0)·분해(Phase1)·문서형식(공통절차)·EARS(Task3)·빈칸방침(공통절차2+Task7)·constitution(Task4)·설치안전(Task0-2)·non-goal(Global Constraints)·검증로그(설계참조) ✓.

**2. Placeholder scan:** 각 EXE task에 구체 FR 동작·코드근거·충돌항목 명시(추상 "적절히 처리" 없음). "공통 절차 참조"는 placeholder 아님 — 절차 본문이 상단에 완전 기술됨(skill의 "repeat the code"는 코드 중복 방지 취지이며, 여기선 51문서 본문이 산출물이라 절차 1회 정의가 DRY에 부합).

**3. Type consistency:** 기능 간 Interfaces(Produces/Consumes) 일관 — EXE-11 연도분리 엔진을 EXE-06/07/08/09가 소비(동일 함수명 _fiscal_year_shares/_split_by_shares), EXE-01 분류를 EXE-02/14가 소비. 충돌값 항목명이 EXE-03↔EXE-09(직급단가표·상여)에서 동일 참조.

**미해결 종속성:** Task 3 Step 1(로컬 프리셋 생성법)·Task 2 Step 1(codex 플래그 실거동)은 설치 시 `specify --help`로 확인 — 현행 README 미기재분이라 의도적으로 "확인 후 진행"으로 둠(지어내지 않음).
