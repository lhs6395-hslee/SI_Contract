"""SheetWriter 베이스 클래스 — 셀 색상 감지 및 공통 유틸.

셀 색상 규칙 (executor.md 기반):
- 노란(FFFFFFCC): 사용자/AI 입력 대상
- 파란(FF0070C0): 고정값 (차수 등)
- 색 없음/흰색: 라벨 또는 수식 → 건드리지 않음
"""

from __future__ import annotations
from enum import Enum
from pathlib import Path
from copy import copy

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.cell.cell import Cell

from models import SprintContract, StepResult, StepStatus, InputUsed

TEMPLATE_PATH = Path(__file__).parent.parent.parent.parent / "templates" / "템플릿.xlsx"

INPUT_COLORS = {"FFFFFFCC"}
SKIP_COLORS = {"FF0070C0"}


class CellType(str, Enum):
    input_cell = "input"
    formula_cell = "formula"
    label_cell = "label"
    skip_cell = "skip"


def _get_rgb(cell: Cell) -> str | None:
    try:
        fill = cell.fill
        if fill and fill.start_color and fill.start_color.rgb:
            rgb = str(fill.start_color.rgb)
            if rgb not in ("00000000", "FFFFFFFF", "00FFFFFF"):
                return rgb
    except Exception:
        pass
    return None


def cell_type(cell: Cell) -> CellType:
    rgb = _get_rgb(cell)
    if rgb in INPUT_COLORS:
        return CellType.input_cell
    if rgb in SKIP_COLORS:
        return CellType.skip_cell
    if cell.data_type == "f":
        return CellType.formula_cell
    return CellType.label_cell


def load_template() -> openpyxl.Workbook:
    return openpyxl.load_workbook(str(TEMPLATE_PATH))


class SheetWriter:
    """시트별 Executor 스텝의 베이스 클래스."""

    sheet_name: str = ""

    def __init__(self, wb: openpyxl.Workbook, contract: SprintContract):
        self.wb = wb
        self.contract = contract
        self.inputs_used: list[InputUsed] = []

    @property
    def ws(self) -> Worksheet:
        return self.wb[self.sheet_name]

    def write_cell(self, cell_ref: str, value, source: str = "", calc_basis: str = ""):
        cell = self.ws[cell_ref]
        ct = cell_type(cell)
        if ct == CellType.skip_cell:
            return
        if ct == CellType.formula_cell:
            return
        cell.value = value
        log_value = value if isinstance(value, (str, int, float, type(None))) else str(value)
        self.inputs_used.append(InputUsed(
            field=cell_ref,
            value=log_value,
            cell=cell_ref,
            source=source,
            calc_basis=calc_basis,
        ))

    def execute(self, step_id: int) -> StepResult:
        try:
            self._write()
            return StepResult(
                step_id=step_id,
                sheet=self.sheet_name,
                status=StepStatus.completed,
                inputs_used=self.inputs_used,
                constraint_compliance={
                    "소스_근거_명시": all(i.source for i in self.inputs_used),
                },
            )
        except Exception as e:
            return StepResult(
                step_id=step_id,
                sheet=self.sheet_name,
                status=StepStatus.failed,
                inputs_used=self.inputs_used,
                notes=str(e),
            )

    def _write(self):
        raise NotImplementedError
