# 구현 태스크: Reviewer 결정론 5단계 (EXE-15)

**Feature Branch**: `EXE-15-reviewer-deterministic`  **Created**: 2026-06-26

> **독자 안내**: 각 태스크는 "실패 테스트 작성 → 최소 구현 → 테스트 통과 → 커밋" 순서로 진행한다.
> 이 문서는 사람이 읽는 산출물이며, 자동 `/speckit-implement` 실행 대상이 아니다.

---

## 전제 조건

- `backend/services/reviewer.py`와 `harness/verifier_rules.json`이 존재한다.
- `backend/models/sprint_contract.py`의 SprintContract·ReviewResult·StepResult·InputUsed 모델이 정의되어 있다.
- 테스트 픽스처(최소 xlsx 워크북 생성 헬퍼)가 `tests/` 에 구성 가능하다.

---

## Task 1: 1원 정밀도 검증 — 수수료 구조 Stage 1 (FR-001a/b~FR-008)

**수용 기준**:
- 계약금액·집행금액 차이 계산 (FR-001a, FR-002a) → 1원 초과 시 FAIL 기록 (FR-001b, FR-002b)
- 역마진(집행단가 > 계약단가) → FAIL 기록 (FR-003)
- 당기수량 0.01 초과 오차 → FAIL 기록 (FR-004)
- 다년도 당기수량=전체수량 → FAIL / 단년도 당기수량<전체수량 → FAIL (FR-005, FR-006)
- 계약수량·계약단가 불일치 → FAIL 기록 (FR-007, FR-008)

### Step 1-A: 실패 테스트 작성

`tests/test_reviewer_stage1.py` 신규 생성.

```python
# 테스트: 역마진 감지
def test_margin_fail(make_wb, make_contract):
    """집행단가 > 계약단가이면 역마진 오류가 기록된다."""
    wb = make_wb(fee_rows=[{"H": 1, "I": 100, "K": 1, "L": 200}])  # L > I
    contract = make_contract(fee_items=[FeeItem(contract_unit_price=100, execution_unit_price=200)])
    result = _verify_fee_structure(wb, contract)
    assert not result["margin_structure_ok"]
    assert any("역마진" in e for e in result["errors"])

# 테스트: 1원 초과 오차 감지 (계약금액)
def test_contract_calc_1won_fail(make_wb, make_contract):
    """H×I와 contract_amount 차이가 1원 초과이면 계약 오류가 기록된다."""
    wb = make_wb(fee_rows=[{"H": 3, "I": 100}])  # H×I = 300
    contract = make_contract(fee_items=[FeeItem(contract_amount=302)])  # 차이=2, > 1원
    result = _verify_fee_structure(wb, contract)
    assert not result["contract_calc_ok"]

# 테스트: 다년도 연도분리 오류
def test_fiscal_year_split_fail(make_wb, make_contract):
    """다년도 사업에서 당기수량=전체수량이면 연도분리 오류가 기록된다."""
    wb = make_wb(fee_rows=[{"Q": 12, "execution_qty": 12}])
    contract = make_contract(
        fee_items=[FeeItem(execution_qty=12, current_period_qty=12)],
        project_period={"start": "2025-01-01", "end": "2026-12-31"}
    )
    result = _verify_fee_structure(wb, contract)
    assert not result["fiscal_year_split_ok"]
```

**예상 결과**: 모두 실패 (구현 전).

### Step 1-B: 최소 구현 확인

`reviewer.py:147 _verify_fee_structure` 코드가 이미 구현되어 있음. 주요 검증 포인트:

- `abs(expected_contract - item.contract_amount) > 1` → FAIL [공식 코드: `reviewer.py:173`]
- `l_val > i_val and i_val > 0` → 역마진 [공식 코드: `reviewer.py:192`]
- `start_year != end_year` + `q >= execution_qty` → 다년도 분리 오류 [공식 코드: `reviewer.py:207-209`]

