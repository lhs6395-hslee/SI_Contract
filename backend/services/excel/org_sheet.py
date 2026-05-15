"""1. 현장조직_업무분장 시트 라이터.

현장소장: Y8(직위), AD8(성명)
업무범위: Y10~ 행
"""

from .base import SheetWriter


class OrgSheetWriter(SheetWriter):
    sheet_name = "1. 현장조직_업무분장"

    def _write(self):
        org = self.contract.organization
        if not org:
            return

        leader = next((m for m in org if m.lead), org[0] if org else None)
        if leader:
            self.write_cell("AD8", leader.name, source="organization.leader.name")
            self.write_cell("Y8", f" 직위 :  {leader.role}", source="organization.leader.role")
