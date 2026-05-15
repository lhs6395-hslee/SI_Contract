"""인원투입계획 시트 라이터.

구조: A5=간접비, A13=직접비
행: 간접비 영역(5~10), 직접비 영역(13~24)
열: B=성명, C=직위, D=급여, E~N=1년차 월별 M/M, Q~AB=2년차 월별
"""

from .base import SheetWriter

INDIRECT_START = 5
INDIRECT_END = 10
DIRECT_START = 13
DIRECT_END = 24


class StaffSheetWriter(SheetWriter):
    sheet_name = "인원투입계획"

    def _write(self):
        staff = self.contract.staff_plan
        if not staff:
            return

        internal = [s for s in staff if s.type == "직접"]
        external = [s for s in staff if s.type != "직접"]

        for i, s in enumerate(external):
            if i >= (INDIRECT_END - INDIRECT_START):
                break
            row = INDIRECT_START + i
            self.write_cell(f"B{row}", s.name, source=f"staff[{i}].name (간접)")
            self.write_cell(f"C{row}", s.role, source=f"staff[{i}].role")
            self.write_cell(f"D{row}", s.monthly_rate, source=f"staff[{i}].monthly_rate")
            for j, mm in enumerate(s.months[:12]):
                col = chr(ord("E") + j)
                if mm > 0:
                    self.write_cell(f"{col}{row}", mm, source=f"staff[{i}].months[{j}]")

        for i, s in enumerate(internal):
            if i >= (DIRECT_END - DIRECT_START):
                break
            row = DIRECT_START + i
            self.write_cell(f"B{row}", s.name, source=f"staff[{i}].name (직접)")
            self.write_cell(f"C{row}", s.role, source=f"staff[{i}].role")
            self.write_cell(f"D{row}", s.monthly_rate, source=f"staff[{i}].monthly_rate")
            for j, mm in enumerate(s.months[:12]):
                col = chr(ord("E") + j)
                if mm > 0:
                    self.write_cell(f"{col}{row}", mm, source=f"staff[{i}].months[{j}]")
