# Implementation Plan: EXE-04 기본정보 확인 게이트

**Feature**: EXE-04 기본정보 확인 게이트 (프론트 전용)
**Created**: 2026-06-26  **Status**: Draft
**작업 깊이**: 문서까지 — 코드 구현/자동 implement 비대상 (헌법 §VII)

---

## 아키텍처 개요

EXE-04는 **프론트엔드 전용** 기능이다. 백엔드 게이트 엔드포인트가 존재하지 않으며, 상태 관리와 UI 로직 전체가 Next.js 클라이언트 컴포넌트 내에 구현된다.

```
[EXE-02 추출 결과]
        │
        ▼
extractedData (클라이언트 스토어 / useApp)
        │
        ▼
ReviewPage (review-page.tsx)
 ├─ useState<Set<string>>(confirmedTabs)   ← 로컬 게이트 상태
 ├─ tabStatus() 계산                        ← 탭 상태(ok/ready/warn)
 ├─ tabs[] 렌더링 (6개 + 조건부 history)
 ├─ TabActionBar per tab                   ← 확인/취소/재추출 UI
 └─ importPending → 익스포트 버튼 disabled  ← 단위 게이트 차단
```

**백엔드 의존 없음** — 이 기능의 모든 변경은 클라이언트 상태와 `ExtractedData` 타입에만 영향을 미친다.

---

## 기술 스택

| 계층 | 기술 | 버전/경로 |
|------|------|-----------|
| 프레임워크 | Next.js (App Router) | `frontend/` |
| 상태 관리 | React `useState` / `useEffect` | `react` |
| 글로벌 스토어 | `useApp()` (Zustand 또는 Context) | `frontend/lib/store` |
| 타입 정의 | TypeScript | `frontend/lib/types.ts` |
| UI 컴포넌트 | shadcn/ui (`Button`, `Badge`, `Alert`) | `frontend/components/ui/` |
| 아이콘 | lucide-react (`Check`, `AlertTriangle`) | — |

---

## FR ↔ 컴포넌트 매핑

| FR | 동작 요약 | 실제 컴포넌트 (file:line) |
|----|-----------|--------------------------|
| FR-001a | 6개 탭 렌더링 | `review-page.tsx:240-248` (tabs 배열 정의) |
| FR-001b | 초기 confirmedTabs Set 초기화 | `review-page.tsx:114-116` (`useState<Set<string>>(new Set(extractedData?.confirmedTabs || []))`) |
| FR-002a | 탭 상태 3단계(ok/ready/warn) 구분 계산 | `review-page.tsx:229-238` (`tabStatus()`) |
| FR-002b | 탭 상태를 색상 배지로 표시 | `review-page.tsx:774` (배지 색상 className 분기) |
| FR-003a | "확인 완료" 클릭 → 탭 상태 "ok" 설정 | `review-page.tsx:124-136` (`confirmTab()`) |
| FR-003b | "확인 완료" 클릭 → confirmedTabs Set에 추가 | `review-page.tsx:124-136` (`confirmTab()`) |
| FR-003c | "확인 완료" 클릭 → extractedData.confirmedTabs 배열에 추가 | `review-page.tsx:124-136` (`confirmTab()`) + `review-page.tsx:794` |
| FR-004a | "확인 취소" 클릭 → 탭 상태 이전 값으로 복원 | `review-page.tsx:138-150` (`unconfirmTab()`) |
| FR-004b | "확인 취소" 클릭 → confirmedTabs Set·배열에서 제거 | `review-page.tsx:138-150` (`unconfirmTab()`) + `review-page.tsx:795` |
| FR-005a | REQUIRED_FIELDS 미입력 시 basic 탭 warn 설정 | `review-page.tsx:167-172` (REQUIRED_FIELDS / missingRequired) + `review-page.tsx:231` |
| FR-005b | REQUIRED_FIELDS 미입력 시 미입력 필드 목록 렌더링 | `review-page.tsx:805` ("필수 미입력 N건" 렌더링) |
| FR-006a | guess 미확인 필드 시 basic 탭 warn 유지 | `review-page.tsx:154-155` (`guessEntries / guessCount`) + `review-page.tsx:231` |
| FR-006b | guess 미확인 필드 시 필드 목록 렌더링 | `review-page.tsx:807` ("확인 필요 N건" 렌더링) |
| FR-007 | 재추출 성공 완료 후 해당 탭 confirmedTabs 제거 | `review-page.tsx:316` (`unconfirmTab(tabId)`, `try` 블록 내 성공 직후) |
| FR-007b | 재추출 API 실패 시 confirmedTabs 불변 유지 | `review-page.tsx:316` (`unconfirmTab` 미호출 — `catch`/`finally` 경로) |
| FR-008 | revision/projectId 변경 시 confirmedTabs 재동기화 | `review-page.tsx:120-122` (`useEffect(() => setConfirmedTabs(...), [revision, projectId])`) |
| FR-009a | importPending 시 익스포트 버튼 disabled 설정 | `review-page.tsx:832-833` (`<Button ... disabled={importPending}>`) + `review-page.tsx:184` |
| FR-009b | importPending 시 "금액 단위 확정 필요" 텍스트 표시 | `review-page.tsx:832-833` (상태 텍스트 렌더링) |
| FR-010a | 재추출 중 버튼 비활성화 | `review-page.tsx:2055-2061` (`disabled={reExtracting}`) |
| FR-010b | 재추출 중 경과시간 표시 | `review-page.tsx:2055-2061` (`reExtractElapsed` 렌더링) |
| FR-011a | confirmedTabs 클라이언트 스토어에 배열로 영속 | `review-page.tsx:132-135` (`setExtractedData` 내 `confirmedTabs` 배열 갱신) + `frontend/lib/types.ts:106` |
| FR-011b | 페이지 재방문 시 이전 확인 상태 복원 | `review-page.tsx:114-116` (`useState` 초기값 — `extractedData?.confirmedTabs`) |