추가 구현이 필요한 경우: harness/cell_map.json에 `fee_sheet.data_start_row` 등 상수가 있으면 `_load_fee_constants()`가 이를 로드한다. 없으면 기본값(8, 16, 17) 사용.

### Step 1-C: 테스트 통과 확인

```bash
cd /Users/toule/Documents/kiro/SI_\ Contract/backend
python -m pytest tests/test_reviewer_stage1.py -v
```

### Step 1-D: 커밋

```bash
git add backend/services/reviewer.py tests/test_reviewer_stage1.py
git commit -m "test(EXE-15): Stage 1 수수료 구조 결정론 검증 테스트"
```

---

## Task 2: 충돌 해결 검증 — Stage 2 (FR-009~FR-010)

**수용 기준**:
- user_choice=None인 충돌 항목 → "미해결 충돌" FAIL (FR-009)
- user_choice 있으나 resolved_value=None → "충돌 해결값 누락" FAIL (FR-010)
- 충돌 항목이 없으면 score=1.0, resolved_ok=True

### Step 2-A: 실패 테스트 작성

```python
# tests/test_reviewer_stage2.py

def test_unresolved_conflict_fail(make_contract):
    """user_choice가 None인 충돌이 있으면 resolved_ok=False."""
    contract = make_contract(conflict_resolutions=[
        ConflictResolution(conflict_type="B", description="단가 충돌", user_choice=None)
    ])
    result = _verify_conflict_resolution(contract, step_results={})
    assert not result["resolved_ok"]
    assert any("미해결 충돌" in e for e in result["errors"])

def test_missing_resolved_value_fail(make_contract):
    """user_choice는 있으나 resolved_value가 None이면 오류."""
    contract = make_contract(conflict_resolutions=[
        ConflictResolution(
            conflict_type="A", description="금액 충돌",
            user_choice="estimate_1", resolved_value=None
        )
    ])
    result = _verify_conflict_resolution(contract, step_results={})
    assert any("해결값 누락" in e for e in result["errors"])

def test_no_conflicts_score_1(make_contract):
    """충돌 항목이 없으면 score=1.0, resolved_ok=True."""
    contract = make_contract(conflict_resolutions=[])
    result = _verify_conflict_resolution(contract, step_results={})
    assert result["resolved_ok"]
    assert result["score"] == 1.0
```

### Step 2-B: 최소 구현 확인

`reviewer.py:248 _verify_conflict_resolution` 참조. [공식 코드: `reviewer.py:263-283`]

### Step 2-C: 테스트 통과 + 커밋

```bash
python -m pytest tests/test_reviewer_stage2.py -v
git add tests/test_reviewer_stage2.py
git commit -m "test(EXE-15): Stage 2 충돌 해결 검증 테스트"
```

---

## Task 3: 산출내역서 교차 검증 — Stage 3 (FR-011a/b~FR-014)

**수용 기준**:
- expected_salary 산출 (FR-011a) → 공통 시트 셀값과 차이 > 1원 → FAIL (FR-011b)
- 수수료 교차 차이 계산 (FR-012a) → 1원 초과 → FAIL (FR-012b)
- 보험료 요율 차이 > 0.0001 → FAIL (FR-013) [NEEDS CLARIFICATION: 헌법 §IV 금액 기반 기준과 충돌]
- 비활성 비목에 값 입력 → FAIL (FR-014)

### Step 3-A: 실패 테스트 작성

