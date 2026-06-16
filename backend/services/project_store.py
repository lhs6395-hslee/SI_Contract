"""DynamoDB 프로젝트 저장소 — DynamoDB 미설정 시 메모리 dict fallback.

테이블 구조:
- DYNAMODB_TABLE: 프로젝트 데이터 (extracted, revisions 포함)
- DYNAMODB_PIPELINE_TABLE: 파이프라인 실행 상태 (없으면 DYNAMODB_TABLE fallback)
"""

import os
import time
from decimal import Decimal
from typing import Optional

from services.cognito_auth import ADMIN_EMAIL

DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "")
DYNAMODB_PIPELINE_TABLE = os.getenv("DYNAMODB_PIPELINE_TABLE", DYNAMODB_TABLE)


def _float_to_decimal(obj):
    """DynamoDB용 float→Decimal + dict키 str 변환."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {str(k): _float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_float_to_decimal(i) for i in obj]
    return obj


def _decimal_to_float(obj):
    """DynamoDB 응답 Decimal→float 재귀 변환."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(i) for i in obj]
    return obj


def _derive_field(project_data: dict, field: str) -> str:
    """extracted 내부에서 필드값 복구 — ExtractedField({value}) 또는 plain string."""
    ext = project_data.get("extracted") or {}
    top = ext.get(field)
    if top and isinstance(top, str):
        return top
    inner = (ext.get("extracted") or {}).get(field)
    if isinstance(inner, dict):
        return str(inner.get("value") or "")
    if isinstance(inner, str):
        return inner
    return ""


# 메모리 fallback (개발환경)
_projects: dict[str, dict] = {}
_pipeline_states: dict[str, dict] = {}

# ─── 프로젝트 목록 캐시 (버전 스탬프 기반) ──────────────────
# uvicorn --workers N: 프로세스별 캐시이므로 단순 invalidate로는 다른 워커에 전파 불가.
# DynamoDB __meta__ 레코드의 버전 카운터를 매 조회 시 확인(get_item 1회)해
# write 직후 모든 워커/replica에서 즉시 최신 데이터를 보장한다.
_META_KEY = "__meta__"
_list_cache: dict = {"data": None, "version": None}
_memory_version = 0


def _bump_projects_version() -> None:
    """프로젝트 write/delete 시 버전 증가 — 모든 워커의 캐시 즉시 무효화."""
    global _memory_version
    if is_dynamo_enabled():
        try:
            _dynamo_project_table().update_item(
                Key={"project_id": _META_KEY},
                UpdateExpression="ADD projects_version :one",
                ExpressionAttributeValues={":one": Decimal(1)},
            )
        except Exception:
            # 버전 갱신 실패 시 로컬 캐시라도 비움
            _list_cache["data"] = None
        return
    _memory_version += 1


def _get_projects_version():
    if is_dynamo_enabled():
        resp = _dynamo_project_table().get_item(
            Key={"project_id": _META_KEY},
            ProjectionExpression="projects_version",
            ConsistentRead=True,
        )
        return resp.get("Item", {}).get("projects_version", Decimal(0))
    return _memory_version


def list_projects_cached(owner: Optional[str] = None, is_admin: bool = False) -> list[dict]:
    """버전 일치 시 캐시 반환, 불일치 시 단일 scan으로 갱신.

    캐시는 전체 scan 결과(사용자 무관)를 유지하고, owner 필터는 read 이후
    메모리에서 적용한다 — scan 비용을 사용자별로 늘리지 않으면서 목록을 격리.

    - is_admin=True: 전체 반환.
    - owner 지정: owner가 일치하는 것만. owner 없는 레거시 레코드는 admin 소유로 간주
      (일반 사용자에겐 안 보임).
    - owner=None & not admin: 빈 목록(인증 없는 호출 방어).
    """
    version = _get_projects_version()
    if _list_cache["data"] is not None and _list_cache["version"] == version:
        data = _list_cache["data"]
    else:
        data = list_projects_full()
        _list_cache["data"] = data
        _list_cache["version"] = version
    if is_admin:
        return data
    if not owner:
        return []
    return [p for p in data if (p.get("owner") or ADMIN_EMAIL) == owner]


