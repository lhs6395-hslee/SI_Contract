# Tasks: EXE-05 — 견적서 충돌 감지·해결

**Created**: 2026-06-26  **Status**: Draft
**주의**: 이 파일은 사람이 읽는 구현 가이드다. 자동 implement 비의존 (설계 §9).
구현자는 "실패 테스트 → 최소 구현 → 통과 → 커밋" 단위로 진행한다.

---

## Task 1: 백엔드 — `/api/validate` 교차 검증 엔드포인트 (FR-001)

**수용기준**:
- `POST /api/validate`에 추출 데이터 JSON을 전달하면 `{"conflicts": [...]}` 형태로 응답한다.
- 응답의 각 항목은 `type`, `field`, `message`, `severity`를 포함한다.
- 인증(JWT) 없이 호출하면 401/403을 반환한다.

**실패 테스트 (먼저 작성)**:
```python
# tests/test_exe05_validate.py

def test_validate_requires_auth(client):
    """인증 없이 /api/validate 호출 시 401/403 반환."""
    resp = client.post("/api/validate", json={"extracted": {}})
    assert resp.status_code in (401, 403)

def test_validate_returns_conflicts_list(auth_client, mock_cross_validate):
    """정상 인증 + 데이터 전달 시 conflicts 키 포함 JSON 반환."""
    mock_cross_validate.return_value = [
        {"type": "mismatch", "field": "projectName", "message": "불일치", "severity": "high"}
    ]
    resp = auth_client.post("/api/validate", json={"extracted": {"projectName": {"value": "A"}}})
    assert resp.status_code == 200
    body = resp.json()
    assert "conflicts" in body
    assert len(body["conflicts"]) == 1
    assert body["conflicts"][0]["type"] == "mismatch"

def test_validate_empty_data_returns_empty_list(auth_client, mock_cross_validate):
    """데이터 없을 때 빈 conflicts 반환."""
    mock_cross_validate.return_value = []
    resp = auth_client.post("/api/validate", json={})
    assert resp.status_code == 200
    assert resp.json()["conflicts"] == []
```

**최소 구현**:
- `backend/main.py:675-684` — 이미 구현됨. `require_auth` 적용, `cross_validate` 위임, `{"conflicts": conflicts}` 반환.
- `backend/services/ai_core.py:522-527` — `cross_validate` 구현 확인.

**통과 기준**: 위 세 테스트 모두 PASS. `pytest tests/test_exe05_validate.py -v`

**커밋**: `test(exe05): FR-001 /api/validate 엔드포인트 수용기준 테스트`

---

## Task 2: 백엔드 — 충돌 유형 A/A'/B/C/D 감지 (FR-002 ~ FR-006)

**수용기준**:
- 유형별 검증 사례셋 입력 데이터에서 `cross_validate`가 해당 충돌을 감지한다.
- 유형 A': 감지되더라도 자동 병합 로직 없음(반환만 함).
- 견적서 1개만 있을 때 유형 A/A'/B/D는 감지되지 않는다.

**실패 테스트**:
```python
# tests/test_exe05_conflict_types.py
# cross_validate는 Bedrock 호출 — 단위 테스트에서는 VALIDATE_PROMPT 생성값 + _parse_json만 검증.
# 통합 테스트에서는 실제 Bedrock stub으로 유형별 응답 시뮬레이션.

def test_validate_prompt_includes_data():
    """VALIDATE_PROMPT에 data_json이 삽입된다."""
    from backend.services.ai_core import VALIDATE_PROMPT
    import json
    data = {"estimates": [{"vendor": "A", "total": 100}]}
    prompt = VALIDATE_PROMPT.format(data_json=json.dumps(data))
    assert "A" in prompt
    assert "estimates" in prompt

def test_cross_validate_returns_list(monkeypatch):
    """_call_claude 스텁으로 cross_validate 반환값이 list임을 확인."""
    from backend.services.ai_core import cross_validate
    stub_resp = '[{"type":"mismatch","field":"vendor","message":"중복","severity":"high"}]'
    monkeypatch.setattr("backend.services.ai_core._call_claude", lambda *a, **kw: stub_resp)
    result = cross_validate({"estimates": []})
    assert isinstance(result, list)
    assert result[0]["type"] == "mismatch"

def test_cross_validate_fallback_on_invalid_json(monkeypatch):
    """Bedrock이 파싱 불가 응답 반환 시 빈 리스트 fallback."""
    from backend.services.ai_core import cross_validate
    monkeypatch.setattr("backend.services.ai_core._call_claude", lambda *a, **kw: "invalid json")
    result = cross_validate({})
    assert result == []
```

