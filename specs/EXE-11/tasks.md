# Tasks: EXE-11 — 연도분리 엔진 (공유)

**Created**: 2026-06-26  **Status**: Draft
**주의**: 이 tasks.md는 사람이 읽는 산출물이다. 자동 implement 비대상. 각 task는 실패 테스트 작성 → 최소 구현 → 테스트 통과 → 커밋 단위로 기술한다.

---

## Task 1: `_fiscal_year_shares` — 기본 비율 계산 (FR-001a·FR-001b·FR-004a~d)

**수용기준 출처**: SC-001, SC-002, SC-004 / spec.md US-1

### 구현할 동작

`_fiscal_year_shares(start_date, end_date, fiscal_year)` 가 사업 기간을 개월수(`total_mm`)로 환산하고(FR-001a), 당기/이후1/이후2/이전 비율을 각각 산출한 뒤(FR-004a~d), 비율 딕셔너리를 반환한다(FR-001b).

### 실패 테스트 (선작성)

```python
# tests/test_contract_builder.py

def test_fiscal_year_shares_basic():
    """다년도 사업 — 기본 비율 합계가 1.0이어야 한다."""
    from services.contract_builder import _fiscal_year_shares
    shares = _fiscal_year_shares("2025-09-01", "2026-09-30", 2025)
    assert shares is not None
    total = shares["current"] + shares["next1"] + shares["next2"] + shares["prev"]
    assert abs(total - 1.0) < 1e-6  # SC-002

def test_fiscal_year_shares_three_years():
    """3개 연도 이상 — prev/cur/next1/next2 모두 양수."""
    from services.contract_builder import _fiscal_year_shares
    shares = _fiscal_year_shares("2024-06-01", "2027-03-31", 2025)
    assert shares["prev"] > 0
    assert shares["current"] > 0
    assert shares["next1"] > 0
    assert shares["next2"] > 0
    total = shares["current"] + shares["next1"] + shares["next2"] + shares["prev"]
    assert abs(total - 1.0) < 1e-6
```

### 최소 구현

`contract_builder.py:160-190` 현행 코드가 구현 완료 상태. 테스트가 현행 코드 대비 회귀 없음을 검증하는 형태.

### 통과 기준

- `test_fiscal_year_shares_basic`: 합계 ≈ 1.0 (오차 1e-6 이내).
- `test_fiscal_year_shares_three_years`: prev/cur/next1/next2 모두 > 0, 합계 ≈ 1.0.

### 커밋

```
test(exe-11): _fiscal_year_shares 기본 비율 계산 회귀 테스트
```

---

## Task 2: `_fiscal_year_shares` — 단년도·예외 처리 (FR-002·FR-003)

**수용기준 출처**: SC-003, SC-004 / spec.md US-1 AC-2

### 구현할 동작

단년도 또는 파싱 불가 입력에서 `None`을 반환하며 예외를 전파하지 않는다.

### 실패 테스트

```python
def test_fiscal_year_shares_single_year_returns_none():
    """단년도 — None 반환 (연도분리 로직 미실행)."""
    from services.contract_builder import _fiscal_year_shares
    result = _fiscal_year_shares("2025-01-01", "2025-12-31", 2025)
    assert result is None  # SC-004

def test_fiscal_year_shares_invalid_date_returns_none():
    """파싱 실패 — 예외 없이 None 반환."""
    from services.contract_builder import _fiscal_year_shares
    result = _fiscal_year_shares("invalid", "2026-12-31", 2025)
    assert result is None  # SC-003

def test_fiscal_year_shares_none_fiscal_year():
    """fiscal_year=None — None 반환."""
    from services.contract_builder import _fiscal_year_shares
    result = _fiscal_year_shares("2025-01-01", "2026-12-31", None)
    assert result is None

def test_fiscal_year_shares_fiscal_year_out_of_range():
    """fiscal_year가 기간 밖 — None 반환."""
    from services.contract_builder import _fiscal_year_shares
    result = _fiscal_year_shares("2025-01-01", "2026-12-31", 2030)
    assert result is None
```

### 최소 구현

`contract_builder.py:169-178` 현행 코드 검증.

### 통과 기준

4개 테스트 모두 `None` 반환 및 예외 전파 없음.

### 커밋