```python
# tests/test_reviewer_stage3.py

def test_salary_mismatch_fail(make_wb_common, make_contract):
    """급료 합계가 1원 초과 오차면 labor_sum_ok=False."""
    wb = make_wb_common(salary_cell_value=500_000)  # 공통시트 급료 셀
    contract = make_contract(
        staff_plan=[StaffItem(type="직접", monthly_rate=100_000, months=[5.0, 0, 0, ...])]
    )  # expected = 100_000 × 5 = 500_000 → 일치시 OK, 셀을 499_998로 바꾸면 차이=2 → FAIL
    # 오차 2원 케이스
    wb_fail = make_wb_common(salary_cell_value=499_998)
    result = _verify_breakdown(wb_fail, contract, step_results={})
    assert not result["labor_sum_ok"]
    assert any("노무비" in e for e in result["errors"])

def test_inactive_budget_item_fail(make_wb_common, make_contract):
    """비활성 비목(재료비=False)에 셀값이 있으면 오류."""
    wb = make_wb_common(material_cell_value=10_000)
    contract = make_contract(active_items={"재료비": False})
    result = _verify_breakdown(wb, contract, step_results={})
    assert any("비활성 비목" in e for e in result["errors"])
```

### Step 3-B: 최소 구현 확인

`reviewer.py:300 _verify_breakdown`. 공통 시트 col은 `_rev_col(contract.revision)`으로 결정된다. [공식 코드: `reviewer.py:311`]

### Step 3-C: 테스트 통과 + 커밋

```bash
python -m pytest tests/test_reviewer_stage3.py -v
git add tests/test_reviewer_stage3.py
git commit -m "test(EXE-15): Stage 3 산출내역서 교차 검증 테스트"
```

---

## Task 4: 갑지 검증 — Stage 4 (FR-015~FR-018)

**수용 기준**:
- 공통!F4 vs revenue 차이 > 1원 → FAIL (FR-015)
- 공통!P4 vs profit 차이 > 1원 → FAIL (FR-016) [NEEDS CLARIFICATION: FR-016 1원 임계 vs FR-016b 동적 임계 충돌]
- 공통!E3 vs project_name 불일치 → FAIL (FR-017)
- 기간 셀({col}125 또는 {col}126) None → FAIL (FR-018)

### Step 4-A: 실패 테스트 작성

```python
# tests/test_reviewer_stage4.py

def test_revenue_mismatch_fail(make_wb_common, make_contract):
    """공통!F4가 revenue 천원 변환값과 1원 초과 차이면 revenue_source_ok=False."""
    # revenue=100_000_000원 → 천원=100_000, 셀=99_999 → 차이=1 → FAIL
    wb = make_wb_common(f4=99_999)
    contract = make_contract(revenue=100_000_000)
    result = _verify_cover_sheet(wb, contract, step_results={})
    assert not result["revenue_source_ok"]

def test_period_not_filled_fail(make_wb_common, make_contract):
    """기간 시작일 셀이 None이면 기간 미입력 오류."""
    wb = make_wb_common(col125=None, col126="2025-12-31")
    contract = make_contract(
        project_period={"start": "2025-01-01", "end": "2025-12-31"}
    )
    result = _verify_cover_sheet(wb, contract, step_results={})
    assert any("기간 시작일" in e for e in result["errors"])
```

### Step 4-B: 최소 구현 확인

`reviewer.py:408 _verify_cover_sheet`. 단위 변환 조건: `value >= 1_000_000`이면 `/1000` 적용. [공식 코드: `reviewer.py:426-427`]

### Step 4-C: 테스트 통과 + 커밋

```bash
python -m pytest tests/test_reviewer_stage4.py -v
git add tests/test_reviewer_stage4.py
git commit -m "test(EXE-15): Stage 4 갑지 검증 테스트"
```

---

## Task 5: 기본정보 검증 — Stage 5 (FR-019a/b)

**수용 기준**:
- project_name·client·contractor·contract_type·pm·sales_owner·written_date 7개 필드 정규화 후 문자열 비교 (FR-019a) → score 계산
- 정규화 규칙: `.` → `-`, `/` → `-`, datetime suffix 제거 후 문자열 비교
- 불일치 있으면 필드명과 함께 오류 기록 (FR-019b)

### Step 5-A: 실패 테스트 작성

