"""MSA 분리 동등성 — backend(모놀리스)와 ai-service가 동일 ai_core를 쓰는지 검증.

ai-service main은 별도 환경에서 import해야 함(backend/services의 secrets.py가 표준
secrets를 가리는 오염 방지) → 서브프로세스로 격리 검증.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_aicore_is_single_source():
    """claude_api / llm_gateway가 ai_core를 re-export하는지(동일 객체)."""
    from services import ai_core, claude_api, llm_gateway
    assert claude_api.extract_costs is ai_core.extract_costs
    assert claude_api.classify_document is ai_core.classify_document
    assert claude_api.cross_validate is ai_core.cross_validate
    assert claude_api.chat_complete is ai_core.chat_complete
    assert llm_gateway.route_model is ai_core.route_model


def test_route_model_tiers():
    """모델 티어 라우팅이 backend·ai-service 공통(ai_core)으로 일관."""
    from services import ai_core
    assert ai_core.route_model("classify") == ai_core.HAIKU_MODEL
    assert ai_core.route_model("chat") == ai_core.HAIKU_MODEL
    assert ai_core.route_model("extract_costs") == ai_core.DEFAULT_MODEL
    assert ai_core.route_model("validate") == ai_core.DEFAULT_MODEL
    assert ai_core.route_model("unknown_task") == ai_core.DEFAULT_MODEL


def test_cost_category_normalization_shared():
    """category 정규화/이름강제 로직이 ai_core에 있고 결정론적."""
    from services import ai_core
    assert ai_core._normalize_cost_category("외주비") == "fee"
    assert ai_core._normalize_cost_category("알수없는값") == "etc"
    assert ai_core._force_category_by_name("복리후생비", "labor") == "welfare"
    assert ai_core._force_category_by_name("상여금", "etc") == "bonus"


def test_aiservice_imports_and_exposes_endpoints():
    """ai-service가 ai_core와 함께 import되고 9개 엔드포인트를 노출(서브프로세스 격리)."""
    aisvc_main = ROOT / "services" / "ai-service" / "main.py"
    aicore = ROOT / "backend" / "services" / "ai_core.py"
    script = (
        "import sys, shutil, tempfile\n"
        "d = tempfile.mkdtemp()\n"
        f"shutil.copy(r'{aisvc_main}', d)\n"
        f"shutil.copy(r'{aicore}', d)\n"
        "sys.path.insert(0, d)\n"
        "import main\n"
        "paths = {r.path for r in main.app.routes}\n"
        "need = ['/classify','/extract','/extract-costs','/extract-people',"
        "'/extract-schedule','/extract-rates','/extract-org','/validate','/chat']\n"
        "missing = [p for p in need if p not in paths]\n"
        "assert not missing, missing\n"
        "assert main.ai_core.extract_costs.__name__ == 'extract_costs'\n"
        "print('OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "OK" in r.stdout
