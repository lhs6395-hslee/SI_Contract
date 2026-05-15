# AI 에이전트 엔지니어링 종합 스펙 2026 — 요구사항 문서 v1.0

## 소개

소프트웨어 개발 프로젝트에서 2026년 기준 최신 AI 에이전트 엔지니어링 기술을 종합한 범용 요구사항 문서이다. 멀티 에이전트 하네스, GAN 영감의 Generator-Evaluator 패턴, Git Worktree 병렬 실행, Auto-Dream 메모리 관리, KAIROS 상시 감시, UltraPlan 계층 분해, Spec-Driven Development, Agent Team 협업, Harness Subtraction 최적화, IDE 어댑터 패턴, 다방향 Sync 파이프라인을 포함한다.

참고 자료:
- [Anthropic: Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Blake Crosley: Building AI-Powered Development Harnesses](https://blakecrosley.com/guides/agent-architecture)
- [Claude Code Agent Teams Guide](https://www.aifreeapi.com/en/posts/claude-code-agent-teams)
- [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나]

## 용어 정의

- **Orchestrator**: 에이전트 간 파일 기반 통신을 조율하고 I/O만 담당하는 메인 프로세스. Coordinator를 서브 모듈로 포함할 수 있다.
- **Planner**: 사용자 요청을 분석하여 상세 실행 스펙(Sprint_Contract)으로 확장하는 에이전트. UltraPlan 전략을 선택적으로 활성화한다.
- **Generator**: Sprint_Contract에 따라 실제 코드를 작성하는 에이전트
- **Evaluator**: Generator의 결과물을 독립적으로 검증하는 에이전트 (tsc, eslint, 보안 스캐너 등 실제 도구 사용). 전체 검증 파이프라인(full pipeline)을 수행한다.
- **Guardian**: 위험 명령을 사전 차단하는 에이전트. Claude API 호출 없이 Pattern_Matcher만으로 동작한다.
- **Coordinator**: Orchestrator의 서브 모듈로, Agent_Team 모드에서만 활성화되어 Specialist 에이전트들의 작업을 분배하고 통합한다.
- **Sprint_Contract**: Planner가 생성하고 Generator와 Evaluator가 합의하는 에이전트 간 작업 계약 JSON 파일
- **Agent_Session**: Claude API를 통해 생성되는 독립 에이전트 실행 단위 (컨텍스트 비공유)
- **Handoff_File**: 에이전트 간 통신에 사용되는 JSON 기반 파일. IDE_Adapter가 반환하는 에이전트 디렉토리에 저장된다.
- **Verdict**: Evaluator가 생성하는 검증 결과 (pass, fail, warn 중 하나)
- **Harness**: 에이전트들의 실행 순서, 통신, 재시도를 관리하는 전체 프레임워크
- **Pattern_Matcher**: Guardian이 위험 명령을 탐지하는 데 사용하는 정규식 기반 스크립트. exit code 2로 차단, exit code 0으로 허용
- **Feedback_Loop**: Evaluator의 Verdict가 fail일 때 Generator에게 수정을 요청하는 반복 구조. 기본 최대 5회, Confidence_Trigger에 의해 조정 가능
- **Context_Reset**: 장기 실행 시 컨텍스트 윈도우를 완전히 리셋하고 파일시스템 상태에서 재시작하는 전략
- **Dispatcher**: 동일 이벤트에 여러 훅이 실행될 때 순차적으로 실행하고 stdin을 캐싱하는 중앙 스크립트
- **Confidence_Trigger**: 작업의 위험도/복잡도를 평가하여 멀티 에이전트 심의 필요 여부를 결정하는 점수 체계
- **Atomic_Write**: 파일 쓰기 시 임시 파일에 먼저 쓰고 mv로 원자적 교체하는 패턴
- **IDE_Adapter**: IDE별 설정 파일 경로, 훅 포맷, 스티어링 구조를 변환하는 어댑터 모듈. 런타임에 현재 IDE 환경(Kiro, Claude Code CLI, Claude Desktop, Antigravity, VS Code)을 감지
- **Sync_Pipeline**: IDE 간 다방향 변환을 수행하는 파이프라인. 변환 매핑 규칙 관리, 충돌 감지 및 해결을 포함
- **Git_Worktree**: git worktree를 사용하여 동일 repo에서 에이전트별 독립 작업 디렉토리를 생성하는 병렬 실행 전략
- **Auto_Dream**: 장기 프로젝트에서 메모리 파일을 주기적으로 자동 정리하는 서브 에이전트. 파이프라인 완료 후 아카이브 수행
- **KAIROS_Monitor**: 백그라운드에서 상시 실행되며 코드 변경을 감시하고 경량 사전 감시(lint-level)를 수행하는 에이전트. Evaluator의 전체 검증과 범위가 분리됨
- **UltraPlan**: 복잡한 작업을 자동으로 계층적 태스크 트리로 분해하는 고급 플래닝 전략. Confidence_Trigger 점수 0.50 미만에서 활성화
- **SDD (Spec-Driven Development)**: 실행 가능한 스펙을 먼저 작성하고, 에이전트가 스펙에 따라 코드를 생성하며, CI/CD에서 스펙 준수를 자동 검증하는 개발 방법론
- **Agent_Team**: 여러 독립 에이전트가 각자 컨텍스트 윈도우를 갖고 병렬 작업하며, 사람은 의사결정 레벨에서만 개입하는 협업 패턴
- **Harness_Subtraction**: 모델 성능 향상에 따라 하네스에서 불필요한 스캐폴딩을 주기적으로 제거하는 최적화 전략
- **Context_Rot**: 장기 실행 세션에서 컨텍스트 누적으로 인해 에이전트 성능이 저하되는 현상. 50k 토큰 이상에서 주로 발생하며, 관련 없는 방해 문장 1개만으로도 성능이 유의미하게 하락한다
- **Right_Altitude**: 에이전트 지시에서 세부 구현(how) 대신 원칙(what)과 이유(why)를 제시하는 추상화 수준 원칙. "원칙 1줄 + 이유 1줄 + 예시 1-2개" 형식으로 작성한다
- **Plan_Critic_Build**: 계획(Plan) → 비평(Critic) → 구현(Build) 순서로 진행하는 에이전트 워크플로우 패턴. 실행 전 계획을 독립 에이전트가 비평하여 오류를 조기 발견한다
- **Ralph_Loop**: 에이전트가 PROMPT.md 또는 지시 파일을 순환 참조하여 무한 루프에 빠지는 안티패턴. 루프 종료 조건(exit condition)을 명시하지 않을 때 발생한다
- **Context_Failure_Mode**: 에이전트 컨텍스트에서 발생하는 실패 유형. Poisoning(오염), Distraction(분산), Confusion(혼동), Clash(충돌) 4가지로 분류된다

## Confidence_Trigger 동작 구간 정의

| 종합 점수 | 파이프라인 모드 | Feedback_Loop 최대 | UltraPlan | Agent_Team |
|-----------|----------------|-------------------|-----------|------------|
| 0.85 이상 | 단일 에이전트 | N/A | 비활성 | 비활성 |
| 0.70-0.84 | 멀티 에이전트 (축소) | 3회 | 비활성 | 비활성 |
| 0.50-0.69 | 멀티 에이전트 (전체) | 5회 | 비활성 | 선택적 |
| 0.50 미만 | 멀티 에이전트 (전체) | 5회 | 활성 | 선택적 |

## 요구사항

### 요구사항 1: Orchestrator 프로세스 구현

**사용자 스토리:** 개발자로서, 에이전트 간 통신을 조율하는 중앙 Orchestrator가 필요하다. 이를 통해 각 에이전트가 독립적으로 실행되면서도 일관된 워크플로우를 유지할 수 있다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. WHEN 사용자가 작업 요청을 제출하면, THE Orchestrator SHALL 요청을 파싱하여 IDE_Adapter가 반환하는 에이전트 디렉토리의 `requests/` 하위에 요청 Handoff_File을 생성한다.
2. THE Orchestrator SHALL 에이전트 실행 순서를 Planner → Generator → Evaluator 순서로 조율한다. Agent_Team 모드에서는 Coordinator 서브 모듈이 Specialist 분배를 담당한다.
3. WHEN 에이전트 실행이 완료되면, THE Orchestrator SHALL 해당 에이전트의 출력 Handoff_File을 읽고 다음 에이전트에게 전달한다.
4. IF 에이전트 실행 중 타임아웃(120초 초과)이 발생하면, THEN THE Orchestrator SHALL 해당 에이전트의 실행을 중단하고 에러 상태를 Handoff_File에 기록한다.
5. THE Orchestrator SHALL 자체적으로 코드 생성이나 검증 로직을 수행하지 않고, I/O 조율에만 집중한다.
6. WHEN 전체 파이프라인이 완료되면, THE Orchestrator SHALL 최종 결과 요약을 에이전트 디렉토리의 `results/` 하위에 기록한다.
7. THE Orchestrator SHALL 각 에이전트 실행 시 Context_Reset 전략을 적용하여, 이전 에이전트의 컨텍스트를 공유하지 않고 클린 컨텍스트에서 시작한다.

### 요구사항 2: Planner 에이전트 구현

**사용자 스토리:** 개발자로서, 사용자의 자연어 요청을 구조화된 실행 스펙으로 변환하는 Planner가 필요하다. 이를 통해 Generator가 명확한 지시에 따라 코드를 작성할 수 있다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. WHEN 사용자 요청 Handoff_File을 수신하면, THE Planner SHALL 요청을 분석하여 Sprint_Contract JSON 파일을 에이전트 디렉토리의 `contracts/` 하위에 생성한다.
2. THE Sprint_Contract SHALL 다음 필드를 포함한다: 작업 목표(goal), 수정 대상 파일 목록(files), 인수 조건(acceptance_criteria), 제약 조건(constraints), 예상 영향 범위(impact_scope).
3. THE Planner SHALL 프로젝트의 기존 디렉토리 구조를 분석하여 Sprint_Contract의 파일 목록에 반영한다.
4. WHEN Sprint_Contract 생성이 완료되면, THE Planner SHALL 완료 상태를 Handoff_File에 기록한다.
5. THE Planner SHALL Claude API를 통해 독립 Agent_Session으로 실행되며, Generator의 컨텍스트를 공유하지 않는다.
6. THE Planner SHALL 1-4문장의 사용자 요청을 야심적인 범위의 상세 제품 스펙으로 확장하되, 세부 기술 구현은 과도하게 명시하지 않는다.

### 요구사항 3: Generator 에이전트 구현

**사용자 스토리:** 개발자로서, Sprint_Contract에 따라 실제 코드를 작성하는 독립 Generator가 필요하다. 이를 통해 코드 생성과 검증이 분리된다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. WHEN Sprint_Contract를 수신하면, THE Generator SHALL 계약에 명시된 파일 목록과 인수 조건에 따라 코드를 생성한다.
2. THE Generator SHALL 생성한 코드를 프로젝트 디렉토리에 직접 작성하고, 변경 사항 목록을 에이전트 디렉토리의 `outputs/` 하위 Handoff_File에 기록한다.
3. THE Generator SHALL 프로젝트의 코드 작성 규칙(Sprint_Contract의 constraints에 명시)을 준수한다.
4. THE Generator SHALL Claude API를 통해 독립 Agent_Session으로 실행되며, Planner 및 Evaluator의 컨텍스트를 공유하지 않는다.
5. WHEN Evaluator로부터 fail Verdict를 수신하면, THE Generator SHALL Evaluator의 피드백을 기반으로 코드를 수정하고 새로운 Handoff_File을 생성한다.
6. IF Feedback_Loop가 Confidence_Trigger에 의해 결정된 최대 횟수를 초과하면, THEN THE Generator SHALL 수정을 중단하고 실패 상태를 Orchestrator에 보고한다.
7. THE Generator SHALL 스프린트 기반 분해(sprint-based decomposition) 방식으로 작업하며, 단일 모놀리식 빌드를 지양한다.

### 요구사항 4: Evaluator 에이전트 구현

**사용자 스토리:** 개발자로서, Generator가 작성한 코드를 독립적으로 검증하는 Evaluator가 필요하다. 이를 통해 자기 검증 편향 없이 객관적인 품질 평가가 가능하다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. WHEN Generator의 출력 Handoff_File을 수신하면, THE Evaluator SHALL 변경된 파일 목록을 기반으로 전체 검증 파이프라인(full pipeline)을 수행한다.
2. THE Evaluator SHALL 다음 외부 도구를 `runCommand` 방식으로 실행하여 검증한다: TypeScript 컴파일러(tsc --noEmit), ESLint(eslint), 보안 패턴 스캐너. KAIROS_Monitor의 경량 사전 감시와 달리, Evaluator는 전체 프로젝트 범위의 검증을 수행한다.
3. THE Evaluator SHALL Sprint_Contract의 인수 조건 각 항목에 대해 pass 또는 fail Verdict를 생성한다.
4. THE Evaluator SHALL Claude API를 통해 독립 Agent_Session으로 실행되며, Generator의 컨텍스트를 공유하지 않는다.
5. WHEN 검증 결과에 fail 항목이 존재하면, THE Evaluator SHALL 실패 사유와 구체적인 코드 위치(파일명:라인번호)를 포함한 수정 제안을 Verdict Handoff_File에 기록한다.
6. WHEN 모든 인수 조건이 pass이면, THE Evaluator SHALL 최종 승인 Verdict를 생성하고 Orchestrator에 완료를 보고한다.
7. THE Evaluator SHALL 코드 생성 전에 Sprint_Contract의 인수 조건을 검토하고, 테스트 가능한 명시적 성공 기준을 협상한다.
8. THE Evaluator SHALL few-shot 보정을 통해 관대한 평가 편향(leniency bias)을 방지한다. 시스템 프롬프트에 pass/fail 판정 예시를 포함한다.
9. WHEN Git_Worktree 병렬 실행 모드에서, THE Evaluator SHALL 각 worktree의 코드를 main 브랜치 기준으로 검증한다.

### 요구사항 5: Guardian 에이전트 구현

**사용자 스토리:** 개발자로서, 위험한 명령이 실행되기 전에 사전 차단하는 Guardian이 필요하다. 이를 통해 개발 환경의 안전성을 보장할 수 있다.

*참조: [Blake Crosley: Building AI-Powered Development Harnesses] / [Anthropic: Harness Design for Long-Running Application Development]*

#### 인수 조건

1. WHEN 쉘 명령 실행 요청이 발생하면, THE Guardian SHALL Pattern_Matcher 스크립트를 실행하여 위험 명령을 탐지한다.
2. THE Guardian SHALL 다음 명령을 무조건 차단한다(exit code 2 반환): `DROP DATABASE`, `DROP SCHEMA`, 시스템 네임스페이스에 대한 `kubectl delete namespace`, `rm -rf /` 또는 시스템 디렉토리 삭제, `git push --force` to main/master.
3. THE Guardian SHALL 다음 명령에 대해 경고 Verdict를 생성한다(exit code 0 + 경고 메시지): `DROP TABLE`, `TRUNCATE`, 사용자 네임스페이스에 대한 `kubectl delete`, `docker compose down -v`.
4. THE Guardian SHALL `runCommand` 기반 외부 스크립트(Pattern_Matcher)를 실행하여 검증하며, `askAgent` 기반 역할극이 아닌 실제 패턴 매칭을 수행한다.
5. IF 차단 대상 명령이 탐지되면, THEN THE Guardian SHALL 실행을 거부하고 차단 사유를 stderr에 출력하며 exit code 2를 반환한다.
6. WHEN 명령이 안전하다고 판정되면, THE Guardian SHALL exit code 0을 반환하여 실행을 허용한다.
7. THE Guardian SHALL Claude API 호출 없이 Pattern_Matcher 로직만으로 위험 명령을 탐지한다. 이를 통해 API 비용 없이 즉각적인(200ms 이내) 안전성 검증을 수행한다.

### 요구사항 6: 파일 기반 에이전트 간 통신 구현

**사용자 스토리:** 개발자로서, 에이전트 간 통신이 파일 기반으로 이루어져야 한다. 이를 통해 에이전트 간 컨텍스트 격리를 보장하고 통신 내역을 추적할 수 있다.

*참조: [Anthropic: Harness Design for Long-Running Application Development]*

#### 인수 조건

1. THE Harness SHALL IDE_Adapter가 반환하는 에이전트 디렉토리 하위에 다음 서브 디렉토리를 사용한다: `requests/`, `contracts/`, `outputs/`, `verdicts/`, `results/`.
2. THE Handoff_File SHALL JSON 형식이며, 다음 공통 필드를 포함한다: `id`(UUID), `timestamp`(ISO 8601), `from_agent`, `to_agent`, `status`(pending, completed, failed), `payload`.
3. WHEN 에이전트가 Handoff_File을 생성하면, THE Harness SHALL 파일명에 타임스탬프와 에이전트 이름을 포함하여 고유성을 보장한다.
4. THE Harness SHALL 활성 파이프라인 실행 중에는 Handoff_File을 불변(immutable)으로 유지한다. 파이프라인 완료 후 Auto_Dream에 의한 아카이브는 허용된다.
5. IF Handoff_File의 JSON 파싱에 실패하면, THEN THE Harness SHALL 파싱 에러를 로그에 기록하고 해당 에이전트에 재생성을 요청한다.
6. THE Harness SHALL 모든 파일 쓰기에 Atomic_Write 패턴을 적용한다. 임시 파일(.tmp)에 먼저 쓰고 mv로 원자적 교체하여 동시 접근 시 JSON 손상을 방지한다.

### 요구사항 7: 독립 Agent_Session 관리

**사용자 스토리:** 개발자로서, 각 에이전트가 Claude API를 통해 독립된 세션으로 실행되어야 한다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Claude Code Agent Teams Guide]*

#### 인수 조건

1. THE Harness SHALL 각 에이전트(Planner, Generator, Evaluator)를 별도의 Claude API 호출로 실행한다.
2. THE Agent_Session SHALL 해당 에이전트의 역할 전용 시스템 프롬프트만 포함하며, 다른 에이전트의 대화 이력을 포함하지 않는다.
3. WHEN Agent_Session을 생성할 때, THE Harness SHALL 에이전트별 시스템 프롬프트를 IDE_Adapter가 반환하는 에이전트 디렉토리의 `prompts/` 하위 설정 파일에서 로드한다.
4. THE Harness SHALL Agent_Session 생성 시 프로젝트에 설정된 Claude API 클라이언트(AWS Bedrock 또는 Anthropic Direct)를 사용한다.
5. IF Claude API 호출이 실패하면, THEN THE Harness SHALL 최대 2회 재시도하고, 재시도 실패 시 에러 상태를 Orchestrator에 보고한다.
6. THE Harness SHALL 각 Agent_Session에 Context_Reset 전략을 적용한다.

### 요구사항 8: Feedback_Loop 구현

**사용자 스토리:** 개발자로서, Evaluator의 검증 실패 시 Generator에게 자동으로 수정을 요청하는 피드백 루프가 필요하다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. WHEN Evaluator가 fail Verdict를 생성하면, THE Orchestrator SHALL Verdict Handoff_File을 Generator에게 전달하여 수정을 요청한다.
2. THE Feedback_Loop SHALL 기본 최대 반복 횟수를 5회로 설정하되, Confidence_Trigger에 의해 조정될 수 있다 (Confidence_Trigger 동작 구간 정의 표 참조).
3. WHEN Feedback_Loop가 실행될 때마다, THE Orchestrator SHALL 반복 횟수를 Handoff_File에 기록한다.
4. IF Confidence_Trigger에 의해 결정된 최대 반복 횟수에 도달하면, THEN THE Orchestrator SHALL 파이프라인을 중단하고 마지막 Evaluator Verdict와 함께 실패 결과를 기록한다.
5. WHEN Feedback_Loop 내에서 Generator가 수정을 완료하면, THE Orchestrator SHALL 수정된 코드를 Evaluator에게 재전달하여 재검증을 요청한다.
6. THE Feedback_Loop SHALL 각 반복마다 Generator에게 새로운 클린 Agent_Session을 생성한다.

### 요구사항 9: IDE Hooks 마이그레이션

**사용자 스토리:** 개발자로서, 기존 `askAgent` 기반 hooks를 `runCommand` 기반 외부 스크립트 호출로 전환해야 한다.

*참조: [Claude Code Agent Teams Guide]*

#### 인수 조건

1. THE Harness SHALL 기존 코드 리뷰 훅의 `askAgent` 방식을 `runCommand` 기반 외부 검증 스크립트 호출로 대체한다.
2. THE Harness SHALL 기존 안전성 검증 훅의 `askAgent` 방식을 `runCommand` 기반 Pattern_Matcher 스크립트 호출로 대체한다.
3. THE Harness SHALL 기존 아키텍처 분석 훅의 `askAgent` 방식을 `runCommand` 기반 아키텍처 분석 스크립트 호출로 대체한다.
4. WHEN `runCommand` 스크립트가 실행되면, THE Harness SHALL 스크립트의 종료 코드(0: 성공, 1: 비차단 경고, 2: 차단)를 기반으로 결과를 판정한다.
5. THE Harness SHALL 기존 최종 검증 훅의 `tsc --noEmit` 검증을 Evaluator 에이전트의 검증 파이프라인에 통합한다.
6. THE Harness SHALL 동일 이벤트에 여러 훅이 실행될 때 Dispatcher 패턴을 적용한다.

### 요구사항 10: 에이전트 실행 스크립트 구현

**사용자 스토리:** 개발자로서, 각 에이전트를 독립 프로세스로 실행하는 스크립트가 필요하다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. THE Harness SHALL `scripts/agents/` 디렉토리에 각 에이전트별 실행 스크립트를 배치한다: `planner.mjs`, `generator.mjs`, `evaluator.mjs`, `guardian.mjs`.
2. WHEN 에이전트 스크립트가 실행되면, THE 스크립트 SHALL 입력 Handoff_File 경로를 명령줄 인자로 받는다.
3. THE 에이전트 스크립트 SHALL Claude API를 호출하여 독립 Agent_Session을 생성하고, 결과를 출력 Handoff_File로 기록한다.
4. THE 에이전트 스크립트 SHALL 실행 완료 시 종료 코드 0(성공), 1(비차단 경고), 2(차단/실패)를 반환한다.
5. THE Guardian 스크립트 SHALL Claude API 호출 없이 Pattern_Matcher 로직만으로 동작한다.
6. WHEN 처리되지 않은 예외가 발생하면, THE 스크립트 SHALL 에러 메시지를 stderr에 출력하고 종료 코드 2를 반환한다.
7. THE 에이전트 스크립트 SHALL 모든 파일 쓰기에 Atomic_Write 패턴을 적용한다.

### 요구사항 11: Sprint_Contract 스키마 정의

**사용자 스토리:** 개발자로서, 에이전트 간 합의 문서인 Sprint_Contract의 구조가 명확히 정의되어야 한다.

*참조: [Blake Crosley: Building AI-Powered Development Harnesses] / [Anthropic: Harness Design for Long-Running Application Development]*

#### 인수 조건

1. THE Sprint_Contract SHALL 다음 필수 필드를 포함하는 JSON 스키마를 따른다: `id`(UUID), `created_at`(ISO 8601), `goal`(문자열), `files`(파일 경로 배열), `acceptance_criteria`(조건 배열), `constraints`(제약 조건 배열), `impact_scope`(영향 범위 객체).
2. THE `acceptance_criteria` 배열 각 항목 SHALL 다음 필드를 포함한다: `id`(문자열), `description`(문자열), `verification_method`(tool_check 또는 manual_review), `test_command`(tool_check인 경우 실행할 명령).
3. THE `constraints` 배열 SHALL 프로젝트별 코드 작성 규칙을 포함한다.
4. THE Sprint_Contract SHALL 에이전트 디렉토리의 `contracts/` 하위에 `{timestamp}-{contract_id}.json` 형식으로 저장된다.
5. IF Sprint_Contract JSON이 스키마 검증에 실패하면, THEN THE Orchestrator SHALL Planner에게 재생성을 요청한다.
6. THE Sprint_Contract SHALL Evaluator가 코드 생성 전에 인수 조건을 검토하고 테스트 가능한 성공 기준을 협상하는 단계를 포함한다.

### 요구사항 12: Verdict 스키마 정의

**사용자 스토리:** 개발자로서, Evaluator의 검증 결과인 Verdict의 구조가 명확히 정의되어야 한다.

*참조: [Blake Crosley: Building AI-Powered Development Harnesses] / [Anthropic: Harness Design for Long-Running Application Development]*

#### 인수 조건

1. THE Verdict SHALL 다음 필수 필드를 포함한다: `id`(UUID), `contract_id`, `created_at`(ISO 8601), `overall_status`(pass, fail, warn), `criteria_results`(배열), `tool_outputs`(배열), `iteration`(정수).
2. THE `criteria_results` 각 항목 SHALL 포함한다: `criteria_id`, `status`(pass/fail), `message`, `code_location`(fail 시 필수), `suggestion`(fail 시 필수).
3. THE `tool_outputs` 각 항목 SHALL 포함한다: `tool_name`, `exit_code`, `stdout`, `stderr`, `duration_ms`.
4. WHEN `overall_status`가 fail이면, THE Verdict SHALL 최소 하나의 fail 항목에서 code_location과 suggestion을 포함한다.
5. THE Verdict SHALL 에이전트 디렉토리의 `verdicts/` 하위에 저장된다.

### 요구사항 13: Confidence_Trigger 기반 에스컬레이션

**사용자 스토리:** 개발자로서, 작업의 위험도와 복잡도에 따라 파이프라인 실행 여부를 자동으로 결정하는 메커니즘이 필요하다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. WHEN 사용자 요청을 수신하면, THE Orchestrator SHALL Confidence_Trigger 모듈을 실행하여 작업의 위험도를 평가한다.
2. THE Confidence_Trigger SHALL 4가지 차원으로 점수를 산출한다: 모호성(ambiguity), 도메인 복잡도(domain_complexity), 위험도(stakes), 컨텍스트 의존성(context_dependency). 각 차원은 0.0-1.0 범위이다.
3. THE Orchestrator SHALL Confidence_Trigger 동작 구간 정의 표에 따라 파이프라인 모드, Feedback_Loop 최대 횟수, UltraPlan 활성화 여부를 결정한다.
4. THE Confidence_Trigger SHALL 보안 관련 작업(인증, 권한, 데이터 처리)에 대해 자동으로 0.70 미만 점수를 부여하여 전체 파이프라인을 강제한다.

### 요구사항 14: 비용 및 토큰 관리

**사용자 스토리:** 개발자로서, 멀티 에이전트 파이프라인의 API 비용을 모니터링하고 제어할 수 있어야 한다.

*참조: [Anthropic: Harness Design for Long-Running Application Development]*

#### 인수 조건

1. THE Harness SHALL 각 Agent_Session의 입력/출력 토큰 수를 Handoff_File에 기록한다.
2. WHEN 파이프라인이 완료되면, THE Orchestrator SHALL 전체 파이프라인의 총 토큰 사용량과 예상 비용을 결과 요약에 포함한다.
3. THE Harness SHALL 파이프라인당 최대 토큰 예산을 설정할 수 있는 구성 파일을 지원한다.
4. IF 토큰 예산의 80%에 도달하면, THEN THE Orchestrator SHALL 경고를 로그에 기록한다.
5. IF 토큰 예산을 초과하면, THEN THE Orchestrator SHALL 현재 에이전트의 실행을 완료한 후 파이프라인을 중단하고 부분 결과를 기록한다.

### 요구사항 15: IDE 어댑터 패턴 (IDE Adapter Pattern)

**사용자 스토리:** 개발자로서, 하네스가 런타임에 현재 IDE 환경을 감지하고 IDE별로 다른 설정 파일 경로, 훅 포맷, 스티어링 구조를 자동으로 적용해야 한다.

*참조: [Claude Code Agent Teams Guide]*

#### 인수 조건

1. WHEN Harness가 초기화되면, THE IDE_Adapter SHALL 런타임 환경 변수 및 프로세스 정보를 분석하여 현재 IDE 환경(Kiro, Claude Code CLI, Claude Desktop, Antigravity, VS Code)을 감지한다.
2. THE IDE_Adapter SHALL IDE별 설정 파일 경로를 매핑한다: Kiro는 `.kiro/steering/*.md` 및 `.kiro/hooks/*.kiro.hook`, Claude Code는 `CLAUDE.md` 및 `.claude/hooks/` 및 `.claude/skills/`, Antigravity는 `.antigravity/` 디렉토리 구조, VS Code는 `.vscode/` 디렉토리 및 확장 설정.
3. WHEN 에이전트 스크립트가 훅을 등록하면, THE IDE_Adapter SHALL 현재 IDE에 맞는 훅 포맷으로 변환한다.
4. THE 에이전트 스크립트 SHALL IDE_Adapter를 통해서만 설정 파일에 접근하며, IDE별 경로를 직접 참조하지 않는다.
5. IF IDE 환경 감지에 실패하면, THEN THE IDE_Adapter SHALL 기본값으로 Kiro 환경을 사용하고 경고를 stderr에 출력한다.
6. THE IDE_Adapter SHALL IDE별 매핑 규칙을 구성 파일의 `ide_adapters` 섹션에서 로드하여, 새로운 IDE 지원 추가 시 코드 변경 없이 설정만으로 확장할 수 있다.
7. THE IDE_Adapter SHALL 감지 기준: Kiro는 `KIRO_IDE` 환경 변수 또는 `.kiro/` 존재, Claude Code CLI는 `CLAUDE_CODE` 환경 변수, Claude Desktop은 `CLAUDE_DESKTOP` 환경 변수, Antigravity는 `.antigravity/` 존재 또는 `ANTIGRAVITY` 환경 변수, VS Code는 `VSCODE_PID` 환경 변수 또는 `.vscode/` 존재.

### 요구사항 16: IDE 간 Sync 파이프라인

**사용자 스토리:** 개발자로서, 한 IDE에서 구현한 하네스 설정을 다른 IDE 형태로 자동 변환하는 sync 파이프라인이 필요하다.

*참조: [Claude Code Agent Teams Guide]*

#### 인수 조건

1. THE Sync_Pipeline SHALL Claude Code의 `CLAUDE.md`를 Kiro의 `.kiro/steering/*.md`로 변환한다.
2. THE Sync_Pipeline SHALL 훅 파일을 IDE별 포맷으로 변환한다.
3. THE Sync_Pipeline SHALL 스킬 파일을 스티어링 파일로 변환한다.
4. THE Sync_Pipeline SHALL 다방향 sync를 지원한다: Claude Code ↔ Kiro ↔ Antigravity ↔ VS Code.
5. THE Sync_Pipeline SHALL Antigravity(`.antigravity/`)와 VS Code(`.vscode/`, tasks.json, settings.json)와의 변환을 지원한다.
6. WHEN 충돌이 감지되면, THE Sync_Pipeline SHALL 충돌 파일 목록과 diff를 기록하고 사용자에게 수동 해결을 요청한다.
7. THE Sync_Pipeline SHALL 변환 매핑 규칙을 설정 파일에서 로드한다.
8. THE Sync_Pipeline SHALL `scripts/agents/sync.mjs` 스크립트로 실행되며, `--from` 및 `--to` 인자를 받는다.

### 요구사항 17: Git Worktree 기반 병렬 에이전트 실행

**사용자 스토리:** 개발자로서, 여러 Generator 에이전트가 동시에 다른 기능을 병렬로 개발할 수 있어야 한다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. WHEN 복수의 Sprint_Contract가 독립적이면(수정 대상 파일이 겹치지 않으면), THE Orchestrator SHALL 각 Generator에게 별도의 Git_Worktree를 할당하여 병렬 실행한다.
2. THE Harness SHALL `git worktree add` 명령으로 에이전트별 임시 브랜치와 작업 디렉토리를 생성한다.
3. WHEN 병렬 Generator가 모두 완료되면, THE Orchestrator SHALL 자동 게이트(tsc, eslint, 테스트)를 통과한 브랜치만 순차적으로 main에 머지한다.
4. IF 머지 시 충돌이 발생하면, THEN THE Orchestrator SHALL 충돌 내역을 Handoff_File에 기록하고 사용자에게 수동 해결을 요청한다.
5. WHEN 병렬 실행이 완료되면, THE Harness SHALL `git worktree remove`로 임시 작업 디렉토리를 정리한다.
6. THE Orchestrator SHALL 동일 파일을 수정하는 Sprint_Contract들은 병렬 실행하지 않고 순차 실행한다 (hotspot 충돌 방지).

### 요구사항 18: Auto-Dream 메모리 자동 정리

**사용자 스토리:** 개발자로서, 장기 프로젝트에서 에이전트 메모리 파일이 자동으로 정리되어야 한다.

*참조: [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. THE Harness SHALL Auto_Dream 서브 에이전트를 24시간 주기로 실행하여 에이전트 디렉토리의 메모리 파일을 정리한다.
2. THE Auto_Dream SHALL 중복된 Handoff_File 엔트리를 탐지하고 제거한다.
3. THE Auto_Dream SHALL 7일 이상 경과한 완료(completed) 상태의 Handoff_File을 `archive/` 디렉토리로 이동한다. 이는 요구사항 6의 불변 정책과 충돌하지 않는다 — 불변 정책은 활성 파이프라인 실행 중에만 적용되며, 파이프라인 완료 후 Auto_Dream에 의한 아카이브는 허용된다.
4. THE Auto_Dream SHALL 상대 날짜 참조를 절대 날짜(ISO 8601)로 변환한다.
5. WHEN Auto_Dream 실행이 완료되면, THE Harness SHALL 정리 결과 요약을 로그에 기록한다.
6. THE Auto_Dream SHALL 5회 이상의 Agent_Session이 누적된 후에만 실행된다.

### 요구사항 19: KAIROS 상시 감시 모드

**사용자 스토리:** 개발자로서, 백그라운드에서 상시 실행되며 코드 변경을 감시하고 자동으로 품질 제안을 생성하는 감시 에이전트가 필요하다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. THE KAIROS_Monitor SHALL 파일 시스템 감시(fs.watch)를 통해 소스 디렉토리의 코드 변경을 실시간으로 감지한다.
2. WHEN 코드 파일이 변경되면, THE KAIROS_Monitor SHALL 변경된 파일에 대해 경량 사전 감시(lint-level)를 실행한다. 이는 Evaluator의 전체 검증 파이프라인(full pipeline)과 범위가 분리된다: KAIROS는 단일 파일 수준의 빠른 피드백, Evaluator는 전체 프로젝트 수준의 종합 검증.
3. IF 분석 결과 문제가 발견되면, THEN THE KAIROS_Monitor SHALL 제안 사항을 에이전트 디렉토리의 `suggestions/` 하위에 기록한다.
4. THE KAIROS_Monitor SHALL CPU 사용률을 5% 이하로 유지하며, 디바운싱(500ms)을 적용한다.
5. THE KAIROS_Monitor SHALL `scripts/agents/kairos.mjs` 스크립트로 실행되며, 백그라운드 데몬 모드를 지원한다.
6. WHEN 사용자가 KAIROS_Monitor를 비활성화하면, THE Harness SHALL 감시를 즉시 중단하고 리소스를 해제한다.

### 요구사항 20: UltraPlan 계층적 태스크 분해

**사용자 스토리:** 개발자로서, 복잡한 작업을 자동으로 계층적 태스크 트리로 분해하는 고급 플래닝이 필요하다.

*참조: [Claude Code Agent Teams Guide] / [Anthropic: Harness Design for Long-Running Application Development]*

#### 인수 조건

1. WHEN Confidence_Trigger 점수가 0.50 미만이면 (Confidence_Trigger 동작 구간 정의 표 참조), THE Planner SHALL UltraPlan 전략을 활성화하여 계층적 태스크 트리를 생성한다. 0.50-0.69 구간에서는 전체 파이프라인이 실행되지만 UltraPlan은 비활성이며 단일 Sprint_Contract로 처리된다.
2. THE UltraPlan SHALL 최상위 목표를 하위 목표(sub-goals)로 분해하고, 각 하위 목표를 독립적인 Sprint_Contract로 변환한다.
3. THE UltraPlan SHALL 하위 목표 간 의존성 그래프를 생성하여, 독립적인 목표는 병렬 실행(Git_Worktree)하고 의존적인 목표는 순차 실행한다.
4. THE UltraPlan SHALL 최대 3단계 깊이까지 분해하며, 각 리프 태스크는 단일 Sprint_Contract로 실행 가능한 크기여야 한다.
5. WHEN UltraPlan이 완료되면, THE Planner SHALL 태스크 트리와 의존성 그래프를 에이전트 디렉토리의 `plans/` 하위에 JSON 형식으로 저장한다.

### 요구사항 21: Spec-Driven Development (SDD) 통합

**사용자 스토리:** 개발자로서, 하네스가 IDE의 spec 시스템과 통합되어 스펙 기반 개발을 자동화해야 한다.

*참조: [Blake Crosley: Building AI-Powered Development Harnesses] / [Anthropic: Harness Design for Long-Running Application Development]*

#### 인수 조건

1. WHEN 프로젝트에 requirements.md와 design.md가 존재하면, THE Planner SHALL 해당 스펙 문서를 입력으로 사용하여 Sprint_Contract를 생성한다.
2. THE Evaluator SHALL 스펙 문서의 인수 조건을 자동으로 추출하여 Verdict의 검증 기준으로 사용한다.
3. WHEN Generator가 코드를 생성하면, THE Evaluator SHALL 생성된 코드가 스펙의 요구사항을 충족하는지 자동 검증한다.
4. IF 스펙과 구현 간 드리프트(drift)가 감지되면, THEN THE Evaluator SHALL 드리프트 항목을 Verdict에 기록하고 Generator에게 수정을 요청한다.
5. THE Harness SHALL tasks.md의 태스크 목록을 Sprint_Contract의 소스로 사용할 수 있다.

### 요구사항 22: Agent Team 협업 패턴

**사용자 스토리:** 개발자로서, 여러 전문화된 에이전트가 팀으로 협업하여 복잡한 작업을 처리할 수 있어야 한다.

*참조: [Claude Code Agent Teams Guide]*

#### 인수 조건

1. THE Harness SHALL Coordinator를 Orchestrator의 서브 모듈로 지원한다. Coordinator는 Agent_Team 모드에서만 활성화되어 Specialist 에이전트들의 작업을 분배하고 결과를 통합한다.
2. THE Agent_Team SHALL 프로젝트 도메인에 맞는 전문화된 역할을 가진 에이전트로 구성될 수 있다 (예: Frontend, Backend, DB, K8s Specialist 등).
3. WHEN Agent_Team이 활성화되면, THE Coordinator SHALL 각 Specialist에게 해당 도메인의 Sprint_Contract를 분배한다.
4. THE Agent_Team의 각 Specialist SHALL 독립된 Agent_Session과 Git_Worktree에서 실행된다. 각 Specialist는 개별 Evaluator 검증을 거치고, 통합 후 전체 Evaluator 검증을 추가로 수행한다.
5. WHEN 모든 Specialist가 완료되면, THE Coordinator SHALL 결과를 통합하고 Evaluator에게 전체 검증을 요청한다.
6. THE Harness SHALL Agent_Team 구성을 구성 파일의 `team` 섹션에서 정의할 수 있다.

### 요구사항 23: Harness Subtraction (하네스 최적화)

**사용자 스토리:** 개발자로서, 모델 성능 향상에 따라 하네스에서 불필요한 스캐폴딩을 주기적으로 제거할 수 있어야 한다.

*참조: [Anthropic: Harness Design for Long-Running Application Development] / [Blake Crosley: Building AI-Powered Development Harnesses]*

#### 인수 조건

1. THE Harness SHALL 각 에이전트 컴포넌트의 기여도를 측정하는 메트릭을 수집한다: Evaluator의 fail 발견 횟수, Guardian의 차단 횟수, Planner의 Sprint_Contract 수정 횟수.
2. WHEN 특정 컴포넌트의 기여도가 30일간 0이면, THE Harness SHALL 해당 컴포넌트의 비활성화를 제안한다.
3. THE Harness SHALL 에이전트 디렉토리의 `metrics/` 하위에 일별 메트릭을 JSON 형식으로 기록한다.
4. THE Harness SHALL 새 모델 버전이 감지되면, 모든 컴포넌트의 기여도 메트릭을 리셋하고 재평가 기간(14일)을 시작한다.
5. THE Harness SHALL 비활성화된 컴포넌트를 즉시 재활성화할 수 있는 설정을 지원한다.
6. WHEN Harness_Subtraction 분석이 완료되면, THE Harness SHALL 최적화 제안 보고서를 에이전트 디렉토리의 `reports/` 하위에 생성한다.

### 요구사항 24: 에이전트 루프 4단계 구현

**사용자 스토리:** 개발자로서, 에이전트의 실행 주기가 Gather Context → Take Action → Verify Work → Repeat의 4단계로 명확하게 구분되어야 한다. 이를 통해 각 단계의 책임이 분리되고 검증이 자동화된다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slide 41]*

#### 인수 조건

1. THE Harness SHALL 에이전트 루프를 4단계로 구현한다: (1) Gather Context — 작업 컨텍스트 수집, (2) Take Action — 계획에 따른 실행, (3) Verify Work — 결과 검증, (4) Repeat — 미완료 항목 반복.
2. THE Gather_Context 단계 SHALL Sprint_Contract, 파일 구조, 이전 Verdict를 수집하며, 현재 step과 무관한 정보는 포함하지 않는다.
3. THE Take_Action 단계 SHALL Sprint_Contract의 단일 step만 실행하고, 다음 step으로 진행하기 전에 Verify_Work를 수행한다.
4. THE Verify_Work 단계 SHALL 실행된 action의 인수 조건 각 항목을 검증하고, fail이 없을 때만 Repeat 단계로 진행한다.
5. WHEN Repeat 단계에서 미완료 항목이 없으면, THE Harness SHALL 루프를 종료하고 최종 Verdict를 생성한다.
6. THE Harness SHALL 각 루프 반복 시 Context_Reset 전략을 적용하여 Context_Rot를 방지한다.

### 요구사항 25: 하네스 6대 구성요소 구현

**사용자 스토리:** 개발자로서, 하네스가 6대 핵심 구성요소를 모두 포함하여 완전한 에이전트 실행 환경을 제공해야 한다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slide 40]*