# DynamoDB 리소스/테이블 생성은 비싸므로 재사용하되, **boto3 resource는 thread-safe가
# 아니므로 스레드별(thread-local)로 보관**한다. (모듈 싱글톤 공유 시 uvicorn 멀티워커 +
# FastAPI threadpool 환경에서 get_item이 간헐적으로 빈 결과를 반환해 result 404 유발.)
import threading as _threading
_tl = _threading.local()


def _get_dynamo_resource():
    r = getattr(_tl, "resource", None)
    if r is None:
        import boto3
        r = _tl.resource = boto3.resource("dynamodb")
    return r


def _dynamo_project_table():
    t = getattr(_tl, "project_table", None)
    if t is None:
        t = _tl.project_table = _get_dynamo_resource().Table(DYNAMODB_TABLE)
    return t


def _dynamo_pipeline_table():
    t = getattr(_tl, "pipeline_table", None)
    if t is None:
        t = _tl.pipeline_table = _get_dynamo_resource().Table(DYNAMODB_PIPELINE_TABLE)
    return t


def is_dynamo_enabled() -> bool:
    """DynamoDB 테이블이 설정되어 있으면 True."""
    return bool(DYNAMODB_TABLE)


# ─── 프로젝트 CRUD ───────────────────────────────────────────

def save_project(project_data: dict, owner: Optional[str] = None) -> dict:
    """프로젝트 저장 (upsert). id 필수.

    owner: 최초 생성 시 소유자(email)를 기록. 업데이트 시에는 기존 owner를
    보존한다(남이 덮어쓰며 소유권을 탈취하지 못하게). owner=None이면 손대지 않음.
    """
    project_id = project_data["id"]
    if not project_data.get("name"):
        project_data["name"] = _derive_field(project_data, "projectName") or ""
    if not project_data.get("client"):
        project_data["client"] = _derive_field(project_data, "client") or ""
    project_data.setdefault("status", "in-progress")
    project_data.setdefault("revision", 0)
    project_data.setdefault("maxRevision", 0)
    project_data.setdefault("revenue", 0)
    project_data["updated"] = time.strftime("%Y-%m-%d")

    # created_at: 최초 1회만 서버 UTC ISO로 세팅, 업데이트 시 기존 값 보존 (읽기전용 시스템 필드)
    if not project_data.get("created_at"):
        from datetime import datetime, timezone
        existing_ca = None
        if is_dynamo_enabled():
            try:
                resp = _dynamo_project_table().get_item(
                    Key={"project_id": project_id}, ProjectionExpression="created_at"
                )
                existing_ca = resp.get("Item", {}).get("created_at")
            except Exception:
                pass
        else:
            existing_ca = (_projects.get(project_id) or {}).get("created_at")
        project_data["created_at"] = existing_ca or datetime.now(timezone.utc).isoformat()

    # owner: 최초 생성 시에만 기록, 이후 기존 값 보존(소유권 탈취 방지).
    existing_owner = None
    if is_dynamo_enabled():
        try:
            resp = _dynamo_project_table().get_item(
                Key={"project_id": project_id}, ProjectionExpression="#o",
                ExpressionAttributeNames={"#o": "owner"},
            )
            existing_owner = resp.get("Item", {}).get("owner")
        except Exception:
            pass
    else:
        existing_owner = (_projects.get(project_id) or {}).get("owner")
    resolved_owner = existing_owner or owner
    if resolved_owner:
        project_data["owner"] = resolved_owner

    if is_dynamo_enabled():
        table = _dynamo_project_table()
        item = _float_to_decimal({"project_id": project_id, **project_data})
        table.put_item(Item=item)
        _bump_projects_version()
        return project_data

    # 메모리 fallback
    _projects[project_id] = project_data
    _bump_projects_version()
    return project_data


