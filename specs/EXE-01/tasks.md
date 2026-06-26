# Tasks: EXE-01 문서분류

**Feature**: EXE-01 문서분류
**Created**: 2026-06-26
**Status**: Draft

> 각 태스크는 "실패 테스트 → 최소 구현 → 통과 → 커밋" 단위로 기술한다.
> 본 문서는 사람이 읽는 구현 가이드이며, 자동 implement 비의존 (constitution §VII).

---

## Task 1: 백엔드 분류 API — 6종 taxonomy 반환 (FR-001, FR-002)

**수용기준 (Given/When/Then)**:
- Given 인증된 사용자가 텍스트 추출 가능한 파일을 업로드할 때,
  When `POST /api/classify` 를 호출하면,
  Then 응답이 `{"category": <6종 중 하나>, "confidence": <0.0~1.0>, "reason": <문자열>}` 구조여야 한다.

**실패 테스트 (작성)**:
```python
# tests/test_classify.py
def test_classify_returns_valid_category(client, auth_headers):
    with open("tests/fixtures/sample_contract.pdf", "rb") as f:
        resp = client.post("/api/classify", files={"file": f}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] in {"contract", "internal", "vendor", "insurance", "execution_plan", "unknown"}
    assert 0.0 <= body["confidence"] <= 1.0
    assert isinstance(body["reason"], str)
```

**최소 구현**:
- `ai_core.py:198-205` `classify_document()` — `CLASSIFY_PROMPT` 포맷 → Bedrock Haiku 호출 → `_parse_json` 반환.
- `main.py:514-526` `POST /api/classify` — 파일 읽기·텍스트 추출·`classify_document` 호출.

**통과 기준**: 위 테스트 PASS. 반환값의 `category`가 taxonomy 외 값(예: "other")인 경우 FAIL.

**커밋 단위**: `feat(EXE-01): classify_document 6종 taxonomy 반환 + /api/classify 엔드포인트`

---

## Task 2: 분류 근거(reason) 필드 보존 (FR-002)

**수용기준**:
- Given 파일 분류가 완료될 때,
  When 응답을 확인하면,
  Then `reason` 필드가 null 또는 빈 문자열이 아닌 한 줄 사유 문자열이어야 한다.

**실패 테스트**:
```python
def test_classify_reason_not_empty(client, auth_headers):
    with open("tests/fixtures/sample_vendor_quote.pdf", "rb") as f:
        resp = client.post("/api/classify", files={"file": f}, headers=auth_headers)
    body = resp.json()
    assert body.get("reason") not in (None, "")
```

**최소 구현**:
- `CLASSIFY_PROMPT`의 JSON 응답 형식에 `"reason":"한 줄 사유"` 포함 (`ai_core.py:194`) — 이미 구현됨.
- `_parse_json` fallback에도 `"reason": "파싱 실패"` 포함 (`ai_core.py:205`) — 이미 구현됨.
- **주의**: Bedrock 응답이 reason 필드를 누락하는 경우를 위한 방어 코드 추가 검토 필요.

**통과 기준**: reason 필드가 항상 문자열(길이 > 0)로 반환.

**커밋 단위**: `fix(EXE-01): reason 필드 항상 문자열 보장`

---

## Task 3: 텍스트 추출 불가 파일 폴백 (FR-008)

**수용기준**:
- Given 스캔 PDF 등 텍스트 추출이 불가능한 파일을 업로드할 때,
  When `POST /api/classify` 를 호출하면,
  Then 응답 상태가 200이고 `category` 값이 6종 taxonomy 중 하나이며 `reason` 필드가 비어 있지 않아야 한다.
- Given 텍스트 추출이 불가능한 파일을 업로드할 때,
  When `POST /api/classify` 를 호출하면,
  Then 백엔드가 Bedrock에 전달한 프롬프트에 `"(텍스트 추출 불가 — 파일명만으로 판단)"` 문자열이 포함되어야 한다 (`ai_core.py:202` FR-008 핵심 동작).

**실패 테스트**:
```python
def test_classify_scan_pdf_no_crash(client, auth_headers):
    # 비어있는 텍스트를 가진 바이너리 PDF(텍스트 추출 불가 시뮬레이션)
    with open("tests/fixtures/scan_only.pdf", "rb") as f:
        resp = client.post("/api/classify", files={"file": f}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] in {"contract", "internal", "vendor", "insurance", "execution_plan", "unknown"}
    assert body.get("reason") not in (None, "")

def test_classify_scan_pdf_prompt_signal(monkeypatch, client, auth_headers):
    # FR-008 핵심: 프롬프트에 텍스트불가 신호가 포함되는지 검증 (ai_core.py:202)
    captured_prompts = []
    original_call = classify_document  # 실제 함수 참조
    def mock_classify(filename, text):
        captured_prompts.append(text)
        return original_call(filename, text)
    monkeypatch.setattr("backend.services.ai_core.classify_document", mock_classify)
    with open("tests/fixtures/scan_only.pdf", "rb") as f:
        client.post("/api/classify", files={"file": f}, headers=auth_headers)
    assert any("텍스트 추출 불가" in p for p in captured_prompts), \
        "프롬프트에 텍스트불가 신호가 포함되어야 한다 (FR-008, ai_core.py:202)"
```