```
test(exe-11): _fiscal_year_shares 단년도·예외 처리 회귀 테스트
```

---

## Task 3: `_split_by_shares` — 금액 배분·합계 보존 (FR-005a·FR-005b·FR-005c·FR-006)

**수용기준 출처**: SC-001 / spec.md US-2

### 구현할 동작

`_split_by_shares(amount, shares)` 가 prev=0 조건에서 `cur + nx1 + nx2 == round(amount)`를 100% 보장한다(잔여분 nx2 보정).

### 실패 테스트

```python
def test_split_by_shares_sum_preserved_no_prev():
    """prev=0 — 합계 = round(amount), 1원 오차 없음."""
    from services.contract_builder import _split_by_shares
    shares = {"current": 0.333, "next1": 0.334, "next2": 0.333, "prev": 0.0}
    cur, nx1, nx2 = _split_by_shares(10_000_000, shares)
    assert cur + nx1 + nx2 == 10_000_000  # SC-001

def test_split_by_shares_odd_amount():
    """반올림 후 잔여분이 발생하는 금액."""
    from services.contract_builder import _split_by_shares
    shares = {"current": 1/3, "next1": 1/3, "next2": 1/3, "prev": 0.0}
    cur, nx1, nx2 = _split_by_shares(10_000_001, shares)
    assert cur + nx1 + nx2 == 10_000_001

def test_split_by_shares_with_prev():
    """prev>0 — nx2는 비율 계산, cur+nx1+nx2 <= amount."""
    from services.contract_builder import _split_by_shares
    shares = {"current": 0.3, "next1": 0.3, "next2": 0.2, "prev": 0.2}
    cur, nx1, nx2 = _split_by_shares(10_000_000, shares)
    # prev 구간 제외이므로 합계 <= amount
    assert cur + nx1 + nx2 <= 10_000_000
    assert cur == round(10_000_000 * 0.3)
    assert nx1 == round(10_000_000 * 0.3)
    assert nx2 == round(10_000_000 * 0.2)
```

### 최소 구현

`contract_builder.py:193-201` 현행 코드 검증.

### 통과 기준

모든 케이스에서 합계 정합성 성립.

### 커밋

```
test(exe-11): _split_by_shares 금액 배분 합계 보존 회귀 테스트
```

---

## Task 4: `_mm_between` — 일할 계산 (FR-007a·FR-007b)

**수용기준 출처**: spec.md FR-007a·FR-007b / Edge Cases

### 구현할 동작

`_mm_between(start, end)` 가 시작일 1일 여부에 따라 해당 월을 1.0(FR-007a) 또는 일할 비율(분모 30, FR-007b)로 계산한다. `end < start`인 경우 0.0을 반환한다(spec.md Edge Cases).

### 실패 테스트

```python
def test_mm_between_full_months():
    """시작일=1일 — 시작월 1.0 포함."""
    from services.contract_builder import _mm_between
    from datetime import date
    result = _mm_between(date(2025, 1, 1), date(2025, 3, 31))
    assert result == 3.0  # 1월 1.0 + 2월 1.0 + 3월 1.0

def test_mm_between_mid_month_start():
    """시작일=중간 — 일할(분모 30) 적용."""
    from services.contract_builder import _mm_between
    from datetime import date
    result = _mm_between(date(2025, 1, 16), date(2025, 2, 28))
    # 1월: (31 - 16 + 1) / 30 = 16/30 ≈ 0.533, 2월: 1.0
    expected = (31 - 16 + 1) / 30 + 1.0
    assert abs(result - expected) < 1e-6

def test_mm_between_end_before_start():
    """end < start — 0.0 반환 (spec.md Edge Cases 명세).
    참고: 이 동작은 spec.md Edge Cases에 명세되어 있다."""
    from services.contract_builder import _mm_between
    from datetime import date
    result = _mm_between(date(2025, 6, 1), date(2025, 1, 1))
    assert result == 0.0
```

### 최소 구현

`contract_builder.py:147-157` 현행 코드 검증.

### 통과 기준

3개 케이스 모두 예상값 일치(1e-6 이내).

### 커밋

```
test(exe-11): _mm_between 일할 계산 회귀 테스트
```

---

