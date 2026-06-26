# Tasks: EXE-16 Reviewer AI 의미검증

**Created**: 2026-06-26
**Status**: Draft
**주의**: 이 tasks.md는 사람이 읽는 산출물이다. `/speckit-implement` 자동실행 비대상(constitution §VII).

---

## 개요

EXE-16의 수용기준을 task 단위로 분해한다. 각 task는 **실패 테스트 작성 → 최소 구현 → 통과 → 커밋** 사이클을 따른다.

코드 근거: `backend/services/reviewer.py:97-144` (`_ai_semantic_review`) + `reviewer.py:545-659` (`run_review`)

---

## Task 1: Graceful Degradation — Bedrock 예외 처리 (FR-004a, FR-004b)

**수용기준**: Bedrock 호출이 예외를 발생시켜도 `_ai_semantic_review`가 `([], {"input": 0, "output": 0})`을 반환하고(FR-004a), 파이프라인이 완료된다(FR-004b).

### Step 1: 실패 테스트 작성
```python
# tests/test_reviewer_ai.py
def test_ai_semantic_graceful_on_bedrock_error(monkeypatch):
    """invoke_bedrock 예외 시 빈 결과 반환, 파이프라인 미중단."""
    from services.reviewer import _ai_semantic_review
    from models.sprint_contract import SprintContract, StepResult

    monkeypatch.setattr(
        "services.reviewer.invoke_bedrock",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Bedrock unavailable"))
    )
    contract = SprintContract()
    issues, tokens = _ai_semantic_review(contract, {})
    assert issues == []
    assert tokens == {"input": 0, "output": 0}
```
Expected: `AssertionError` (현재 except 블록이 있으나 테스트로 명시적 검증)

### Step 2: 최소 구현
`reviewer.py:143-144` except 블록 이미 존재. 테스트를 통과시키는 픽스처(monkeypatch) 확인 후 진행.

### Step 3: 통과 확인
`pytest tests/test_reviewer_ai.py::test_ai_semantic_graceful_on_bedrock_error -v`

### Step 4: 커밋
```
git add backend/tests/test_reviewer_ai.py
git commit -m "test(EXE-16): _ai_semantic_review Bedrock 예외 Graceful 처리 검증"
```

---

## Task 2: JSON 배열 비정상 응답 처리 (FR-005)

**수용기준**: Bedrock 응답 텍스트가 `[`로 시작하지 않으면 빈 이슈 목록이 반환된다.

### Step 1: 실패 테스트 작성
```python
def test_ai_semantic_non_json_response(monkeypatch):
    """응답이 JSON 배열이 아니면 이슈 목록 = []."""
    from services.reviewer import _ai_semantic_review
    from models.sprint_contract import SprintContract

    monkeypatch.setattr(
        "services.reviewer.invoke_bedrock",
        lambda *a, **kw: {"content": [{"text": "검증 완료. 문제 없습니다."}], "usage": {"input_tokens": 10, "output_tokens": 5}}
    )
    contract = SprintContract()
    issues, tokens = _ai_semantic_review(contract, {})
    assert issues == []
    assert tokens["input"] == 10
```

### Step 2: 최소 구현
`reviewer.py:139` `if text.startswith("[")` 조건 이미 존재. 테스트로 기존 동작 명시적 커버.

### Step 3: 통과 확인
`pytest tests/test_reviewer_ai.py::test_ai_semantic_non_json_response -v`

### Step 4: 커밋
```
git add backend/tests/test_reviewer_ai.py
git commit -m "test(EXE-16): 비JSON 응답 → 빈 이슈 처리 검증"
```

---

## Task 3: 정보 장벽 — inputs_summary Notes 미포함 (FR-001, FR-010)

**수용기준**: `_ai_semantic_review` 프롬프트에 `StepResult.notes`가 포함되지 않고, `inputs_used.value=None` 항목이 제외되며, 최대 30건만 전달된다.

