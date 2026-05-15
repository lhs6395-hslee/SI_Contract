"""
GS네오텍 ITEK 포털 — MIS 손익관리 매출/원가추정 데이터 수집
headless=True 로 백그라운드 실행 (화면 점유 없음)

환경변수:
  ITEK_USER  : 로그인 ID
  ITEK_PASS  : 로그인 PW

사용법:
  ITEK_USER=아이디 ITEK_PASS=비밀번호 python3 scripts/fetch_mis.py
"""

import os
import sys
import json
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL = "https://itek.gsneotek.co.kr/myoffice/ezportal/index_portal.aspx"
USER = os.environ.get("ITEK_USER", "")
PASS = os.environ.get("ITEK_PASS", "")

if not USER or not PASS:
    print("❌ 환경변수 ITEK_USER / ITEK_PASS 를 설정해주세요.")
    sys.exit(1)

# 브라우저 세션 쿠키 (itek.gsneotek.co.kr 로그인 상태)
# 환경변수 ITEK_SESSION_ID 로 ASP.NET_SessionId 오버라이드 가능
SESSION_COOKIES = [
    {"name": "ASP.NET_SessionId", "value": os.environ.get("ITEK_SESSION_ID", "e5ggg1oc3vzw1lbieyzv3ilt"),
     "domain": "itek.gsneotek.co.kr", "path": "/"},
    {"name": "GWUSER",
     "value": "NTJCREE1QzRDMzI5QTM2RkE5NEFEMTEzMzgyOTZENjgwNkZBQkFDMEMzMDU3Mjg4QkU0RjdBOTE0NTZBMzg2RENDMjI2MjNEMzE2MkRGMzdFNTZGMjg1M0Y4NTM0ODREOTY0RTU4MDhCOUEyNUU4RUYwMzY3MUVGQzg3RDBFRDZFMjg4RUZGOTBGQTE1OUJDMUY5RkVEMDAxQjk0NDFCNjhGMUI2ODEzMTQyMkNBN0FBQkFDRjgzOTE4QTNCMTgzRTAzMEJGMDIxMzlGQ0EwMDk0NTIxQzNEMDZDQTMxRTYyQzNERjdGMDMxOTUzQUJFQjA3NzA5MDkxRjRERDJCOTQxMTNGMTNEMDRDNjNEMEJFQzJENDlDOEU0RDlBNUUxM0U3RDNFRTBCMTE2QTdGQkUxMTgxN0M5NzMxODJGMjFCRkVBRUE4MUYyRkVEQzExMzc1MzAxNzAwMDJFQTY3N0QxN0IyNDZFQ0IwQkZEQTBDMzA3NUNFRTA4RURCQTIwMUE5MEYwNEEwN0FBRDM3N0ZCRTZCM0Y5MTg0MUIyN0JGNjA1QzE5NzZGM0YwMzI0RjRCMDBDMkYwMkZDODkzNjUyMkEwREM4ODVERTEwRkUyRUM1ODBGNzRDODZDRDc0QTlBMDZBREU4QzU3QjlFRjI0QjBCNTlBQkIyRDZBRjE=",
     "domain": ".itek.gsneotek.co.kr", "path": "/"},
    {"name": "LoginCookie",
     "value": "23313411210457662947178837581636178829475340370323315708531756220734093132661107223707104096005057660734534025423622370307104605005017880710562217881672178825420710",
     "domain": ".gsneotek.co.kr", "path": "/"},
    {"name": "Login", "value": "", "domain": ".gsneotek.co.kr", "path": "/"},
    {"name": "UTF8_Option", "value": "0", "domain": ".gsneotek.co.kr", "path": "/"},
    {"name": "lastActionTime", "value": "1776922890429", "domain": "itek.gsneotek.co.kr", "path": "/"},
    {"name": "lockTimeGap", "value": "60", "domain": "itek.gsneotek.co.kr", "path": "/"},
]

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"
        )
        # 세션 쿠키 주입
        ctx.add_cookies(SESSION_COOKIES)
        page = ctx.new_page()

        # ── 1. 포털 진입 (쿠키 세션으로 바로 접근) ────────────────
        print("🔐 세션 쿠키로 포털 진입 중...")
        try:
            page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
            page.screenshot(path=".pipeline/step1_portal.png")
            print(f"  → URL: {page.url}")
            print(f"  → 제목: {page.title()}")
        except PWTimeout:
            page.screenshot(path=".pipeline/step_error_portal.png")
            print("❌ 포털 진입 타임아웃 — step_error_portal.png 확인")
            browser.close()
            return

        # ── 2. MIS 메뉴 진입 ───────────────────────────────────────
        print("📂 MIS 메뉴 이동 중...")
        try:
            page.click("text=MIS", timeout=10000)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.screenshot(path=".pipeline/step4_mis.png")
            print("  → MIS 진입")
        except PWTimeout:
            page.screenshot(path=".pipeline/step_error_mis.png")
            print("❌ MIS 메뉴를 찾을 수 없음 — step_error_mis.png 확인")
            browser.close()
            return

        # ── 3. 손익관리 ────────────────────────────────────────────
        print("📂 손익관리 이동 중...")
        try:
            page.click("text=손익관리", timeout=10000)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.screenshot(path=".pipeline/step5_pnl.png")
            print("  → 손익관리 진입")
        except PWTimeout:
            page.screenshot(path=".pipeline/step_error_pnl.png")
            print("❌ 손익관리 메뉴를 찾을 수 없음 — step_error_pnl.png 확인")
            browser.close()
            return

        # ── 4. 매출/원가추정 ───────────────────────────────────────
        print("📂 매출/원가추정 이동 중...")
        try:
            page.click("text=매출/원가추정", timeout=10000)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.screenshot(path=".pipeline/step6_revenue_cost.png")
            print("  → 매출/원가추정 진입 ✅")
        except PWTimeout:
            page.screenshot(path=".pipeline/step_error_revenue.png")
            print("❌ 매출/원가추정 메뉴를 찾을 수 없음 — step_error_revenue.png 확인")
            browser.close()
            return

        # ── 5. 현재 URL 및 페이지 제목 출력 ──────────────────────
        print(f"\n📌 최종 URL  : {page.url}")
        print(f"📌 페이지 제목: {page.title()}")

        # ── 6. 테이블 데이터 추출 시도 ────────────────────────────
        print("\n📊 테이블 데이터 추출 중...")
        try:
            # iframe 내부일 가능성 고려
            frames = page.frames
            print(f"  frame 수: {len(frames)}")
            for i, frame in enumerate(frames):
                tables = frame.query_selector_all("table")
                if tables:
                    print(f"  frame[{i}] ({frame.url[:80]}): 테이블 {len(tables)}개 발견")

            # 메인 프레임 테이블
            rows = page.query_selector_all("table tr")
            print(f"  메인 프레임 테이블 행 수: {len(rows)}")
            if rows:
                sample = []
                for row in rows[:5]:
                    cells = row.query_selector_all("td, th")
                    sample.append([c.inner_text().strip() for c in cells])
                print("  샘플 (첫 5행):")
                for r in sample:
                    print(f"    {r}")
        except Exception as e:
            print(f"  테이블 추출 중 오류: {e}")

        browser.close()
        print("\n✅ 완료. .pipeline/ 폴더의 스크린샷을 확인하세요.")

if __name__ == "__main__":
    os.makedirs(".pipeline", exist_ok=True)
    run()