## Task 5: `_calc_period_ratios` — 공통 시트 비율 기록 (FR-008a·FR-008b·FR-009·FR-010a·FR-010b)

**수용기준 출처**: SC-005 / spec.md US-3

### 구현할 동작

`_calc_period_ratios(start_str, end_str, fiscal_year)` 가 일수 기반으로 D13~D16 비율을 계산하고 `{13: float|None, 14: float|None, 15: float|None, 16: float|None}`을 반환한다.

### 실패 테스트

```python
def test_calc_period_ratios_multi_year():
    """다년도 — 비율 합계 ≈ 1.0 (None 제외)."""
    from services.excel.common_sheet import _calc_period_ratios
    ratios = _calc_period_ratios("2025-09-01", "2026-09-30", 2025)
    values = [v for v in ratios.values() if v is not None]
    assert abs(sum(values) - 1.0) < 1e-4  # SC-005

def test_calc_period_ratios_invalid_date():
    """파싱 실패 — 모두 None."""
    from services.excel.common_sheet import _calc_period_ratios
    ratios = _calc_period_ratios("bad-date", "2026-09-30", 2025)
    assert all(v is None for v in ratios.values())  # FR-009

def test_calc_period_ratios_three_years():
    """3개 연도 — prev(D13)/cur(D14)/next1(D15)/next2(D16) 모두 유효."""
    from services.excel.common_sheet import _calc_period_ratios
    ratios = _calc_period_ratios("2024-06-01", "2027-03-31", 2025)
    # prev(13), cur(14), next1(15), next2(16) 각각 양수
    assert ratios[13] is not None and ratios[13] > 0
    assert ratios[14] is not None and ratios[14] > 0
    assert ratios[15] is not None and ratios[15] > 0
    assert ratios[16] is not None and ratios[16] > 0
```

### 최소 구현

`common_sheet.py:16-63` 현행 코드 검증.

### 통과 기준

비율 합계 ≈ 1.0(1e-4 이내), 파싱 실패 시 전 None, 3연도 전체 양수.

### 커밋

```
test(exe-11): _calc_period_ratios 공통 시트 비율 회귀 테스트
```

---

## Task 6: FeeItem 연도분리·확인 플래그 (FR-011·FR-012)

**수용기준 출처**: SC-006, SC-007 / spec.md US-1 AC-3 이후

### 구현할 동작

`_build_fee_items` 에서 fy_shares 비nil 시 당기 금액을 비율로 산출하고 `ConflictResolution(conflict_type="연도배분확인")` 플래그를 반드시 생성한다. 사용자 명시값(currentQty/currentAmount)이 있으면 자동 배분을 건너뛴다.

### 실패 테스트

```python
def test_fee_items_carryover_flag_generated():
    """다년도 사업 — ConflictResolution '연도배분확인' 플래그 생성."""
    from services.contract_builder import _build_fee_items
    extracted = {"startDate": "2025-09-01", "endDate": "2026-09-30", "fiscalYear": 2025}
    cost_items = [{
        "category": "fee", "name": "PM", "unit": "M/M",
        "contractQty": 13, "executionQty": 13,
        "contractPrice": 6_000_000, "executionPrice": 5_500_000,
    }]
    fee_items, conflicts = _build_fee_items(extracted, cost_items)
    flag_types = [c.conflict_type for c in conflicts]
    assert "연도배분확인" in flag_types  # SC-006

def test_fee_items_explicit_current_skips_auto():
    """명시값(currentAmount) 있으면 자동 배분 skip — 플래그 없음."""
    from services.contract_builder import _build_fee_items
    extracted = {"startDate": "2025-09-01", "endDate": "2026-09-30", "fiscalYear": 2025}
    cost_items = [{
        "category": "fee", "name": "PM", "unit": "M/M",
        "contractQty": 13, "executionQty": 13,
        "contractPrice": 6_000_000, "executionPrice": 5_500_000,
        "currentAmount": 20_000_000,  # 사용자 명시값
    }]
    fee_items, conflicts = _build_fee_items(extracted, cost_items)
    flag_types = [c.conflict_type for c in conflicts]
    assert "연도배분확인" not in flag_types  # SC-007
    assert fee_items[0].current_period_amount == 20_000_000
```

### 최소 구현

`contract_builder.py:256-273` 현행 코드 검증.

