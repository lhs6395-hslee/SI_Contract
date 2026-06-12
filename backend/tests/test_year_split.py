"""연도분리(_fiscal_year_shares/_split_by_shares) + 수수료/비목 당기 배분 단위 테스트."""
import pytest

from services.contract_builder import (
    _calc_prorated_qty,
    _fiscal_year_shares,
    _mm_between,
    _parse_fiscal_year,
    _split_by_shares,
    _build_fee_items,
    build_sprint_contract,
)


def _date(s):
    from datetime import date
    return date.fromisoformat(s)


class TestMmBetween:
    def test_full_months(self):
        assert _mm_between(_date("2025-10-01"), _date("2026-03-31")) == 6.0

    def test_mid_month_start_prorated_by_30(self):
        # 10/15 시작 → 10월 잔여 17일/30 + 11월~3월 5개월
        assert _mm_between(_date("2025-10-15"), _date("2026-03-31")) == pytest.approx(17 / 30 + 5)

    def test_end_before_start_is_zero(self):
        assert _mm_between(_date("2026-03-31"), _date("2025-10-01")) == 0.0


class TestParseFiscalYear:
    def test_plain_and_suffixed(self):
        assert _parse_fiscal_year({"fiscalYear": {"value": "2025"}}) == 2025
        assert _parse_fiscal_year({"fiscalYear": {"value": "2025년"}}) == 2025

    def test_fallback_to_start_date(self):
        assert _parse_fiscal_year({"startDate": {"value": "2024-12-01"}}) == 2024

    def test_missing(self):
        assert _parse_fiscal_year({}) is None


class TestFiscalYearShares:
    def test_single_year_returns_none(self):
        assert _fiscal_year_shares("2026-01-01", "2026-12-31", 2026) is None

    def test_a1_half_split(self):
        s = _fiscal_year_shares("2025-10-01", "2026-03-31", 2025)
        assert s["current"] == pytest.approx(0.5)
        assert s["next1"] == pytest.approx(0.5)
        assert s["next2"] == 0.0
        assert s["prev"] == 0.0

    def test_24_months_three_buckets(self):
        s = _fiscal_year_shares("2025-07-01", "2027-06-30", 2025)
        assert s["current"] == pytest.approx(6 / 24)
        assert s["next1"] == pytest.approx(12 / 24)
        assert s["next2"] == pytest.approx(6 / 24)

    def test_next2_absorbs_remaining_years(self):
        # 4개년: 이후2 = fy+2~종료 (2026+2027 = 24/48)
        s = _fiscal_year_shares("2024-01-01", "2027-12-31", 2024)
        assert s["next2"] == pytest.approx(24 / 48)

    def test_mid_project_fiscal_year_separates_prev(self):
        # 다년도 사업의 중간 차수: fy=2025, 2024-12 시작 → prev=1MM/36
        s = _fiscal_year_shares("2024-12-01", "2027-11-30", 2025)
        assert s["prev"] == pytest.approx(1 / 36)
        assert s["current"] == pytest.approx(12 / 36)

    def test_fy_outside_period_returns_none(self):
        assert _fiscal_year_shares("2025-10-01", "2026-03-31", 2028) is None

    def test_invalid_dates_return_none(self):
        assert _fiscal_year_shares(None, "2026-03-31", 2025) is None
        assert _fiscal_year_shares("2026-03-31", "2025-10-01", 2025) is None


class TestSplitByShares:
    def test_sum_preserved_without_prev(self):
        s = _fiscal_year_shares("2025-07-01", "2027-06-30", 2025)
        cur, nx1, nx2 = _split_by_shares(240_000_000, s)
        assert cur + nx1 + nx2 == 240_000_000

    def test_prev_not_absorbed_into_next2(self):
        s = _fiscal_year_shares("2024-12-01", "2027-11-30", 2025)
        cur, nx1, nx2 = _split_by_shares(36_000_000, s)
        # prev(1MM=1,000,000)는 어느 버킷에도 들어가지 않음
        assert cur + nx1 + nx2 == 35_000_000


def _fee_fixture(start, end, fy, qty=6, cprice=9_000_000, eprice=7_500_000, **item_kw):
    extracted = {
        "startDate": {"value": start}, "endDate": {"value": end},
        "fiscalYear": {"value": fy},
    }
    item = {
        "category": "fee", "name": "운영", "unit": "M/M", "vendor": "V",
        "contractQty": qty, "contractPrice": cprice, "contractAmount": qty * cprice,
        "executionQty": qty, "executionPrice": eprice, "executionAmount": qty * eprice,
    }
    item.update(item_kw)
    return extracted, [item]


