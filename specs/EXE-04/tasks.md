# Tasks: EXE-04 기본정보 확인 게이트

**Feature**: EXE-04 기본정보 확인 게이트 (프론트 전용)
**Created**: 2026-06-26  **Status**: Draft
**작업 깊이**: 이 tasks.md는 사람이 읽는 산출물이다. 자동 implement(speckit-implement) 비의존. 코드 구현 단계에서 참조한다.

> **읽는 법**: 각 task는 TDD 사이클(실패 테스트 작성 → 최소 구현 → 통과 확인 → 커밋)을 기술한다. 구현자는 task 순서대로 진행한다.

---

## Task 1: `confirmTab` / `unconfirmTab` 함수 단위 동작 검증

**수용기준 출처**: FR-003a, FR-003b, FR-003c, FR-004a, FR-004b, SC-001  
**대상 파일**: `frontend/components/pages/review-page.tsx:124-150`

### 실패 테스트 (작성 먼저)

```typescript
// __tests__/review-page.confirmTab.test.tsx
describe("confirmTab / unconfirmTab", () => {
  it("confirmTab: Set에 tabId 추가 + extractedData.confirmedTabs 배열에도 추가", () => {
    // extractedData.confirmedTabs = [] 초기 상태
    // confirmTab("basic") 호출
    // confirmedTabs.has("basic") === true
    // extractedData.confirmedTabs.includes("basic") === true
    expect(false).toBe(true); // 실패 플래그
  });

  it("unconfirmTab: Set에서 tabId 제거 + extractedData.confirmedTabs 배열에서도 제거", () => {
    // confirmedTabs = new Set(["basic"]) 초기 상태
    // unconfirmTab("basic") 호출
    // confirmedTabs.has("basic") === false
    // extractedData.confirmedTabs.includes("basic") === false
    expect(false).toBe(true);
  });
});
```

### 최소 구현

`confirmTab(tabId)` (review-page.tsx:124):
1. `setConfirmedTabs(prev => new Set(prev).add(tabId))`
2. `setExtractedData(prev => ({ ...prev, confirmedTabs: [...new Set([...(prev?.confirmedTabs||[]), tabId])] }))`

`unconfirmTab(tabId)` (review-page.tsx:138):
1. `setConfirmedTabs(prev => { const next = new Set(prev); next.delete(tabId); return next; })`
2. `setExtractedData(prev => ({ ...prev, confirmedTabs: (prev?.confirmedTabs||[]).filter(t=>t!==tabId) }))`

### 통과 조건

- `confirmTab("basic")` 후 `confirmedTabs.has("basic") === true`
- `unconfirmTab("basic")` 후 `confirmedTabs.has("basic") === false`
- 양쪽 모두 `extractedData.confirmedTabs` 배열에 반영됨

### 커밋

```
test(EXE-04): confirmTab/unconfirmTab 단위 테스트 통과
```

---

## Task 2: `tabStatus()` 함수 — 탭 상태 3단계 분기 검증

**수용기준 출처**: FR-002a, FR-002b, FR-005a, FR-005b, FR-006a, FR-006b, SC-005  
**대상 파일**: `frontend/components/pages/review-page.tsx:229-238`

### 실패 테스트

```typescript
describe("tabStatus()", () => {
  it("confirmedTabs에 포함된 탭은 'ok' 반환", () => {
    // confirmedTabs = new Set(["basic"])
    // tabStatus("basic") === "ok"
    expect(false).toBe(true);
  });

  it("REQUIRED_FIELDS 중 하나가 null이면 basic 탭 'warn' 반환", () => {
    // extractedData.extracted.projectName.value = null
    // confirmedTabs = new Set()
    // tabStatus("basic") === "warn"
    expect(false).toBe(true);
  });

  it("guess 미확인 필드 존재 시 basic 탭 'warn' 반환", () => {
    // extracted.client.confidence = "guess", manuallyVerified에 없음
    // tabStatus("basic") === "warn"
    expect(false).toBe(true);
  });

  it("REQUIRED_FIELDS 전부 입력 + guess 없으면 basic 탭 'ready' 반환", () => {
    // 모든 REQUIRED_FIELDS 값 있음, guessCount = 0
    // tabStatus("basic") === "ready"
    expect(false).toBe(true);
  });
});
```

