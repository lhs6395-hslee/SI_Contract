"""5.집행예산산출내역서 시트 라이터.

이 시트는 거의 전부 수식. 실제 값 입력은 공통 시트의 차수별 열에 해야 함.
0차=E열, 1차=F열, 2차=G열 ...

공통 시트 행 매핑 (D열=인덱스):
  행23~29: 급료(직원) — 산출내역/계약/집행/정산/당기/당기이후(27)/당기이후(28~)
  행30~35: 상여금(직원)
  행36~42: 임금(현장사원)
  행43~49: 복리후생비
  행50~56: 여비교통비
  등...
"""

from .base import SheetWriter


def _rev_col(revision: int) -> str:
    return chr(ord("E") + revision)


LABOR_SALARY = {"desc": 23, "contract": 24, "execution": 25, "settled": 26, "current": 27, "next1": 28, "next2": 29}
LABOR_BONUS = {"desc": 30, "execution": 31, "settled": 32, "current": 33, "next1": 34, "next2": 35}
LABOR_WAGE = {"desc": 36, "contract": 37, "execution": 38, "settled": 39, "current": 40, "next1": 41, "next2": 42}


class BreakdownSheetWriter(SheetWriter):
    """공통 시트 차수별 열에 비목별 금액을 입력하여 산출내역서 수식을 채운다."""

    sheet_name = "공통"

    def _write(self):
        col = _rev_col(self.contract.revision)
        staff = self.contract.staff_plan

        internal_staff = [s for s in staff if s.type == "직접"]

        # 노무비 — 급료(직원): 자사 인원 월급 × M/M
        total_salary = sum(s.monthly_rate * sum(s.months) for s in internal_staff)
        if total_salary > 0:
            desc = ", ".join(f"{s.name}({s.grade}) {sum(s.months)}M/M" for s in internal_staff if sum(s.months) > 0)
            self.write_cell(f"{col}{LABOR_SALARY['desc']}", desc, source="staff_plan")
            self.write_cell(f"{col}{LABOR_SALARY['execution']}", total_salary, source="staff_plan 급료합계", calc_basis="월급×M/M")
            self.write_cell(f"{col}{LABOR_SALARY['current']}", total_salary, source="당기=집행(최초)")

    @property
    def ws(self):
        return self.wb["공통"]
