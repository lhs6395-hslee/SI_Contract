"""공통 시트 라이터 — 마스터 데이터 입력.

구조: D열=인덱스(1~15), 행8의 E~P열=차수(0~11)
값은 현재 차수에 해당하는 열에 입력.
  0차=E열, 1차=F열, 2차=G열 ...

고정 셀(차수 무관):
  E3: 사업명, K3: 공사코드, M3: 발주처, O3: 계약처
  F4: 매출액, P4: 영업이익
  G5: 계약방법, I5: 수금조건, O5: 영업담당자
"""

from .base import SheetWriter


def _calc_period_ratios(start_str: str, end_str: str, fiscal_year: int) -> dict:
    """공사 기간에서 정산누계/당기계획/당기이후 비율 계산.
    반환: {13: 정산누계비율, 14: 당기계획비율, 15: 당기이후(내년)비율, 16: 당기이후(내후년~)비율}
    """
    from datetime import date
    import re

    def _parse(s):
        if not s:
            return None
        s = str(s).strip()
        s = re.sub(r'[./]', '-', s)
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None

    start = _parse(start_str)
    end = _parse(end_str)
    if not start or not end:
        return {13: None, 14: None, 15: None, 16: None}

    total_days = (end - start).days + 1
    if total_days <= 0:
        return {13: None, 14: None, 15: None, 16: None}

    def _days_in_year(yr):
        y_start = max(start, date(yr, 1, 1))
        y_end = min(end, date(yr, 12, 31))
        if y_end < y_start:
            return 0
        return (y_end - y_start).days + 1

    prev_year_days = sum(_days_in_year(y) for y in range(start.year, fiscal_year))
    curr_year_days = _days_in_year(fiscal_year)
    next_year_days = _days_in_year(fiscal_year + 1)
    after_days = total_days - prev_year_days - curr_year_days - next_year_days

    def _ratio(d):
        r = round(d / total_days, 6)
        return r if r > 0 else None

    return {
        13: _ratio(prev_year_days),
        14: _ratio(curr_year_days),
        15: _ratio(next_year_days),
        16: _ratio(after_days) if after_days > 0 else None,
    }


def _rev_col(revision: int) -> str:
    """차수 번호(0~11) → 열 문자(E~P)."""
    return chr(ord("E") + revision)


