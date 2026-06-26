# Tasks: EXE-06 — Sprint_Contract 생성

**Feature Branch**: `EXE-06-sprint-contract-build`
**Created**: 2026-06-26
**Status**: Draft

> 이 파일은 사람이 읽는 산출물이다. `/speckit-implement` 자동 실행 비대상 (constitution §VII).
> 각 태스크는 "실패 테스트 작성 → 최소 구현 → 통과 → 커밋" 단위로 구성된다.
> 수용기준은 spec.md의 Given/When/Then 및 Success Criteria에서 직접 도출한다.

---

## Task 1: MAX_REVISION 초과 거부 게이트 검증

**수용기준**: SC-003 — revision > 11 요청 100% HTTP 400 거부  
**관련 FR**: FR-002

### 실패 테스트 (먼저 작성)

```python
# tests/test_contract_builder.py
def test_revision_over_max_raises():
    """revision=12 시 ValueError 발생 확인 (contract_builder 레이어)."""
    import pytest
    from services.contract_builder import build_sprint_contract
    with pytest.raises(ValueError, match="최대 11차"):
        build_sprint_contract("proj_x", {}, revision=12)

# tests/test_api_pipeline.py
async def test_pipeline_start_revision_over_max_returns_400(client):
    """main.py API 레이어 — revision=12 → HTTP 400."""
    resp = await client.post("/api/pipeline/start", json={
        "projectId": "proj_x", "extractedData": {"extracted": {}}, "revision": 12
    })
    assert resp.status_code == 400
    assert "11" in resp.json()["error"]
```

### 최소 구현 확인 사항

- `company_standards.py:12` MAX_REVISION=11 현행값 확인 (변경 없음)
- `main.py:729-734` HTTP 400 분기 현행 동작 확인
- `contract_builder.py:307` ValueError 현행 동작 확인

### 통과 기준

두 레이어(API/빌더) 모두 테스트 통과. revision=11은 정상 통과, revision=12는 거부.

### 커밋

```
test(exe-06): MAX_REVISION 초과 거부 양측 레이어 테스트
```

---

## Task 2: ConfirmedFields 매핑 검증

**수용기준**: SC-001(부분) — 동일 입력에 동일 출력, 1초 이내  
**관련 FR**: FR-003

### 실패 테스트

```python
def test_confirmed_fields_mapping():
    """extracted 딕셔너리의 값이 ConfirmedFields로 정확히 매핑되는지 확인."""
    from services.contract_builder import build_sprint_contract
    data = {
        "extracted": {
            "projectName": {"value": "테스트 사업"},
            "startDate":   {"value": "2026-01-01"},
            "endDate":     {"value": "2026-12-31"},
            "fiscalYear":  {"value": "2026"},
            "client":      {"value": "발주처A"},
            "contractor":  {"value": "계약처B"},
        },
        "costItems": [], "staffPlan": [], "rates": None,
        "conflicts": [], "files": [], "schedule": [], "organization": [],
    }
    contract = build_sprint_contract("p1", data, revision=0)
    cf = contract.confirmed_fields
    assert cf.project_name == "테스트 사업"
    assert cf.project_period["start"] == "2026-01-01"
    assert cf.fiscal_year == "2026"
    assert cf.client == "발주처A"
```

### 최소 구현 확인 사항

- `contract_builder.py:327-349` ConfirmedFields 블록이 모든 필드를 커버하는지 확인
- writtenDate 없을 때 오늘 날짜로 채워지는지 확인 (`contract_builder.py:325`)

### 통과 기준

테스트 통과. `cf.written_date`가 None이 아니고 ISO 날짜 형식임.

### 커밋

```
test(exe-06): ConfirmedFields 매핑 검증 테스트
```

---

## Task 3: FeeItem 변환 및 일할계산 검증

**수용기준**: SC-002(FeeItem 연도분리), SC-006(VAT 제외)  
**관련 FR**: FR-004a, FR-004b, FR-014

### 실패 테스트

```python
def test_fee_item_prorated_qty():
    """월 중간 시작(2026-01-15), M/M 단위 → 일할계산 수량 검증."""
    from services.contract_builder import _calc_prorated_qty
    qty = _calc_prorated_qty("2026-01-15", "2026-06-30", 6)
    # 1월: (31-15+1)/30 = 17/30 ≈ 0.567, 2~6월: 5개월 → 합 ≈ 5.567 → 반올림 5.6
    assert qty == 5.6, f"기대 5.6 실제 {qty}"

def test_fee_item_vat_excluded():
    """VAT 항목은 BudgetItem 집계에서 제외."""
    from services.contract_builder import build_sprint_contract
    data = {
        "extracted": {"startDate": {"value": "2026-01-01"}, "endDate": {"value": "2026-12-31"}},
        "costItems": [
            {"category": "labor", "name": "노무비", "contractAmount": 1000000, "executionAmount": 900000},
            {"category": "labor", "name": "부가세(VAT)", "contractAmount": 100000, "executionAmount": 90000},
        ],
        "staffPlan": [], "rates": None, "conflicts": [], "files": [], "schedule": [], "organization": [],
    }
    contract = build_sprint_contract("p2", data)
    # VAT 항목 BudgetItem에 없어야 함
    assert all("VAT" not in (b.desc or "") and "부가세" not in (b.desc or "")
               for b in contract.budget_items)
```

