"""Sprint_Contract 빌더 — UI 확정 데이터를 SprintContract로 변환.

AI 호출 없음. 프론트엔드 ExtractedData를 확정론적으로 매핑.
"""

from __future__ import annotations
from pathlib import Path
from models import (
    SprintContract, ConfirmedFields, SourceFiles, SourceFile,
    ConflictResolution, FeeItem, StaffItem, ScheduleItem, OrgMember,
    RateSet, StepDef,
)

TEMPLATE_PATH = str(Path(__file__).parent.parent / "templates" / "템플릿.xlsx")

CATEGORY_TO_CODE = {"fee": 1, "material": 2, "labor": 3, "supply": 4, "line": 5, "travel": 6, "other": 7}

STEPS = [
    StepDef(
        id=1, sheet="공통",
        action="마스터 데이터 입력",
        dependencies=[],
        acceptance_criteria=["확인된 기본 정보 정확히 입력", "발주처/계약처/계약방법/수금조건 소스 근거 명시"],
    ),
    StepDef(
        id=2, sheet="5-4. 수수료산출내역",
        action="협력사 견적서 기반 수수료 항목 입력 (N행 가변)",
        dependencies=[],
        acceptance_criteria=["모든 협력사 견적서 항목이 행으로 입력됨", "계약단가/집행단가 분리 입력", "각 행 수량×단가=금액 일치", "소계/합계 정확"],
    ),
    StepDef(
        id=3, sheet="5.집행예산산출내역서",
        action="active_items 기준 비목별 금액 입력",
        dependencies=[1, 2],
        acceptance_criteria=["active_items=true인 비목만 입력", "수수료 금액이 5.4 수수료 집행합계와 일치", "비목별 합계 정확"],
    ),
    StepDef(
        id=4, sheet="0. 집행계획(갑지)",
        action="갑지 집계 및 특기사항 입력",
        dependencies=[1, 2, 3],
        acceptance_criteria=["비목별 금액이 산출내역서 합계와 일치", "영업이익 = 매출액 - 합계", "기본 정보 정확히 반영"],
    ),
    StepDef(
        id=5, sheet="인원투입계획",
        action="투입 인원 월별 M/M 입력",
        dependencies=[1],
        acceptance_criteria=["자사/외부 인원 구분", "월별 M/M 합계 일치"],
    ),
    StepDef(
        id=6, sheet="3. 예정공정표",
        action="공종별 일정 입력",
        dependencies=[1],
        acceptance_criteria=["공종 시작/종료 월 정확"],
    ),
    StepDef(
        id=7, sheet="1. 현장조직_업무분장",
        action="현장조직 및 업무분장 입력",
        dependencies=[1],
        acceptance_criteria=["PM 포함 역할별 인원 기재"],
    ),
]

ACCEPTANCE_CRITERIA = [
    "모든 시트 필드 입력 완료",
    "계약금액 합계가 발주처 계약서와 일치",
    "집행금액 합계가 협력사 견적서 합산과 일치",
    "[추측] 항목 없음 또는 사용자 확인 완료",
]


def _extract_field(extracted: dict, key: str, default=None):
    """프론트엔드 extracted 딕셔너리에서 value를 꺼냄."""
    entry = extracted.get(key)
    if entry and isinstance(entry, dict):
        return entry.get("value", default)
    return default


def _normalize_date(date_str: str | None) -> str | None:
    """날짜 포맷 정규화: 2026.03.23 → 2026-03-23"""
    if not date_str:
        return date_str
    return date_str.replace(".", "-").replace("/", "-")