#### 인수 조건

1. THE Harness SHALL 컨텍스트 엔지니어링(Context Engineering) 구성요소를 포함한다: CLAUDE.md/스티어링 파일로 에이전트 행동 방향을 설정하고, 컨텍스트 윈도우 품질을 관리한다.
2. THE Harness SHALL 도구 오케스트레이션(Tool Orchestration) 구성요소를 포함한다: MCP, Bash, 파일 I/O 도구의 실행 순서와 권한을 관리한다.
3. THE Harness SHALL 상태 및 메모리(State & Memory) 구성요소를 포함한다: 세션 간 영속 상태(Sprint_Contract, Verdict 파일)와 Auto_Dream 기반 메모리 정리를 관리한다.
4. THE Harness SHALL 검증 루프(Verification Loop) 구성요소를 포함한다: Evaluator가 Generator 출력을 독립 검증하는 Feedback_Loop를 구현한다.
5. THE Harness SHALL 오류 복구(Error Recovery) 구성요소를 포함한다: 실패한 step만 재시도하고, 최대 5회 재시도 후 실패를 상위에 보고한다.
6. THE Harness SHALL 인간 개입 제어(Human-in-the-Loop Control) 구성요소를 포함한다: Confidence_Trigger 기반으로 자동화 수준을 조절하고, 임계값 미만 시 사용자 승인을 요청한다.

