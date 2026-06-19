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


def test_parse_json_ignores_trailing_prose():
    """모델이 JSON 뒤에 설명/표를 덧붙여도 균형 추출로 JSON만 파싱(실측 회귀 가드).

    naive greedy 정규식은 뒤따르는 산문 속 ']'/'}'까지 삼켜 파싱 전체가 실패했었다.
    """
    from services import ai_core
    raw = (
        '```json\n{"a": 1, "list": [1, 2], "s": "값] 안의 괄호 }"}\n```\n\n'
        "| 항목 | 설명 |\n| 단위 | `[단위:천원,%]` 라벨 존재 → unitGuessed: false |\n"
    )
    parsed = ai_core._parse_json(raw, fallback={"FAIL": True})
    assert parsed == {"a": 1, "list": [1, 2], "s": "값] 안의 괄호 }"}


def test_parse_json_array_with_nested_objects():
    """배열 응답(cross_validate 형태)도 균형 추출이 올바르게 끝을 찾는다."""
    from services import ai_core
    raw = 'noise [{"x": 1}, {"y": 2}] 그리고 뒤에 설명 ] 더'
    assert ai_core._parse_json(raw, fallback=None) == [{"x": 1}, {"y": 2}]


def test_import_execution_plan_parses_unit_confidence(monkeypatch):
    """import_execution_plan: 모델 JSON을 그대로 파싱하고 금액 unitConfidence/importMeta를 보존.

    Bedrock 미호출(_call_claude 스텁) — 파싱/구조 계약만 검증한다.
    """
    from services import ai_core
    import json as _json

    canned = _json.dumps({
        "extracted": {
            "projectName": {"value": "퀘이사존 운영", "source": "p.1", "confidence": "verified"},
            "revenue": {"value": 91800000, "unit": "원", "unitConfidence": "low",
                        "source": "산출내역", "confidence": "guess"},
            "cost": {"value": 72000000, "unit": "원", "unitConfidence": "high",
                     "source": "산출내역", "confidence": "verified"},
        },
        "costItems": [
            {"category": "fee", "name": "AWS 운영", "executionAmount": 72000000,
             "unitConfidence": "low", "source": "수수료", "confidence": "guess"},
        ],
        "rates": None,
        "importMeta": {"unitGuessed": True, "missingFields": ["pm"]},
    }, ensure_ascii=False)

    monkeypatch.setattr(ai_core, "_call_claude", lambda *a, **k: canned)
    result = ai_core.import_execution_plan([{"filename": "plan.pdf", "text": "집행계획서", "images": []}])

    assert result["extracted"]["projectName"]["value"] == "퀘이사존 운영"
    assert result["extracted"]["revenue"]["unitConfidence"] == "low"
    assert result["extracted"]["cost"]["unitConfidence"] == "high"
    assert result["importMeta"]["unitGuessed"] is True
    assert "pm" in result["importMeta"]["missingFields"]
    assert result["costItems"][0]["unitConfidence"] == "low"


def test_import_execution_plan_fallback_on_garbage(monkeypatch):
    """모델 응답이 JSON이 아니면 안전한 fallback(unitGuessed=True)을 반환."""
    from services import ai_core
    monkeypatch.setattr(ai_core, "_call_claude", lambda *a, **k: "정상 JSON 아님")
    result = ai_core.import_execution_plan([{"filename": "x.pdf", "text": "t", "images": []}])
    assert result["extracted"] == {}
    assert result["costItems"] == []
    assert result["importMeta"]["unitGuessed"] is True


def test_aiservice_imports_and_exposes_endpoints():
    """ai-service가 ai_core와 함께 import되고 10개 엔드포인트를 노출(서브프로세스 격리)."""
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
        "'/extract-schedule','/extract-rates','/extract-org','/import','/validate','/chat']\n"
        "missing = [p for p in need if p not in paths]\n"
        "assert not missing, missing\n"
        "assert main.ai_core.extract_costs.__name__ == 'extract_costs'\n"
        "assert main.ai_core.import_execution_plan.__name__ == 'import_execution_plan'\n"
        "print('OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert r.returncode == 0, f"stdout={r.stdout} stderr={r.stderr}"
    assert "OK" in r.stdout