**최소 구현**:
- `ai_core.py:522-527` 기존 구현 확인.
- `VALIDATE_PROMPT`가 유형 A/A'/B/C/D 패턴을 감지하도록 프롬프트 보강 필요 여부는 실제 Bedrock 응답 로그 확인 후 결정 (`[NEEDS CLARIFICATION: Clarification #1]`).

**통과 기준**: 위 단위 테스트 PASS. 통합 테스트는 Bedrock stub 환경에서 유형별 시뮬레이션.

**커밋**: `test(exe05): FR-002~006 충돌 유형 감지 단위 테스트`

---

## Task 3: 프론트엔드 — 충돌 알림 배너 + conflictCount 연동 (FR-007, FR-008)

**수용기준**:
- 추출 완료 시 `apiValidate` 호출 결과로 `conflictCount`가 설정된다.
- `conflictCount > 0`이면 review-page에 충돌 알림 배너가 렌더링된다.
- 배너에 "충돌 해결 →" 버튼이 있고 클릭 시 `route`가 `"conflicts"`로 변경된다.
- `conflictCount === 0`이면 배너가 렌더링되지 않는다.

**실패 테스트** (React Testing Library):
```typescript
// tests/frontend/review-page.conflict-banner.test.tsx

it("conflictCount > 0일 때 충돌 배너가 렌더된다", () => {
  render(<ReviewPage />, { wrapper: AppContextWith({ conflictCount: 2 }) });
  expect(screen.getByText(/충돌이 감지되었습니다/)).toBeInTheDocument();
  expect(screen.getByText(/충돌 해결 →/)).toBeInTheDocument();
});

it("conflictCount === 0일 때 충돌 배너가 없다", () => {
  render(<ReviewPage />, { wrapper: AppContextWith({ conflictCount: 0 }) });
  expect(screen.queryByText(/충돌이 감지되었습니다/)).not.toBeInTheDocument();
});

it("충돌 해결 버튼 클릭 시 route가 conflicts로 변경된다", async () => {
  const setRoute = jest.fn();
  render(<ReviewPage />, { wrapper: AppContextWith({ conflictCount: 1, setRoute }) });
  await userEvent.click(screen.getByText(/충돌 해결 →/));
  expect(setRoute).toHaveBeenCalledWith("conflicts");
});
```

**최소 구현**:
- `review-page.tsx:706-712` — 이미 구현됨.
- `page.tsx:183,203` — `conflictCount` 설정 경로 확인.

**통과 기준**: 위 세 테스트 PASS.

**커밋**: `test(exe05): FR-007/008 충돌 알림 배너 렌더링 테스트`

---

## Task 4: 프론트엔드 — ConflictsPage 충돌 선택 UI (FR-009, FR-010, FR-011)

**수용기준**:
- `rawConflicts`가 비어있으면 "충돌 없음" 안내 화면이 표시된다.
- 충돌 항목마다 옵션 A / 옵션 B / 직접 입력 버튼이 표시된다.
- 모든 항목을 선택하지 않으면 "해결 완료" 버튼이 비활성(disabled)이다.
- 모든 항목을 선택하면 "해결 완료" 버튼이 활성화된다.
- "해결 완료" 클릭 시 `extractedData.conflicts`가 `[]`, `conflictCount`가 `0`, `route`가 `"review"`가 된다.
- 유형 A' 충돌이 있을 때 자동 병합이 발생하지 않는다(사용자 선택 필수).