### 최소 구현

`tabStatus(id)` (review-page.tsx:229):
```
if (confirmedTabs.has(id)) return "ok";
if (id === "basic") return basicFields > 0 && guessCount === 0 && missingCount === 0 ? "ready" : "warn";
// ... 나머지 탭 조건
```

REQUIRED_FIELDS = `["projectName", "client", "pm", "startDate", "endDate", "revenue"]` (review-page.tsx:167)

### 통과 조건

- confirmedTabs 포함 → "ok" **100%**
- REQUIRED_FIELDS 하나라도 null → "warn" **100%** (SC-005)
- guess 미확인 → "warn" **100%**
- 모든 조건 만족 → "ready"

### 커밋

```
test(EXE-04): tabStatus 3단계 분기 단위 테스트 통과
```

---

## Task 3: 재추출 완료 시 confirmedTabs 자동 해제 검증

**수용기준 출처**: FR-007, FR-007b, SC-002  
**대상 파일**: `frontend/components/pages/review-page.tsx:254-323` (`doTabReExtract`)

### 실패 테스트

```typescript
describe("doTabReExtract", () => {
  it("재추출 성공 후 해당 탭이 confirmedTabs에서 제거됨", async () => {
    // confirmedTabs = new Set(["calc"])
    // doTabReExtract("calc") 모킹 후 실행
    // 완료 후 confirmedTabs.has("calc") === false
    expect(false).toBe(true);
  });

  it("재추출 실패 시에도 unconfirmTab이 호출되지 않아야 한다", async () => {
    // API가 reject 시 confirmedTabs 변화 없음
    expect(false).toBe(true);
  });
});
```

> 주의: 현재 코드(review-page.tsx:316)에서 `unconfirmTab(tabId)`는 `try` 블록 내부 API 호출 성공 직후에 위치한다. `finally`가 아니므로 실패(reject) 시 `unconfirmTab`이 호출되지 않아 `confirmedTabs`가 변경되지 않는다. 이는 FR-007b의 의도된 동작이며, 테스트는 성공 경로(FR-007)와 실패 경로(FR-007b) 양쪽을 모두 검증한다.

### 최소 구현

`doTabReExtract` 내 성공 경로 마지막:
```typescript
unconfirmTab(tabId);  // review-page.tsx:316
```

### 통과 조건

- 재추출 성공 후 `confirmedTabs.has(tabId) === false` 100% (SC-002)
- 재추출 실패(API reject) 시 `confirmedTabs` 변화 없음

### 커밋

```
test(EXE-04): doTabReExtract 완료 시 unconfirmTab 호출 테스트 통과
```

---

## Task 4: revision/projectId 변경 시 confirmedTabs 재동기화 검증

**수용기준 출처**: FR-008, SC-003  
**대상 파일**: `frontend/components/pages/review-page.tsx:120-122`

### 실패 테스트

```typescript
describe("confirmedTabs 재동기화", () => {
  it("revision 변경 시 extractedData.confirmedTabs 기준으로 재초기화됨", () => {
    // 초기: revision=0, confirmedTabs=new Set(["basic"])
    // revision=1로 변경, extractedData.confirmedTabs=["calc"]
    // useEffect 실행 후 confirmedTabs === new Set(["calc"])
    expect(false).toBe(true);
  });
});
```

### 최소 구현

```typescript
React.useEffect(() => {
  setConfirmedTabs(new Set(extractedData?.confirmedTabs || []));
}, [revision, projectId]);  // review-page.tsx:120-122
```

