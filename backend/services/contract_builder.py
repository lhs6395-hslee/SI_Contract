"""Sprint_Contract 빌더 — UI 확정 데이터를 SprintContract로 변환.

AI 호출 없음. 프론트엔드 ExtractedData를 확정론적으로 매핑.
"""

from __future__ import annotations
from pathlib import Path
from models import (
    SprintContract, ConfirmedFields, SourceFiles, SourceFile,
    ConflictResolution, FeeItem, BudgetItem, StaffItem, ScheduleItem, OrgMember,
    RateSet, StepDef,
)

from services.excel_writer import resolve_template_path

TEMPLATE_PATH = str(resolve_template_path(Path(__file__).parent.parent / "templates"))

CATEGORY_TO_CODE = {"fee": 1, "material": 2, "labor": 3, "supply": 4, "line": 5, "travel": 6, "other": 7}

# 공통 시트 비목 블록에 직접 입력되는 카테고리 (fee 제외 — fee는 5-4 시트 별도)
BUDGET_CATEGORIES = {
    "labor", "bonus", "wage", "welfare", "travel", "vehicle", "equipment",
    "rent", "transport", "comm", "print", "safety", "etc",
}

# 비목 카테고리의 일반 라벨 — item.name이 이 라벨 그대로면 산출내역(desc)에 에코하지 않는다
# (extract-costs가 세부내역 없이 카테고리명만 반환할 때 블록 라벨이 산출내역 칸에 중복 기입되는 것 방지)
CATEGORY_LABELS = {
    "노무비", "인건비", "상여금", "상여", "임금", "복리후생비", "복리후생",
    "여비", "출장비", "여비교통비", "차량유지비", "차량", "장비", "기자재", "장비구입비",
    "임차료", "임대료", "운반비", "운송비", "통신비", "회선료", "인쇄비", "출력비",
    "안전관리비", "기타경비", "경비", "기타", "재료비", "외주비", "수수료", "용역비",
}

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


def _parse_fiscal_year(extracted: dict) -> int | None:
    """fiscalYear('2025'/'2025년') → int. 없으면 시작일 연도."""
    import re
    raw = _extract_field(extracted, "fiscalYear")
    if raw:
        m = re.search(r"\d{4}", str(raw))
        if m:
            return int(m.group())
    start = _normalize_date(_extract_field(extracted, "startDate"))
    if start and str(start)[:4].isdigit():
        return int(str(start)[:4])
    return None


def _mm_between(start, end) -> float:
    """개월수 계산 — 시작월은 일할(잔여일/30, 업계 관행), 이후 월은 1개월씩."""
    if end < start:
        return 0.0
    import calendar
    if start.day == 1:
        start_ratio = 1.0
    else:
        days_in_month = calendar.monthrange(start.year, start.month)[1]
        start_ratio = (days_in_month - start.day + 1) / 30
    return start_ratio + (end.year - start.year) * 12 + (end.month - start.month)


def _fiscal_year_shares(start_date: str | None, end_date: str | None, fiscal_year: int | None):
    """연도 경계 걸침 시 (당기, 이후1, 이후2~) 비율 반환. 걸치지 않으면 None.

    당기 = 회계연도(fiscal_year) 내 개월 비율, 이후1 = 익년, 이후2 = fy+2년~종료 합산
    (집행계획서 양식 버킷이 당기/이후1/이후2 3개 — 3개 연도 초과분은 이후2 합산).
    회계연도 이전(prev) 구간은 다년도 사업의 중간 차수 작성 시 발생 — 당기/이후에
    포함하지 않고 비율만 반환 (정산누계는 실적 기반이라 자동 입력하지 않음).
    """
    from datetime import date
    try:
        start = date.fromisoformat(_normalize_date(start_date))
        end = date.fromisoformat(_normalize_date(end_date))
    except (ValueError, TypeError):
        return None
    if fiscal_year is None or end.year == start.year or not (start.year <= fiscal_year <= end.year):
        return None
    total = _mm_between(start, end)
    if total <= 0:
        return None

    def _window(y_from, y_to):
        lo = max(start, date(y_from, 1, 1))
        hi = min(end, date(y_to, 12, 31))
        return _mm_between(lo, hi) if hi >= lo else 0.0

    cur = _window(fiscal_year, fiscal_year)
    next1 = _window(fiscal_year + 1, fiscal_year + 1)
    next2 = _window(fiscal_year + 2, end.year) if end.year >= fiscal_year + 2 else 0.0
    prev = max(0.0, total - cur - next1 - next2)
    return {"current": cur / total, "next1": next1 / total, "next2": next2 / total,
            "prev": prev / total, "total_mm": total}