---

## 컴포넌트 상세

### `ReviewPage` (review-page.tsx:31)

EXE-04의 핵심 컴포넌트. 다음 로컬 상태를 소유한다:

- `confirmedTabs: Set<string>` — 확인 완료된 tabId 집합 (`useState`, line 114)
- `tabReExtracting: boolean` — 탭별 재추출 진행 중 여부 (`useState`, line 251)
- `verifiedFields: Set<string>` — 수동 확인 필드 집합 (`useState`, line 97)

주요 함수:

| 함수 | 위치 | 역할 |
|------|------|------|
| `confirmTab(tabId)` | line 124 | tabId를 confirmedTabs(Set) + extractedData.confirmedTabs(배열) 양쪽에 추가 |
| `unconfirmTab(tabId)` | line 138 | tabId를 confirmedTabs(Set) + extractedData.confirmedTabs(배열) 양쪽에서 제거 |
| `tabStatus(id)` | line 229 | 탭별 상태(ok/ready/warn) 계산 — confirmedTabs 우선, 이후 데이터 조건 분기 |
| `doTabReExtract(tabId)` | line 254 | 탭별 개별 재추출 실행, 완료 시 unconfirmTab 호출 |

### `TabActionBar` (review-page.tsx:2023)

탭 하단 확인/취소/재추출 액션 바. props:
- `confirmed: boolean` — 현재 탭 확인 여부
- `onConfirm / onUnconfirm` — 확인·취소 콜백
- `onReExtract` — 재추출 콜백
- `reExtracting: boolean` — 재추출 진행 중 여부 (버튼 비활성화 조건)

### `ExtractedData.confirmedTabs` (types.ts:106)

```typescript
confirmedTabs?: string[];  // types.ts:106
```

클라이언트 스토어 영속 배열. `Set<string>` 로컬 상태와 항상 쌍으로 갱신된다.

---

## 의존 관계

| 방향 | 대상 | 설명 |
|------|------|------|
| 소비 (Consumes) | EXE-02 소스추출 | `extractedData`(추출 결과 + `confirmedTabs` 초기값)가 EXE-02 결과물 |
| 생성 (Produces) | `confirmedTabs` 상태 | EXE-06(Sprint_Contract 생성)이 간접 소비 가능하나, 현재 코드에서 직접 의존 없음 |
| 익스포트 게이트 | `importPending` | EXE-14(import 역추출)의 `importMeta`/`unitConfirmed` 상태를 읽어 익스포트 차단 |

**백엔드 의존 없음**: EXE-04에 대응하는 FastAPI 엔드포인트가 존재하지 않는다. 설계 §3 코드 근거: `main.py` 엔드포인트 전수 확인 결과 기본정보 확인 게이트 엔드포인트 부재.

---

## 비범위 (non-goal)

- 확인 상태의 서버 동기화(백엔드 저장) — 현재 클라이언트 전용
- 탭 확인 여부를 기반으로 한 익스포트 차단 — 현재 `importPending`만이 차단 조건
- 편집잠금(`locked`) 기능 — 설계 §9 범위 밖
- 챗봇, OTEL, 보안 미들웨어 — 설계 §9 범위 밖