**실패 테스트** (React Testing Library):
```typescript
// tests/frontend/conflicts-page.test.tsx

it("충돌 없을 때 충돌 없음 안내가 표시된다", () => {
  render(<ConflictsPage />, { wrapper: AppContextWith({ conflicts: [] }) });
  expect(screen.getByText(/충돌이 없습니다/)).toBeInTheDocument();
});

it("충돌 2건 시 각 항목에 옵션 버튼이 표시된다", () => {
  const conflicts = [
    { type: "mismatch", field: "revenue", message: "금액 불일치", valueA: 1000, valueB: 2000 },
    { type: "mismatch", field: "vendor",  message: "업체 불일치", valueA: "A사", valueB: "B사" },
  ];
  render(<ConflictsPage />, { wrapper: AppContextWith({ conflicts }) });
  expect(screen.getAllByRole("button", { name: /출처/ })).toHaveLength(4); // A+B × 2건
});

it("일부만 선택 시 해결 완료 버튼이 비활성이다", async () => {
  const conflicts = [
    { type: "mismatch", field: "revenue", message: "", valueA: 1000, valueB: 2000 },
    { type: "mismatch", field: "vendor",  message: "", valueA: "A사", valueB: "B사" },
  ];
  render(<ConflictsPage />, { wrapper: AppContextWith({ conflicts }) });
  const [firstA] = screen.getAllByRole("button");
  await userEvent.click(firstA);
  const resolveBtn = screen.getByText(/해결 완료/);
  expect(resolveBtn).toBeDisabled();
});

it("모두 선택 후 해결 완료 클릭 시 conflicts=[] conflictCount=0 route=review", async () => {
  const setExtractedData = jest.fn();
  const setConflictCount = jest.fn();
  const setRoute = jest.fn();
  const conflicts = [
    { type: "mismatch", field: "revenue", message: "", valueA: 1000, valueB: 2000, sourceA: "출처A", sourceB: "출처B" },
  ];
  render(<ConflictsPage />, {
    wrapper: AppContextWith({ conflicts, setExtractedData, setConflictCount, setRoute })
  });
  const optABtn = screen.getByText("출처A").closest("button")!;
  await userEvent.click(optABtn);
  await userEvent.click(screen.getByText(/해결 완료/));
  expect(setConflictCount).toHaveBeenCalledWith(0);
  expect(setRoute).toHaveBeenCalledWith("review");
});
```

**최소 구현**:
- `other-pages.tsx:24-155` — 이미 구현됨. 유형 A' 자동 병합 없음 확인.
- `other-pages.tsx:53-54` — `allResolved` 조건 확인.

**통과 기준**: 위 네 테스트 PASS.

**커밋**: `test(exe05): FR-009/010/011 ConflictsPage UI 수용기준 테스트`

---

## Task 5: 백엔드 — ConflictResolution 모델 + 보존 (FR-012)

**수용기준**:
- `ConflictResolution` Pydantic 모델이 `conflict_type`, `description`, `options`, `user_choice`, `resolved_value` 필드를 가진다.
- `SprintContract.conflict_resolutions` 필드가 `list[ConflictResolution]`이고 기본값이 빈 리스트이다.

**실패 테스트**:
```python
# tests/test_exe05_model.py

def test_conflict_resolution_model():
    from backend.models.sprint_contract import ConflictResolution
    cr = ConflictResolution(
        conflict_type="A",
        description="동일 협력사 중복",
        options=["파일1", "파일2"],
        user_choice="1",
        resolved_value="파일1",
    )
    assert cr.conflict_type == "A"
    assert cr.user_choice == "1"

def test_conflict_resolution_optional_fields():
    from backend.models.sprint_contract import ConflictResolution
    cr = ConflictResolution(conflict_type="B", description="금액 불일치")
    assert cr.user_choice is None
    assert cr.resolved_value is None
    assert cr.options == []

def test_sprint_contract_conflict_resolutions_default():
    from backend.models.sprint_contract import SprintContract
    sc = SprintContract()
    assert sc.conflict_resolutions == []
```

