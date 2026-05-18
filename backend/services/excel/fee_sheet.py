"""5-4. 수수료산출내역 시트 라이터 — 가변 N행 수수료 항목 입력.

데이터 행: 8~16 (기본 9행). 항목이 9개 초과 시 합계행 위에 동적 행 삽입.
컬럼 매핑:
  D: 자재코드, E: 품명, F: 규격, G: 단위
  H: 계약수량, I: 계약단가 (J=H*I 수식 유지)
  K: 집행수량, L: 집행단가 (M=K*L 수식 유지)
  Q: 당기수량, R: 당기단가 (S=Q*R 수식 유지)
  AJ: 비고
합계행: 17 (동적으로 조정됨)
"""

from copy import copy
from .base import SheetWriter

DATA_START_ROW = 8
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

        ws = self.ws
        n = len(items)
        extra = max(0, n - DEFAULT_MAX_ITEMS)
        total_row = DEFAULT_TOTAL_ROW + extra

        # 9개 초과 시 합계행 위에 행 삽입 + 서식 복사
        if extra > 0:
            insert_at = DEFAULT_TOTAL_ROW  # 기존 합계행 위치에 삽입
            ws.insert_rows(insert_at, amount=extra)
            # 삽입된 행에 기존 마지막 데이터 행(16행) 서식 복사
            template_row = DEFAULT_DATA_END_ROW
            for i in range(extra):
                _copy_row_style(ws, template_row, insert_at + i)

        # 모든 항목 입력
        for i, item in enumerate(items):
            row = DATA_START_ROW + i

            self._write_cell_direct(ws, f"D{row}", item.code, f"fee_items[{i}].code")
            self._write_cell_direct(ws, f"E{row}", item.item_name, f"fee_items[{i}].item_name")
            self._write_cell_direct(ws, f"F{row}", item.spec, f"fee_items[{i}].spec")
            self._write_cell_direct(ws, f"G{row}", item.unit, f"fee_items[{i}].unit")

            self._write_cell_direct(ws, f"H{row}", item.contract_qty, f"fee_items[{i}].contract_qty")
            self._write_cell_direct(ws, f"I{row}", item.contract_unit_price, f"fee_items[{i}].contract_unit_price")
            # J: 수식 없으면 값 직접 입력 (일할계산이면 그 값, 아니면 H*I)
            contract_amount = item.contract_amount if item.contract_amount else round(item.contract_qty * item.contract_unit_price)
            self._write_cell_direct_force(ws, f"J{row}", contract_amount, f"fee_items[{i}].contract_amount")

            self._write_cell_direct(ws, f"K{row}", item.execution_qty, f"fee_items[{i}].execution_qty")
            self._write_cell_direct(ws, f"L{row}", item.execution_unit_price, f"fee_items[{i}].execution_unit_price")
            # M: 수식 없으면 값 직접 입력
            execution_amount = item.execution_amount if item.execution_amount else round(item.execution_qty * item.execution_unit_price)
            self._write_cell_direct_force(ws, f"M{row}", execution_amount, f"fee_items[{i}].execution_amount")

            self._write_cell_direct(ws, f"Q{row}", item.current_period_qty, f"fee_items[{i}].current_period_qty")
            self._write_cell_direct(ws, f"R{row}", item.execution_unit_price, f"fee_items[{i}].execution_unit_price (당기단가=집행단가)")
            # S: 수식 없으면 값 직접 입력
            current_amount = item.current_period_amount if item.current_period_amount else round(item.current_period_qty * item.execution_unit_price)
            self._write_cell_direct_force(ws, f"S{row}", current_amount, f"fee_items[{i}].current_period_amount")

            if item.vendor:
                self._write_cell_direct(ws, f"AJ{row}", item.vendor, f"fee_items[{i}].vendor")

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
