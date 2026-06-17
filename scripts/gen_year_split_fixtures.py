#!/usr/bin/env python3
"""연도분리/골든 검증용 senario/검증시나리오 픽스처(scenario.json/rev*.json) 생성.

run_year_split.py / golden_runner.py 가 읽는 형식:
  {"extracted": {<field>: {"value": ...}}, "costItems": [ {category:"fee", unit:"M/M", ...} ]}

값은 run_year_split.CASES 기대 당기수량/금액과 일치하도록 구성. .gitignore 대상이라
디스크에서 휘발되므로, 검증 전 1회 실행해 복원한다.
"""
import json
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SCEN = os.path.join(ROOT, "senario", "검증시나리오")


def ex(**kv):
    """extracted dict: {key: {"value": v}}."""
    return {k: {"value": v} for k, v in kv.items()}


def fee(name, unit, qty, price, vendor=""):
    # amount는 qty×price로 명시(실입력과 동일) — 0이면 빌더가 금액 0으로 둠.
    amt = round(qty * price)
    return {
        "category": "fee", "name": name, "spec": "", "unit": unit,
        "contractQty": qty, "contractPrice": price, "contractAmount": amt,
        "executionQty": qty, "executionPrice": price, "executionAmount": amt,
        "vendor": vendor, "source": "fixture", "confidence": "verified",
    }


# (dir, filename, extracted, costItems) — 이름은 run_year_split/golden_runner 기대 키와 일치
CASES = [
    # A1: 2025.10~2026.03 (6개월), 당기(2025)=3MM → 3 × 7,500,000 = 22,500,000
    ("A1_연도경계_6개월", "scenario.json",
     ex(projectName="A1 연도경계", client="미래누리정보기술", startDate="2025.10.01",
        endDate="2026.03.31", fiscalYear="2025", pm="강민호", salesOwner="윤서진"),
     [fee("ITSM 운영", "M/M", 6, 7_500_000, "클라우드밸리")]),
    # A2: 2025.07~2027.06 (24개월), 당기(2025)=6MM → 6 × 10,000,000 = 60,000,000
    ("A2_연도경계_24개월", "scenario.json",
     ex(projectName="A2 24개월", client="동방데이터시스템", startDate="2025.07.01",
        endDate="2027.06.30", fiscalYear="2025", pm="조현우", salesOwner="윤서진"),
     [fee("ERP 구축 개발", "M/M", 24, 10_000_000, "넥스트코어솔루션")]),
    # A3: 2024.12~2027.11 (36개월), 당기(2024)=1MM → 1 × 6,800,000 = 6,800,000
    ("A3_다년도_36개월", "scenario.json",
     ex(projectName="A3 다년도", client="그린IT파트너스", startDate="2024.12.01",
        endDate="2027.11.30", fiscalYear="2024", pm="한지원", salesOwner="배성철"),
     [fee("통합관제 운영", "M/M", 36, 6_800_000, "한울시스템즈")]),
    # C1: 단년도 — 전액 유지, 당기=1.8MM → 1.8 × 12,000,000 = 21,600,000
    ("C1_주말프로젝트", "scenario.json",
     ex(projectName="C1 주말투입", client="위클리시스템", startDate="2026.01.03",
        endDate="2026.06.28", fiscalYear="2026", pm="문재상", salesOwner="배성철"),
     [{"category": "fee", "name": "주말 전산실 이전", "spec": "", "unit": "M/M",
       "contractQty": 1.8, "contractPrice": 12_000_000, "contractAmount": 21_600_000,
       "executionQty": 1.8, "executionPrice": 12_000_000, "executionAmount": 21_600_000,
       "vendor": "위크엔드테크", "source": "fixture", "confidence": "verified"}]),
    # C2: 4개년 복수발주처 — 당기=12MM → 12 × 7,500,000 = 90,000,000
    ("C2_4개년_복수발주처", "scenario.json",
     ex(projectName="C2 4개년", client="멀티클라이언트", startDate="2026.01.01",
        endDate="2029.12.31", fiscalYear="2026", pm="배수진", salesOwner="윤서진"),
     [fee("통합 운영", "M/M", 48, 7_500_000, "포코어시스템즈")]),
]

