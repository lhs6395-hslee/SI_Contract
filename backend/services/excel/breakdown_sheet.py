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

# 공통 시트 비목 블록: 카테고리 → 행 매핑
# 표준 블록(7행): 산출내역/계약/집행/정산/당기/이후1/이후2
# 상여금(6행): 계약금액 행 없음
BUDGET_BLOCKS: dict[str, dict[str, int | None]] = {
    "labor":     {"desc": 23, "contract": 24, "execution": 25, "settled": 26, "current": 27, "next1": 28, "next2": 29},
    "bonus":     {"desc": 30, "contract": None, "execution": 31, "settled": 32, "current": 33, "next1": 34, "next2": 35},
    "wage":      {"desc": 36, "contract": 37, "execution": 38, "settled": 39, "current": 40, "next1": 41, "next2": 42},
    "welfare":   {"desc": 43, "contract": 44, "execution": 45, "settled": 46, "current": 47, "next1": 48, "next2": 49},
    "travel":    {"desc": 50, "contract": 51, "execution": 52, "settled": 53, "current": 54, "next1": 55, "next2": 56},
    "vehicle":   {"desc": 57, "contract": 58, "execution": 59, "settled": 60, "current": 61, "next1": 62, "next2": 63},
    "equipment": {"desc": 64, "contract": 65, "execution": 66, "settled": 67, "current": 68, "next1": 69, "next2": 70},
    "rent":      {"desc": 71, "contract": 72, "execution": 73, "settled": 74, "current": 75, "next1": 76, "next2": 77},
    "transport": {"desc": 78, "contract": 79, "execution": 80, "settled": 81, "current": 82, "next1": 83, "next2": 84},
    "comm":      {"desc": 85, "contract": 86, "execution": 87, "settled": 88, "current": 89, "next1": 90, "next2": 91},
    "print":     {"desc": 92, "contract": 93, "execution": 94, "settled": 95, "current": 96, "next1": 97, "next2": 98},
    "safety":    {"desc": 99, "contract": 100, "execution": 101, "settled": 102, "current": 103, "next1": 104, "next2": 105},
    "etc":       {"desc": 106, "contract": 107, "execution": 108, "settled": 109, "current": 110, "next1": 111, "next2": 112},
}


class BreakdownSheetWriter(SheetWriter):
    """공통 시트 차수별 열에 비목별 금액을 입력하여 산출내역서 수식을 채운다."""

    sheet_name = "공통"

    def _write(self):
        col = _rev_col(self.contract.revision)

        # 비목 블록 입력 (budget_items 우선)
        written_categories: set[str] = set()
        for item in getattr(self.contract, 'budget_items', None) or []:
            block = BUDGET_BLOCKS.get(item.category)
            if not block:
                continue
            written_categories.add(item.category)
            if item.desc:
                self.write_cell(f"{col}{block['desc']}", item.desc, source=f"budget_items.{item.category}.desc")
            for key, amount in (
                ("contract", item.contract_amount), ("execution", item.execution_amount),
                ("settled", item.settled_amount), ("current", item.current_amount),
                ("next1", item.next1_amount), ("next2", item.next2_amount),
            ):
                row = block.get(key)
                if row is not None:
                    self.write_cell(f"{col}{row}", amount, source=f"budget_items.{item.category}.{key}")

        # budget_items에 노무비가 없으면 staff_plan에서 급료 산출 (하위 호환)
        if "labor" not in written_categories:
            staff = self.contract.staff_plan
            internal_staff = [s for s in staff if s.type == "직접"]
            total_salary = sum(s.monthly_rate * sum(s.months) for s in internal_staff)
            if total_salary > 0:
                desc = ", ".join(f"{s.name}({s.grade}) {sum(s.months)}M/M" for s in internal_staff if sum(s.months) > 0)
                self.write_cell(f"{col}{LABOR_SALARY['desc']}", desc, source="staff_plan")
                self.write_cell(f"{col}{LABOR_SALARY['execution']}", total_salary, source="staff_plan 급료합계", calc_basis="월급×M/M")
                self.write_cell(f"{col}{LABOR_SALARY['current']}", total_salary, source="당기=집행(최초)")

    @property
    def ws(self):
        return self.wb["공통"]