### 요구사항 26: Context Engineering — 실패 모드 방지

**사용자 스토리:** 개발자로서, 에이전트 컨텍스트의 4가지 실패 모드(Poisoning, Distraction, Confusion, Clash)를 사전에 방지하는 메커니즘이 필요하다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slide 58] / [Drew Breunig: Context Failure Modes]*

#### 인수 조건

1. THE Harness SHALL Poisoning(오염) 방지를 위해, 악의적이거나 잘못된 정보가 컨텍스트에 주입되지 않도록 Guardian이 입력 소스를 검증한다.
2. THE Harness SHALL Distraction(분산) 방지를 위해, 에이전트에게 전달되는 컨텍스트에서 현재 step과 무관한 정보를 제거한다. Executor/Reviewer는 전체 Sprint_Contract가 아닌 해당 step 정보만 수신한다.
3. THE Harness SHALL Confusion(혼동) 방지를 위해, 상충되는 지시사항이 동일 컨텍스트에 공존하지 않도록 CLAUDE.md와 step별 constraints를 계층적으로 관리한다.
4. THE Harness SHALL Clash(충돌) 방지를 위해, 두 에이전트가 동일 파일을 동시에 수정하지 않도록 Orchestrator가 파일 잠금(file lock)을 관리한다.
5. THE Harness SHALL Context_Failure_Mode 탐지 시 해당 실패 유형을 Verdict에 기록하고, 다음 iteration에서 회피 전략을 적용한다.

