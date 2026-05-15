"""DynamoDB 프로젝트 저장소 — DynamoDB 미설정 시 메모리 dict fallback.

테이블 구조:
- DYNAMODB_TABLE: 프로젝트 데이터 (extracted, revisions 포함)
- DYNAMODB_PIPELINE_TABLE: 파이프라인 실행 상태 (없으면 DYNAMODB_TABLE fallback)
"""

import os
import time
from decimal import Decimal
from typing import Optional

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


# 메모리 fallback (개발환경)
_projects: dict[str, dict] = {}
_pipeline_states: dict[str, dict] = {}


def _dynamo_project_table():
    import boto3
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(DYNAMODB_TABLE)


def _dynamo_pipeline_table():
    import boto3
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(DYNAMODB_PIPELINE_TABLE)


def is_dynamo_enabled() -> bool:
    """DynamoDB 테이블이 설정되어 있으면 True."""
    return bool(DYNAMODB_TABLE)


# ─── 프로젝트 CRUD ───────────────────────────────────────────

def save_project(project_data: dict) -> dict:
    """프로젝트 저장 (upsert). id 필수."""
    project_id = project_data["id"]
    project_data.setdefault("status", "in-progress")
    project_data.setdefault("revision", 0)
    project_data.setdefault("maxRevision", 0)
    project_data.setdefault("revenue", 0)
    project_data["updated"] = time.strftime("%Y-%m-%d")

    if is_dynamo_enabled():
        table = _dynamo_project_table()
        item = _float_to_decimal({"project_id": project_id, **project_data})
        table.put_item(Item=item)
        return project_data

    # 메모리 fallback
    _projects[project_id] = project_data
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
            items.append(_decimal_to_float(item))
        return items

    # 메모리 fallback
    result = []
    for p in _projects.values():
        entry = {k: v for k, v in p.items() if k != "extracted"}
        result.append(entry)
    return result


def delete_project(project_id: str) -> None:
    """프로젝트 삭제."""
    if is_dynamo_enabled():
        table = _dynamo_project_table()
        table.delete_item(Key={"project_id": project_id})
        return

    _projects.pop(project_id, None)


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
            resp = table.get_item(Key={"project_id": project_id})
            item = resp.get("Item")
            if not item:
                return None
            return _decimal_to_float(item.get("pipeline_state"))
        else:
            resp = table.get_item(
                Key={"project_id": project_id},
                ProjectionExpression="pipeline_state",
            )
            item = resp.get("Item")
            if not item:
                return None
            return _decimal_to_float(item.get("pipeline_state"))

    return _pipeline_states.get(project_id)


# ─── 편집 잠금 (Clash 방지) ─────────────────────────────────

def acquire_edit_lock(project_id: str, user_id: str, timeout: int = 300) -> dict:
    """편집 잠금 획득. 이미 다른 사용자가 잠금 중이면 거부."""
    import time as _time
    now = _time.time()

    if is_dynamo_enabled():
        table = _dynamo_project_table()
        resp = table.get_item(Key={"project_id": project_id}, ProjectionExpression="edit_lock")
        item = resp.get("Item", {})
        lock = _decimal_to_float(item.get("edit_lock", {}))

        if lock and lock.get("userId") != user_id:
            if now - lock.get("timestamp", 0) < timeout:
                return {"locked": True, "by": lock.get("userId")}

        table.update_item(
            Key={"project_id": project_id},
            UpdateExpression="SET edit_lock = :l",
            ExpressionAttributeValues={":l": _float_to_decimal({"userId": user_id, "timestamp": int(now)})},
        )
        return {"locked": False, "acquired": True, "userId": user_id}

    # 메모리 fallback
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
