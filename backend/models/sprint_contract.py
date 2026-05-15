"""Sprint_Contract 및 파이프라인 데이터 모델.

.claude/agents/planner.md의 JSON 스키마 기반.
Executor/Reviewer 간 교환 형식 정의.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ─── Sprint_Contract 구성 요소 ───


class ConfirmedFields(BaseModel):
    project_name: Optional[str] = None
    project_code: Optional[str] = None
    project_period: dict = Field(default_factory=lambda: {"start": None, "end": None})
    pm: Optional[str] = None
    sales_owner: Optional[str] = None
    written_date: Optional[str] = None
    plan_date: Optional[str] = None  # 집행계획작성일
    fiscal_year: Optional[str] = None
    client: Optional[str] = None
    contractor: Optional[str] = None
    contract_type: Optional[str] = None
    payment_terms: Optional[str] = None
    revenue: Optional[int] = None
    cost: Optional[int] = None
    profit: Optional[int] = None
    profit_rate: Optional[float] = None
    scope: Optional[str] = None
    special_notes: Optional[str] = None


class SourceFile(BaseModel):
    path: str
    vendor: Optional[str] = None
    total_amount: Optional[int] = None


class SourceFiles(BaseModel):
    contract: list[str] = Field(default_factory=list)
    estimates: list[SourceFile] = Field(default_factory=list)


class ConflictResolution(BaseModel):
    conflict_type: str
    description: str
    options: list[str] = Field(default_factory=list)
    user_choice: Optional[str] = None
    resolved_value: Optional[str] = None


class FeeItem(BaseModel):
    code: int = 1
    vendor: str = ""
    item_name: str = ""
    spec: str = ""
    unit: str = ""
    contract_qty: float = 0
    contract_unit_price: float = 0
    contract_amount: float = 0
    execution_qty: float = 0
    execution_unit_price: float = 0
    execution_amount: float = 0
    current_period_qty: float = 0
    current_period_amount: float = 0
    source_doc: str = ""


class StaffItem(BaseModel):
    name: str = "TBD"
    role: str = ""
    grade: str = ""
    type: str = "직접"
    company: str = ""
    months: list[float] = Field(default_factory=lambda: [0.0] * 12)
    monthly_rate: int = 0


class ScheduleItem(BaseModel):
    name: str = ""
    start_month: int = 0
    end_month: int = 11


class OrgMember(BaseModel):
    role: str = ""
    name: str = ""
    scope: str = ""
    lead: bool = False


class RateSet(BaseModel):
    indirect_rate: float = 0
    admin_rate: float = 0
    national_pension: float = 0
    health_insurance: float = 0
    employment_insurance: float = 0
    industrial_accident: float = 0


class StepDef(BaseModel):
    id: int
    sheet: str
    action: str
    dependencies: list[int] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


# ─── Sprint_Contract 본체 ───


class SprintContract(BaseModel):
    task: str = "집행계획서 작성"
    mode: str = "create"
    revision: int = 0
    confidence_score: float = 0.0
    confirmed_fields: ConfirmedFields = Field(default_factory=ConfirmedFields)
    source_files: SourceFiles = Field(default_factory=SourceFiles)
    target_file: str = ""
    active_items: dict[str, bool] = Field(default_factory=dict)
    conflict_resolutions: list[ConflictResolution] = Field(default_factory=list)
    fee_items: list[FeeItem] = Field(default_factory=list)
    staff_plan: list[StaffItem] = Field(default_factory=list)
    schedule: list[ScheduleItem] = Field(default_factory=list)
    organization: list[OrgMember] = Field(default_factory=list)
    rates: Optional[RateSet] = None
    prev_revisions: dict[str, dict] = Field(default_factory=dict)  # 이전 차수 데이터 {"0": {...}, ...}
    steps: list[StepDef] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


# ─── Executor 출력 ───


class InputUsed(BaseModel):
    field: str
    value: str | int | float | None = None
    cell: str = ""
    source: str = ""
    calc_basis: str = ""


class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    pending_user_input = "pending_user_input"


class StepResult(BaseModel):
    step_id: int
    sheet: str
    status: StepStatus = StepStatus.pending
    inputs_used: list[InputUsed] = Field(default_factory=list)
    constraint_compliance: dict[str, bool] = Field(default_factory=dict)
    retry_fixes: list[dict] = Field(default_factory=list)
    pending_confirmations: list[dict] = Field(default_factory=list)
    notes: str = ""


# ─── Reviewer 출력 ───


class ReviewResult(BaseModel):
    verdict: str = "pending"
    score: float = 0.0
    amount_verification: dict = Field(default_factory=dict)
    basic_info_verification: dict = Field(default_factory=dict)
    checklist_results: dict = Field(default_factory=dict)
    constraint_violations: list[dict] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


# ─── 파이프라인 상태 ───


class PipelineStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    escalated = "escalated"


class PipelineState(BaseModel):
    project_id: str
    sprint_contract: Optional[SprintContract] = None
    step_results: dict[int, StepResult] = Field(default_factory=dict)
    review_results: list[ReviewResult] = Field(default_factory=list)
    retry_count: dict[int, int] = Field(default_factory=dict)
    status: PipelineStatus = PipelineStatus.pending
    output_file: Optional[str] = None
    error: Optional[str] = None
    token_usage: dict[str, int] = Field(default_factory=lambda: {"input": 0, "output": 0, "total": 0})