### 요구사항 27: Context Rot 방지

**사용자 스토리:** 개발자로서, 장기 실행 세션에서 컨텍스트 누적으로 인한 성능 저하(Context Rot)를 방지해야 한다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slide 59]*

#### 인수 조건

1. THE Harness SHALL 에이전트 컨텍스트 토큰이 50,000을 초과하면 Context_Reset을 트리거한다.
2. WHEN Context_Reset이 트리거되면, THE Harness SHALL 현재 세션을 종료하고 파일시스템 상태에서 클린 컨텍스트로 새 세션을 시작한다.
3. THE Harness SHALL 각 Agent_Session에 현재 step에 필요한 컨텍스트만 포함하며, 완료된 step의 대화 이력은 포함하지 않는다.
4. THE Evaluator SHALL 에이전트 응답에서 현재 task와 무관한 정보가 추가되거나, 이전에 완료한 작업을 반복하는 징후를 탐지하면 Context_Rot 경고를 Verdict에 기록한다.
5. THE Harness SHALL step별 독립 Agent_Session 실행을 기본 정책으로 한다 (세션 간 컨텍스트 공유 금지).

### 요구사항 28: 에이전트 실패 패턴 방지

**사용자 스토리:** 개발자로서, 에이전트 운영에서 반복되는 5가지 실패 패턴을 사전에 방지하는 가드레일이 필요하다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slide 60]*