def load_project(project_id: str) -> Optional[dict]:
    """프로젝트 상세 조회 (extracted 포함)."""
    if is_dynamo_enabled():
        table = _dynamo_project_table()
        resp = table.get_item(Key={"project_id": project_id})
        item = resp.get("Item")
        if not item:
            return None
        item.pop("project_id", None)
        return _decimal_to_float(item)

    return _projects.get(project_id)


def list_projects() -> list[dict]:
    """프로젝트 목록 (extracted 제외 — 목록용 경량)."""
    if is_dynamo_enabled():
        table = _dynamo_project_table()
        resp = table.scan(
            ProjectionExpression="project_id, #n, client, #s, revision, maxRevision, revenue, updated",
            ExpressionAttributeNames={"#n": "name", "#s": "status"},
        )
        items = []
        for item in resp.get("Items", []):
            item["id"] = item.pop("project_id", item.get("id"))
            item.setdefault("name", "")
            item.setdefault("client", "")
            items.append(_decimal_to_float(item))
        return items

    # 메모리 fallback
    result = []
    for p in _projects.values():
        entry = {k: v for k, v in p.items() if k != "extracted"}
        result.append(entry)
    return result


def list_projects_full() -> list[dict]:
    """프로젝트 전체 데이터 목록 (revisions 제외) — 단일 scan, N+1 get_item 방지.

    테이블에 user별 파티션 키가 없어 query 전환 불가 — scan 1회로 통합.
    """
    if is_dynamo_enabled():
        table = _dynamo_project_table()
        items = []
        scan_kwargs = {}
        while True:
            resp = table.scan(**scan_kwargs)
            for item in resp.get("Items", []):
                item["id"] = item.pop("project_id", item.get("id"))
                if item["id"] == _META_KEY:
                    continue
                item.pop("revisions", None)
                item.pop("pipeline_state", None)
                if not item.get("name"):
                    item["name"] = _derive_field(item, "projectName") or f"프로젝트 ({item['id']})"
                if not item.get("client"):
                    item["client"] = _derive_field(item, "client")
                items.append(_decimal_to_float(item))
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return items

    result = []
    for p in _projects.values():
        entry = {k: v for k, v in p.items() if k != "revisions"}
        result.append(entry)
    return result


def delete_project(project_id: str) -> None:
    """프로젝트 삭제."""
    if is_dynamo_enabled():
        table = _dynamo_project_table()
        table.delete_item(Key={"project_id": project_id})
        _bump_projects_version()
        return

    _projects.pop(project_id, None)
    _bump_projects_version()


# ─── 파이프라인 상태 ─────────────────────────────────────────

def save_pipeline_state(project_id: str, state: dict) -> None:
    """파이프라인 실행 상태 저장 (별도 테이블 또는 프로젝트 테이블 공유). TTL 30일."""
    if is_dynamo_enabled():
        table = _dynamo_pipeline_table()
        # TTL: 30일 후 자동 삭제
        import time as _time
        expires_at = int(_time.time()) + 30 * 24 * 3600

        if DYNAMODB_PIPELINE_TABLE != DYNAMODB_TABLE:
            item = _float_to_decimal({"project_id": project_id, "pipeline_state": state, "expires_at": expires_at})
            table.put_item(Item=item)
        else:
            table.update_item(
                Key={"project_id": project_id},
                UpdateExpression="SET pipeline_state = :s, expires_at = :e",
                ExpressionAttributeValues={":s": _float_to_decimal(state), ":e": expires_at},
            )
        return

    _pipeline_states[project_id] = state


def load_pipeline_state(project_id: str) -> Optional[dict]:
    """파이프라인 상태 조회."""
    if is_dynamo_enabled():
        table = _dynamo_pipeline_table()
        if DYNAMODB_PIPELINE_TABLE != DYNAMODB_TABLE:
            resp = table.get_item(Key={"project_id": project_id}, ConsistentRead=True)
            item = resp.get("Item")
            if not item:
                return None
            return _decimal_to_float(item.get("pipeline_state"))
        else:
            resp = table.get_item(
                Key={"project_id": project_id},
                ProjectionExpression="pipeline_state",
                ConsistentRead=True,
            )
            item = resp.get("Item")
            if not item:
                return None
            return _decimal_to_float(item.get("pipeline_state"))

    return _pipeline_states.get(project_id)