**최소 구현**:
- `backend/models/sprint_contract.py:51-56` — 이미 구현됨.
- `backend/models/sprint_contract.py:168` — 이미 구현됨.

**통과 기준**: 위 세 테스트 PASS.

**커밋**: `test(exe05): FR-012 ConflictResolution 모델 구조 테스트`

---

## Task 6: 백엔드 — Reviewer Stage 2 충돌 해결 검증 (FR-013, FR-014)

**수용기준**:
- `_verify_conflict_resolution`에서 `user_choice`가 있는 항목은 `ok_count` 증가.
- `user_choice`가 None/빈 문자열인 항목은 `errors`에 "미해결 충돌: ..." 추가.
- `resolved_value`가 None인 항목은 `errors`에 "충돌 해결값 누락: ..." 추가.
- `conflict_resolutions`가 빈 리스트이고 `errors`가 없으면 `score = 1.0`.
- `score = ok_count / max(ok_count + len(errors), 1)`.

**실패 테스트**:
```python
# tests/test_exe05_reviewer_stage2.py

from backend.models.sprint_contract import SprintContract, ConflictResolution
from backend.services.reviewer import _verify_conflict_resolution

def make_contract(resolutions):
    return SprintContract(conflict_resolutions=resolutions)

def test_all_resolved_score_1():
    cr = ConflictResolution(conflict_type="A", description="d", user_choice="1", resolved_value="v")
    contract = make_contract([cr])
    result = _verify_conflict_resolution(contract, {})
    assert result["resolved_ok"] is True
    assert result["score"] == 1.0

def test_missing_user_choice_error():
    cr = ConflictResolution(conflict_type="B", description="금액 불일치")
    contract = make_contract([cr])
    result = _verify_conflict_resolution(contract, {})
    assert result["resolved_ok"] is False
    assert any("미해결 충돌" in e for e in result["errors"])

def test_missing_resolved_value_error():
    cr = ConflictResolution(conflict_type="C", description="중복", user_choice="1")
    contract = make_contract([cr])
    result = _verify_conflict_resolution(contract, {})
    assert result["resolved_ok"] is False
    assert any("충돌 해결값 누락" in e for e in result["errors"])

def test_empty_resolutions_score_1():
    contract = make_contract([])
    result = _verify_conflict_resolution(contract, {})
    assert result["score"] == 1.0
    assert result["resolved_ok"] is True

def test_partial_resolution_score():
    cr_ok = ConflictResolution(conflict_type="A", description="d1", user_choice="1", resolved_value="v")
    cr_fail = ConflictResolution(conflict_type="B", description="d2")  # user_choice=None
    contract = make_contract([cr_ok, cr_fail])
    result = _verify_conflict_resolution(contract, {})
    # ok_count=1, errors=1 → score = 1/2 = 0.5
    assert result["score"] == 0.5
    assert result["resolved_ok"] is False
```

**최소 구현**:
- `backend/services/reviewer.py:248-284` — 이미 구현됨.

**통과 기준**: 위 다섯 테스트 PASS. `pytest tests/test_exe05_reviewer_stage2.py -v`

**커밋**: `test(exe05): FR-013/014 Reviewer Stage 2 충돌 해결 검증 테스트`

---

## Task 7: 통합 테스트 — 충돌 감지 → 해결 → 검증 엔드투엔드

**수용기준**:
- 견적서 충돌이 있는 데이터 셋 → `/api/validate` → conflicts 반환 → (프론트) ConflictsPage 해결 → 해결 완료 → SprintContract 생성 → Reviewer Stage 2 PASS 흐름 전 단계가 오류 없이 완료된다.
- 유형 A' 충돌 데이터 셋에서 자동 병합 없이 사용자 선택이 강제된다.