### 통과 기준

- 다년도 자동 배분 시 플래그 1건 필수(SC-006).
- 명시값 존재 시 플래그 없고 명시값 그대로(SC-007).

### 커밋

```
test(exe-11): FeeItem 연도분리 자동 배분·명시값 우선 회귀 테스트
```

---

## Task 7: 통합 시나리오 — 전체 파이프라인 (SC-001~SC-007 종합)

**수용기준 출처**: 전체 SC

### 구현할 동작

`build_sprint_contract` 실행 시 다년도 사업에서 FeeItem 당기 금액 합계와 전체 집행 금액 비율이 fy_shares["current"]와 일치하는지 엔드투엔드 검증한다.

### 실패 테스트

```python
def test_sprint_contract_multi_year_fee_distribution():
    """SprintContract 생성 — 다년도 FeeItem 당기 금액 비율 정합성."""
    from services.contract_builder import build_sprint_contract, _fiscal_year_shares
    extracted_data = {
        "extracted": {
            "projectName": {"value": "테스트사업"},
            "startDate": {"value": "2025-09-01"},
            "endDate": {"value": "2026-09-30"},
            "fiscalYear": {"value": 2025},
        },
        "costItems": [{
            "category": "fee", "name": "PM", "unit": "M/M",
            "contractQty": 13, "executionQty": 13,
            "contractPrice": 6_000_000, "executionPrice": 5_500_000,
        }],
        "staffPlan": [], "schedule": [], "organization": [], "conflicts": [], "files": [],
    }
    contract = build_sprint_contract("proj-001", extracted_data, revision=0)
    shares = _fiscal_year_shares("2025-09-01", "2026-09-30", 2025)
    assert shares is not None
    # 당기 비율 검증 (1원 정밀도)
    total_exec = contract.fee_items[0].execution_amount
    cur_amount = contract.fee_items[0].current_period_amount
    expected_cur = round(total_exec * shares["current"])
    assert cur_amount == expected_cur  # SC-001

def test_sprint_contract_single_year_no_split():
    """단년도 — 연도분리 없이 전액 당기."""
    from services.contract_builder import build_sprint_contract
    extracted_data = {
        "extracted": {
            "projectName": {"value": "단년도사업"},
            "startDate": {"value": "2025-01-01"},
            "endDate": {"value": "2025-12-31"},
            "fiscalYear": {"value": 2025},
        },
        "costItems": [{
            "category": "fee", "name": "개발자", "unit": "M/M",
            "contractQty": 12, "executionQty": 12,
            "contractPrice": 6_000_000, "executionPrice": 5_500_000,
        }],
        "staffPlan": [], "schedule": [], "organization": [], "conflicts": [], "files": [],
    }
    contract = build_sprint_contract("proj-002", extracted_data, revision=0)
    fee = contract.fee_items[0]
    # 단년도: 당기 = 집행 전액
    assert fee.current_period_amount == fee.execution_amount
```

### 통과 기준

- 다년도: 당기 금액 = round(총액 × current_share) ± 0원.
- 단년도: 당기 금액 = 집행 전액.

### 커밋

```
test(exe-11): 통합 시나리오 — 다년도/단년도 FeeItem 배분 정합성
```

---

## Task 8: [TO-BE] 미구현 항목 추적 (구현 전 별도 사이클)

**이 task는 코드 변경 없음. 추적 목적.**

다음 항목은 현재 코드에 없으며 구현 전 NC-03 해소 및 사용자 확인 필요:

| 항목 | 기준 요구 | 선행 NC |
|------|----------|---------|
| `FeeItem.settlement_cumulative_qty/amount` 추가 | Kiro Req.3 | NC-03 |
| `SprintContract.is_multi_year` 플래그 | Kiro Req.9 | - |
| 이월 차수 생성 엔드포인트 | Kiro Req.10 | NC-03 |
| 정산누계 자동 누적 로직 | Kiro Req.8 | NC-03 |
| Fee_Sheet_Writer 정산누계 컬럼 기록 | Kiro Req.4 | NC-01 |

**진행 조건**: NC-01(비율 이원화), NC-02(일할 분모), NC-03(prev 귀속)이 해소된 뒤 별도 EXE-11 to-be 사이클 착수.