class TestBuildFeeItems:
    def test_year_boundary_auto_split(self):
        extracted, items = _fee_fixture("2025-10-01", "2026-03-31", "2025")
        fees, conflicts = _build_fee_items(extracted, items)
        assert fees[0].current_period_qty == pytest.approx(3.0)
        assert fees[0].current_period_amount == pytest.approx(22_500_000)
        assert any(c.conflict_type == "연도배분확인" for c in conflicts)

    def test_single_year_keeps_full_amount(self):
        extracted, items = _fee_fixture("2026-01-01", "2026-06-30", "2026")
        fees, conflicts = _build_fee_items(extracted, items)
        assert fees[0].current_period_qty == 6
        assert fees[0].current_period_amount == 45_000_000
        assert not conflicts

    def test_explicit_current_qty_wins_over_auto_split(self):
        # 자동 처리 금지 원칙: 사용자 확인값(currentQty/currentAmount) 최우선
        extracted, items = _fee_fixture(
            "2025-10-01", "2026-03-31", "2025", currentQty=5, currentAmount=37_500_000)
        fees, conflicts = _build_fee_items(extracted, items)
        assert fees[0].current_period_qty == 5
        assert fees[0].current_period_amount == 37_500_000
        assert not any(c.conflict_type == "연도배분확인" for c in conflicts)

    def test_decimal_qty_no_proration(self):
        # 소수점 수량(주말 0.3MM/월)은 일할계산 미적용
        extracted, items = _fee_fixture("2026-01-03", "2026-06-28", "2026",
                                        qty=1.8, cprice=15_000_000, eprice=12_000_000)
        fees, _ = _build_fee_items(extracted, items)
        assert fees[0].execution_qty == 1.8
        assert fees[0].current_period_amount == pytest.approx(1.8 * 12_000_000)


class TestCalcProratedQty:
    def test_month_start_unchanged(self):
        assert _calc_prorated_qty("2026-03-01", "2026-12-31", 10) == 10

    def test_mid_month_prorated(self):
        # 퀘이사존 사례: 3/23 시작 → 9일/30 + 9개월 = 9.3
        assert _calc_prorated_qty("2026-03-23", "2026-12-31", 10) == pytest.approx(9.3)


class TestBuildSprintContract:
    def _payload(self, cost_items, start="2025-07-01", end="2027-06-30", fy="2025"):
        return {
            "extracted": {
                "projectName": {"value": "T"}, "startDate": {"value": start},
                "endDate": {"value": end}, "fiscalYear": {"value": fy},
                "writtenDate": {"value": "2025-06-01"},
            },
            "costItems": cost_items,
        }

    def test_budget_year_split_sum_preserved(self):
        c = build_sprint_contract("t", self._payload(
            [{"category": "welfare", "name": "복리후생", "executionAmount": 24_000_000}]))
        b = next(b for b in c.budget_items if b.category == "welfare")
        assert (b.current_amount, b.next1_amount, b.next2_amount) == (6_000_000, 12_000_000, 6_000_000)
        assert any(cf.conflict_type == "연도배분확인" for cf in c.conflict_resolutions)

    def test_budget_explicit_current_wins(self):
        c = build_sprint_contract("t", self._payload(
            [{"category": "welfare", "name": "복리후생", "executionAmount": 24_000_000,
              "currentAmount": 10_000_000, "next1Amount": 14_000_000}]))
        b = next(b for b in c.budget_items if b.category == "welfare")
        assert b.current_amount == 10_000_000
        assert b.next1_amount == 14_000_000

    def test_single_year_budget_full_current(self):
        c = build_sprint_contract("t", self._payload(
            [{"category": "travel", "name": "여비", "executionAmount": 3_000_000}],
            start="2026-01-01", end="2026-06-30", fy="2026"))
        b = next(b for b in c.budget_items if b.category == "travel")
        assert b.current_amount == 3_000_000
        assert b.next1_amount == 0

    def test_max_revision_rejected(self):
        from services.company_standards import MAX_REVISION
        with pytest.raises(ValueError):
            build_sprint_contract("t", self._payload([]), revision=MAX_REVISION + 1)

    def test_vat_row_filtered(self):
        c = build_sprint_contract("t", self._payload(
            [{"category": "etc", "name": "V.A.T", "executionAmount": 7_200_000}]))
        assert not any(b.category == "etc" for b in c.budget_items)