### 최소 구현 확인 사항

- `_calc_prorated_qty` 함수 동작 (분모 30 고정, 0.1 단위 반올림)
- `contract_builder.py:382-384` VAT 키워드 필터 현행 동작

### 통과 기준

일할계산 수량 및 VAT 제외 테스트 통과.

### 커밋

```
test(exe-06): FeeItem 일할계산 + VAT 제외 검증
```

---

## Task 4: BudgetItem 이중계상 방어 검증

**수용기준**: SC-006 — 퇴직금·보험료 0건 포함  
**관련 FR**: FR-005

### 실패 테스트

```python
def test_auto_calculated_excluded():
    """퇴직금·국민연금이 BudgetItem에 포함되지 않아야 함."""
    from services.contract_builder import build_sprint_contract
    data = {
        "extracted": {},
        "costItems": [
            {"category": "labor", "name": "노무비", "contractAmount": 1000000, "executionAmount": 900000},
            {"category": "labor", "name": "퇴직금", "contractAmount": 75000, "executionAmount": 70000},
            {"category": "labor", "name": "국민연금", "contractAmount": 45000, "executionAmount": 40000},
        ],
        "staffPlan": [], "rates": None, "conflicts": [], "files": [], "schedule": [], "organization": [],
    }
    contract = build_sprint_contract("p3", data)
    desc_texts = " ".join(b.desc or "" for b in contract.budget_items)
    assert "퇴직금" not in desc_texts
    assert "국민연금" not in desc_texts
    # "자동계산중복" 플래그 생성 확인
    conflict_types = [c.conflict_type for c in contract.conflict_resolutions]
    assert "자동계산중복" in conflict_types
```

### 최소 구현 확인 사항

- `company_standards.py:43-50 AUTO_CALCULATED_KEYWORDS` 목록 확인
- `contract_builder.py:376-381` is_auto_calculated 필터 현행 동작

### 통과 기준

테스트 통과. 자동계산 항목 0건 + 플래그 생성.

### 커밋

```
test(exe-06): 퇴직금·보험료 이중계상 방어 검증
```

---

## Task 5: 연도분리(EXE-11 엔진) 정합성 검증

**수용기준**: SC-002 — current+next1+next2 합 = execution_amount (1원 오차 FAIL)  
**관련 FR**: FR-007

### 실패 테스트

```python
def test_year_split_sum_preservation():
    """연도 경계 걸침 시 BudgetItem 배분 합계가 execution_amount와 1원 일치."""
    from services.contract_builder import build_sprint_contract
    data = {
        "extracted": {
            "startDate":  {"value": "2025-09-01"},
            "endDate":    {"value": "2026-06-30"},
            "fiscalYear": {"value": "2025"},
        },
        "costItems": [
            {"category": "labor", "name": "노무비",
             "contractAmount": 10_000_000, "executionAmount": 9_000_000},
        ],
        "staffPlan": [], "rates": None, "conflicts": [], "files": [], "schedule": [], "organization": [],
    }
    contract = build_sprint_contract("p4", data)
    for b in contract.budget_items:
        total = b.current_amount + b.next1_amount + b.next2_amount
        assert abs(total - b.execution_amount) <= 1, (
            f"[{b.category}] current+next1+next2={total} ≠ execution={b.execution_amount}"
        )
    # "연도배분확인" 플래그 생성 확인
    types = [c.conflict_type for c in contract.conflict_resolutions]
    assert "연도배분확인" in types

def test_fy_shares_ratio_sum():
    """_fiscal_year_shares: current+next1+next2+prev 합이 1.0 (±0.001)."""
    from services.contract_builder import _fiscal_year_shares
    shares = _fiscal_year_shares("2025-09-01", "2026-06-30", 2025)
    assert shares is not None
    ratio_sum = shares["current"] + shares["next1"] + shares["next2"] + shares["prev"]
    assert abs(ratio_sum - 1.0) < 0.001, f"비율 합 = {ratio_sum}"
```

### 최소 구현 확인 사항

- `_fiscal_year_shares` (:160): prev=0 시 nx2 잔여분 보존 (`_split_by_shares` :197-199)
- `_split_by_shares` (:193): prev < 1e-9 일 때 nx2 = round(amount) - cur - nx1 (합계 보존)

### 통과 기준