**실패 테스트** (Bedrock stub 환경):
```python
# tests/test_exe05_integration.py

def test_conflict_to_resolution_to_reviewer_pass(auth_client, bedrock_stub):
    """충돌 감지 → 해결 완료 → Reviewer Stage 2 PASS 전체 흐름."""
    # 1. 충돌 있는 데이터로 /api/validate 호출
    bedrock_stub.set_validate_response([
        {"type": "mismatch", "field": "revenue", "message": "금액 불일치", "severity": "high"}
    ])
    validate_resp = auth_client.post("/api/validate", json={"extracted": {"revenue": {}}})
    assert len(validate_resp.json()["conflicts"]) == 1

    # 2. 사용자가 충돌 해결 → resolved_value 포함 ConflictResolution 생성
    cr = ConflictResolution(
        conflict_type="B",
        description="금액 불일치",
        options=["1000원", "2000원"],
        user_choice="1",
        resolved_value="1000원",
    )
    contract = SprintContract(conflict_resolutions=[cr])

    # 3. Reviewer Stage 2
    result = _verify_conflict_resolution(contract, {})
    assert result["resolved_ok"] is True
    assert result["score"] == 1.0
```

**통과 기준**: 통합 테스트 PASS. Bedrock stub 없는 환경에서는 skip 마커 적용.

**커밋**: `test(exe05): 충돌 감지→해결→Reviewer E2E 통합 테스트`

---

## Task 8: SC 게이트 검증

**수용기준 체크리스트 (SC-003 ~ SC-006)**:

- [ ] **SC-003**: 유형 A' 충돌 포함 데이터에서 자동 병합 코드 경로 없음 — `other-pages.tsx:56-78` `handleResolve` 함수에서 `picks[i]`가 `undefined`인 항목에 대해 자동으로 값을 설정하는 분기(예: `picks[i] ?? "A"` 등)가 없음을 확인. 구체적으로: (1) `resolvedValue` 계산부(`other-pages.tsx:62-67` 추정)에서 `user_choice`가 없는 경우 fallback 자동 선택 코드가 없는지 검토, (2) `allResolved` 조건(`other-pages.tsx:53-54`)이 `resolvedCount === rawConflicts.length`를 정확히 검사하는지 확인.
- [ ] **SC-004**: `conflictCount > 0` 상태에서 익스포트 차단 UI 동작 확인 — `[NEEDS CLARIFICATION: 익스포트 버튼 disabled 조건 위치 확인 후 테스트 추가]`.
- [ ] **SC-005**: 해결 완료 후 review-page에서 충돌 배너 미표시 확인 — Task 4 테스트에서 커버.
- [ ] **SC-006**: user_choice 미충족 시 Reviewer Stage 2 FAIL — Task 6 테스트에서 커버.

**[NEEDS CLARIFICATION] 항목 해소 전 보류**:
- SC-001 (응답 시간 목표): Bedrock P95 측정 후 확정.
- SC-002 (검증 사례셋 감지율): 검증 사례셋 정의 후 확정.
- SC-004 (익스포트 차단 위치): 코드 확인 후 테스트 추가.

**커밋**: `chore(exe05): SC 게이트 체크리스트 완료 기록`

---

## 완료 기준 요약

| 번호 | 설명 | 상태 |
|------|------|------|
| Task 1 | `/api/validate` 엔드포인트 테스트 | ☐ |
| Task 2 | 유형 A/A'/B/C/D 감지 단위 테스트 | ☐ |
| Task 3 | 충돌 배너 렌더링 테스트 | ☐ |
| Task 4 | ConflictsPage UI 테스트 | ☐ |
| Task 5 | ConflictResolution 모델 테스트 | ☐ |
| Task 6 | Reviewer Stage 2 테스트 | ☐ |
| Task 7 | E2E 통합 테스트 | ☐ |
| Task 8 | SC 게이트 검증 | ☐ (일부 NEEDS CLARIFICATION 보류) |

모든 Task가 완료되고 `[NEEDS CLARIFICATION]` 항목이 사용자가 사내 기준으로 직접 확정되면 EXE-05 완료.