```python
# tests/test_reviewer_stage5.py

def test_project_name_mismatch_fail(make_wb_common, make_contract):
    """공통!E3 사업명이 confirmed_fields.project_name과 다르면 오류."""
    wb = make_wb_common(e3="GS네오텍 SI 프로젝트B")
    contract = make_contract(project_name="GS네오텍 SI 프로젝트A")
    result = _verify_basic_info(wb, contract)
    assert not result["project_name_ok"]
    assert any("project_name" in e for e in result["errors"])

def test_date_normalization_ok(make_wb_common, make_contract):
    """날짜 표기 차이(점-vs-하이픈)는 정규화 후 동일로 처리한다."""
    wb = make_wb_common(written_date_cell="2026.01.15")  # 점 표기
    contract = make_contract(written_date="2026-01-15")  # 하이픈
    result = _verify_basic_info(wb, contract)
    assert result["written_date_ok"]
    assert not any("written_date" in e for e in result["errors"])
```

### Step 5-B: 최소 구현 확인

`reviewer.py:500 _verify_basic_info` + `reviewer.py:89-94 _normalize_for_compare`. [공식 코드: `reviewer.py:523-530`]

### Step 5-C: 테스트 통과 + 커밋

```bash
python -m pytest tests/test_reviewer_stage5.py -v
git add tests/test_reviewer_stage5.py
git commit -m "test(EXE-15): Stage 5 기본정보 검증 테스트"
```

---

## Task 6: 판정(verdict) + 통합 run_review() (FR-020~FR-025)

**수용 기준**:
- 5단계 avg_score 산술평균 정확성 (FR-020)
- constraint_violations=0 AND avg_score ≥ 0.85 → "approved" (FR-022b) [공식: `harness/verifier_rules.json`]
- constraint_violations>0이면 "approved" 차단 (FR-021b)
- avg_score ≥ 0.60 AND < 0.85 → "needs_revision" (FR-021)
- avg_score < 0.60 → "rejected" (FR-022)
- 5단계 순서(1→5) 실행 (FR-023a)
- 이전 단계 실패 시에도 전단계 완료 (FR-023b)
- Executor reasoning 미사용 (FR-024) — 정적 코드 검토
- 차수 시트 NFC 해석 (FR-025)

### Step 6-A: 실패 테스트 작성

```python
# tests/test_reviewer_integration.py

def test_approved_verdict(make_wb_all_ok, make_contract_clean):
    """오류 0건, avg_score >= 0.85이면 verdict='approved'."""
    wb = make_wb_all_ok()
    contract = make_contract_clean()
    result, _ = run_review(contract, step_results={}, wb=wb)
    assert result.verdict == "approved"
    assert result.score >= 0.85

def test_revision_sheet_selection():
    """차수=1이면 '5-4. 수수료산출내역 (1차)' 시트가 선택된다."""
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.title = "5-4. 수수료산출내역 (1차)"
    ws = _resolve_sheet(wb, "5-4. 수수료산출내역", contract=None)
    assert ws.title == "5-4. 수수료산출내역 (1차)"

def test_information_barrier():
    """reviewer.py 소스에 step_results[x].notes 또는 reasoning 접근이 없다."""
    import ast, pathlib
    src = pathlib.Path("backend/services/reviewer.py").read_text()
    tree = ast.parse(src)
    # notes/reasoning 필드 접근 여부 검사
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ("notes", "reasoning"):
            raise AssertionError(f"정보 장벽 위반: .{node.attr} 접근 발견 line {node.lineno}")

def test_all_stages_executed_on_error():
    """Stage 1에 오류가 있어도 Stage 2~5가 모두 실행된다."""
    # Stage 1 FAIL 조건 + 나머지 OK 픽스처
    # run_review 결과에 5개 스테이지 점수 모두 존재하는지 확인
    result, _ = run_review(contract_with_stage1_error, {}, wb_ok)
    assert "fee_sheet" in result.amount_verification
    assert result.basic_info_verification is not None
```

### Step 6-B: 최소 구현 확인