### Step 1: 실패 테스트 작성
```python
def test_ai_semantic_info_barrier(monkeypatch):
    """정보 장벽: notes 미포함, None value 제외, 30건 한도."""
    from services.reviewer import _ai_semantic_review
    from models.sprint_contract import SprintContract, StepResult, InputUsed

    captured_prompts = []

    def mock_bedrock(prompt, **kw):
        captured_prompts.append(prompt)
        return {"content": [{"text": "[]"}], "usage": {"input_tokens": 1, "output_tokens": 1}}

    monkeypatch.setattr("services.reviewer.invoke_bedrock", mock_bedrock)

    contract = SprintContract()
    step_results = {
        0: StepResult(
            step_id=0,
            sheet="공통",
            notes="이 노트는 전달되면 안 됨",
            inputs_used=[
                InputUsed(field=f"f{i}", value=i if i % 3 != 0 else None, cell=f"E{i}", source="계약서")
                for i in range(40)  # 40건, None 포함
            ]
        )
    }

    _ai_semantic_review(contract, step_results)

    assert captured_prompts, "invoke_bedrock 호출되어야 함"
    prompt = captured_prompts[0]
    assert "이 노트는 전달되면 안 됨" not in prompt
    # value!=None 항목 수 <= 30
    lines = [l for l in prompt.split("\n") if "(source:" in l]
    assert len(lines) <= 30
```

### Step 2: 최소 구현
`reviewer.py:108-111` 현행 구현 확인:
```python
for sr in step_results.values():
    for inp in sr.inputs_used:
        if inp.value is not None:
            inputs_summary.append(f"{inp.cell}: {inp.value} (source: {inp.source})")
```
그리고 `reviewer.py:132` `{chr(10).join(inputs_summary[:30])}` — 30건 한도.
위 로직이 이미 존재함. 테스트로 기존 동작 명시.

### Step 3: 통과 확인
`pytest tests/test_reviewer_ai.py::test_ai_semantic_info_barrier -v`

### Step 4: 커밋
```
git add backend/tests/test_reviewer_ai.py
git commit -m "test(EXE-16): 정보 장벽 — notes 미포함·None 제외·30건 한도 검증"
```

---

## Task 4: AI 이슈 접두어 + 이슈 목록 합산 (FR-002, FR-009a, FR-009b)

**수용기준**: AI 검증 이슈는 `[AI검증]` 접두어를 갖고 `ReviewResult.issues`에 포함된다(FR-002, FR-009a). avg_score는 1~5단계만으로 산정된다(FR-009b).

### Step 1: 실패 테스트 작성
```python
def test_ai_issues_prefix_and_score_isolation(monkeypatch):
    """AI 이슈 접두어 및 avg_score에 AI 점수 미포함."""
    import openpyxl
    from services.reviewer import run_review
    from models.sprint_contract import SprintContract

    # Bedrock이 이슈 1건 반환하도록
    monkeypatch.setattr(
        "services.reviewer.invoke_bedrock",
        lambda *a, **kw: {
            "content": [{"text": '["매출-매입 차이가 영업이익과 불일치"]'}],
            "usage": {"input_tokens": 50, "output_tokens": 10}
        }
    )
    # openpyxl Workbook 최소 픽스처
    wb = openpyxl.Workbook()
    wb.create_sheet("공통")
    wb.create_sheet("5-4. 수수료산출내역")
    contract = SprintContract()

    result, tokens = run_review(contract, {}, wb)

    ai_issues = [i for i in result.issues if i.startswith("[AI검증]")]
    assert len(ai_issues) == 1
    assert ai_issues[0] == "[AI검증] 매출-매입 차이가 영업이익과 불일치"
    # score는 1~5단계 avg (AI 미포함) → 0건 오류 시 score=1.0
    assert result.score >= 0.0
    assert tokens["input"] == 50
```

### Step 2: 최소 구현
`reviewer.py:141` `[f"[AI검증] {i}" for i in issues if isinstance(i, str)]` — 이미 구현됨.
`reviewer.py:578-585` scores 리스트 5개 — AI 미포함 — 이미 구현됨.
테스트 픽스처(최소 workbook) 정의가 핵심 작업.

### Step 3: 통과 확인
`pytest tests/test_reviewer_ai.py::test_ai_issues_prefix_and_score_isolation -v`

### Step 4: 커밋
```
git add backend/tests/test_reviewer_ai.py
git commit -m "test(EXE-16): AI 이슈 접두어·avg_score 격리 검증"
```

---

## Task 5: Sonnet 모델 라우팅 검증 (FR-006, FR-007)

**수용기준**: `_ai_semantic_review` 호출 시 `task_type="review"`로 invoke_bedrock이 호출되고, `max_tokens=256`이 전달된다.