### 통과 조건

- revision 변경 후 다음 render에서 `confirmedTabs`가 신규 `extractedData.confirmedTabs` 기준으로 갱신됨
- 이전 차수의 tabId가 신규 차수 `confirmedTabs`에 잔존하지 않음

### 커밋

```
test(EXE-04): revision 전환 시 confirmedTabs 재동기화 테스트 통과
```

---

## Task 5: `importPending` → 익스포트 버튼 차단 검증

**수용기준 출처**: FR-009a, FR-009b, SC-004  
**대상 파일**: `frontend/components/pages/review-page.tsx:184, 832-833`

### 실패 테스트

```typescript
describe("importPending 익스포트 게이트", () => {
  it("importMeta 있고 unitConfirmed=false이면 익스포트 버튼이 disabled", () => {
    // extractedData = { importMeta: { unitGuessed: true }, unitConfirmed: false, ... }
    // 렌더링 후 익스포트 버튼의 disabled prop === true
    expect(false).toBe(true);
  });

  it("unitConfirmed=true이면 익스포트 버튼이 활성화됨", () => {
    // extractedData = { importMeta: { ... }, unitConfirmed: true, ... }
    // 렌더링 후 익스포트 버튼의 disabled prop === false
    expect(false).toBe(true);
  });

  it("importMeta가 없으면 importPending=false → 익스포트 버튼 활성화", () => {
    // extractedData.importMeta = undefined
    // 익스포트 버튼의 disabled prop === false
    expect(false).toBe(true);
  });
});
```

### 최소 구현

```typescript
const importPending = !!importMeta && !extractedData?.unitConfirmed;  // review-page.tsx:184
// ...
<Button onClick={() => setRoute("export")} disabled={importPending}>  // review-page.tsx:832
```

### 통과 조건

- `importMeta` 있고 `unitConfirmed=false` → `disabled=true` **100%** (SC-004)
- `unitConfirmed=true` → `disabled=false`
- `importMeta=undefined` → `disabled=false`

### 커밋

```
test(EXE-04): importPending 익스포트 차단 테스트 통과
```

---

## Task 6: TabActionBar UI 렌더링 — 확인 완료/미완 분기 검증

**수용기준 출처**: FR-010a, FR-010b, SC-001  
**대상 파일**: `frontend/components/pages/review-page.tsx:2023-2070`

### 실패 테스트

```typescript
describe("TabActionBar 렌더링", () => {
  it("confirmed=true이면 '확인 완료' 텍스트와 '확인 취소' 버튼이 표시됨", () => {
    // render(<TabActionBar confirmed={true} ... />)
    // "확인 완료" 텍스트 존재
    // "확인 취소" 버튼 존재
    // "확인 완료" 버튼 없음
    expect(false).toBe(true);
  });

  it("confirmed=false이면 '확인 완료' 버튼이 표시됨", () => {
    // render(<TabActionBar confirmed={false} ... />)
    // "확인 완료" 버튼 존재
    // "확인 취소" 버튼 없음
    expect(false).toBe(true);
  });

  it("reExtracting=true이면 재추출 버튼이 disabled", () => {
    // render(<TabActionBar reExtracting={true} ... />)
    // 재추출 버튼 disabled === true
    // reExtractElapsed 초 표시
    expect(false).toBe(true);
  });
});
```

### 최소 구현

`TabActionBar` (review-page.tsx:2023-2070):
- `confirmed` 분기로 확인완료/미완 상태 렌더링
- `disabled={reExtracting}` 재추출 버튼 제어
- `reExtractElapsed` 경과시간 표시

### 통과 조건

- `confirmed=true` → 초록 배경 + "확인 완료" 텍스트 + "확인 취소" 버튼
- `confirmed=false` → 기본 배경 + "확인 완료" 버튼
- `reExtracting=true` → 재추출 버튼 `disabled=true`

### 커밋