#### 인수 조건

1. THE Harness SHALL 컨텍스트 과부하 방지를 위해, step별 컨텍스트를 최소화하고 Context_Reset 임계값(50k 토큰)을 적용한다.
2. THE Harness SHALL 불명확한 요구사항 방지를 위해, Sprint_Contract 생성 시 Planner가 인수 조건을 측정 가능한 형태로 구체화하도록 강제한다. 모호한 acceptance_criteria는 Orchestrator가 재생성을 요청한다.
3. THE Harness SHALL 검증 없는 자동수락 방지를 위해, Generator의 모든 출력은 반드시 Evaluator 검증을 거쳐야 한다. Evaluator 없이 결과를 승인하는 경로는 존재하지 않는다.
4. THE Harness SHALL 긴 세션 드리프트(drift) 방지를 위해, 각 step은 새로운 Agent_Session으로 실행되며, step 간 누적 컨텍스트를 상속하지 않는다.
5. THE Harness SHALL 권한 과다 방지를 위해, Guardian이 에이전트 도구 사용 권한을 step 단위로 제한하고, 필요한 도구만 컨텍스트에 포함한다.

### 요구사항 29: Right Altitude 원칙 적용

**사용자 스토리:** 개발자로서, 에이전트에 대한 지시가 세부 구현 대신 원칙과 이유 중심으로 작성되어 에이전트의 자율적 판단을 유도해야 한다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slide 42]*

