"""Claude API — 문서 분류 / 필드 추출 / 교차 검증 + 공용 Bedrock 클라이언트.

실제 로직은 backend·ai-service 공유 모듈 `ai_core`로 이전됨(프롬프트 drift 차단).
이 모듈은 하위호환을 위한 re-export 레이어다. 기존 import 경로
(`from services.claude_api import ...`)는 그대로 동작한다.
"""

from services.ai_core import (  # noqa: F401  (re-export)
    AIUnavailableError,
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
    bedrock_ready,
    get_bedrock_client,
    invoke_bedrock,
    route_model,
    classify_document,
    extract_all_fields,
    extract_costs,
    extract_people,
    extract_schedule,
    extract_rates,
    extract_org,
    extract_section,
    cross_validate,
    chat_complete,
    import_execution_plan,
    # 프롬프트/유틸 — 테스트·재사용 호환
    CLASSIFY_PROMPT,
    EXTRACT_PROMPT,
    COSTS_PROMPT,
    PEOPLE_PROMPT,
    SCHEDULE_PROMPT,
    RATES_PROMPT,
    ORG_PROMPT,
    VALIDATE_PROMPT,
    _parse_json,
    _doc_block,
    _collect_images,
    _normalize_cost_category,
    _force_category_by_name,
)
