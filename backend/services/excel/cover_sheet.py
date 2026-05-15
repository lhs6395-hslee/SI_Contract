"""0. 집행계획(갑지) 시트 라이터.

갑지는 전부 수식 — 공통 시트와 집계표에서 참조.
이 라이터는 공통 시트의 차수별 열에 특기사항/PM/기간 등을 입력한다.
공통 시트 행 127~134 영역 + 행 12(PM).
"""

from datetime import datetime

from .base import SheetWriter


def _rev_col(revision: int) -> str:
    return chr(ord("E") + revision)


def _to_date(date_str: str):
    """문자열 날짜를 datetime 객체로 변환 (엑셀 날짜 셀 호환)."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return date_str


class CoverSheetWriter(SheetWriter):
    sheet_name = "공통"

    def _write(self):
        cf = self.contract.confirmed_fields
        col = _rev_col(self.contract.revision)

        start = cf.project_period.get("start", "")
        end = cf.project_period.get("end", "")

        # E125: 시작일, E126: 종료일 (날짜값 직접 입력 — E127/E128 수식이 참조)
        if start:
            self.write_cell(f"{col}125", _to_date(start), source="confirmed_fields.project_period.start")
        if end:
            self.write_cell(f"{col}126", _to_date(end), source="confirmed_fields.project_period.end")

        # 사업범위 (E129)
        if cf.scope:
            self.write_cell(f"{col}129", cf.scope, source="confirmed_fields.scope")

        # 특기사항 (E134)
        if cf.special_notes:
            self.write_cell(f"{col}134", cf.special_notes, source="confirmed_fields.special_notes")

        # ─── 이전 차수 데이터 기록 ───
        prev_revisions = getattr(self.contract, 'prev_revisions', None)
        if prev_revisions:
            for prev_rev_num, prev_data in prev_revisions.items():
                prev_col = _rev_col(int(prev_rev_num))
                prev_extracted = prev_data.get("extracted", prev_data)

                def _get(field):
                    v = prev_extracted.get(field, {})
                    return v.get("value") if isinstance(v, dict) else v

                prev_start = _get("startDate")
                prev_end = _get("endDate")
                prev_scope = _get("scope")
                prev_notes = _get("specialNotes")

                if prev_start:
                    self.write_cell(f"{prev_col}125", _to_date(str(prev_start)), source=f"rev{prev_rev_num}.startDate")
                if prev_end:
                    self.write_cell(f"{prev_col}126", _to_date(str(prev_end)), source=f"rev{prev_rev_num}.endDate")
                if prev_scope:
                    self.write_cell(f"{prev_col}129", prev_scope, source=f"rev{prev_rev_num}.scope")
                if prev_notes:
                    self.write_cell(f"{prev_col}134", prev_notes, source=f"rev{prev_rev_num}.specialNotes")