```
test(EXE-04): TabActionBar 확인/미확인/재추출중 UI 분기 테스트 통과
```

---

## Task 7: 하단 요약 바 — 필수 미입력/guess 목록 표시 검증

**수용기준 출처**: FR-005a, FR-005b, FR-006a, FR-006b  
**대상 파일**: `frontend/components/pages/review-page.tsx:802-808`

### 실패 테스트

```typescript
describe("하단 요약 바 basic 탭", () => {
  it("REQUIRED_FIELDS 미입력 시 '필수 미입력 N건: 필드명' 텍스트 표시", () => {
    // extractedData.extracted.projectName = null → missingRequired=["projectName"]
    // 하단 바에 "필수 미입력 1건: 사업명" 텍스트 존재
    expect(false).toBe(true);
  });

  it("guess 미확인 필드 존재 시 '확인 필요 N건: 필드명' 텍스트 표시", () => {
    // extracted.client.confidence = "guess", manuallyVerified에 없음
    // 하단 바에 "확인 필요 1건: 발주처" 텍스트 존재
    expect(false).toBe(true);
  });
});
```

### 최소 구현

```tsx
// review-page.tsx:805-808
{missingCount > 0 && <span>필수 미입력 {missingCount}건: {필드명목록}</span>}
{guessCount > 0 && <span>확인 필요 {guessCount}건: {필드명목록}</span>}
```

### 통과 조건

- REQUIRED_FIELDS 미입력 → "필수 미입력 N건" 텍스트 + 필드명 목록 렌더링
- guess 미확인 → "확인 필요 N건" 텍스트 + 필드명 목록 렌더링

### 커밋

```
test(EXE-04): 하단 요약 바 필수/guess 필드 목록 표시 테스트 통과
```

---

## Task 8: 통합 검증 — 전체 ReviewPage 게이트 흐름

**수용기준 출처**: FR-001a ~ FR-011b 통합, 모든 SC  
**대상 파일**: `frontend/components/pages/review-page.tsx` 전체

### 실패 테스트

```typescript
describe("ReviewPage 게이트 통합", () => {
  it("6개 탭 전부 확인 완료 후에도 importPending=false이면 익스포트 버튼 활성화", () => {
    // 모든 탭 confirmedTabs에 포함
    // extractedData.importMeta = undefined
    // 익스포트 버튼 disabled === false
    expect(false).toBe(true);
  });

  it("6개 탭 전부 확인 완료라도 importPending=true이면 익스포트 버튼 차단", () => {
    // 모든 탭 confirmedTabs에 포함
    // importMeta 있고 unitConfirmed=false
    // 익스포트 버튼 disabled === true
    expect(false).toBe(true);
  });
});
```

### 통과 조건

- 탭 확인 완료 상태와 무관하게 `importPending`만이 익스포트 차단 조건
- confirmedTabs Set ↔ ExtractedData.confirmedTabs 배열 항상 동기화됨

### 커밋

```
test(EXE-04): ReviewPage 게이트 통합 테스트 통과
feat(EXE-04): 기본정보 확인 게이트 구현 완료
```

---

## 구현 순서 요약

| Task | 선행 의존 | 예상 규모 |
|------|-----------|-----------|
| Task 1: confirmTab/unconfirmTab 단위 | 없음 | 소 |
| Task 2: tabStatus() 분기 | Task 1 | 소 |
| Task 3: 재추출 후 해제 | Task 1 | 소 |
| Task 4: revision 재동기화 | Task 1 | 소 |
| Task 5: importPending 차단 | 없음 | 소 |
| Task 6: TabActionBar UI | Task 1, Task 3 | 소 |
| Task 7: 하단 요약 바 | Task 2 | 소 |
| Task 8: 통합 검증 | Task 1~7 전체 | 중 |

> Task 1·5는 독립적으로 병렬 시작 가능. Task 2·3·4는 Task 1 완료 후 진행.