def _split_by_shares(amount: float, shares: dict) -> tuple[int, int, int]:
    """금액을 (당기, 이후1, 이후2)로 배분. prev(회계연도 이전)가 없으면 합계 보존."""
    cur = round(amount * shares["current"])
    nx1 = round(amount * shares["next1"])
    if shares.get("prev", 0) < 1e-9:
        nx2 = round(amount) - cur - nx1
    else:
        nx2 = round(amount * shares["next2"])
    return cur, nx1, nx2


def _build_fee_items(extracted: dict, cost_items: list) -> tuple[list[FeeItem], list[ConflictResolution]]:
    """costItems에서 수수료(fee) 항목을 FeeItem 목록으로 변환 (일할계산 + 연도분리 포함)."""
    start_date = _normalize_date(_extract_field(extracted, "startDate"))
    end_date = _normalize_date(_extract_field(extracted, "endDate"))
    fiscal_year = _parse_fiscal_year(extracted)
    fy_shares = _fiscal_year_shares(start_date, end_date, fiscal_year)
    fee_conflicts: list[ConflictResolution] = []

    fee_items: list[FeeItem] = []
    for item in cost_items:
        if item.get("category", "other") != "fee":
            continue
        raw_contract_qty = item.get("contractQty", 0)
        raw_execution_qty = item.get("executionQty", 0)
        contract_price = item.get("contractPrice", 0)
        execution_price = item.get("executionPrice", 0)

        # 일할계산: 시작일이 월 중간이고 M/M 단위이며 정수 수량일 때만 적용
        # 이미 소수점 수량이면 사용자가 수정한 것이므로 건드리지 않음
        # 확정 금액(contractAmount)이 명시돼 있으면 사용자 확인값 — 자동 일할계산 금지
        prorated_contract_qty = raw_contract_qty
        prorated_execution_qty = raw_execution_qty
        is_integer_qty = (raw_contract_qty == int(raw_contract_qty)) and (raw_execution_qty == int(raw_execution_qty))
        has_confirmed_amount = bool(item.get("contractAmount") or item.get("executionAmount"))
        if item.get("unit", "") in ("M/M", "월") and start_date and is_integer_qty and not has_confirmed_amount:
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

        # ── 당기(회계연도) 분리 ──
        # 1) 명시값(currentQty/currentAmount) 있으면 사용자 확인값 — 그대로 사용 (자동 처리 금지 원칙)
        # 2) 없고 연도 경계 걸침이면 회계연도 내 개월 비율로 배분 + 확인 플래그
        # 3) 단년도면 집행 전액
        explicit_cur_qty = item.get("currentQty")
        explicit_cur_amt = item.get("currentAmount")
        if explicit_cur_qty is not None or explicit_cur_amt is not None:
            current_qty = explicit_cur_qty if explicit_cur_qty is not None else prorated_execution_qty
            current_amount = explicit_cur_amt if explicit_cur_amt is not None else round(
                (current_qty or 0) * (execution_price or 0))
        elif fy_shares:
            share = fy_shares["current"]
            current_qty = round(prorated_execution_qty * share, 1)
            current_amount = round((execution_amount or 0) * share)
            fee_conflicts.append(ConflictResolution(
                conflict_type="연도배분확인",
                description=(
                    f"수수료 '{item.get('name', '')}': 연도 경계 걸침({start_date}~{end_date}, 당기={fiscal_year}년) — "
                    f"당기수량 {current_qty}/{prorated_execution_qty}, 당기금액 {current_amount:,.0f}원을 "
                    f"회계연도 개월 비율({share:.4f})로 자동 배분함. 관문에서 재확인 필요."
                ),
            ))
        else:
            current_qty = prorated_execution_qty
            current_amount = execution_amount

        fee_items.append(FeeItem(
            code=CATEGORY_TO_CODE.get("fee", 1),
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
            current_period_qty=current_qty,
            current_period_amount=current_amount,
            source_doc=item.get("source", ""),
        ))
    return fee_items, fee_conflicts