`reviewer.py:545-659 run_review`. 순서: Stage 1→2→3→4→5, 중단 없음. `avg_score` 5단계 산술평균. [공식 코드: `reviewer.py:578-599`]

`verifier_rules.json` 임계 로드 실패 시 fallback `approved_t=0.85, revision_t=0.60`. [공식 코드: `reviewer.py:587-592`]

### Step 6-C: 테스트 통과 확인

```bash
python -m pytest tests/test_reviewer_integration.py -v
```

### Step 6-D: 최종 커밋

```bash
git add tests/test_reviewer_integration.py
git commit -m "test(EXE-15): run_review() 통합 + verdict + 정보 장벽 테스트"
```

---

## Task 7: 차수 시트 해석 — _resolve_sheet() (FR-025)

**수용 기준**:
- 정확히 base_name과 일치하는 시트 존재 → 그 시트 반환
- `"base_name (N차)"` 패턴 시트만 존재 → 가장 높은 N 반환
- 한글 NFC 분해/결합 차이 흡수 (`unicodedata.normalize`)

### Step 7-A: 실패 테스트 작성

```python
# tests/test_reviewer_resolve_sheet.py

def test_resolve_exact_match():
    wb = openpyxl.Workbook()
    wb.active.title = "5-4. 수수료산출내역"
    ws = _resolve_sheet(wb, "5-4. 수수료산출내역", None)
    assert ws.title == "5-4. 수수료산출내역"

def test_resolve_latest_revision():
    wb = openpyxl.Workbook()
    wb.active.title = "5-4. 수수료산출내역 (1차)"
    wb.create_sheet("5-4. 수수료산출내역 (3차)")
    wb.create_sheet("5-4. 수수료산출내역 (2차)")
    ws = _resolve_sheet(wb, "5-4. 수수료산출내역", None)
    assert ws.title == "5-4. 수수료산출내역 (3차)"

def test_resolve_nfc_normalization():
    """NFC로 정규화된 이름과 NFD로 저장된 이름이 일치해야 한다."""
    import unicodedata
    wb = openpyxl.Workbook()
    nfd_title = unicodedata.normalize("NFD", "5-4. 수수료산출내역")
    wb.active.title = nfd_title
    ws = _resolve_sheet(wb, "5-4. 수수료산출내역", None)
    assert ws is not None
```

### Step 7-B: 최소 구현 확인

`reviewer.py:43-67`. `unicodedata.normalize("NFC")` 사용, regex `\s*\((\d+)차\)` 패턴. [공식 코드: `reviewer.py:49-58`]

### Step 7-C: 테스트 통과 + 커밋

```bash
python -m pytest tests/test_reviewer_resolve_sheet.py -v
git add tests/test_reviewer_resolve_sheet.py
git commit -m "test(EXE-15): _resolve_sheet() 차수 시트 NFC 해석 테스트"
```

---

## Task 8: 게이트 체크리스트

모든 Task 완료 후 아래를 수동 확인한다.

- [ ] FR-001a/b~FR-025(FR-016b, FR-021b, FR-022b, FR-023a/b 포함) 전체가 테스트로 커버된다 (grep 확인)
- [ ] `reviewer.py`에 "should/적절히/가능하면" 류 변수명 없음 (코드 일관성)
- [ ] `harness/verifier_rules.json` precision=1 인용이 테스트 오차 1원에 반영됨
- [ ] 정보 장벽 정적 검사 통과 — `.notes` / `.reasoning` 접근 0건
- [ ] SC-001~SC-007 모두 테스트 케이스 1개 이상으로 커버됨
- [ ] [NEEDS CLARIFICATION] 항목(영업이익 역산 허용, 수수료코드 판단, 보험요율 연도)이 테스트에서 하드코딩값으로 검증되지 않고 별도 주석으로 표시됨

### 최종 커밋

```bash
git add specs/EXE-15
git commit -m "feat(sdd): EXE-15 Reviewer 결정론 5단계 spec/plan/tasks"
```