def _calc_prorated_qty(start_date: str | None, end_date: str | None, raw_qty: float) -> float:
    """시작일이 월 중간이면 일할계산된 수량 반환. 아니면 원래 수량 그대로."""
    if not start_date or not end_date or raw_qty <= 0:
        return raw_qty
    try:
        from datetime import datetime
        start = datetime.strptime(_normalize_date(start_date), "%Y-%m-%d")
        end = datetime.strptime(_normalize_date(end_date), "%Y-%m-%d")
    except (ValueError, TypeError):
        return raw_qty

    if start.day == 1:
        return raw_qty

    # 시작월 일할: (월말 - 시작일 + 1) / 30 (30일 고정 분모 — 업계 관행)
    import calendar
    days_in_start_month = calendar.monthrange(start.year, start.month)[1]
    working_days = days_in_start_month - start.day + 1
    start_month_ratio = working_days / 30

    # 시작월 다음달 ~ 종료월까지 완전 월수
    full_months = (end.year - start.year) * 12 + (end.month - start.month)

    prorated_qty = start_month_ratio + full_months

    # 0.1 단위 반올림 (9.233 → 9.2, 9.267 → 9.3)
    rounded = round(prorated_qty, 1)
    return rounded


def build_sprint_contract(
    project_id: str,
    extracted_data: dict,
    revision: int = 0,
    prev_revisions: dict | None = None,
) -> SprintContract:
    """프론트엔드 ExtractedData JSON을 SprintContract로 변환."""

    extracted = extracted_data.get("extracted", {})
    cost_items = extracted_data.get("costItems", [])
    staff_plan = extracted_data.get("staffPlan", [])
    schedule = extracted_data.get("schedule", [])
    rates_data = extracted_data.get("rates")
    organization = extracted_data.get("organization", [])
    conflicts = extracted_data.get("conflicts", [])
    files = extracted_data.get("files", [])

    start_date = _normalize_date(_extract_field(extracted, "startDate"))
    end_date = _normalize_date(_extract_field(extracted, "endDate"))
    written_date = _normalize_date(_extract_field(extracted, "writtenDate"))

    confirmed = ConfirmedFields(
        project_name=_extract_field(extracted, "projectName"),
        project_code=_extract_field(extracted, "projectCode"),
        project_period={"start": start_date, "end": end_date},
        pm=_extract_field(extracted, "pm"),
        sales_owner=_extract_field(extracted, "salesOwner"),
        written_date=written_date,
        plan_date=_normalize_date(_extract_field(extracted, "planDate")),
        fiscal_year=_extract_field(extracted, "fiscalYear") or (str(start_date or "")[:4] or None),
        client=_extract_field(extracted, "client"),
        contractor=_extract_field(extracted, "contractor"),
        contract_type=_extract_field(extracted, "contractType"),
        payment_terms=_extract_field(extracted, "paymentTerms"),
        revenue=_extract_field(extracted, "revenue"),
        cost=_extract_field(extracted, "cost"),
        profit=_extract_field(extracted, "profit"),
        profit_rate=_extract_field(extracted, "profitRate"),
        scope=_extract_field(extracted, "scope"),
        special_notes=_extract_field(extracted, "specialNotes"),
    )

    source_files = SourceFiles(
        contract=[f["name"] for f in files if f.get("category") == "contract"],
        estimates=[
            SourceFile(path=f["name"], vendor=f.get("vendor"), total_amount=f.get("totalAmount"))
            for f in files if f.get("category") == "vendor"
        ],
    )

    categories_present: set[str] = set()
    fee_items: list[FeeItem] = []
    for item in cost_items:
        cat = item.get("category", "other")
        categories_present.add(cat)
        if cat == "fee":
            raw_contract_qty = item.get("contractQty", 0)
            raw_execution_qty = item.get("executionQty", 0)
            contract_price = item.get("contractPrice", 0)
            execution_price = item.get("executionPrice", 0)

            # 일할계산: 시작일이 월 중간이고 M/M 단위이며 정수 수량일 때만 적용
            # 이미 소수점 수량이면 사용자가 수정한 것이므로 건드리지 않음
            prorated_contract_qty = raw_contract_qty
            prorated_execution_qty = raw_execution_qty
            is_integer_qty = (raw_contract_qty == int(raw_contract_qty)) and (raw_execution_qty == int(raw_execution_qty))
            if item.get("unit", "") in ("M/M", "월") and start_date and is_integer_qty:
                prorated_contract_qty = _calc_prorated_qty(start_date, end_date, raw_contract_qty)
                prorated_execution_qty = _calc_prorated_qty(start_date, end_date, raw_execution_qty)

            # 일할 적용 시 금액도 재계산 (반올림하지 않은 정확한 일할수량 × 단가)
            if prorated_contract_qty != raw_contract_qty and contract_price:
                from datetime import datetime as _dt
                import calendar as _cal
                try:
                    _s = _dt.strptime(start_date, "%Y-%m-%d")
                    _e = _dt.strptime(end_date, "%Y-%m-%d")
                    _dim = _cal.monthrange(_s.year, _s.month)[1]
                    _wd = _dim - _s.day + 1
                    _exact_qty = _wd / 30 + (_e.year - _s.year) * 12 + (_e.month - _s.month)
                    contract_amount = round(_exact_qty * contract_price)
                    execution_amount = round(_exact_qty * execution_price) if execution_price else 0
                except (ValueError, TypeError):
                    contract_amount = item.get("contractAmount", 0)
                    execution_amount = item.get("executionAmount", 0)
            else:
                contract_amount = item.get("contractAmount", 0)
                execution_amount = item.get("executionAmount", 0)

            fee_items.append(FeeItem(
                code=CATEGORY_TO_CODE.get(cat, 7),
                vendor=item.get("vendor", ""),
                item_name=item.get("name", ""),
                spec=item.get("spec", ""),
                unit=item.get("unit", ""),
                contract_qty=prorated_contract_qty,
                contract_unit_price=contract_price,
                contract_amount=contract_amount,
                execution_qty=prorated_execution_qty,
                execution_unit_price=execution_price,
                execution_amount=execution_amount,
                current_period_qty=prorated_execution_qty,
                current_period_amount=execution_amount,
                source_doc=item.get("source", ""),
            ))

    active_items = {
        "재료비": "material" in categories_present,
        "노무비": "labor" in categories_present or len(staff_plan) > 0,
        "외주비": "supply" in categories_present,
        "경비_복리후생비": len(staff_plan) > 0,
        "경비_보험료": len(staff_plan) > 0,
        "경비_수수료": len(fee_items) > 0,
        "경비_회선비": "line" in categories_present,
        "경비_소모품비": any(i.get("category") == "supply" for i in cost_items),
        "경비_여비교통비": "travel" in categories_present,
    }

    staff_items = [
        StaffItem(
            name=s.get("name", "TBD"),
            role=s.get("role", ""),
            grade=s.get("grade", ""),
            type=s.get("type", "직접"),
            company=s.get("company", ""),
            months=s.get("months", [0.0] * 12),
            monthly_rate=s.get("monthlyRate", 0),
        )
        for s in staff_plan
    ]

    schedule_items = [
        ScheduleItem(name=s.get("name", ""), start_month=s.get("startMonth", 0), end_month=s.get("endMonth", 11))
        for s in schedule
    ]

    org_members = [
        OrgMember(role=o.get("role", ""), name=o.get("name", ""), scope=o.get("scope", ""), lead=o.get("lead", False))
        for o in organization
    ]

    rates = None
    if rates_data:
        rates = RateSet(
            indirect_rate=rates_data.get("indirectRate", {}).get("value", 0) or 0,
            admin_rate=rates_data.get("adminRate", {}).get("value", 0) or 0,
            national_pension=rates_data.get("nationalPension", {}).get("value", 0) or 0,
            health_insurance=rates_data.get("healthInsurance", {}).get("value", 0) or 0,
            employment_insurance=rates_data.get("employmentInsurance", {}).get("value", 0) or 0,
            industrial_accident=rates_data.get("industrialAccident", {}).get("value", 0) or 0,
        )

    conflict_resolutions = [
        ConflictResolution(
            conflict_type=c.get("type", ""),
            description=c.get("message", ""),
        )
        for c in conflicts
    ]

    return SprintContract(
        revision=revision,
        confirmed_fields=confirmed,
        source_files=source_files,
        target_file=f"results/{project_id}_집행계획서.xlsx",
        active_items=active_items,
        conflict_resolutions=conflict_resolutions,
        fee_items=fee_items,
        staff_plan=staff_items,
        schedule=schedule_items,
        organization=org_members,
        rates=rates,
        prev_revisions=prev_revisions or {},
        steps=STEPS,
        acceptance_criteria=ACCEPTANCE_CRITERIA,
    )