class CommonSheetWriter(SheetWriter):
    sheet_name = "공통"

    def _write(self):
        cf = self.contract.confirmed_fields
        revision = self.contract.revision
        col = _rev_col(revision)

        # E5: 현재 차수 (갑지 수정집행 시트에서 HLOOKUP으로 참조)
        self.write_cell("E5", revision, source="현재 차수")

        # 고정 셀 (차수 무관)
        self.write_cell("E3", cf.project_name, source="confirmed_fields.project_name")
        if cf.project_code:
            self.write_cell("K3", cf.project_code, source="confirmed_fields.project_code")
        else:
            import logging
            logging.getLogger(__name__).warning("공사코드(project_code)가 없습니다. K3 셀이 비어있습니다.")
        self.write_cell("M3", cf.client, source="confirmed_fields.client")
        self.write_cell("O3", cf.contractor, source="confirmed_fields.contractor")

        # F4: 매출액 — 천원 단위 (원 단위 → /1000)
        if cf.revenue:
            rev_val = cf.revenue
            if rev_val >= 1_000_000:
                rev_val = round(rev_val / 1000)
            self.write_cell("F4", rev_val, source="confirmed_fields.revenue (천원)", calc_basis="원÷1000")

        # P4: 영업이익 — 천원 단위
        if cf.profit:
            profit_val = cf.profit
            if profit_val >= 100_000:
                profit_val = round(profit_val / 1000)
            self.write_cell("P4", profit_val, source="confirmed_fields.profit (천원)", calc_basis="원÷1000")

        # N4: 경비 — 천원 단위
        if cf.cost:
            cost_val = cf.cost
            if cost_val >= 1_000_000:
                cost_val = round(cost_val / 1000)
            self.write_cell("N4", cost_val, source="confirmed_fields.cost (천원)", calc_basis="원÷1000")

        self.write_cell("G5", cf.contract_type, source="confirmed_fields.contract_type")
        self.write_cell("I5", cf.payment_terms, source="confirmed_fields.payment_terms")

        # O5: 영업담당자 (PM이 아닌 salesOwner)
        sales_owner = getattr(cf, 'sales_owner', None) or cf.pm
        self.write_cell("O5", sales_owner, source="confirmed_fields.sales_owner")

        # E6: 년도구분
        if cf.fiscal_year:
            self.write_cell(f"{col}6", f"{cf.fiscal_year}년", source="confirmed_fields.fiscal_year")

        # 차수별 셀 (인덱스 행 9~22 → 현재 차수 열에 입력)
        if cf.written_date:
            self.write_cell(f"{col}9", cf.written_date, source="confirmed_fields.written_date")

        # 집행계획작성일: planDate가 있으면 사용, 없으면 오늘 날짜
        import datetime
        plan_date = getattr(cf, 'plan_date', None)
        self.write_cell(f"{col}10", plan_date or datetime.date.today().isoformat(), source="confirmed_fields.plan_date" if plan_date else "오늘 날짜")

        # D11=4: 낙찰율 (기본값 1 = 100%)
        bid_rate = getattr(cf, 'bid_rate', None) or 1
        self.write_cell(f"{col}11", bid_rate, source="confirmed_fields.bid_rate (기본값 1)")

        # D12=5: PM
        if cf.pm:
            self.write_cell(f"{col}12", cf.pm, source="confirmed_fields.pm")

        # D13~16: 정산누계/당기계획/당기이후 비율 — 공사기간에서 계산
        fiscal_year = int(cf.fiscal_year) if cf.fiscal_year else None
        period = getattr(cf, 'project_period', None) or {}
        start_str = period.get('start') if period else None
        end_str = period.get('end') if period else None
        if fiscal_year and start_str and end_str:
            ratios = _calc_period_ratios(start_str, end_str, fiscal_year)
            for row, ratio in ratios.items():
                # 0도 써야 함 (정산누계 없는 경우 등)
                self.write_cell(f"{col}{row}", ratio if ratio is not None else 0, source=f"기간비율계산 row{row}")

        # D17~22: 요율 — 현재 차수가 null이면 이전 차수에서 가장 최근 유효값 사용
        prev_revisions = getattr(self.contract, 'prev_revisions', None) or {}
        sorted_prev_revs = sorted(prev_revisions.keys(), key=int, reverse=True)

        def _fallback_rate(rate_key: str, current_val):
            if current_val:
                return current_val, "현재차수"
            for prev_rev in sorted_prev_revs:
                prev_rates = prev_revisions[prev_rev].get("rates", {})
                entry = prev_rates.get(rate_key, {})
                val = entry.get("value") if isinstance(entry, dict) else entry
                if val:
                    try:
                        fval = float(val)
                        if fval > 0:
                            return fval, f"rev{prev_rev} fallback"
                    except (TypeError, ValueError):
                        pass
            return None, None

        r = self.contract.rates
        rate_rows = {
            17: ("indirectRate", r.indirect_rate if r else None, "간접비 요율"),
            18: ("adminRate", r.admin_rate if r else None, "일반관리비 요율"),
            19: ("nationalPension", r.national_pension if r else None, "국민연금 요율"),
            20: ("healthInsurance", r.health_insurance if r else None, "건강보험 요율"),
            21: ("industrialAccident", r.industrial_accident if r else None, "산재보험 요율"),
            22: ("employmentInsurance", r.employment_insurance if r else None, "고용보험 요율"),
        }
        for row, (rate_key, current_val, label) in rate_rows.items():
            val, source = _fallback_rate(rate_key, current_val)
            if val:
                try:
                    self.write_cell(f"{col}{row}", float(val) / 100, source=f"rates.{label} ({source})")
                except (TypeError, ValueError):
                    pass

        # ─── 이전 차수 데이터 기록 (0차 컬럼 등) ───
        def _get_val(v):
            if isinstance(v, dict):
                return v.get("value")
            return v

        prev_revisions = getattr(self.contract, 'prev_revisions', None)
        if prev_revisions:
            for prev_rev_num, prev_data in prev_revisions.items():
                prev_col = _rev_col(int(prev_rev_num))
                prev_extracted = prev_data.get("extracted", prev_data)
                prev_rates = prev_data.get("rates", {})

                # 년도구분
                fy = prev_extracted.get("fiscalYear", {})
                if isinstance(fy, dict):
                    fy_val = fy.get("value")
                else:
                    fy_val = fy
                if fy_val:
                    self.write_cell(f"{prev_col}6", f"{str(fy_val).replace('년', '')}년", source=f"rev{prev_rev_num}.fiscalYear")

                # 견적서작성일
                wd = prev_extracted.get("writtenDate", {})
                if isinstance(wd, dict):
                    wd_val = wd.get("value")
                else:
                    wd_val = wd
                if wd_val:
                    self.write_cell(f"{prev_col}9", wd_val, source=f"rev{prev_rev_num}.writtenDate")

                # 집행계획작성일 (이전 차수는 저장된 값 사용)
                pd_val = prev_extracted.get("planDate", {})
                if isinstance(pd_val, dict):
                    pd_val = pd_val.get("value")
                if pd_val:
                    self.write_cell(f"{prev_col}10", pd_val, source=f"rev{prev_rev_num}.planDate")

                # PM — null이면 이후 차수에서 fallback
                pm = prev_extracted.get("pm", {})
                if isinstance(pm, dict):
                    pm_val = pm.get("value")
                else:
                    pm_val = pm
                if not pm_val:
                    # 이후 차수(현재 포함)에서 가장 가까운 유효값 사용
                    for fallback_rev in sorted(prev_revisions.keys(), key=int):
                        if int(fallback_rev) <= int(prev_rev_num):
                            continue
                        fb_ext = prev_revisions[fallback_rev].get("extracted", {})
                        fb_pm = fb_ext.get("pm", {})
                        fb_val = fb_pm.get("value") if isinstance(fb_pm, dict) else fb_pm
                        if fb_val:
                            pm_val = fb_val
                            break
                    if not pm_val and cf.pm:
                        pm_val = cf.pm
                if pm_val:
                    self.write_cell(f"{prev_col}12", pm_val, source=f"rev{prev_rev_num}.pm(fallback)")

                # 기간 비율 (정산누계/당기계획/당기이후)
                prev_start = _get_val(prev_extracted.get("startDate", {}))
                prev_end = _get_val(prev_extracted.get("endDate", {}))
                prev_fy_str = _get_val(prev_extracted.get("fiscalYear", {}))
                if prev_fy_str and prev_start and prev_end:
                    try:
                        prev_ratios = _calc_period_ratios(str(prev_start), str(prev_end), int(str(prev_fy_str).replace('년', '')))
                        for row, ratio in prev_ratios.items():
                            # 0도 써야 함
                            self.write_cell(f"{prev_col}{row}", ratio if ratio is not None else 0, source=f"rev{prev_rev_num}.기간비율 row{row}")
                    except (ValueError, TypeError):
                        pass

                # 요율 — 해당 차수에 값 없으면 이후 차수에서 fallback
                prev_rate_rows = {
                    17: ("indirectRate", "간접비"),
                    18: ("adminRate", "일반관리비"),
                    19: ("nationalPension", "국민연금"),
                    20: ("healthInsurance", "건강보험"),
                    21: ("industrialAccident", "산재보험"),
                    22: ("employmentInsurance", "고용보험"),
                }
                # 이후 차수 목록 (현재 차수 포함, 오름차순)
                later_revs = sorted(
                    [k for k in prev_revisions.keys() if int(k) > int(prev_rev_num)],
                    key=int
                )
                for row, (rate_key, label) in prev_rate_rows.items():
                    rate_entry = prev_rates.get(rate_key, {})
                    if isinstance(rate_entry, dict):
                        rate_val = rate_entry.get("value", 0)
                    else:
                        rate_val = rate_entry or 0
                    # fallback: 해당 차수에 값 없으면 이후 차수에서 가장 가까운 값 사용
                    if not rate_val:
                        for later_rev in later_revs:
                            later_rates = prev_revisions[later_rev].get("rates", {})
                            later_entry = later_rates.get(rate_key, {})
                            later_val = later_entry.get("value", 0) if isinstance(later_entry, dict) else (later_entry or 0)
                            if later_val:
                                rate_val = later_val
                                break
                        # 현재 차수(cf) rates에서도 확인
                        if not rate_val and self.contract.rates:
                            r_now = self.contract.rates
                            rate_map = {
                                "indirectRate": r_now.indirect_rate,
                                "adminRate": r_now.admin_rate,
                                "nationalPension": r_now.national_pension,
                                "healthInsurance": r_now.health_insurance,
                                "industrialAccident": r_now.industrial_accident,
                                "employmentInsurance": r_now.employment_insurance,
                            }
                            rate_val = rate_map.get(rate_key) or 0
                    if rate_val:
                        self.write_cell(f"{prev_col}{row}", rate_val / 100, source=f"rev{prev_rev_num}.{label}")

        # ─── 수정집행 시트 참조 수식 (revision >= 1인 경우, 해당 차수 열에 입력) ───
        # 수정집행 집계표 열 구조: F=계약당초, H=계약변경, J=집행당초, L=집행변경
        # 공통 시트 F열(1차)/G열(2차) 등에 수정집행 집계표를 참조하는 수식 삽입
        if revision >= 1:
            modified_sheet = "'4. 집행예산집계표 (수정집행)'"
            # 계약금액 (rows 135-138): 재료비/노무비/외주비/경비
            contract_rows = {135: 10, 136: 13, 137: 19, 138: 22}
            for r_row, ref_row in contract_rows.items():
                formula = f"={modified_sheet}!H{ref_row}*1000"
                self.write_cell(f"{col}{r_row}", formula, source=f"수정집행집계표.계약변경.row{ref_row}")
            # 집행계획 (rows 141-144): 재료비/노무비/외주비/경비
            plan_rows = {141: 10, 142: 13, 143: 19, 144: 22}
            for r_row, ref_row in plan_rows.items():
                formula = f"={modified_sheet}!L{ref_row}*1000"
                self.write_cell(f"{col}{r_row}", formula, source=f"수정집행집계표.집행변경.row{ref_row}")
            # 영업이익 (rows 148-149)
            self.write_cell(f"{col}148", f"={modified_sheet}!L42*1000", source="수정집행집계표.영업이익")
            self.write_cell(f"{col}149", f"={modified_sheet}!M42/100", source="수정집행집계표.영업이익%")