# ─── 편집 잠금 (Clash 방지) ─────────────────────────────────

_memory_lock_mutex = None  # 메모리 fallback용 — 지연 초기화


def acquire_edit_lock(project_id: str, user_id: str, timeout: int = 300) -> dict:
    """편집 잠금 획득 — DynamoDB ConditionExpression 기반 atomic conditional write.

    잠금 레코드가 없거나, 본인 소유이거나, TTL(timeout) 만료 시에만 write 성공.
    실패 시 {"locked": True, "by": <owner>} 반환 (라우터에서 409 처리).
    """
    import time as _time
    now = _time.time()

    if is_dynamo_enabled():
        from botocore.exceptions import ClientError

        table = _dynamo_project_table()
        try:
            table.update_item(
                Key={"project_id": project_id},
                UpdateExpression="SET edit_lock = :l",
                # 없음 / 본인 소유 / TTL 만료 시에만 성공 — race condition 방지
                ConditionExpression=(
                    "attribute_not_exists(edit_lock)"
                    " OR edit_lock.userId = :u"
                    " OR edit_lock.#ts < :expired"
                ),
                ExpressionAttributeNames={"#ts": "timestamp"},
                ExpressionAttributeValues={
                    ":l": _float_to_decimal({"userId": user_id, "timestamp": int(now)}),
                    ":u": user_id,
                    ":expired": Decimal(int(now - timeout)),
                },
            )
            return {"locked": False, "acquired": True, "userId": user_id}
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            # 다른 사용자가 유효한 잠금 보유 — 현재 owner 조회
            resp = table.get_item(Key={"project_id": project_id}, ProjectionExpression="edit_lock")
            lock = _decimal_to_float(resp.get("Item", {}).get("edit_lock", {}))
            return {"locked": True, "by": lock.get("userId")}

    # 메모리 fallback — threading.Lock으로 atomic 보장
    global _memory_lock_mutex
    if _memory_lock_mutex is None:
        import threading
        _memory_lock_mutex = threading.Lock()
    with _memory_lock_mutex:
        lock = _pipeline_states.get(f"lock_{project_id}")
        if lock and lock.get("userId") != user_id and now - lock.get("timestamp", 0) < timeout:
            return {"locked": True, "by": lock.get("userId")}
        _pipeline_states[f"lock_{project_id}"] = {"userId": user_id, "timestamp": now}
        return {"locked": False, "acquired": True, "userId": user_id}


def release_edit_lock(project_id: str) -> dict:
    """편집 잠금 해제."""
    if is_dynamo_enabled():
        table = _dynamo_project_table()
        table.update_item(
            Key={"project_id": project_id},
            UpdateExpression="REMOVE edit_lock",
        )
        return {"released": True}

    _pipeline_states.pop(f"lock_{project_id}", None)
    return {"released": True}


def get_edit_lock_status(project_id: str, timeout: int = 300) -> dict:
    """편집 잠금 상태 조회."""
    import time as _time
    now = _time.time()

    if is_dynamo_enabled():
        table = _dynamo_project_table()
        resp = table.get_item(Key={"project_id": project_id}, ProjectionExpression="edit_lock")
        item = resp.get("Item", {})
        lock = _decimal_to_float(item.get("edit_lock", {}))
        if lock and now - lock.get("timestamp", 0) < timeout:
            return {"locked": True, "by": lock.get("userId"), "expires_in": int(timeout - (now - lock.get("timestamp", 0)))}
        return {"locked": False}

    lock = _pipeline_states.get(f"lock_{project_id}")
    if lock and now - lock.get("timestamp", 0) < timeout:
        return {"locked": True, "by": lock.get("userId"), "expires_in": int(timeout - (now - lock.get("timestamp", 0)))}
    return {"locked": False}