def build_sprint_contract(
    project_id: str,
    extracted_data: dict,
    revision: int = 0,
    prev_revisions: dict | None = None,
) -> SprintContract:
    """프론트엔드 ExtractedData JSON을 SprintContract로 변환."""

    from services.company_standards import MAX_REVISION
    if revision > MAX_REVISION:
        raise ValueError(
            f"수정집행은 최대 {MAX_REVISION}차까지 가능합니다 (요청: {revision}차). "
            f"집행계획서 양식의 차수 열(E~P)이 {MAX_REVISION}차에서 끝납니다."
        )

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
    # 작성일(견적서/집행계획) 기본값 = 오늘 (사용자 결정 2026-06-11) — 관문에서 수정 가능
    from datetime import date as _today_date
    written_date = _normalize_date(_extract_field(extracted, "writtenDate")) or _today_date.today().isoformat()

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
        quote_material=_extract_field(extracted, "quoteMaterial"),
        quote_labor=_extract_field(extracted, "quoteLabor"),
        quote_outsourcing=_extract_field(extracted, "quoteOutsourcing"),
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
    for item in cost_items:
        categories_present.add(item.get("category", "other"))
    fee_items, fee_conflicts = _build_fee_items(extracted, cost_items)

    # 연도 경계 비율 (당기/이후1/이후2) — 비목·상여·급료 배분에 공용
    fiscal_year = _parse_fiscal_year(extracted)
    fy_shares = _fiscal_year_shares(start_date, end_date, fiscal_year)

    # 비목 블록 입력 (공통 E23~E124) — 카테고리별 집계 (desc는 줄바꿈 병합)
    from services.company_standards import is_auto_calculated
    budget_acc: dict[str, BudgetItem] = {}
    auto_calc_skipped: list[str] = []
    budget_year_split_applied: list[str] = []
    for item in cost_items:
        cat = item.get("category", "other")
        if cat not in BUDGET_CATEGORIES:
            continue
        # 퇴직금/보험료는 산출내역서 수식이 자동 계산 — 이중 계상 방지
        if is_auto_calculated(item.get("name", "")):
            auto_calc_skipped.append(item.get("name", ""))
            continue
        # VAT/부가세 행 방어 (모든 금액은 공급가액 기준)
        if any(k in item.get("name", "").upper() for k in ("VAT", "V.A.T", "부가세")):
            auto_calc_skipped.append(item.get("name", ""))
            continue
        b = budget_acc.setdefault(cat, BudgetItem(category=cat))
        name = (item.get("name", "") or "").strip()
        # 산출내역(desc)에는 실제 세부내역만 기입. name이 카테고리 라벨(예: "복리후생비")
        # 그대로면 빈칸 유지 — 비목 블록 라벨이 산출내역 칸에 에코되는 것 방지.
        if name and name not in CATEGORY_LABELS:
            b.desc = f"{b.desc}\n{name}" if b.desc else name
        b.contract_amount += item.get("contractAmount", 0) or 0
        b.execution_amount += item.get("executionAmount", 0) or 0
        b.settled_amount += item.get("settledAmount", 0) or 0
        # 당기/이후: 명시값 우선 (사용자 확인값 — 자동 처리 금지 원칙)
        # 없으면 단년도는 집행 전액, 연도 경계 걸침은 회계연도 개월 비율로 배분 (합계 보존)
        exec_amt = item.get("executionAmount", 0) or 0
        if "currentAmount" in item or "next1Amount" in item or "next2Amount" in item:
            b.current_amount += item.get("currentAmount", exec_amt) or 0
            b.next1_amount += item.get("next1Amount", 0) or 0
            b.next2_amount += item.get("next2Amount", 0) or 0
        elif fy_shares and exec_amt:
            cur, nx1, nx2 = _split_by_shares(exec_amt, fy_shares)
            b.current_amount += cur
            b.next1_amount += nx1
            b.next2_amount += nx2
            budget_year_split_applied.append(item.get("name", "") or cat)
        else:
            b.current_amount += exec_amt
    budget_items = list(budget_acc.values())

    # ─── 사내 기준 보정 (사용자 확인 전제 — conflicts로 플래그) ───
    from services.company_standards import (
        standard_rate_for, holidays_in_period, GRADE_RATES,
    )
    standards_conflicts: list[ConflictResolution] = []
    standards_conflicts.extend(fee_conflicts)
    if auto_calc_skipped:
        standards_conflicts.append(ConflictResolution(
            conflict_type="자동계산중복",
            description=f"퇴직금/보험료는 산출내역서 수식이 자동 계산하므로 비목 입력에서 제외함: {', '.join(auto_calc_skipped)}",
        ))
    if budget_year_split_applied:
        standards_conflicts.append(ConflictResolution(
            conflict_type="연도배분확인",
            description=(
                f"연도 경계 걸침(당기={fiscal_year}년) — 비목 당기/이후1/이후2를 회계연도 개월 비율"
                f"(당기 {fy_shares['current']:.4f} / 이후1 {fy_shares['next1']:.4f} / 이후2 {fy_shares['next2']:.4f})로 "
                f"자동 배분함: {', '.join(budget_year_split_applied)}. 관문에서 재확인 필요."
                + (f" ※ 회계연도 이전 구간 비율 {fy_shares['prev']:.4f}는 정산누계 실적으로 직접 입력 필요."
                   if fy_shares.get("prev", 0) > 1e-9 else "")
            ),
        ))

    # 급료: budget_items에 labor가 없고 staffPlan이 있으면 사내 직급단가표로 산출
    # (문서상 실급여와 단가표가 다르면 관문 확인 필요 플래그)
    has_labor_budget = any(b.category == "labor" for b in budget_items)
    internal_staff = [s for s in staff_plan if s.get("type", "직접") == "직접"]

    # labor 입력값이 있어도 사내 단가표 기준액과 다르면 재확인 플래그 (값은 입력값 유지)
    if has_labor_budget and internal_staff:
        std_total = sum(
            (standard_rate_for(s.get("grade", "")) or 0) * (s.get("totalMM") or sum(s.get("months", []) or []))
            for s in internal_staff
        )
        labor_total = sum(b.execution_amount for b in budget_items if b.category == "labor")
        if std_total > 0 and abs(std_total - labor_total) > 1:
            standards_conflicts.append(ConflictResolution(
                conflict_type="급료단가확인",
                description=(
                    f"급료 입력값 {labor_total:,.0f}원이 사내 직급단가표 기준 {std_total:,.0f}원과 다름 — "
                    f"단가표(부장750/차장650/과장550/대리450/사원350만원) 기준 재확인 필요."
                ),
            ))
    if not has_labor_budget and internal_staff and start_date and end_date:
        salary_total = 0.0
        desc_lines = []
        for i, s in enumerate(internal_staff):
            mm = s.get("totalMM") or sum(s.get("months", []) or [])
            std_rate = standard_rate_for(s.get("grade", ""))
            doc_rate = s.get("monthlyRate", 0)
            rate = std_rate or doc_rate
            if not mm or not rate:
                continue
            salary_total += rate * mm
            desc_lines.append(f"{i+1}) {s.get('role','')} {s.get('name','')} ({s.get('grade','')} {mm}M/M * {rate/10000:.0f}만원)")
            if std_rate and doc_rate and std_rate != doc_rate:
                standards_conflicts.append(ConflictResolution(
                    conflict_type="급료단가확인",
                    description=f"{s.get('name','')}({s.get('grade','')}): 문서 급여 {doc_rate:,}원 vs 사내 단가표 {std_rate:,}원 — 사내 단가표 적용함. 급료 재확인 필요.",
                ))
        if salary_total > 0:
            # 연도 경계 걸침이면 급료도 회계연도 개월 비율로 당기/이후 배분
            if fy_shares:
                _cur, _nx1, _nx2 = _split_by_shares(salary_total, fy_shares)
                budget_items.append(BudgetItem(
                    category="labor",
                    desc="\n".join(desc_lines),
                    contract_amount=0,
                    execution_amount=salary_total,
                    current_amount=_cur,
                    next1_amount=_nx1,
                    next2_amount=_nx2,
                ))
                budget_year_split_applied.append("급료(자동산출)")
            else:
                budget_items.append(BudgetItem(
                    category="labor",
                    desc="\n".join(desc_lines),
                    contract_amount=0,
                    execution_amount=salary_total,
                    current_amount=salary_total,
                ))
            standards_conflicts.append(ConflictResolution(
                conflict_type="급료확인",
                description=f"급료 {salary_total:,.0f}원 — 사내 직급단가표 기준 자동 산출. 관문에서 재확인 필요.",
            ))

        # 계약(매출) 비목 배분: 문서에 계약 배분이 전혀 없으면 노무비에 매출 전액 배분
        # (인력투입 프로젝트 관행 — EPS: 계약 노무비 104,000천 = 매출 전액)
        revenue_val = confirmed.revenue or 0
        total_contract = sum(b.contract_amount for b in budget_items) + sum(f.contract_amount for f in fee_items)
        if revenue_val and total_contract == 0:
            for b in budget_items:
                if b.category == "labor":
                    b.contract_amount = revenue_val
                    standards_conflicts.append(ConflictResolution(
                        conflict_type="계약배분확인",
                        description=f"계약금액 비목 배분이 문서에 없어 매출 전액 {revenue_val:,}원을 노무비에 배분함. 관문에서 재확인 필요.",
                    ))
                    break

        # 상여금: 투입 기간 내 명절(설/추석)이 있을 때만 자동 산출 (기간 밖이면 미책정)
        has_bonus_budget = any(b.category == "bonus" for b in budget_items)
        if not has_bonus_budget:
            try:
                from datetime import date as _date
                _s = _date.fromisoformat(start_date)
                _e = _date.fromisoformat(end_date)
                holidays = holidays_in_period(_s, _e)
            except (ValueError, TypeError):
                holidays = []
            if holidays:
                bonus_total = 0.0
                bonus_lines = []
                # 상여금 연도 귀속: 명절이 속한 연도 기준 (당기=회계연도, 이후1=익년, 이후2=잔여)
                bonus_cur = bonus_nx1 = 0.0
                for hname, hday in holidays:
                    for i, s in enumerate(internal_staff):
                        mm = s.get("totalMM") or sum(s.get("months", []) or [])
                        rate = standard_rate_for(s.get("grade", "")) or s.get("monthlyRate", 0)
                        if not mm or not rate:
                            continue
                        # R30 가이드: 명절까지 투입개월/9 비율 × 1M/M 급여
                        months_before = min(
                            mm,
                            (hday.year - _s.year) * 12 + hday.month - _s.month,
                        )
                        if months_before <= 0:
                            continue
                        amount = round(rate * months_before / 9)
                        bonus_total += amount
                        if fiscal_year is None or hday.year <= fiscal_year:
                            bonus_cur += amount
                        elif hday.year == fiscal_year + 1:
                            bonus_nx1 += amount
                        bonus_lines.append(f"{len(bonus_lines)+1}) {hname}상여 {s.get('grade','')} ({months_before}/9) * {rate/10000:.0f}만원")
                if bonus_total > 0:
                    budget_items.append(BudgetItem(
                        category="bonus",
                        desc="\n".join(bonus_lines),
                        execution_amount=bonus_total,
                        current_amount=bonus_cur,
                        next1_amount=bonus_nx1,
                        next2_amount=bonus_total - bonus_cur - bonus_nx1,
                    ))
                    standards_conflicts.append(ConflictResolution(
                        conflict_type="상여확인",
                        description=f"상여금 {bonus_total:,.0f}원 — 기간 내 명절({', '.join(h for h, _ in holidays)}) 기준 자동 산출. 관문에서 재확인 필요.",
                    ))

    # 이전 차수의 수수료 항목 — 수정집행 시트의 '당초' 열 데이터
    prev_fee_items: dict[str, list[FeeItem]] = {}
    for rev_num, rev_data in (prev_revisions or {}).items():
        prev_fee_items[str(rev_num)], _ = _build_fee_items(
            rev_data.get("extracted", {}),
            rev_data.get("costItems", []),
        )

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

    # get(k, default)는 키 부재 시에만 default — 값이 명시적 None이면 그대로 들어가 Pydantic
    # ValidationError 크래시. `or`로 None도 기본값으로 흡수한다(빈 문자열/0/빈 배열 안전).
    staff_items = [
        StaffItem(
            name=s.get("name") or "TBD",
            role=s.get("role") or "",
            grade=s.get("grade") or "",
            type=s.get("type") or "직접",
            company=s.get("company") or "",
            months=s.get("months") or [0.0] * 12,
            monthly_rate=s.get("monthlyRate") or 0,
        )
        for s in staff_plan if isinstance(s, dict)
    ]

    schedule_items = [
        ScheduleItem(name=s.get("name") or "",
                     start_month=s.get("startMonth") if s.get("startMonth") is not None else 0,
                     end_month=s.get("endMonth") if s.get("endMonth") is not None else 11)
        for s in schedule if isinstance(s, dict)
    ]

    org_members = [
        OrgMember(role=o.get("role", ""), name=o.get("name", ""), scope=o.get("scope", ""), lead=o.get("lead", False))
        for o in organization
    ]

    # 요율 — 업로드 문서(공문/품의서) 값 우선, 없으면 템플릿 내장 공문 기준(사내 기본).
    # 어느 쪽이든 값은 채우되 반드시 사용자 확인을 받는다 (요율확인 플래그 무조건 생성).
    from services.company_standards import DEFAULT_RATES
    rate_provenance: list[str] = []

    def _rate(key: str, default_key: str, label: str) -> float:
        val = (rates_data or {}).get(key, {})
        val = val.get("value", 0) if isinstance(val, dict) else (val or 0)
        if val:
            rate_provenance.append(f"{label} {float(val)}% (업로드 문서)")
            return float(val)
        rate_provenance.append(f"{label} {DEFAULT_RATES[default_key]}% (사내 기본 — 템플릿 내장 공문)")
        return DEFAULT_RATES[default_key]

    rates = RateSet(
        indirect_rate=_rate("indirectRate", "indirect_rate", "간접비"),
        admin_rate=_rate("adminRate", "admin_rate", "일반관리비"),
        national_pension=_rate("nationalPension", "national_pension", "국민연금"),
        health_insurance=_rate("healthInsurance", "health_insurance", "건강보험"),
        employment_insurance=_rate("employmentInsurance", "employment_insurance", "고용보험"),
        industrial_accident=_rate("industrialAccident", "industrial_accident", "산재보험"),
    )
    standards_conflicts.append(ConflictResolution(
        conflict_type="요율확인",
        description="적용 요율 확인 필요: " + ", ".join(rate_provenance),
    ))

    conflict_resolutions = [
        ConflictResolution(
            conflict_type=c.get("type", ""),
            description=c.get("message", ""),
        )
        for c in conflicts
    ] + standards_conflicts

    return SprintContract(
        revision=revision,
        confirmed_fields=confirmed,
        source_files=source_files,
        target_file=f"results/{project_id}_집행계획서.xlsx",
        active_items=active_items,
        conflict_resolutions=conflict_resolutions,
        fee_items=fee_items,
        budget_items=budget_items,
        staff_plan=staff_items,
        schedule=schedule_items,
        organization=org_members,
        rates=rates,
        prev_revisions=prev_revisions or {},
        prev_fee_items=prev_fee_items,
        steps=STEPS,
        acceptance_criteria=ACCEPTANCE_CRITERIA,
    )
