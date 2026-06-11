# AHE 하네스 엔지니어링 원칙 (SI 집행계획서)

> 이 문서는 본 프로젝트의 모든 하네스 변경 판단 기준이다.
> 출처: Anthropic 공식 블로그 + AHE 논문 arXiv:2604.25850

---

## 0. 출처
- Anthropic — *Harness design for long-running application development*
- Anthropic — *Scaling Managed Agents: Decoupling the brain from the hands*
- *Agentic Harness Engineering* — arXiv:2604.25850

## 1. 핵심 원칙
1. **constrain / inform / verify / correct / human-in-loop**
2. **생성자 ≠ 판정자** — Executor와 Reviewer는 정보 장벽으로 분리
3. **명시적·채점 가능 기준** — 1원 정밀도, 선언적 verifier_rules.json
4. **작업 분해 + 구조화된 핸드오프** — Sprint_Contract JSON으로 세션 간 전달

## 2. 확증편향 방지
- Reviewer는 Executor의 reasoning/notes를 받지 않음 (inputs_used만)
- AI 의미 검증은 독립 Agent_Session에서 수행

## 3. stale 가정 제거
- 하네스 컴포넌트 추가 전: "현 모델(Opus 4.8)에서 still load-bearing인가?"
- 약한 모델용 보상 장치는 stress test 후 비-load-bearing이면 제거
- 단, 결정적 정확성(셀 매핑, 수식 규칙)은 모델이 잘해도 하네스에 고정

## 4. falsifiable-contract
- 모든 하네스 변경은 `change_manifest.jsonl`에 기록
- 필드: evidence, root_cause, fix, predicted_fixes, regression_risk, verification
- 다음 실행에서 verified/refuted 판정

## 5. AHE 3기둥
- **컴포넌트 관찰성**: `harness/*.json` (cell_map, verifier_rules, long_term_memory)
- **경험 관찰성**: `long_term_memory.json:runs[]` + 구조화된 실행 리포트
- **결정 관찰성**: `change_manifest.jsonl`

## 6. 브레인/핸드 분리
- **Brain**: Planner(추출), Reviewer(AI 의미검증) — 에이전트 세션
- **Hands**: Executor(셀 입력), 시트 라이터 — 결정적 Python 코드

---

## 적용 체크리스트 (모든 하네스 변경 전)
- [ ] 이 변경이 현 모델 기준 load-bearing인가?
- [ ] 생성과 판정이 분리돼 있는가?
- [ ] `change_manifest.jsonl`에 falsifiable-contract를 기록했는가?
- [ ] 하네스 JSON으로 표현 가능한가? (불가피한 경우만 Python)
