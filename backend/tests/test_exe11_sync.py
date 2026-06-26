"""EXE-11 (연도분리 엔진) spec↔code 적합성(sync) 검증.

방법론 US2 방식: spec의 수용기준/SC를 실행 테스트로 변환해 현 코드에 실행.
GREEN = 코드가 spec 충족(sync) / RED = 드리프트(spec가 코드를 잘못 기술).
기존 test_year_split.py가 커버하지 않는 EXE-11 수용기준만 대상으로 한다.
"""
import pytest

from services.contract_builder import _fiscal_year_shares, _split_by_shares
from services.excel.common_sheet import _calc_period_ratios


class TestSC002_SharesSumToOne:
    """SC-002: _fiscal_year_shares 반환의 current+next1+next2+prev 합 = 1.0 ± 1e-6."""

    @pytest.mark.parametrize("start,end,fy", [
        ("2025-09-01", "2026-09-30", 2025),   # US1 AC1 (경계 걸침 2년)
        ("2025-07-01", "2027-06-30", 2025),   # 24개월 3버킷
        ("2024-06-01", "2027-03-31", 2025),   # US1 AC3 (prev 포함 4구간)
        ("2024-12-01", "2027-11-30", 2025),   # 중간 차수 prev
    ])
    def test_shares_sum_to_one(self, start, end, fy):
        s = _fiscal_year_shares(start, end, fy)
        assert s is not None
        total = s["current"] + s["next1"] + s["next2"] + s["prev"]
        assert total == pytest.approx(1.0, abs=1e-6)
        assert s["total_mm"] > 0


class TestUS1AC3_FourBuckets:
    """US1 AC3: 2024-06~2027-03, fy=2025 → prev/current/next1/next2 모두 > 0."""

    def test_all_four_buckets_positive(self):
        s = _fiscal_year_shares("2024-06-01", "2027-03-31", 2025)
        assert s is not None
        assert s["prev"] > 0
        assert s["current"] > 0
        assert s["next1"] > 0
        assert s["next2"] > 0


class TestFR006_PrevBranch:
    """FR-006: prev>=1e-9 이면 cur+nx1+nx2 <= round(amount) (prev 금액 제외)."""

    def test_prev_excluded_from_buckets(self):
        s = _fiscal_year_shares("2024-12-01", "2027-11-30", 2025)  # prev=1/36
        cur, nx1, nx2 = _split_by_shares(36_000_000, s)
        assert cur + nx1 + nx2 < 36_000_000          # prev 1MM 제외
        assert cur + nx1 + nx2 == pytest.approx(35_000_000, abs=1)


class TestSC005_PeriodRatiosSum:
    """SC-005: _calc_period_ratios 비None 비율 합 = 1.0 ± 1e-4 (common_sheet)."""

    @pytest.mark.parametrize("start,end,fy", [
        ("2025-09-01", "2026-09-30", 2025),
        ("2025-07-01", "2027-06-30", 2025),
        ("2024-06-01", "2027-03-31", 2025),
    ])
    def test_ratios_sum_to_one(self, start, end, fy):
        r = _calc_period_ratios(start, end, fy)
        vals = [v for v in r.values() if v is not None]
        assert sum(vals) == pytest.approx(1.0, abs=1e-4)

    def test_single_year_curr_is_one(self):
        # 단년도: 당기(14)=1.0, 나머지 None
        r = _calc_period_ratios("2026-01-01", "2026-12-31", 2026)
        assert r[14] == pytest.approx(1.0, abs=1e-4)
        assert r[13] is None and r[15] is None and r[16] is None


class TestFR009_ParseFailAllNone:
    """FR-009: 파싱 실패 시 {13,14,15,16} 모두 None."""

    def test_invalid_start_returns_all_none(self):
        r = _calc_period_ratios("", "2026-09-30", 2025)
        assert r == {13: None, 14: None, 15: None, 16: None}

    def test_none_dates_return_all_none(self):
        r = _calc_period_ratios(None, None, 2025)
        assert r == {13: None, 14: None, 15: None, 16: None}
