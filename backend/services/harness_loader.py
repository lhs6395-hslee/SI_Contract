"""하네스 JSON 로더 — harness/ 디렉토리의 선언적 설정을 Python에서 참조."""

from __future__ import annotations
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("si-contract")

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
    """실행 결과를 long_term_memory.json에 기록.

    멀티워커(uvicorn --workers N) 동시 기록 시 read-modify-write 경합으로 갱신이 유실되던
    문제 → 파일 락(fcntl.flock, 락 하에서 재read) + 원자적 rename으로 보호. 손상 JSON은 기본값.
    """
    import os
    import tempfile
    ltm_path = HARNESS_DIR / "long_term_memory.json"
    if not ltm_path.exists():
        return

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

    lock_path = str(ltm_path) + ".lock"
    try:
        import fcntl
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
    except Exception:
        lock_fd = None  # fcntl 미지원 환경 — best-effort

    try:
        try:
            ltm = json.loads(ltm_path.read_text(encoding="utf-8"))
            if not isinstance(ltm, dict):
                ltm = {}
        except (json.JSONDecodeError, OSError):
            logger.warning("long_term_memory.json 손상/읽기실패 — 기본값으로 재초기화")
            ltm = {}

        runs = ltm.get("runs", [])
        runs.insert(0, run_entry)
        ltm["runs"] = runs[:50]
        ltm["total_runs"] = ltm.get("total_runs", 0) + 1

        completed_runs = [r for r in ltm["runs"] if r.get("verdict") in ("approved", "needs_revision", "rejected")]
        if completed_runs:
            approved = sum(1 for r in completed_runs if r["verdict"] == "approved")
            ltm["success_rate"] = round(approved / len(completed_runs), 3)

        ltm["last_updated"] = datetime.now(timezone.utc).isoformat()

        fd, tmp = tempfile.mkstemp(dir=str(HARNESS_DIR), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(ltm, f, ensure_ascii=False, indent=2)
            os.replace(tmp, str(ltm_path))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
    finally:
        if lock_fd is not None:
            try:
                import fcntl
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            lock_fd.close()


def clear_cache() -> None:
    _cache.clear()
