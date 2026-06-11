"""5-4. 수수료산출내역 시트 라이터 — 가변 N행 수수료 항목 입력.

원본(0차) 시트 — 데이터 행 8~16, 합계행 17:
  D: 자재코드, E: 품명, F: 규격, G: 단위
  H/I/J: 계약 수량/단가/금액, K/L/M: 집행 수량/단가/금액
  Q/R/S: 당기 수량/단가/금액, AJ: 비고

수정집행(N차) 시트 — 데이터 행 9~17(1구간), 소계 18/26/32, 합계 48:
  H/I/J: 계약 당초 (이전 차수 값), K/L/M: 계약 변경 (현재 값)
  N/O/P: 집행 당초, Q/R/S: 집행 변경
  U~W: 정산누계, X/Y/Z: 당기, AQ: 비고
  금액 셀(J/M/P/S/Z)은 템플릿 수식(수량×단가)이 계산 — 값을 쓰지 않음
"""

from copy import copy
from .base import SheetWriter

DATA_START_ROW = 8        # 원본(0차) 데이터 시작행
REV_DATA_START_ROW = 9   # 수정집행(1차~) 데이터 시작행
DEFAULT_DATA_END_ROW = 16
DEFAULT_TOTAL_ROW = 17
DEFAULT_MAX_ITEMS = DEFAULT_DATA_END_ROW - DATA_START_ROW + 1  # 9


def _copy_row_style(ws, src_row: int, dst_row: int):
    """src_row 서식을 dst_row에 복사 (값 제외)."""
    for col in range(1, ws.max_column + 1):
        src = ws.cell(row=src_row, column=col)
        dst = ws.cell(row=dst_row, column=col)
        if src.has_style:
            dst.font = copy(src.font)
            dst.border = copy(src.border)
            dst.fill = copy(src.fill)
            dst.number_format = src.number_format
            dst.alignment = copy(src.alignment)


