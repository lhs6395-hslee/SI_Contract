"""Claude API 호출 — 문서 분류 / 필드 추출 / 교차 검증 + 공용 Bedrock 클라이언트"""

import os
import json
import logging
import boto3
from botocore.config import Config

_client = None
_logger = logging.getLogger("si-contract")

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-8-20251101-v1:0")
BEDROCK_REGION = os.getenv("AWS_REGION", "ap-northeast-2")

_BEDROCK_CONFIG = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=10,
    read_timeout=60,
)


def get_bedrock_client():
    """싱글톤 Bedrock 클라이언트 — main.py, reviewer.py에서도 사용."""
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION, config=_BEDROCK_CONFIG)
    return _client


def invoke_bedrock(prompt: str, max_tokens: int = 2048, system: str | None = None) -> dict:
    """공용 Bedrock invoke_model — 결과 dict 반환. main.py/reviewer.py에서 재사용."""
    client = get_bedrock_client()
    body_dict = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body_dict["system"] = system
    try:
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body_dict),
        )
        return json.loads(response["body"].read())
    except client.exceptions.ThrottlingException:
        _logger.warning("Bedrock throttled — rate limit exceeded")
        raise RuntimeError("AI 서비스 요청 한도 초과. 잠시 후 다시 시도해 주세요.")
    except client.exceptions.ModelNotReadyException:
        _logger.warning("Bedrock model not ready: %s", BEDROCK_MODEL_ID)
        raise RuntimeError("AI 모델이 준비되지 않았습니다. 잠시 후 다시 시도해 주세요.")
    except Exception as e:
        _logger.error("Bedrock invoke_model failed: %s", e)
        raise RuntimeError(f"AI 호출 실패: {e}")


def _call_claude(prompt: str, max_tokens: int = 2048) -> str:
    """Bedrock Claude 단일 호출 — JSON 응답 기대."""
    result = invoke_bedrock(prompt, max_tokens)
    return result["content"][0]["text"]


# ─── 문서 분류 ─────────────────────────────────────────────

CLASSIFY_PROMPT = """당신은 SI/MSP 사업 문서 분류 도우미입니다. 아래 파일의 종류를 판정하세요.

파일명: {filename}

문서 내용 (앞부분):
\"\"\"
{text}
\"\"\"

다음 5개 카테고리 중 하나로 분류하세요:
- contract: 계약서, 업무위탁계약서, SLA, 부속계약서, 서명된 계약문서
- internal: 내부 견적품의서, 사내 기안 문서 (GS네오텍 자체 양식)
- vendor:   외부 협력사가 제출한 견적서
- insurance: 보험료율 공문, 4대 보험료율 안내 공문서
- unknown:  위 어디에도 해당하지 않거나 판단 불가

JSON 형식으로만 응답:
{{"category":"contract|internal|vendor|insurance|unknown","confidence":0.0~1.0,"reason":"한 줄 사유"}}"""


def classify_document(filename: str, text: str) -> dict:
    """파일 텍스트로 문서 종류 분류."""
    prompt = CLASSIFY_PROMPT.format(
        filename=filename,
        text=text[:2000] if text else "(텍스트 추출 불가 — 파일명만으로 판단)",
    )
    raw = _call_claude(prompt, max_tokens=256)
    return _parse_json(raw, fallback={"category": "unknown", "confidence": 0.3, "reason": "파싱 실패"})


# ─── 필드 추출 ─────────────────────────────────────────────

EXTRACT_PROMPT = """당신은 GS네오텍 SI/MSP 사업의 집행계획서 추출 도우미입니다.
아래 문서들에서 주요 항목을 추출하세요. 값이 명확하지 않으면 null로 두고, 추측한 값은 confidence를 "guess"로 표시하세요.

{doc_block}

다음 JSON 형식으로만 응답 (다른 텍스트 일절 없이):
{{
  "projectName":   {{"value": "사업명",        "source": "출처(예: 계약서 p.1)", "confidence": "verified|guess|null"}},
  "client":        {{"value": "발주처(법인명)","source": "...", "confidence": "..."}},
  "contractor":    {{"value": "계약처",         "source": "...", "confidence": "..."}},
  "contractType":  {{"value": "수의계약/경쟁입찰 등", "source": "...", "confidence": "..."}},
  "paymentTerms":  {{"value": "수금조건",       "source": "...", "confidence": "..."}},
  "pm":            {{"value": "PM 이름/직급",   "source": "...", "confidence": "..."}},
  "salesOwner":    {{"value": "영업담당자",     "source": "...", "confidence": "..."}},
  "startDate":     {{"value": "YYYY.MM.DD",     "source": "...", "confidence": "..."}},
  "endDate":       {{"value": "YYYY.MM.DD",     "source": "...", "confidence": "..."}},
  "revenue":       {{"value": 0, "unit": "원", "source": "...", "confidence": "..."}},
  "cost":          {{"value": 0, "unit": "원", "source": "...", "confidence": "..."}},
  "scope":         {{"value": "사업범위 내용",  "source": "...", "confidence": "..."}},
  "specialNotes":  {{"value": "특기사항",       "source": "...", "confidence": "..."}},
  "fiscalYear":    {{"value": "YYYY (4자리 연도, 예: 2026)", "source": "...", "confidence": "..."}},
  "writtenDate":   {{"value": "YYYY.MM.DD",     "source": "...", "confidence": "..."}}
}}

값을 찾을 수 없는 항목은 {{"value": null, "source": "", "confidence": "null"}} 로 두세요.
숫자 항목(revenue, cost)은 원 단위 정수로. 천원 단위가 아닌 원 단위입니다.
fiscalYear는 계약 시작일의 연도(4자리 숫자만, "년" 제외)를 사용하세요."""


def extract_all_fields(documents: list[dict]) -> dict:
    """여러 문서에서 집행계획서 필드를 추출한다.

    documents: [{"filename": "...", "text": "..."}]
    """
    doc_block = "\n\n".join(
        f"[문서 {i+1}: {d['filename']}]\n{d['text'][:2000]}"
        for i, d in enumerate(documents)
    )
    prompt = EXTRACT_PROMPT.format(doc_block=doc_block)
    raw = _call_claude(prompt, max_tokens=1024)
    return _parse_json(raw, fallback={"error": "추출 실패"})


# ─── 교차 검증 ─────────────────────────────────────────────

VALIDATE_PROMPT = """당신은 집행계획서 교차 검증 도우미입니다.
아래 추출된 데이터에서 모순이나 누락을 찾아 보고하세요.

{data_json}

다음 JSON 배열로만 응답하세요:
[
  {{"type": "mismatch|missing|warning", "field": "필드명", "message": "설명", "severity": "high|medium|low"}}
]

문제가 없으면 빈 배열 [] 을 반환하세요."""


def cross_validate(data: dict) -> list[dict]:
    """추출 데이터 교차 검증 — 충돌/누락 감지."""
    prompt = VALIDATE_PROMPT.format(data_json=json.dumps(data, ensure_ascii=False, indent=2))
    raw = _call_claude(prompt, max_tokens=512)
    result = _parse_json(raw, fallback=[])
    return result if isinstance(result, list) else []


# ─── 유틸 ─────────────────────────────────────────────────

def _parse_json(text: str, fallback=None):
    """응답에서 JSON 블록 추출."""
    import re
    m = re.search(r"[\[{][\s\S]*[\]}]", text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return fallback