#### 인수 조건

1. THE Harness SHALL Sprint_Contract의 acceptance_criteria를 Right_Altitude 원칙에 따라 작성한다: "원칙 1줄 + 이유 1줄 + 예시 1-2개" 형식을 따른다.
2. THE Sprint_Contract SHALL 구체적인 코드 구현 방법을 명시하지 않고, 달성해야 할 결과(what)와 이유(why)를 명시한다.
3. THE Planner SHALL 과도하게 세부적인 구현 지시(how)를 포함한 Sprint_Contract를 생성하지 않는다. Evaluator가 이를 감지하면 Planner에게 재작성을 요청한다.
4. THE Harness SHALL CLAUDE.md와 스티어링 파일에 Right_Altitude 원칙을 적용하여, 에이전트 행동 규칙을 "원칙 + 이유" 형식으로 작성한다.

### 요구사항 30: Plan-Critic-Build 패턴 구현

**사용자 스토리:** 개발자로서, 계획(Plan) → 비평(Critic) → 구현(Build) 순서로 진행하는 워크플로우를 통해 구현 전 오류를 조기 발견해야 한다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slide 52]*

#### 인수 조건

1. THE Harness SHALL Plan_Critic_Build 패턴을 지원한다: (1) Planner가 Sprint_Contract 생성, (2) 독립 Critic 에이전트가 Sprint_Contract를 비평하고 개선 제안 생성, (3) Planner가 비평을 반영하여 Sprint_Contract 수정, (4) Generator가 최종 Sprint_Contract로 구현.
2. THE Critic 에이전트 SHALL Sprint_Contract의 다음 항목을 검토한다: 인수 조건의 측정 가능성, 제약 조건의 완전성, step 간 의존성 정확성, 누락된 edge case.
3. WHEN Critic이 생성한 개선 제안이 3개 이상이면, THE Orchestrator SHALL Planner에게 Sprint_Contract 수정을 요청한다.
4. THE Critic 에이전트 SHALL Planner와 Generator의 컨텍스트를 공유하지 않는 독립 Agent_Session으로 실행된다.
5. THE Plan_Critic_Build 패턴 SHALL Confidence_Trigger 점수 0.70 미만일 때 자동으로 활성화된다.

