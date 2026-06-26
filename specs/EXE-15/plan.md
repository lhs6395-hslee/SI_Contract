# 구현 계획: Reviewer 결정론 5단계 (EXE-15)

**Feature Branch**: `EXE-15-reviewer-deterministic`  **Created**: 2026-06-26  **Status**: Draft

---

## 아키텍처 개요

EXE-15는 **공유 엔진**이다. 파이프라인 오케스트레이터(`orchestrator.py`)가 Executor 완료 후 `run_review()`를 호출하며, Reviewer는 xlsx 워크북 셀값과 SprintContract 데이터를 직접 대조하는 결정론적 검증을 5단계로 수행한다. AI 의미검증(EXE-16)은 동일 `reviewer.py` 내 별도 함수(`_ai_semantic_review`)로 분리되어 있으나 EXE-15 스펙 범위가 아니다.

```
[Orchestrator]
    │
    ├─ Executor (Sprint_Contract 기입 완료)
    │
    └─ run_review(contract, step_results, wb)    ← EXE-15 진입점
           │
           ├─ Stage 1: _verify_fee_structure()   ← 수수료 구조
           ├─ Stage 2: _verify_conflict_resolution() ← 충돌 해결
           ├─ Stage 3: _verify_breakdown()       ← 산출내역서 교차
           ├─ Stage 4: _verify_cover_sheet()     ← 갑지
           ├─ Stage 5: _verify_basic_info()      ← 기본정보
           │
           └─ ReviewResult (verdict + score + violations)
```

---

## 기술 스택

| 레이어 | 기술 | 역할 |
|--------|------|------|
| 언어 | Python 3.14 | 백엔드 전반 |
| xlsx 읽기 | openpyxl (data_only=False) | 셀 원본값 읽기 — 수식 평가 불가 특성 활용 |
| 데이터 모델 | Pydantic v2 (`SprintContract`, `ReviewResult`) | 타입 안전 검증 |
| 검증 규칙 | `harness/verifier_rules.json` | 임계·허용 오차 선언적 분리 |
| 셀 매핑 | `harness/cell_map.json` | 행번호 상수 외부화 |
| 감사 기록 | `harness/long_term_memory.json` | 실행 결과 영속 |

---

## FR ↔ 컴포넌트 매핑

| FR | 함수 / 파일:라인 | 설명 |
|----|-----------------|------|
| FR-001a | `reviewer.py:147 _verify_fee_structure` / `reviewer.py:169-175` | 계약금액 차이 계산 |
| FR-001b | `reviewer.py:169-175` | 계약금액 1원 초과 오류 기록 |
| FR-002a | `reviewer.py:179-188` | 집행금액 차이 계산 |
| FR-002b | `reviewer.py:179-188` | 집행금액 1원 초과 오류 기록 |
| FR-003 | `reviewer.py:192-193` | 역마진 감지 |
| FR-004 | `reviewer.py:196-199` | 당기수량 0.01 허용 오차 검증 |
| FR-005 | `reviewer.py:202-209` | 다년도 연도분리 검증 |
| FR-006 | `reviewer.py:210-212` | 단년도 연도분리 검증 |
| FR-007 | `reviewer.py:221-223` | 계약수량 불일치 오류 기록 |
| FR-008 | `reviewer.py:224` | 계약단가 불일치 오류 기록 |
| FR-009 | `reviewer.py:248 _verify_conflict_resolution` / `reviewer.py:264-265` | 미해결 충돌 감지 |
| FR-010 | `reviewer.py:267-269` | 충돌 해결값 누락 감지 |
| FR-011a | `reviewer.py:300 _verify_breakdown` / `reviewer.py:315-328` | expected_salary 산출 |
| FR-011b | `reviewer.py:315-328` | 급료 합계 1원 초과 오류 기록 |
| FR-012a | `reviewer.py:331-354` | 수수료 교차 차이 계산 |
| FR-012b | `reviewer.py:331-354` | 수수료 교차 1원 초과 오류 기록 |
| FR-013 | `reviewer.py:359-388` | 보험료 요율 검증 [NEEDS CLARIFICATION] |
| FR-014 | `reviewer.py:391-394` | 비활성 비목 값 검증 |
| FR-015 | `reviewer.py:408 _verify_cover_sheet` / `reviewer.py:425-432` | 매출액 1원 초과 오류 기록 |
| FR-016 | `reviewer.py:436-444` | 영업이익 1원 초과 오류 기록 [NEEDS CLARIFICATION] |
| FR-016b | `reviewer.py:478` | 영업이익 동적 임계 WARN 처리 [NEEDS CLARIFICATION] |
| FR-017 | `reviewer.py:450-456` | 갑지 사업명 불일치 오류 기록 |
| FR-018 | `reviewer.py:460-469` | 기간 셀 입력 여부 검증 |
| FR-019a | `reviewer.py:500 _verify_basic_info` / `reviewer.py:507-530` | 기본정보 7개 필드 정규화 비교 |
| FR-019b | `reviewer.py:507-530` | 기본정보 불일치 오류 기록 |
| FR-020 | `reviewer.py:578-585 run_review` | 5단계 avg_score 산술평균 |
| FR-021 | `reviewer.py:594-596` | needs_revision 판정 |
| FR-021b | `reviewer.py:594` | constraint_violations>0이면 approved 차단 |
| FR-022 | `reviewer.py:597-599` | rejected 판정 |
| FR-022b | `reviewer.py:594` | approved 판정 (constraint_violations=0 AND avg_score>=0.85) |
| FR-023a | `reviewer.py:560-564` | 5단계 순서(1→5) 실행 |
| FR-023b | `reviewer.py:560-564` | 이전 단계 실패 시에도 전단계 완료 |
| FR-024 | `reviewer.py:1-17` (모듈 docstring), `reviewer.py:97-104` | 정보 장벽 보장 |
| FR-025 | `reviewer.py:43-67 _resolve_sheet` | 차수 시트 NFC 해석 |