두 테스트 통과. 1원 오차 없음.

### 커밋

```
test(exe-06): 연도분리 합계 보존 정합성 검증 (EXE-11 공유 함수)
```

---

## Task 6: 급료 자동산출 및 관문 플래그 검증

**수용기준**: User Story 4 — labor 없고 staffPlan 있으면 급료 자동산출  
**관련 FR**: FR-008, FR-009

### 실패 테스트

```python
def test_labor_auto_generated_from_staff_plan():
    """staffPlan에 내부 인원, costItems에 labor 없음 → 급료 BudgetItem 자동 생성."""
    from services.contract_builder import build_sprint_contract
    data = {
        "extracted": {
            "startDate": {"value": "2026-01-01"},
            "endDate":   {"value": "2026-06-30"},
        },
        "costItems": [],  # labor 없음
        "staffPlan": [
            {"name": "김철수", "grade": "과장", "type": "직접",
             "totalMM": 6, "monthlyRate": 0, "months": [1,1,1,1,1,1,0,0,0,0,0,0]}
        ],
        "rates": None, "conflicts": [], "files": [], "schedule": [], "organization": [],
    }
    contract = build_sprint_contract("p5", data)
    labor_items = [b for b in contract.budget_items if b.category == "labor"]
    assert len(labor_items) == 1, "급료 BudgetItem이 1건 생성되어야 함"
    # GRADE_RATES["과장"] = 5_500_000 (company_standards.py:19) — 잠정값
    assert labor_items[0].execution_amount == 5_500_000 * 6
    # "급료확인" 플래그 생성
    types = [c.conflict_type for c in contract.conflict_resolutions]
    assert "급료확인" in types

def test_labor_grade_mismatch_flag():
    """문서 급여와 사내 단가표 불일치 → '급료단가확인' 플래그 생성, 입력값 불변."""
    from services.contract_builder import build_sprint_contract
    data = {
        "extracted": {
            "startDate": {"value": "2026-01-01"},
            "endDate":   {"value": "2026-06-30"},
        },
        "costItems": [
            {"category": "labor", "name": "노무비",
             "contractAmount": 10_000_000, "executionAmount": 7_200_000}  # 과장 단가표(5500만×6=33M)와 다름
        ],
        "staffPlan": [
            {"name": "이영희", "grade": "과장", "type": "직접",
             "totalMM": 6, "monthlyRate": 1_200_000}  # 사내기준과 다른 문서 급여
        ],
        "rates": None, "conflicts": [], "files": [], "schedule": [], "organization": [],
    }
    contract = build_sprint_contract("p6", data)
    types = [c.conflict_type for c in contract.conflict_resolutions]
    assert "급료단가확인" in types
    # 입력값(7_200_000)은 변경되지 않아야 함
    labor = next(b for b in contract.budget_items if b.category == "labor")
    assert labor.execution_amount == 7_200_000
```

### 주의

- `GRADE_RATES["과장"] = 5_500_000` (`company_standards.py:19`)은 **잠정값**이다.
  직급 단가표 3중 충돌이 해소되면 이 테스트의 기대값을 업데이트해야 한다.
  (`[NEEDS CLARIFICATION]` — spec.md Clarifications Retained 항목 1)

### 커밋

```
test(exe-06): 급료 자동산출 + 단가 불일치 플래그 검증
```

---

## Task 7: 요율확인 플래그 무조건 생성 검증

**수용기준**: SC-004 — 요율확인 플래그 정확히 1건  
**관련 FR**: FR-010

### 실패 테스트

```python
import pytest

@pytest.mark.parametrize("rates_data", [
    None,       # rates 없음 → DEFAULT_RATES 사용
    {"indirectRate": {"value": 2.0}},  # 업로드 문서 값
])
def test_rate_confirmation_flag_always_generated(rates_data):
    """rates 출처 무관하게 '요율확인' 플래그가 정확히 1건 생성."""
    from services.contract_builder import build_sprint_contract
    data = {
        "extracted": {}, "costItems": [], "staffPlan": [],
        "rates": rates_data, "conflicts": [], "files": [], "schedule": [], "organization": [],
    }
    contract = build_sprint_contract("p7", data)
    rate_flags = [c for c in contract.conflict_resolutions if c.conflict_type == "요율확인"]
    assert len(rate_flags) == 1, f"요율확인 플래그 1건 기대, 실제 {len(rate_flags)}건"
```

### 커밋

```
test(exe-06): 요율확인 플래그 무조건 1건 생성 검증
```

---

## Task 8: active_items 9개 키 완전성 검증

**수용기준**: SC-005 — active_items 딕셔너리 9개 키 전부 포함  
**관련 FR**: FR-012

### 실패 테스트