### 요구사항 31: Ralph Loop 방지

**사용자 스토리:** 개발자로서, 에이전트가 PROMPT.md 또는 지시 파일을 순환 참조하여 무한 루프에 빠지는 Ralph_Loop 안티패턴을 방지해야 한다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slide 53]*

#### 인수 조건

1. THE Harness SHALL 모든 에이전트 지시 파일(CLAUDE.md, 스티어링 파일, Sprint_Contract)에 명시적인 종료 조건(exit condition)을 포함한다.
2. THE Guardian SHALL 에이전트가 동일 파일을 3회 이상 연속으로 읽는 패턴을 감지하면 Ralph_Loop 경고를 발생시키고 실행을 중단한다.
3. THE Harness SHALL 에이전트 루프 내에서 반복 횟수를 카운트하고, 최대 횟수(기본 5회) 초과 시 강제 종료한다.
4. WHEN Ralph_Loop가 감지되면, THE Harness SHALL 마지막 성공한 Verdict 이전 상태로 롤백하고 Orchestrator에 보고한다.
5. THE Sprint_Contract SHALL 재귀적 self-reference를 허용하지 않는다: 하나의 step이 자신을 의존성으로 포함할 수 없다.

### 요구사항 32: CLAUDE.md 운영 원칙 준수

**사용자 스토리:** 개발자로서, CLAUDE.md(및 동등한 스티어링 파일)가 효과적으로 유지 관리되어 에이전트 행동을 일관되게 제어할 수 있어야 한다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slides 44-46]*

#### 인수 조건

1. THE CLAUDE.md SHALL 60줄 이하로 유지하며, 초과 시 Harness가 경고를 발생시킨다.
2. THE Harness SHALL CLAUDE.md를 모듈화하여 관리한다: 핵심 규칙은 CLAUDE.md에, 상세 내용은 `@파일명`으로 참조하는 별도 파일로 분리한다.
3. THE Harness SHALL 새로운 규칙을 CLAUDE.md에 추가하기 전에 "이 규칙이 없으면 에이전트가 잘못된 행동을 하는가?"를 검증한다. 불필요한 규칙 추가를 방지한다.
4. THE Harness SHALL 정기적으로 CLAUDE.md의 각 규칙에 대해 "한 줄 삭제 테스트(one-line deletion test)"를 수행한다: 규칙을 삭제해도 에이전트 행동이 변하지 않으면 제거한다.
5. THE CLAUDE.md SHALL 에이전트가 해서는 안 되는 행동(금지 규칙)과 반드시 해야 하는 행동(강제 규칙)을 명확히 구분한다.
6. THE Harness SHALL CLAUDE.md의 버전을 git 이력으로 관리하며, 규칙 변경 시 변경 이유를 커밋 메시지에 기록한다.

### 요구사항 33: 멀티 에이전트 패턴 선택 기준