**최소 구현**:
- `main.py:519` `_safe_extract_text()` 가 빈 문자열 반환 시, `ai_core.py:202`의 `text[:2000] if text else "(텍스트 추출 불가 — 파일명만으로 판단)"` 로 분기 — 이미 구현됨.
- 파일명만으로 분류 결과를 얻는 통합 테스트 fixture 준비 필요.

**통과 기준**: 스캔 PDF 업로드 시 (1) 200 응답 + 유효 category 반환, (2) Bedrock 전달 프롬프트에 `"(텍스트 추출 불가 — 파일명만으로 판단)"` 문자열 포함 — 두 조건 모두 충족.

**커밋 단위**: `test(EXE-01): 텍스트 추출 불가 파일 분류 통합 테스트`

---

## Task 4: 프론트엔드 — `unknown`+`confidence<0.5` 폴백 (FR-003)

**수용기준**:
- Given AI 분류 결과가 `{category: "unknown", confidence: 0.4, reason: "..."}` 일 때,
  When 프론트엔드가 결과를 수신하면,
  Then `classifyFileFallback(filename)` 을 적용한 카테고리와 "키워드 기반 추정" 사유가 표시되어야 한다.

**실패 테스트 (Jest/RTL)**:
```typescript
// __tests__/upload-page.test.tsx
it("unknown+low-confidence falls back to filename heuristic", () => {
  const result = { category: "unknown", confidence: 0.4, reason: "" };
  // 핵심 분기: upload-page.tsx:185
  const final = result.category === "unknown" && result.confidence < 0.5
    ? { ...classifyFileFallback("집행계획서_2026.xlsx"), reason: result.reason || "키워드 기반 추정" }
    : result;
  expect(final.category).toBe("execution_plan");
  expect(final.reason).toBe("키워드 기반 추정");
});
```

**최소 구현**:
- `upload-page.tsx:185-187` 조건 분기 — 이미 구현됨.
- `classifyFileFallback()` (`upload-page.tsx:36-44`) — 이미 구현됨.
- 단위 테스트 파일 추가 필요.

**통과 기준**: 폴백 적용 후 파일명에 "집행계획서" 포함 시 category = `"execution_plan"`.

**커밋 단위**: `test(EXE-01): unknown+low-confidence 폴백 단위 테스트`

---

## Task 5: 프론트엔드 — AI 호출 실패 시 파일명 폴백 (FR-004)

**수용기준**:
- Given `apiClassify()` 호출이 네트워크 오류로 실패할 때,
  When 파일 업로드 처리가 완료되면,
  Then 해당 파일의 `classifying`이 `false`로, `reason`이 "분석 실패 — 파일명 기반"으로 표시되어야 한다.

**실패 테스트 (Jest/RTL)**:
```typescript
it("API failure uses filename fallback with error reason", async () => {
  jest.spyOn(api, "apiClassify").mockRejectedValue(new Error("network"));
  // 파일명: "계약서_퀘이사존.pdf"
  // 기대: category="contract", reason="분석 실패 — 파일명 기반"
  // upload-page.tsx:191-195 검증
});
```

**최소 구현**:
- `upload-page.tsx:191-195` catch 블록 — 이미 구현됨.
- 테스트 추가 필요.

**통과 기준**: 오류 시 UI에 `category≠"unknown"` (파일명에 키워드 있는 경우) + reason = "분석 실패 — 파일명 기반".

**커밋 단위**: `test(EXE-01): apiClassify 실패 시 파일명 폴백 테스트`

---

## Task 6: 프론트엔드 — `unknown` 잔존 시 추출 차단 (FR-005)

**수용기준**:
- Given 파일 목록에 `category: "unknown"` 파일이 1건 이상 존재할 때,
  When UI를 확인하면,
  Then "추출 시작" 버튼이 `disabled` 상태이어야 한다.

**실패 테스트 (Jest/RTL)**:
```typescript
it("start button disabled when unknown file exists", () => {
  // files 상태에 category="unknown" 포함
  // canStart = name && hasContract && hasInternal && counts.unknown === 0
  // upload-page.tsx:312
  // 기대: button[disabled] 존재
});
```

**최소 구현**:
- `upload-page.tsx:312` `canStart` 조건 — 이미 구현됨.
- 테스트 추가 필요.

**통과 기준**: `counts.unknown > 0` 인 경우 버튼 비활성.

