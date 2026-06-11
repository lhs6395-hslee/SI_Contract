"""LLM Gateway — 모델 티어링 + 사용자별 토큰 제한.

티어링:
  - haiku: 분류, 짧은 Q&A, 간단 추출
  - sonnet: 전체 필드 추출, 교차 검증, AI 리뷰 (기본)
  - opus: configmap override 시에만

토큰 제한:
  - DynamoDB에 사용자별 일간 사용량 기록
  - 기본 한도: 100,000 토큰/일 (DAILY_TOKEN_LIMIT)
  - 초과 시 RuntimeError("token_limit_exceeded")
"""

import os
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger("si-contract")

HAIKU_MODEL = os.getenv("HAIKU_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "us.anthropic.claude-sonnet-4-6-20250514-v1:0")
OPUS_MODEL = os.getenv("OPUS_MODEL", "")
DAILY_TOKEN_LIMIT = int(os.getenv("DAILY_TOKEN_LIMIT", "100000"))

TASK_TIER = {
    "classify": "haiku",
    "chat_simple": "haiku",
    "extract_single": "haiku",
    "extract_full": "sonnet",
    "extract_costs": "sonnet",
    "extract_people": "sonnet",
    "extract_schedule": "sonnet",
    "extract_rates": "sonnet",
    "extract_org": "sonnet",
    "validate": "sonnet",
    "review": "sonnet",
}

MODEL_MAP = {
    "haiku": HAIKU_MODEL,
    "sonnet": DEFAULT_MODEL,
    "opus": OPUS_MODEL or DEFAULT_MODEL,
}


def route_model(task_type: str, user_id: str = "default") -> str:
    """작업 유형에 따라 모델 ID 반환."""
    tier = TASK_TIER.get(task_type, "sonnet")
    model = MODEL_MAP.get(tier, DEFAULT_MODEL)
    logger.debug("LLM route: task=%s tier=%s model=%s user=%s", task_type, tier, model, user_id)
    return model


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_dynamo_table():
    table_name = os.getenv("DYNAMODB_TABLE", "")
    if not table_name:
        return None
    import boto3
    return boto3.resource("dynamodb").Table(table_name)


def check_and_record_tokens(user_id: str, input_tokens: int, output_tokens: int) -> bool:
    """토큰 사용량 기록 + 한도 체크. True=허용, False=한도 초과.

    DynamoDB 미설정 시 항상 True (로컬 개발).
    """
    total = input_tokens + output_tokens
    if DAILY_TOKEN_LIMIT <= 0:
        return True

    table = _get_dynamo_table()
    if not table:
        return True

    today = _today_key()
    record_key = f"token_usage#{user_id}#{today}"

    try:
        from decimal import Decimal
        resp = table.get_item(Key={"project_id": record_key})
        item = resp.get("Item", {})
        current_usage = int(item.get("total_tokens", 0))

        if current_usage >= DAILY_TOKEN_LIMIT:
            return False

        expires_at = int(time.time()) + 86400 * 2

        table.update_item(
            Key={"project_id": record_key},
            UpdateExpression="SET total_tokens = if_not_exists(total_tokens, :zero) + :t, "
                           "input_tokens = if_not_exists(input_tokens, :zero) + :i, "
                           "output_tokens = if_not_exists(output_tokens, :zero) + :o, "
                           "call_count = if_not_exists(call_count, :zero) + :one, "
                           "last_call = :now, "
                           "expires_at = :exp",
            ExpressionAttributeValues={
                ":t": Decimal(str(total)),
                ":i": Decimal(str(input_tokens)),
                ":o": Decimal(str(output_tokens)),
                ":one": Decimal("1"),
                ":zero": Decimal("0"),
                ":now": datetime.now(timezone.utc).isoformat(),
                ":exp": expires_at,
            },
        )
        return True
    except Exception as e:
        logger.warning("Token tracking failed (allowing request): %s", e)
        return True


def get_token_usage(user_id: str) -> dict:
    """사용자의 오늘 토큰 사용량 조회."""
    table = _get_dynamo_table()
    if not table:
        return {"used": 0, "limit": DAILY_TOKEN_LIMIT, "remaining": DAILY_TOKEN_LIMIT}

    today = _today_key()
    record_key = f"token_usage#{user_id}#{today}"

    try:
        resp = table.get_item(Key={"project_id": record_key})
        item = resp.get("Item", {})
        used = int(item.get("total_tokens", 0))
        return {
            "used": used,
            "limit": DAILY_TOKEN_LIMIT,
            "remaining": max(0, DAILY_TOKEN_LIMIT - used),
            "calls": int(item.get("call_count", 0)),
        }
    except Exception:
        return {"used": 0, "limit": DAILY_TOKEN_LIMIT, "remaining": DAILY_TOKEN_LIMIT}


def reset_at() -> str:
    """다음 리셋 시각 (UTC 자정)."""
    now = datetime.now(timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if tomorrow <= now:
        from datetime import timedelta
        tomorrow += timedelta(days=1)
    return tomorrow.isoformat()
