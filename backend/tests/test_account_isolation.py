"""계정 격리 단위테스트 — owner 저장/보존, 목록 필터, S3 owner prefix, role 판별.

DynamoDB 미설정 시 메모리 fallback으로 동작 → 로컬에서 검증 가능.
"""
import importlib

import pytest

from services.cognito_auth import resolve_role, ADMIN_EMAIL


@pytest.fixture
def store():
    """메모리 fallback 모드의 project_store (테스트마다 초기화)."""
    import services.project_store as ps
    importlib.reload(ps)
    assert not ps.is_dynamo_enabled(), "이 테스트는 DYNAMODB_TABLE 미설정 환경 전제"
    ps._projects.clear()
    ps._list_cache["data"] = None
    ps._list_cache["version"] = None
    return ps


# ─── role 판별 ─────────────────────────────────────────────

def test_resolve_role_admin():
    assert resolve_role(ADMIN_EMAIL) == "admin"
    assert resolve_role(ADMIN_EMAIL.upper()) == "admin"  # 대소문자 무관


def test_resolve_role_user():
    assert resolve_role("someone@gsneotek.com") == "user"
    assert resolve_role("") == "user"
    assert resolve_role(None) == "user"


# ─── owner 저장/보존 ────────────────────────────────────────

def test_save_records_owner(store):
    store.save_project({"id": "p1", "name": "A"}, owner="alice@x.com")
    assert store.load_project("p1")["owner"] == "alice@x.com"


def test_owner_preserved_on_update(store):
    store.save_project({"id": "p1", "name": "A"}, owner="alice@x.com")
    # bob이 같은 프로젝트를 덮어써도 owner는 alice 유지 (소유권 탈취 방지)
    store.save_project({"id": "p1", "name": "A-edited"}, owner="bob@x.com")
    p = store.load_project("p1")
    assert p["owner"] == "alice@x.com"
    assert p["name"] == "A-edited"


def test_save_without_owner_leaves_none(store):
    store.save_project({"id": "p1", "name": "A"})
    assert "owner" not in store.load_project("p1")


# ─── 목록 필터 ─────────────────────────────────────────────

def test_list_filters_by_owner(store):
    store.save_project({"id": "p1", "name": "A"}, owner="alice@x.com")
    store.save_project({"id": "p2", "name": "B"}, owner="bob@x.com")
    alice = store.list_projects_cached(owner="alice@x.com", is_admin=False)
    assert {p["id"] for p in alice} == {"p1"}


def test_admin_sees_all(store):
    store.save_project({"id": "p1", "name": "A"}, owner="alice@x.com")
    store.save_project({"id": "p2", "name": "B"}, owner="bob@x.com")
    allp = store.list_projects_cached(owner=ADMIN_EMAIL, is_admin=True)
    assert {p["id"] for p in allp} == {"p1", "p2"}


def test_legacy_no_owner_belongs_to_admin(store):
    # owner 없는 레거시 레코드는 admin 소유로 간주 → 일반 사용자에겐 안 보임
    store.save_project({"id": "legacy", "name": "old"})
    assert store.list_projects_cached(owner="alice@x.com", is_admin=False) == []
    admin = store.list_projects_cached(owner=ADMIN_EMAIL, is_admin=True)
    assert {p["id"] for p in admin} == {"legacy"}


def test_no_owner_non_admin_returns_empty(store):
    store.save_project({"id": "p1", "name": "A"}, owner="alice@x.com")
    # 인증 없는(owner=None, admin 아님) 호출은 빈 목록
    assert store.list_projects_cached(owner=None, is_admin=False) == []


# ─── S3 owner prefix ───────────────────────────────────────

def test_s3_prefix_with_owner():
    from services.s3_storage import _project_prefix
    assert _project_prefix("p1", None, "alice@x.com") == "projects/alice@x.com/p1/"
    assert _project_prefix("p1", 2, "alice@x.com") == "projects/alice@x.com/p1/rev2/"


def test_s3_prefix_legacy_without_owner():
    from services.s3_storage import _project_prefix
    assert _project_prefix("p1", None, None) == "projects/p1/"
    assert _project_prefix("p1", 0, None) == "projects/p1/rev0/"
