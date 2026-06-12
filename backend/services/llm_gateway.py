"""LLM Gateway — 모델 티어링 (라우팅만, 토큰 제한 없음).

티어링:
  - haiku: 분류, 챗봇, 짧은 Q&A, 간단 추출
  - sonnet: 전체 필드 추출, 교차 검증, AI 리뷰 (기본)
  - opus: configmap override 시에만
"""

import os
import logging

logger = logging.getLogger("si-contract")

# ap-northeast-2에는 us.* inference profile이 없음 — global.* 프로필만 유효
HAIKU_MODEL = os.getenv("HAIKU_MODEL", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "global.anthropic.claude-sonnet-4-6")
OPUS_MODEL = os.getenv("OPUS_MODEL", "")

TASK_TIER = {
    "classify": "haiku",
    "chat": "haiku",
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