---

## 데이터 흐름

```
SprintContract (from Executor)
  ├─ confirmed_fields  →  Stage 4(갑지), Stage 5(기본정보)
  ├─ fee_items         →  Stage 1(수수료 구조), Stage 3(수수료 교차)
  ├─ staff_plan        →  Stage 3(급료 합계)
  ├─ rates             →  Stage 3(보험료 요율), Stage 4(영업이익 역산)
  ├─ conflict_resolutions → Stage 2(충돌 해결)
  └─ active_items      →  Stage 3(비활성 비목)

openpyxl Workbook (xlsx 파일)
  ├─ "5-4. 수수료산출내역" (또는 N차 접미사)  →  Stage 1, Stage 3
  ├─ "공통" 시트                             →  Stage 3, Stage 4, Stage 5
  └─ _resolve_sheet()로 차수 시트명 자동 해석

harness/cell_map.json        →  행번호 상수 (Stage 1, 3 fallback)
harness/verifier_rules.json  →  임계·허용 오차 (Stage 1~5, verdict)

→ ReviewResult
  ├─ verdict: "approved" | "needs_revision" | "rejected"
  ├─ score: avg_score (float, 3자리 반올림)
  ├─ amount_verification: {fee_sheet, breakdown_sheet, cover_sheet}
  ├─ basic_info_verification
  ├─ constraint_violations: [{constraint, violation, severity, sheet, cell}]
  └─ issues: [str] (전 단계 오류 메시지 통합)
```

---

## 의존 관계

| 소비자 | EXE-15가 제공하는 것 | 비고 |
|--------|---------------------|------|
| `orchestrator.py` | `run_review()` 반환값 (`ReviewResult`) | 파이프라인 최종 단계 |
| `main.py` | `/api/pipeline` 엔드포인트가 ReviewResult를 응답에 포함 | FastAPI 라우터 |

| EXE-15가 소비하는 것 | 제공자 | 비고 |
|---------------------|--------|------|
| `SprintContract` | EXE-06 (Sprint_Contract 생성) | Executor 완료 후 수신 |
| `StepResult` (inputs_used) | Executor 각 단계 | Stage 2 충돌 검증에 간접 사용 |
| xlsx Workbook | EXE-12 (템플릿 생성) + EXE-13 (수정집행 차수) | openpyxl로 로드된 상태 |
| `verifier_rules.json` | `harness/verifier_rules.json` | 검증 임계 선언 |
| `cell_map.json` | `harness/cell_map.json` | 셀 행번호 매핑 |

**EXE-16(Reviewer AI 의미검증)과의 경계**: `run_review()` 내부에서 `_ai_semantic_review()`를 호출하지만, EXE-16은 별도 스펙으로 분리되어 있다. EXE-15는 결정론적 5단계(Stage 1~5)만 담당한다.

---

## 셀 접근 방식 (수식 체인 제약)

산출내역서 시트와 갑지 시트는 수식 체인(공통→집계표→산출내역서/갑지)으로 구성되어 `data_only=False` 모드에서 셀값이 None이다. 따라서:

- **산출내역서(Stage 3)**: 공통 시트 원본 셀값 + SprintContract 데이터를 직접 대조한다.
- **갑지(Stage 4)**: 공통 시트 원본 셀값(F4, P4, E3, {col}125, {col}126)과 confirmed_fields를 대조한다.
- **수수료 시트(Stage 1)**: 직접 입력 셀(H, I, J, K, L, M, Q, R열)을 읽는다.

[공식 코드: `reviewer.py:13-16` 모듈 docstring 셀 매핑 주석]

---

## 감사 기록

`run_review()` 완료 후 `harness_loader.record_run()`을 호출해 verdict·score·errors_count·token_usage를 `harness/long_term_memory.json`에 원자적으로 기록한다. 기록 실패는 파이프라인을 중단하지 않고 WARNING 로그만 남긴다. [공식 코드: `reviewer.py:627-639`]

---

## 비고: non-goal

- 파일 저장소 CRUD, 편집잠금, 챗봇, OTEL/RateLimit/Security 미들웨어 미포함.
- AI 의미검증(Bedrock 호출, `_ai_semantic_review`) = EXE-16 권역.
- 코드 구현·TDD·`/speckit-implement` 자동실행 비대상 (문서까지).