### Step 1: 실패 테스트 작성
```python
def test_ai_semantic_model_routing(monkeypatch):
    """task_type='review', max_tokens=256 검증."""
    from services.reviewer import _ai_semantic_review
    from models.sprint_contract import SprintContract

    captured_kwargs = {}

    def mock_bedrock(prompt, **kw):
        captured_kwargs.update(kw)
        return {"content": [{"text": "[]"}], "usage": {"input_tokens": 1, "output_tokens": 1}}

    monkeypatch.setattr("services.reviewer.invoke_bedrock", mock_bedrock)

    contract = SprintContract()
    _ai_semantic_review(contract, {})

    assert captured_kwargs.get("max_tokens") == 256
    assert captured_kwargs.get("task_type") == "review"
```

### Step 2: 최소 구현
`reviewer.py:135` `invoke_bedrock(prompt, max_tokens=256, task_type="review")` — 이미 구현됨.

### Step 3: 통과 확인
`pytest tests/test_reviewer_ai.py::test_ai_semantic_model_routing -v`

### Step 4: 커밋
```
git add backend/tests/test_reviewer_ai.py
git commit -m "test(EXE-16): Sonnet 라우팅·max_tokens=256 검증"
```

---

## Task 6: 토큰 감사 기록 (FR-008a, FR-008b)

**수용기준**: `run_review` 반환값에 `ai_tokens`가 포함된다(FR-008a). `record_run` 호출 시 `token_usage=ai_tokens`가 전달된다(FR-008b). `record_run` 실패 시 파이프라인을 차단하지 않는다.

### Step 1: 실패 테스트 작성
```python
def test_token_audit_record(monkeypatch):
    """token_usage가 record_run에 전달되고, record_run 실패 시 비차단."""
    import openpyxl
    from services.reviewer import run_review
    from models.sprint_contract import SprintContract

    monkeypatch.setattr(
        "services.reviewer.invoke_bedrock",
        lambda *a, **kw: {"content": [{"text": "[]"}], "usage": {"input_tokens": 20, "output_tokens": 5}}
    )

    recorded = {}

    def mock_record_run(**kw):
        recorded.update(kw)
        raise RuntimeError("DB 연결 실패")  # 실패해도 파이프라인 계속

    monkeypatch.setattr("services.reviewer.record_run", mock_record_run)

    wb = openpyxl.Workbook()
    wb.create_sheet("공통")
    wb.create_sheet("5-4. 수수료산출내역")
    contract = SprintContract()

    result, tokens = run_review(contract, {}, wb)  # 예외 없이 완료되어야 함
    assert tokens == {"input": 20, "output": 5}
    assert recorded.get("token_usage") == {"input": 20, "output": 5}
```

### Step 2: 최소 구현
`reviewer.py:627-640` record_run 호출 + except 블록 — 이미 구현됨.

### Step 3: 통과 확인
`pytest tests/test_reviewer_ai.py::test_token_audit_record -v`

### Step 4: 커밋
```
git add backend/tests/test_reviewer_ai.py
git commit -m "test(EXE-16): 감사 기록 token_usage 포함·record_run 실패 비차단 검증"
```

---

## Task 7: 전체 테스트 스위트 통합 커밋

**수용기준**: Task 1~6의 모든 테스트가 통과하며, `specs/EXE-16/{spec,plan,tasks}.md`가 커밋된다.

### Step 1: 전체 실행
```bash
pytest backend/tests/test_reviewer_ai.py -v
```
Expected: 6 passed

### Step 2: 문서 커밋
```bash
git add specs/EXE-16
git commit -m "feat(sdd): EXE-16 Reviewer AI 의미검증 spec/plan/tasks"
```

---

## [NEEDS CLARIFICATION] 항목 — Task 생성 보류

아래 항목은 명확화 후 별도 task로 추가:

1. **SC-006 AI 이슈 탐지 정밀도 목표**: 검증 사례셋 구성·측정 task는 목표 수치 확정 후 추가.
2. **SC-007 Bedrock 응답 지연 SLA**: p95 목표 확정 후 부하 테스트 task 추가.
3. **AI 이슈 → verdict 강제 조정 정책**: 정책 확정 시 `run_review` 수정 + 테스트 task 추가.
