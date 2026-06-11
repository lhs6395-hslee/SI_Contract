"""하네스 JSON 로더 — harness/ 디렉토리의 선언적 설정을 Python에서 참조."""

from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

HARNESS_DIR = Path(__file__).parent.parent.parent / "harness"

_cache: dict[str, dict] = {}


def _load(name: str) -> dict:
    if name not in _cache:
        path = HARNESS_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"Harness file not found: {path}")
        _cache[name] = json.loads(path.read_text(encoding="utf-8"))
    return _cache[name]


def cell_map() -> dict:
    return _load("cell_map.json")


def verifier_rules() -> dict:
    return _load("verifier_rules.json")


def long_term_memory() -> dict:
    return _load("long_term_memory.json")


def record_run(project_id: str, scenario: str, revision: int,
               verdict: str, score: float, errors: list[str],
               token_usage: dict | None = None) -> None:
    """실행 결과를 long_term_memory.json에 기록."""
    ltm_path = HARNESS_DIR / "long_term_memory.json"
    if not ltm_path.exists():
        return

    ltm = json.loads(ltm_path.read_text(encoding="utf-8"))
    run_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "scenario": scenario,
        "revision": revision,
        "verdict": verdict,
        "score": score,
        "errors_count": len(errors),
        "token_usage": token_usage or {},
    }

    runs = ltm.get("runs", [])
    runs.insert(0, run_entry)
    ltm["runs"] = runs[:50]
    ltm["total_runs"] = ltm.get("total_runs", 0) + 1

    completed_runs = [r for r in runs if r.get("verdict") in ("approved", "needs_revision", "rejected")]
    if completed_runs:
        approved = sum(1 for r in completed_runs if r["verdict"] == "approved")
        ltm["success_rate"] = round(approved / len(completed_runs), 3)

    ltm["last_updated"] = datetime.now(timezone.utc).isoformat()
    ltm_path.write_text(json.dumps(ltm, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_cache() -> None:
    _cache.clear()
