"""파이프라인 오케스트레이터 — Sprint_Contract 스텝을 의존성 순서대로 실행.

의존성 레벨별로 병렬(asyncio.gather)/순차 실행.
Reviewer는 별도 단계 (Iteration 3에서 구현).
"""

from __future__ import annotations
import asyncio
import os
import shutil
from collections import defaultdict
from pathlib import Path

import openpyxl

from models import (
    SprintContract, StepDef, StepResult, StepStatus,
    PipelineState, PipelineStatus,
)
from services.excel.base import load_template
from services.excel.common_sheet import CommonSheetWriter
from services.excel.fee_sheet import FeeSheetWriter
from services.excel.breakdown_sheet import BreakdownSheetWriter
from services.excel.cover_sheet import CoverSheetWriter
from services.excel.staff_sheet import StaffSheetWriter
from services.excel.org_sheet import OrgSheetWriter
from services.excel.schedule_sheet import ScheduleSheetWriter

RESULTS_DIR = Path(__file__).parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

SHEET_WRITERS: dict[str, type] = {
    "공통": CommonSheetWriter,
    "5-4. 수수료산출내역": FeeSheetWriter,
    "5.집행예산산출내역서": BreakdownSheetWriter,
    "0. 집행계획(갑지)": CoverSheetWriter,
    "인원투입계획": StaffSheetWriter,
    "1. 현장조직_업무분장": OrgSheetWriter,
    "3. 예정공정표": ScheduleSheetWriter,
}


def compute_dependency_levels(steps: list[StepDef]) -> dict[int, list[StepDef]]:
    step_map = {s.id: s for s in steps}
    levels: dict[int, int] = {}

    def get_level(sid: int) -> int:
        if sid in levels:
            return levels[sid]
        step = step_map[sid]
        if not step.dependencies:
            levels[sid] = 0
            return 0
        lvl = max(get_level(d) for d in step.dependencies) + 1
        levels[sid] = lvl
        return lvl

    for s in steps:
        get_level(s.id)

    by_level: dict[int, list[StepDef]] = defaultdict(list)
    for s in steps:
        by_level[levels[s.id]].append(s)
    return dict(by_level)


def _execute_step(step: StepDef, contract: SprintContract, wb: openpyxl.Workbook) -> StepResult:
    writer_cls = SHEET_WRITERS.get(step.sheet)
    if not writer_cls:
        return StepResult(
            step_id=step.id,
            sheet=step.sheet,
            status=StepStatus.pending,
            notes=f"시트 라이터 미구현: {step.sheet}",
        )
    writer = writer_cls(wb, contract)
    return writer.execute(step.id)


async def _execute_step_async(step: StepDef, contract: SprintContract, wb: openpyxl.Workbook) -> StepResult:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _execute_step, step, contract, wb)


async def run_pipeline(
    project_id: str,
    contract: SprintContract,
) -> PipelineState:
    state = PipelineState(
        project_id=project_id,
        sprint_contract=contract,
        status=PipelineStatus.running,
    )

    wb = load_template()
    levels = compute_dependency_levels(contract.steps)

    for level_num in sorted(levels.keys()):
        steps = levels[level_num]
        results = await asyncio.gather(*[
            _execute_step_async(step, contract, wb)
            for step in steps
        ])
        for result in results:
            state.step_results[result.step_id] = result
            if result.status == StepStatus.failed:
                retry = state.retry_count.get(result.step_id, 0)
                if retry >= 3:
                    state.status = PipelineStatus.escalated
                    state.error = f"Step {result.step_id} failed after 3 retries: {result.notes}"
                    return state
                state.retry_count[result.step_id] = retry + 1

    output_filename = f"{project_id}_집행계획서.xlsx"
    output_path = RESULTS_DIR / output_filename
    wb.save(str(output_path))

    # S3에 업로드 (Pod 재시작 시에도 다운로드 가능)
    from services.s3_storage import is_s3_enabled, _s3_client, S3_FILES_BUCKET
    s3_key = f"results/{output_filename}"
    if is_s3_enabled():
        try:
            s3 = _s3_client()
            s3.upload_file(str(output_path), S3_FILES_BUCKET, s3_key)
        except Exception as e:
            print(f"[WARN] S3 upload failed: {e}")

    state.status = PipelineStatus.completed
    state.output_file = s3_key  # S3 키 저장 (로컬 경로 대신)
    return state


def _identify_failed_sheets(issues: list[str]) -> set[str]:
    sheet_keywords = {
        "5-4. 수수료산출내역": ["행", "계약:", "집행:", "역마진", "연도분리", "당기수량"],
        "공통": ["노무비", "보험료", "project_name", "client", "pm", "매출액", "영업이익"],
        "5.집행예산산출내역서": ["수수료 교차", "비활성 비목"],
    }
    failed = set()
    for issue in issues:
        for sheet, keywords in sheet_keywords.items():
            if any(kw in issue for kw in keywords):
                failed.add(sheet)
    return failed if failed else {"공통"}


def run_pipeline_sync(project_id: str, contract: SprintContract) -> PipelineState:
    return asyncio.run(run_pipeline(project_id, contract))