```python
def test_active_items_keys_complete():
    """active_items에 9개 키가 모두 포함되어야 함."""
    from services.contract_builder import build_sprint_contract
    contract = build_sprint_contract("p8", {
        "extracted": {}, "costItems": [], "staffPlan": [],
        "rates": None, "conflicts": [], "files": [], "schedule": [], "organization": [],
    })
    expected_keys = {
        "재료비", "노무비", "외주비",
        "경비_복리후생비", "경비_보험료", "경비_수수료",
        "경비_회선비", "경비_소모품비", "경비_여비교통비",
    }
    assert set(contract.active_items.keys()) == expected_keys
```

### 커밋

```
test(exe-06): active_items 9개 키 완전성 검증
```

---

## Task 9: 계약배분 자동 처리 및 플래그 검증

**수용기준**: User Story(FR-013) — 계약금액 배분 없을 때 노무비에 매출 전액 배분  
**관련 FR**: FR-013

### 실패 테스트

```python
def test_revenue_auto_assigned_to_labor_when_no_contract():
    """계약금액 배분 없을 때 매출 전액을 노무비 contract_amount로 배분."""
    from services.contract_builder import build_sprint_contract
    data = {
        "extracted": {"revenue": {"value": 10_000_000}},
        "costItems": [
            {"category": "labor", "name": "노무비",
             "contractAmount": 0, "executionAmount": 9_000_000}  # contractAmount=0
        ],
        "staffPlan": [], "rates": None, "conflicts": [], "files": [], "schedule": [], "organization": [],
    }
    contract = build_sprint_contract("p9", data)
    labor = next((b for b in contract.budget_items if b.category == "labor"), None)
    assert labor is not None
    assert labor.contract_amount == 10_000_000
    types = [c.conflict_type for c in contract.conflict_resolutions]
    assert "계약배분확인" in types
```

### 커밋

```
test(exe-06): 계약배분 자동 처리 + 플래그 검증
```

---

## Task 10: prev_revisions 이전 차수 데이터 포함 검증

**수용기준**: User Story 3(revision), FR-011a/FR-011b  
**관련 FR**: FR-011a, FR-011b

### 실패 테스트

```python
def test_prev_revisions_included_in_contract():
    """revision=1 시 prev_revisions에 revision=0 데이터가 포함."""
    from services.contract_builder import build_sprint_contract
    prev_data = {
        "0": {
            "extracted": {"projectName": {"value": "이전사업"}},
            "costItems": [], "staffPlan": [], "rates": None,
            "conflicts": [], "files": [], "schedule": [], "organization": [],
        }
    }
    contract = build_sprint_contract("p10", {
        "extracted": {}, "costItems": [], "staffPlan": [],
        "rates": None, "conflicts": [], "files": [], "schedule": [], "organization": [],
    }, revision=1, prev_revisions=prev_data)
    assert "0" in contract.prev_revisions
```

### 커밋

```
test(exe-06): prev_revisions 이전 차수 포함 검증
```

---

## Task 11: 통합 — 전체 수용기준 회귀 실행

**수용기준**: SC-001~SC-006 전체 (SC-007은 Clarifications Retained으로 이동됨)

### 실행 명령

```bash
# backend/ 디렉토리에서
python -m pytest tests/test_contract_builder.py tests/test_api_pipeline.py -v --tb=short
```

### 체크리스트

- [ ] Task 1~10 테스트 모두 통과
- [ ] revision > 11 → 100% 거부 (SC-003)
- [ ] 연도분리 합계 1원 이하 오차 (SC-002)
- [ ] 요율확인 플래그 정확히 1건 (SC-004)
- [ ] active_items 9개 키 전부 (SC-005)
- [ ] VAT·퇴직금·보험료 BudgetItem 0건 (SC-006)
- [ ] `[NEEDS CLARIFICATION]` 항목(직급단가표·이원화된 요율·MAX_REVISION 이중 게이트)은 테스트에 주석으로 명시하고 확정 전까지 잠정값 사용

### 커밋

```
test(exe-06): EXE-06 Sprint_Contract 생성 통합 회귀 완료
feat(sdd): EXE-06 Sprint_Contract 생성 spec/plan/tasks
```

---

## 미해결 사항 (구현 전 확인 필요)

| 항목 | 현황 | 필요 조치 |
|------|------|----------|
| 직급단가표 3중 충돌 | 코드=550만, executor.md=600만, REPORT=650만 | 사용자 확정 → 테스트 기대값 업데이트 |
| MAX_REVISION 이중 게이트 | main.py:729 + contract_builder.py:307 양측 | 단일 진입점 결정 후 한 쪽 제거 |
| 간접·관리비율 공문 근거 | 주석만 ("윤지민과장 25년 기준") | 공문 수령 후 DEFAULT_RATES 갱신 |
| 보험요율 이원화 | DEFAULT_RATES 값 = 정산 기준인지 집행 기준인지 미정 | 집행/정산 구분 확인 후 갱신 |
