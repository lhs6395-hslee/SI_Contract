"""엔드포인트 인가 게이트 테스트 — _assert_project_access를 실제 라우트로 호출.

2라운드 감사에서 main.py:739 ADMIN_EMAIL NameError가 단위테스트를 통과한 이유 =
엔드포인트를 통해 게이트를 호출하는 테스트가 없었음. 그 공백을 메운다.
메모리 fallback(DYNAMODB_TABLE="")로 토큰 서명까지 실제 경로 사용.
"""
import base64
import hashlib
import hmac
import importlib
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_and_store(monkeypatch):
    monkeypatch.setenv("DYNAMODB_TABLE", "")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("TEST_USERNAME", "test")
    monkeypatch.setenv("TEST_PASSWORD", "test")
    import services.project_store as ps
    importlib.reload(ps)
    import main
    importlib.reload(main)
    ps._projects.clear()
    return TestClient(main.app), main, ps


def _token(main, username):
    payload = f"{username}:{int(time.time()) + 28800}"
    sig = hmac.new(main.JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()


def _hdr(main, username):
    return {"Authorization": f"Bearer {_token(main, username)}"}


def test_legacy_project_access_no_nameerror(client_and_store):
    """레거시(owner 없음) 프로젝트 + 비admin → 500(NameError) 아닌 404여야 함. (#1 회귀 가드)"""
    client, main, ps = client_and_store
    ps.save_project({"id": "legacy1", "name": "L", "extracted": {}})  # owner 없음
    r = client.get("/api/projects/legacy1", headers=_hdr(main, "test"))
    assert r.status_code == 404, r.text


def test_lock_status_requires_auth(client_and_store):
    """lock-status 무토큰 → 401."""
    client, main, ps = client_and_store
    r = client.get("/api/projects/whatever/lock-status")
    assert r.status_code == 401, r.text


def test_pipeline_status_requires_auth(client_and_store):
    """pipeline status 무토큰 → 401 (이번 라운드 #2 수정)."""
    client, main, ps = client_and_store
    r = client.get("/api/pipeline/whatever/status")
    assert r.status_code == 401, r.text


def test_owner_can_access_own_project(client_and_store):
    """소유자는 본인 프로젝트 단건 조회 200."""
    client, main, ps = client_and_store
    ps.save_project({"id": "p_test", "name": "P", "extracted": {}}, owner="test")
    r = client.get("/api/projects/p_test", headers=_hdr(main, "test"))
    assert r.status_code == 200, r.text


def test_nonowner_blocked_404(client_and_store):
    """타인 소유 프로젝트 → 404(존재 은닉)."""
    client, main, ps = client_and_store
    ps.save_project({"id": "p_alice", "name": "A", "extracted": {}}, owner="alice@x.com")
    r = client.get("/api/projects/p_alice", headers=_hdr(main, "test"))
    assert r.status_code == 404, r.text


def test_admin_sees_legacy(client_and_store):
    """admin은 레거시 프로젝트(owner 없음) 접근 200."""
    client, main, ps = client_and_store
    ps.save_project({"id": "legacy2", "name": "L2", "extracted": {}})
    r = client.get("/api/projects/legacy2", headers=_hdr(main, "admin"))
    assert r.status_code == 200, r.text


def test_revision_range_validation(client_and_store):
    """revision 음수 → 422 (이번 라운드 #5)."""
    client, main, ps = client_and_store
    ps.save_project({"id": "p_test", "name": "P", "extracted": {}}, owner="test")
    r = client.get("/api/files/p_test?revision=-5", headers=_hdr(main, "test"))
    assert r.status_code == 422, r.text