**사용자 스토리:** 개발자로서, 작업 특성에 맞는 멀티 에이전트 패턴(Sub-Agent, Orchestrator, Parallel, GAN-Style, Agent Teams)을 명확한 기준으로 선택할 수 있어야 한다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slide 64]*

#### 인수 조건

1. THE Harness SHALL 다음 5가지 멀티 에이전트 패턴을 지원한다: **Sub-Agent** — 오케스트레이터가 전문화된 서브 에이전트에게 작업을 위임; **Orchestrator** — 중앙 조율자가 전체 워크플로우를 관리; **Parallel** — 독립적인 작업을 동시에 병렬 실행(Git_Worktree 기반); **GAN-Style** — Generator-Evaluator 적대적 검증 패턴; **Agent Teams** — 전문화된 에이전트들이 팀으로 협업.
2. THE Orchestrator SHALL 작업 특성에 따라 패턴을 선택한다: 단일 독립 작업 → Sub-Agent, 의존성 있는 복수 작업 → Orchestrator, 독립 복수 작업 → Parallel, 품질 검증 필수 → GAN-Style, 대규모 복잡 작업 → Agent Teams.
3. THE Harness SHALL 동일 파이프라인에서 복수 패턴을 혼합할 수 있다 (예: Orchestrator + Parallel + GAN-Style 조합).
4. WHEN 패턴 선택 시, THE Orchestrator SHALL 선택 이유를 `.pipeline/` 로그에 기록한다.

### 요구사항 34: 하네스 신뢰성 수학 기반 설계

**사용자 스토리:** 개발자로서, 멀티 에이전트 파이프라인에서 각 step의 성공률이 전체 파이프라인 신뢰성에 미치는 영향을 정량적으로 관리해야 한다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slide 57]*

#### 인수 조건

1. THE Harness SHALL 각 에이전트 step의 성공률을 측정하고 기록한다.
2. THE Harness SHALL 복합 파이프라인의 전체 성공률을 계산한다: 전체 성공률 = 각 step 성공률의 곱. 예: step 성공률 0.95, 20 steps → 0.95^20 ≈ 0.358.
3. WHEN 전체 파이프라인 성공률이 0.80 미만으로 예측되면, THE Orchestrator SHALL 파이프라인 단계 수를 줄이거나 step 신뢰성을 높이는 방안을 제안한다.
4. THE Harness SHALL step 신뢰성 향상 전략을 우선 적용한다: 검증 루프 추가, step 세분화, Context_Reset 적용.
5. THE Harness SHALL 30일 rolling window로 각 에이전트 step의 성공률 추이를 `metrics/` 디렉토리에 기록한다.

### 요구사항 35: SDD + TDD 조합 방법론

**사용자 스토리:** 개발자로서, Spec-Driven Development(SDD)와 Test-Driven Development(TDD)를 조합하여 요구사항 정의부터 구현, 검증까지의 전 과정을 자동화해야 한다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slides 27-33]*

#### 인수 조건

1. THE Harness SHALL SDD + TDD 조합 워크플로우를 지원한다: (1) 요구사항 스펙 작성 → (2) 스펙 기반 테스트 케이스 생성 → (3) 테스트 실패 확인 → (4) 스펙 기반 코드 생성 → (5) 테스트 통과 확인 → (6) 리팩토링.
2. THE Planner SHALL requirements.md에서 인수 조건을 추출하여 테스트 케이스 목록을 Sprint_Contract에 포함한다.
3. THE Generator SHALL Sprint_Contract의 테스트 케이스를 먼저 작성(TDD)하고, 테스트를 통과하는 코드를 구현한다.
4. THE Evaluator SHALL 테스트 실행 결과를 Verdict의 `tool_outputs`에 포함하며, 모든 테스트 통과 여부를 acceptance_criteria에서 검증한다.
5. THE Harness SHALL 스펙 문서(requirements.md, design.md)와 구현 코드 간 드리프트를 주기적으로 감지하고 보고한다 (요구사항 21 확장).
6. IF 테스트 커버리지가 Sprint_Contract에 명시된 최소 커버리지 이하이면, THEN THE Evaluator SHALL fail Verdict를 생성한다.

### 요구사항 36: 에이전트 엔지니어링 진화 단계 적용

**사용자 스토리:** 개발자로서, 프로젝트의 에이전트 성숙도에 따라 Prompt Engineering → Context Engineering → Harness Engineering으로 단계적으로 진화하는 로드맵을 갖춰야 한다.

*참조: [김영동 (NKIA AI팀): 클로드코드 잘 사용하기, 2026-04-07 전사 세미나, Slides 36-37]*

#### 인수 조건

1. THE Harness SHALL 프로젝트의 현재 에이전트 엔지니어링 성숙도를 3단계로 평가한다: 1단계(Prompt Engineering) — 단일 에이전트, 수동 프롬프트 작성; 2단계(Context Engineering) — 컨텍스트 설계, CLAUDE.md 운영; 3단계(Harness Engineering) — 멀티 에이전트 파이프라인, 자동 검증.
2. THE Harness SHALL 1단계에서 2단계로 진화하기 위한 기준을 제공한다: CLAUDE.md 운영, 메모리 파일 관리, Context_Reset 전략 적용.
3. THE Harness SHALL 2단계에서 3단계로 진화하기 위한 기준을 제공한다: 멀티 에이전트 파이프라인 구축, GAN-Style 검증 루프, Confidence_Trigger 기반 자동 에스컬레이션.
4. THE Harness SHALL 현재 성숙도 단계를 `metrics/maturity.json`에 기록하고, 다음 단계로의 전환 조건을 모니터링한다.

---

## 충돌 해결 기록

본 문서는 다음 충돌을 식별하고 해결하였다:

| # | 충돌 | 관련 요구사항 | 해결 |
|---|------|-------------|------|
| 1 | Orchestrator vs Coordinator 역할 중복 | 1 ↔ 22 | Coordinator를 Orchestrator의 서브 모듈로 정의. Agent_Team 모드에서만 활성화 |
| 2 | Feedback_Loop 최대 횟수 불일치 | 8 ↔ 13 | 기본 5회, Confidence_Trigger에 의해 조정 가능. 동작 구간 정의 표로 명확화 |
| 3 | 파일 경로 하드코딩 vs IDE_Adapter | 6 ↔ 15 | 모든 경로를 IDE_Adapter가 반환하는 에이전트 디렉토리로 추상화 |
| 4 | KAIROS vs Evaluator 역할 중복 | 4 ↔ 19 | KAIROS는 경량 사전 감시(lint-level, 단일 파일), Evaluator는 전체 검증(full pipeline, 프로젝트 범위)으로 분리 |
| 5 | Auto_Dream 삭제 vs 불변 정책 | 6 ↔ 18 | 불변 정책을 활성 파이프라인 실행 중으로 한정. 완료 후 Auto_Dream 아카이브 허용 |
| 6 | UltraPlan vs Confidence_Trigger 임계값 | 13 ↔ 20 | 동작 구간 정의 표로 0.50-0.69(전체 파이프라인, UltraPlan 비활성)과 0.50 미만(UltraPlan 활성) 명확 분리 |
| 7 | Git_Worktree에서 Evaluator 실행 위치 | 4 ↔ 17 | Evaluator는 각 worktree의 코드를 main 기준으로 검증 (요구사항 4 AC9) |
| 8 | Agent_Team Specialist의 Feedback_Loop | 8 ↔ 22 | 각 Specialist는 개별 Evaluator 검증 후, 통합 시 전체 Evaluator 검증 추가 수행 (요구사항 22 AC4) |

---

*문서 버전: v1.1 | 최초 작성: 2026-04-13 | 갱신: 2026-04-18 | 36개 요구사항(+13 from NKIA 세미나), 8개 충돌 해결*
