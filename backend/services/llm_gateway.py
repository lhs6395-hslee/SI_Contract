"""LLM Gateway — 모델 티어 라우팅.

라우팅 로직은 `ai_core`로 통합됨(backend·ai-service 단일 출처). 하위호환 re-export.
티어: haiku(분류/챗/간단추출), sonnet(전체추출/검증/리뷰, 기본), opus(override 시).
"""

from services.ai_core import (  # noqa: F401  (re-export)
    route_model,
    HAIKU_MODEL,
    DEFAULT_MODEL,
    OPUS_MODEL,
    TASK_TIER,
    MODEL_MAP,
)