class FeeSheetWriter(SheetWriter):
    sheet_name = "5-4. 수수료산출내역"

    def _write(self):
        items = self.contract.fee_items
        if not items:
            return

        revision = getattr(self.contract, 'revision', 0) or 0
        prev_map = getattr(self.contract, 'prev_fee_items', None) or {}

        if revision == 0:
            self._write_base_rows(self.ws, items, tag="rev0")
            return

        # 현재 차수 (N차) 시트: 당초 = (N-1)차 값
        self._write_rev_rows(self.ws, items, prev_map.get(str(revision - 1), []), tag=f"rev{revision}")

        # 이전 차수 (1..N-1차) 시트들도 해당 차수 데이터로 채움
        # — 차수별 시트가 독립 생성되므로 각 시트의 데이터도 그 차수 기준이어야 함
        for k in range(1, revision):
            name = f"{self.sheet_name} ({k}차)"
            if name in self.wb.sheetnames and prev_map.get(str(k)):
                self._write_rev_rows(self.wb[name], prev_map[str(k)], prev_map.get(str(k - 1), []), tag=f"rev{k}")

        # (0차) 원본 시트 데이터 (rename된 0차 시트)
        zero_name = f"{self.sheet_name} (0차)"
        if zero_name in self.wb.sheetnames and prev_map.get("0"):
            self._write_base_rows(self.wb[zero_name], prev_map["0"], tag="rev0")

    def _write_base_rows(self, ws, items, tag: str):
        """원본(0차) 양식: H/I=계약, K/L=집행, Q/R=당기. 금액(J/M/S)은 수식이 계산."""
        n = len(items)
        extra = max(0, n - DEFAULT_MAX_ITEMS)
        if extra > 0:
            ws.insert_rows(DEFAULT_TOTAL_ROW, amount=extra)
            template_row = DATA_START_ROW + DEFAULT_MAX_ITEMS - 1
            for i in range(extra):
                _copy_row_style(ws, template_row, DEFAULT_TOTAL_ROW + i)

        for i, item in enumerate(items):
            row = DATA_START_ROW + i
            src = f"{tag}.fee_items[{i}]"
            self._write_cell_direct(ws, f"D{row}", item.code, f"{src}.code")
            self._write_cell_direct(ws, f"E{row}", item.item_name, f"{src}.item_name")
            self._write_cell_direct(ws, f"F{row}", item.spec, f"{src}.spec")
            self._write_cell_direct(ws, f"G{row}", item.unit, f"{src}.unit")
            self._write_cell_direct(ws, f"H{row}", item.contract_qty, f"{src}.contract_qty")
            self._write_cell_direct(ws, f"I{row}", item.contract_unit_price, f"{src}.contract_unit_price")
            self._force_if_mismatch(ws, f"J{row}", item.contract_amount, item.contract_qty, item.contract_unit_price, f"{src}.contract_amount")
            self._write_cell_direct(ws, f"K{row}", item.execution_qty, f"{src}.execution_qty")
            self._write_cell_direct(ws, f"L{row}", item.execution_unit_price, f"{src}.execution_unit_price")
            self._force_if_mismatch(ws, f"M{row}", item.execution_amount, item.execution_qty, item.execution_unit_price, f"{src}.execution_amount")
            self._write_cell_direct(ws, f"Q{row}", item.current_period_qty, f"{src}.current_period_qty")
            self._write_cell_direct(ws, f"R{row}", item.execution_unit_price, f"{src}.execution_unit_price (당기단가)")
            self._force_if_mismatch(ws, f"S{row}", item.current_period_amount, item.current_period_qty, item.execution_unit_price, f"{src}.current_period_amount")
            if item.vendor:
                self._write_cell_direct(ws, f"AJ{row}", item.vendor, f"{src}.vendor")

    def _write_rev_rows(self, ws, items, prev_items, tag: str):
        """수정집행 양식: H/I·N/O=당초(계약/집행), K/L·Q/R=변경, X/Y=당기. 금액은 수식이 계산."""
        n = len(items)
        extra = max(0, n - DEFAULT_MAX_ITEMS)
        if extra > 0:
            insert_at = REV_DATA_START_ROW + DEFAULT_MAX_ITEMS
            ws.insert_rows(insert_at, amount=extra)
            template_row = REV_DATA_START_ROW + DEFAULT_MAX_ITEMS - 1
            for i in range(extra):
                _copy_row_style(ws, template_row, insert_at + i)

        for i, item in enumerate(items):
            row = REV_DATA_START_ROW + i
            src = f"{tag}.fee_items[{i}]"
            self._write_cell_direct(ws, f"D{row}", item.code, f"{src}.code")
            self._write_cell_direct(ws, f"E{row}", item.item_name, f"{src}.item_name")
            self._write_cell_direct(ws, f"F{row}", item.spec, f"{src}.spec")
            self._write_cell_direct(ws, f"G{row}", item.unit, f"{src}.unit")

            # ── 당초 (이전 차수 값): H/I=계약, N/O=집행 ──
            prev = self._match_item(prev_items, item, i)
            if prev:
                self._write_cell_direct(ws, f"H{row}", prev.contract_qty, f"{src}.당초.contract_qty")
                self._write_cell_direct(ws, f"I{row}", prev.contract_unit_price, f"{src}.당초.contract_unit_price")
                self._write_cell_direct(ws, f"N{row}", prev.execution_qty, f"{src}.당초.execution_qty")
                self._write_cell_direct(ws, f"O{row}", prev.execution_unit_price, f"{src}.당초.execution_unit_price")
            # ── 변경 (해당 차수 값): K/L=계약, Q/R=집행 ──
            self._write_cell_direct(ws, f"K{row}", item.contract_qty, f"{src}.contract_qty (변경)")
            self._write_cell_direct(ws, f"L{row}", item.contract_unit_price, f"{src}.contract_unit_price (변경)")
            self._write_cell_direct(ws, f"Q{row}", item.execution_qty, f"{src}.execution_qty (변경)")
            self._write_cell_direct(ws, f"R{row}", item.execution_unit_price, f"{src}.execution_unit_price (변경)")
            # ── 당기: X/Y (Z=X*Y 수식이 계산) ──
            self._write_cell_direct(ws, f"X{row}", item.current_period_qty, f"{src}.current_period_qty (당기)")
            self._write_cell_direct(ws, f"Y{row}", item.execution_unit_price, f"{src}.execution_unit_price (당기단가)")
            expected = round(item.current_period_qty * item.execution_unit_price)
            if item.current_period_amount and round(item.current_period_amount) != expected:
                self._write_cell_direct_force(ws, f"Z{row}", item.current_period_amount, f"{src}.current_period_amount (당기, 수동)")
            if item.vendor:
                self._write_cell_direct(ws, f"AQ{row}", item.vendor, f"{src}.vendor")

    def _force_if_mismatch(self, ws, cell_ref: str, amount, qty, unit_price, source: str):
        """금액이 수량×단가와 다르면 값으로 강제 입력, 같으면 수식 유지."""
        if not amount:
            return
        if round(amount) != round((qty or 0) * (unit_price or 0)):
            self._write_cell_direct_force(ws, cell_ref, amount, source + " (수동)")

    @staticmethod
    def _match_item(prev_items, item, index: int):
        """이전 차수 목록에서 같은 항목 찾기 — 품명+협력사 일치 우선, 없으면 같은 순번."""
        if not prev_items:
            return None
        for p in prev_items:
            if p.item_name == item.item_name and p.vendor == item.vendor:
                return p
        if index < len(prev_items):
            return prev_items[index]
        return None

    def _write_cell_direct(self, ws, cell_ref: str, value, source: str):
        """행 삽입 후에도 안전하게 셀에 직접 쓰기 + 로그. 수식 셀은 스킵."""
        from models import InputUsed
        cell = ws[cell_ref]
        if cell.data_type == "f":
            return
        cell.value = value
        log_value = value if isinstance(value, (str, int, float, type(None))) else str(value)
        self.inputs_used.append(InputUsed(
            field=cell_ref, value=log_value, cell=cell_ref, source=source,
        ))

    def _write_cell_direct_force(self, ws, cell_ref: str, value, source: str):
        """수식 셀도 포함해서 값을 강제로 입력 (J/M/S 금액 셀용)."""
        from models import InputUsed
        cell = ws[cell_ref]
        cell.value = value
        log_value = value if isinstance(value, (str, int, float, type(None))) else str(value)
        self.inputs_used.append(InputUsed(
            field=cell_ref, value=log_value, cell=cell_ref, source=source,
        ))
