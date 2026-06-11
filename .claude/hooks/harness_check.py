#!/usr/bin/env python3
"""
PreToolUse hook: Python 파일 수정 전 하네스 우선 원칙 강제.
- backend/services/*.py 편집 시도 → 차단 + 하네스 확인 체크리스트 출력
- 사용자 확인 후 `touch /tmp/si-py-approved` → 5분간 통과
"""
import json, sys, os, time

try:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", data)
    fp = tool_input.get("file_path", "")
except Exception:
    sys.exit(0)

if not fp.endswith(".py"):
    sys.exit(0)

if "backend/services/" not in fp and "backend/main.py" not in fp:
    sys.exit(0)

FLAG = "/tmp/si-py-approved"
if os.path.exists(FLAG):
    age = time.time() - os.path.getmtime(FLAG)
    if age < 300:
        os.remove(FLAG)
        sys.exit(0)
    os.remove(FLAG)

print("⛔  [하네스 우선 원칙 — 차단됨]")
print(f"    대상: {fp}")
print()
print("이 변경을 harness JSON으로 표현할 수 있는가?")
print("  • 셀 주소·행번호·열 매핑 변경  →  harness/cell_map.json")
print("  • 검증 규칙·임계값·판정 기준   →  harness/verifier_rules.json")
print("  • 실패 패턴·회피 방법 기록     →  harness/long_term_memory.json")
print("  • 변경 근거·예측·회귀 위험     →  harness/change_manifest.jsonl")
print()
print("Python 수정이 불가피하다면:")
print("  1. 사용자에게 하네스로 불가능한 이유를 먼저 설명")
print("  2. 사용자 확인 후: Bash(touch /tmp/si-py-approved)")
print("  3. 즉시 Python 수정 재시도 (5분 유효)")
sys.exit(1)