**커밋 단위**: `test(EXE-01): unknown 잔존 시 추출 차단 UI 테스트`

---

## Task 7: 프론트엔드 — 수동 재분류 (FR-006)

**수용기준**:
- Given AI가 `vendor`로 분류한 파일이 존재할 때,
  When 담당자가 드롭다운에서 `contract`를 선택하면,
  Then 해당 파일의 `category="contract"`, `confidence=1.0`, `manual=true` 이어야 한다.

**실패 테스트 (Jest/RTL)**:
```typescript
it("manual reclassify sets category, confidence=1.0, manual=true", () => {
  const result = reclassify(fileId, "contract");
  // upload-page.tsx:300-301
  expect(result.category).toBe("contract");
  expect(result.confidence).toBe(1.0);
  expect(result.manual).toBe(true);
});
```

**최소 구현**:
- `upload-page.tsx:300-301` `reclassify()` — 이미 구현됨.
- 테스트 추가 필요.

**통과 기준**: 수동 지정 후 `manual=true`, `confidence=1.0` 상태 확인.

**커밋 단위**: `test(EXE-01): 수동 재분류 상태 변환 테스트`

---

## Task 8: 프론트엔드 — 분류 중 UI 비활성 표시 (FR-007)

**수용기준**:
- Given 파일 업로드 직후 `classifying: true` 상태일 때,
  When 파일 행(FileRow)을 렌더링하면,
  Then "AI 분석 중…" 텍스트와 카테고리 수동 선택 드롭다운 비활성이 표시되어야 한다.

**실패 테스트 (Jest/RTL)**:
```typescript
it("shows loading state during classification", () => {
  // upload-page.tsx:523,526
  // classifying=true → "AI 분석 중…" 텍스트, 드롭다운 hidden/disabled
});
```

**최소 구현**:
- `upload-page.tsx:523` `{f.classifying ? "AI 분석 중…" : ...}` — 이미 구현됨.
- `upload-page.tsx:526` classifying 상태에서 드롭다운 미표시 — 이미 구현됨.

**통과 기준**: `classifying=true` 렌더링 시 로딩 레이블 노출 + 드롭다운 미노출.

**커밋 단위**: `test(EXE-01): 분류 중 UI 상태 렌더링 테스트`

---

## Task 9: 병렬 분류 최대 3건 제한 (SC-006)

**수용기준**:
- Given 5건 파일을 동시에 업로드했을 때,
  When 분류가 진행되면,
  Then 최대 3건이 동시에 `classifying: true` 상태이어야 한다.

**실패 테스트 (Jest)**:
```typescript
it("classifies at most 3 files concurrently", async () => {
  // upload-page.tsx:199-212
  // inflight 배열 최대 길이 = 3 확인
  let maxConcurrent = 0;
  let current = 0;
  jest.spyOn(api, "apiClassify").mockImplementation(async () => {
    current++;
    maxConcurrent = Math.max(maxConcurrent, current);
    await delay(100);
    current--;
    return { category: "contract", confidence: 0.9, reason: "test" };
  });
  // 파일 5건 업로드 시뮬레이션
  expect(maxConcurrent).toBeLessThanOrEqual(3);
});
```

**최소 구현**:
- `upload-page.tsx:199-212` `runBatch()` — 이미 구현됨.

**통과 기준**: 5건 업로드 시 inflight 최대 3건.

**커밋 단위**: `test(EXE-01): 분류 병렬 최대 3건 제한 테스트`

---

## 구현 순서 권장

1. Task 1 (백엔드 핵심) → Task 2 (reason 보장) → Task 3 (텍스트 불가 폴백)
2. Task 4 → Task 5 → Task 6 → Task 7 → Task 8 → Task 9 (프론트엔드 단위 테스트군)

> 백엔드 핵심 로직(Task 1~3)은 현행 코드에 이미 구현되어 있으며, 테스트 fixture 준비가 주 작업이다.
> 프론트엔드 Task 4~9는 현행 코드를 테스트로 커버하는 작업이다.

---

## 미해결 사항 (구현 전 확인 필요)

- **신뢰도 임계값 0.5**: `upload-page.tsx:185`의 `confidence < 0.5` 기준 변경 가능성 — 운영팀 확정 후 상수화 권장. `[NEEDS CLARIFICATION]` (spec.md Clarifications 1번 참조).
- **6종 taxonomy 공식 정의**: 프롬프트 내 자연어 정의만 존재. 정책 문서 없이 변경 시 프롬프트만 수정하면 됨. `[NEEDS CLARIFICATION]` (spec.md Clarifications 2번 참조).
- **분류 정확도 목표**: 베이스라인 측정 후 SC-003, SC-005 수치 결정. `[NEEDS CLARIFICATION]` (spec.md Clarifications 3번 참조).
