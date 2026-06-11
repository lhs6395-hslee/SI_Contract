"""사내 기준 테이블 — 문서에 없는 값의 기본 보정 (사용자 확인 전제).

모든 기본값은 관문(추출 결과 확인)에서 사용자가 확인/수정하는 것을 전제로 한다.
출처: 템플릿 공통 시트 R열 가이드 + 25년 안전보건팀 공문 (템플릿 내장 image4).
"""
from __future__ import annotations

from datetime import date

# 수정집행 최대 차수 — 양식 구조 한계 (공통 차수열 E~P = 0~11차,
# HLOOKUP 범위 $E$8:$P$149, 갑지 변경차수표 1~11차)
MAX_REVISION = 11

# 직급 단가표 (원/월) — 템플릿 R23 가이드 (정직원/PJT직군)
# 사용자 결정(2026-06-11): 이 표를 기본 적용하되, 급료는 관문에서 반드시 재확인
GRADE_RATES: dict[str, int] = {
    "부장": 7_500_000,
    "차장": 6_500_000,
    "과장": 5_500_000,
    "대리": 4_500_000,
    "사원": 3_500_000,
}

# 기본 요율 (%) — 문서/공문에서 추출 실패 시 적용
# 간접비/일반관리비: 템플릿 R17 가이드 (요율은 윤지민과장 문의 — 25년 기준)
# 4대보험: 25년 안전보건팀 공문 (템플릿 내장 캡처) — 보험료율 공문 업로드 시 덮어씀
DEFAULT_RATES: dict[str, float] = {
    "indirect_rate": 1.9,
    "admin_rate": 3.0,
    "national_pension": 4.5,
    "health_insurance": 4.0041,
    "industrial_accident": 0.766,
    "employment_insurance": 1.75,
}

# 명절 날짜 (설날/추석 당일) — 상여금 계산용. 매년 갱신 필요.
HOLIDAYS: dict[int, dict[str, date]] = {
    2025: {"설날": date(2025, 1, 29), "추석": date(2025, 10, 6)},
    2026: {"설날": date(2026, 2, 17), "추석": date(2026, 9, 25)},
    2027: {"설날": date(2027, 2, 7), "추석": date(2027, 9, 15)},
}

# 산출내역서 수식이 자동 계산하는 항목 — costItems로 들어와도 비목 입력에서 제외
# (퇴직금 = (급료+상여)/12, 보험료 = (급료+임금+상여) × 공통 E19~E22 요율)
AUTO_CALCULATED_KEYWORDS = ("퇴직금", "보험료", "국민연금", "건강보험", "산재보험", "고용보험")


def is_auto_calculated(item_name: str) -> bool:
    """산출내역서 수식이 자동 계산하는 항목인지 (이중 계상 방지)."""
    return any(kw in (item_name or "") for kw in AUTO_CALCULATED_KEYWORDS)


def standard_rate_for(grade: str) -> int | None:
    """직급 문자열에서 사내 단가 조회 (부분 일치 허용: '과장(PM)' 등)."""
    if not grade:
        return None
    for g, rate in GRADE_RATES.items():
        if g in grade:
            return rate
    return None


def holidays_in_period(start: date, end: date) -> list[tuple[str, date]]:
    """투입 기간 [start, end] 안에 포함된 명절 목록.

    사용자 규칙(2026-06-11): 명절이 투입 기간 밖이면 해당 상여 없음
    (예: 설날 2/20인데 투입이 2/5에 끝나면 설 상여 미책정).
    """
    found = []
    for year in range(start.year, end.year + 1):
        for name, day in HOLIDAYS.get(year, {}).items():
            if start <= day <= end:
                found.append((name, day))
    return found
