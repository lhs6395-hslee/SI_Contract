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


def _rev_col(revision: int) -> str:
    """차수 번호(0~11) → 열 문자(E~P)."""
    return chr(ord("E") + revision)


class CommonSheetWriter(SheetWriter):
    sheet_name = "공통"

    def _write(self):
        cf = self.contract.confirmed_fields
        revision = self.contract.revision
        col = _rev_col(revision)

        # 고정 셀 (차수 무관)
        self.write_cell("E3", cf.project_name, source="confirmed_fields.project_name")
        self.write_cell("K3", cf.project_code, source="confirmed_fields.project_code")
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

        # D12=5: PM
        if cf.pm:
            self.write_cell(f"{col}12", cf.pm, source="confirmed_fields.pm")

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

                # PM
                pm = prev_extracted.get("pm", {})
                if isinstance(pm, dict):
                    pm_val = pm.get("value")
                else:
                    pm_val = pm
                if pm_val:
                    self.write_cell(f"{prev_col}12", pm_val, source=f"rev{prev_rev_num}.pm")

                # 요율
                prev_rate_rows = {
                    17: ("indirectRate", "간접비"),
                    18: ("adminRate", "일반관리비"),
                    19: ("nationalPension", "국민연금"),
                    20: ("healthInsurance", "건강보험"),
                    21: ("industrialAccident", "산재보험"),
                    22: ("employmentInsurance", "고용보험"),
                }
                for row, (rate_key, label) in prev_rate_rows.items():
                    rate_entry = prev_rates.get(rate_key, {})
                    if isinstance(rate_entry, dict):
                        rate_val = rate_entry.get("value", 0)
                    else:
                        rate_val = rate_entry or 0
                    if rate_val:
                        self.write_cell(f"{prev_col}{row}", rate_val / 100, source=f"rev{prev_rev_num}.{label}")