# B1 수정집행 기간연장: rev0(6MM) → rev1(9MM 연장). run_year_split B1 체크: H9/N9=6, K9/Q9=9, X9=9
B1_REV0 = (
    ex(projectName="세종클라우드웍스 DC 이전", client="세종클라우드웍스", startDate="2026.01.01",
       endDate="2026.06.30", fiscalYear="2026", pm="오태경", salesOwner="배성철"),
    [fee("DC 이전 지원", "M/M", 6, 8_000_000, "비트윈테크")],
)
B1_REV1 = (
    ex(projectName="세종클라우드웍스 DC 이전", client="세종클라우드웍스", startDate="2026.01.01",
       endDate="2026.09.30", fiscalYear="2026", pm="오태경", salesOwner="배성철"),
    [fee("DC 이전 지원", "M/M", 9, 8_000_000, "비트윈테크")],
)


# B2 인원변경 수정집행: rev0(6MM) → rev1(인원 9MM로 증가)
B2_REV0 = (
    ex(projectName="대한정보기술 통합운영", client="대한정보기술", startDate="2026.01.01",
       endDate="2026.12.31", fiscalYear="2026", pm="김도윤", salesOwner="윤서진"),
    [fee("운영 인력", "M/M", 6, 9_000_000, "이음시스템")],
)
B2_REV1 = (
    ex(projectName="대한정보기술 통합운영", client="대한정보기술", startDate="2026.01.01",
       endDate="2026.12.31", fiscalYear="2026", pm="김도윤", salesOwner="윤서진"),
    [fee("운영 인력", "M/M", 9, 9_000_000, "이음시스템")],
)

# B3 금액증액 수정집행: rev0(단가 8M) → rev1(단가 10M로 증액)
B3_REV0 = (
    ex(projectName="한빛데이터 클라우드 전환", client="한빛데이터", startDate="2026.03.01",
       endDate="2026.08.31", fiscalYear="2026", pm="장하늘", salesOwner="배성철"),
    [fee("전환 컨설팅", "M/M", 6, 8_000_000, "코어브릿지")],
)
B3_REV1 = (
    ex(projectName="한빛데이터 클라우드 전환", client="한빛데이터", startDate="2026.03.01",
       endDate="2026.08.31", fiscalYear="2026", pm="장하늘", salesOwner="배성철"),
    [fee("전환 컨설팅", "M/M", 6, 10_000_000, "코어브릿지")],
)


def write(path, extracted, cost_items):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"extracted": extracted, "costItems": cost_items}, f, ensure_ascii=False, indent=2)
    print(f"  ✓ {os.path.relpath(path, ROOT)}")


def main():
    print(f"검증시나리오 픽스처 생성 → {os.path.relpath(SCEN, ROOT)}/")
    for name, fn, extracted, items in CASES:
        write(os.path.join(SCEN, name, fn), extracted, items)
    # B1/B2/B3 수정집행 (golden_runner B1·B2·B3 케이스용)
    write(os.path.join(SCEN, "B1_수정집행_기간연장", "rev0.json"), *B1_REV0)
    write(os.path.join(SCEN, "B1_수정집행_기간연장", "rev1.json"), *B1_REV1)
    write(os.path.join(SCEN, "B2_수정집행_인원변경", "rev0.json"), *B2_REV0)
    write(os.path.join(SCEN, "B2_수정집행_인원변경", "rev1.json"), *B2_REV1)
    write(os.path.join(SCEN, "B3_수정집행_금액증액", "rev0.json"), *B3_REV0)
    write(os.path.join(SCEN, "B3_수정집행_금액증액", "rev1.json"), *B3_REV1)
    print("완료. run_year_split.py / golden_runner.py 실행 가능.")


if __name__ == "__main__":
    main()
