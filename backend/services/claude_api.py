"""Claude API 호출 — 문서 분류 / 필드 추출 / 교차 검증 + 공용 Bedrock 클라이언트"""

import os
import json
import logging
import boto3
from botocore.config import Config

_client = None
_logger = logging.getLogger("si-contract")

# ap-northeast-2에는 us.* inference profile이 없음 — global.* 프로필만 유효
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
BEDROCK_REGION = os.getenv("AWS_REGION", "ap-northeast-2")

_BEDROCK_CONFIG = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=10,
    read_timeout=60,
)


class AIUnavailableError(RuntimeError):
    """AI 서비스 사용 불가 — 클라이언트에는 일반 메시지만 노출."""


def bedrock_ready() -> bool:
    """Bedrock 호출 가능 여부 — AWS credential 존재 확인 (health check용)."""
    try:
        import botocore.session
        creds = botocore.session.get_session().get_credentials()
        return creds is not None
    except Exception:
        return False


def get_bedrock_client():
    """싱글톤 Bedrock 클라이언트 — main.py, reviewer.py에서도 사용.

    credential 미설정/획득 실패 시 raw 예외 대신 AIUnavailableError.
    """
    global _client
    if _client is None:
        try:
            client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION, config=_BEDROCK_CONFIG)
            if not bedrock_ready():
                raise RuntimeError("AWS credentials not found")
            _client = client
        except Exception as e:
            _logger.error("Bedrock client init failed: %s", e)
            raise AIUnavailableError("AI 서비스 일시적 오류")
    return _client


def invoke_bedrock(
    prompt: str,
    max_tokens: int = 2048,
    system: str | None = None,
    model_id: str | None = None,
    task_type: str = "sonnet",
    user_id: str = "default",
) -> dict:
    """공용 Bedrock invoke — LLM Gateway 통과 (모델 라우팅)."""
    from services.llm_gateway import route_model

    if not model_id:
        model_id = route_model(task_type, user_id)

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
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body_dict),
        )
        result = json.loads(response["body"].read())

        usage = result.get("usage", {})
        _logger.info("Bedrock call: model=%s task=%s tokens=%d+%d user=%s",
                      model_id, task_type, usage.get("input_tokens", 0), usage.get("output_tokens", 0), user_id)
        return result
    except client.exceptions.ThrottlingException:
        _logger.warning("Bedrock throttled — rate limit exceeded")
        raise AIUnavailableError("AI 서비스 요청 한도 초과. 잠시 후 다시 시도해 주세요.")
    except client.exceptions.ModelNotReadyException:
        _logger.warning("Bedrock model not ready: %s", model_id)
        raise AIUnavailableError("AI 모델이 준비되지 않았습니다. 잠시 후 다시 시도해 주세요.")
    except Exception as e:
        # raw AWS 예외 메시지는 로그에만 남기고 클라이언트에는 일반 메시지만 반환
        _logger.error("Bedrock invoke_model failed: model=%s error=%s", model_id, e)
        raise AIUnavailableError("AI 서비스 일시적 오류")


def _call_claude(prompt: str, max_tokens: int = 2048, task_type: str = "sonnet", user_id: str = "default") -> str:
    """Bedrock Claude 단일 호출 — LLM Gateway 경유."""
    result = invoke_bedrock(prompt, max_tokens, task_type=task_type, user_id=user_id)
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
    raw = _call_claude(prompt, max_tokens=256, task_type="classify")
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
    raw = _call_claude(prompt, max_tokens=1024, task_type="extract_full")
    return _parse_json(raw, fallback={"error": "추출 실패"})


# ─── 탭별(섹션) 추출 ───────────────────────────────────────

def _doc_block(documents: list[dict], limit: int = 4000) -> str:
    return "\n\n".join(
        f"[문서 {i+1}: {d['filename']}]\n{d['text'][:limit]}"
        for i, d in enumerate(documents)
    )


COSTS_PROMPT = """당신은 GS네오텍 SI/MSP 집행계획서의 '산출내역(비목)' 추출 도우미입니다.
아래 문서(견적서/품의서/검토서)에서 비목 항목을 추출하세요.

{doc_block}

규칙:
- 경비/재료비/외주비 등 실제 비목만 추출. 카테고리(category)는 labor/material/outsourcing/expense 중 하나로 분류.
- **퇴직금·보험료·국민연금·건강보험·산재보험·고용보험·인건비(급료)는 제외** (산출내역서 수식이 자동 계산).
- **V.A.T.(부가세)는 제외**. 값이 전부 '-'(대시)인 행도 제외.
- 금액은 원 단위 정수. 계약(contract)/집행(execution) 값이 구분되면 각각, 한쪽만 있으면 같은 값으로.

다음 JSON으로만 응답:
{{"items": [
  {{"category": "expense", "name": "비목명", "spec": "규격", "unit": "단위",
    "contractQty": 0, "contractPrice": 0, "contractAmount": 0,
    "executionQty": 0, "executionPrice": 0, "executionAmount": 0,
    "vendor": "공급처", "source": "출처", "confidence": "verified|guess"}}
]}}
항목이 없으면 {{"items": []}}."""


PEOPLE_PROMPT = """당신은 GS네오텍 SI/MSP 집행계획서의 '투입 인원' 추출 도우미입니다.
아래 문서에서 투입 인력 계획을 추출하세요.

{doc_block}

규칙:
- monthlyRate는 **급료(월 인건비/원가 단가)** 를 사용. **견적서의 매출 단가는 절대 쓰지 마세요.** 불명확하면 0.
- type은 자사 직접 투입이면 "직접", 외주/협력사면 "간접". company는 간접일 때 소속사명.
- months는 길이 12의 0/1 배열(해당 월 투입 시 1). 기간만 있으면 시작~종료월을 1로.
- grade는 직급(부장/차장/과장/대리/사원 등), role은 역할(PM/개발/운영 등).

다음 JSON으로만 응답:
{{"staffPlan": [
  {{"name": "이름", "role": "역할", "grade": "직급", "type": "직접",
    "company": "", "months": [0,0,0,0,0,0,0,0,0,0,0,0], "monthlyRate": 0, "source": "출처"}}
]}}
인원이 없으면 {{"staffPlan": []}}."""


SCHEDULE_PROMPT = """당신은 GS네오텍 SI/MSP 집행계획서의 '공정(일정)' 추출 도우미입니다.
아래 문서에서 작업 공정/단계 일정을 추출하세요.

{doc_block}

규칙:
- startMonth/endMonth는 사업 시작월 기준 1부터 시작하는 정수(예: 1차월=1).
- 단계명(name)은 분석/설계/개발/테스트/이행 등.

다음 JSON으로만 응답:
{{"schedule": [
  {{"name": "단계명", "startMonth": 1, "endMonth": 3, "source": "출처"}}
]}}
공정이 없으면 {{"schedule": []}}."""


RATES_PROMPT = """당신은 GS네오텍 SI/MSP 집행계획서의 '요율' 추출 도우미입니다.
아래 문서에서 간접비율/일반관리비율/4대보험 요율을 추출하세요.

{doc_block}

규칙:
- 값은 % 숫자(예: 1.9). 문서에 명시 없으면 0.
- **간접+일반관리가 '합산'으로만 표기되어 개별 분리가 불가하면 둘 다 0**으로 두세요(빌더가 사내기준 적용).
- 4대보험(국민연금/건강보험/고용보험/산재보험)은 명시된 요율만, 없으면 0.

다음 JSON으로만 응답:
{{"rates": {{
  "indirectRate": {{"value": 0, "source": "출처"}},
  "adminRate": {{"value": 0, "source": "출처"}},
  "nationalPension": {{"value": 0, "source": "출처"}},
  "healthInsurance": {{"value": 0, "source": "출처"}},
  "employmentInsurance": {{"value": 0, "source": "출처"}},
  "industrialAccident": {{"value": 0, "source": "출처"}}
}}}}"""


ORG_PROMPT = """당신은 GS네오텍 SI/MSP 집행계획서의 '수행 조직' 추출 도우미입니다.
아래 문서에서 조직/역할 구성을 추출하세요.

{doc_block}

규칙:
- lead는 총괄/책임자(PM 등)이면 true, 아니면 false.
- scope는 담당 업무 범위.

다음 JSON으로만 응답:
{{"organization": [
  {{"role": "역할", "name": "이름/조직", "scope": "담당범위", "lead": false}}
]}}
조직 정보가 없으면 {{"organization": []}}."""


def extract_costs(documents: list[dict]) -> dict:
    raw = _call_claude(COSTS_PROMPT.format(doc_block=_doc_block(documents)), max_tokens=2048, task_type="extract_costs")
    return _parse_json(raw, fallback={"items": []})


def extract_people(documents: list[dict]) -> dict:
    raw = _call_claude(PEOPLE_PROMPT.format(doc_block=_doc_block(documents)), max_tokens=2048, task_type="extract_people")
    return _parse_json(raw, fallback={"staffPlan": []})


def extract_schedule(documents: list[dict]) -> dict:
    raw = _call_claude(SCHEDULE_PROMPT.format(doc_block=_doc_block(documents)), max_tokens=1024, task_type="extract_schedule")
    return _parse_json(raw, fallback={"schedule": []})


def extract_rates(documents: list[dict]) -> dict:
    raw = _call_claude(RATES_PROMPT.format(doc_block=_doc_block(documents)), max_tokens=512, task_type="extract_rates")
    return _parse_json(raw, fallback={"rates": None})


def extract_org(documents: list[dict]) -> dict:
    raw = _call_claude(ORG_PROMPT.format(doc_block=_doc_block(documents)), max_tokens=1024, task_type="extract_org")
    return _parse_json(raw, fallback={"organization": []})


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
    raw = _call_claude(prompt, max_tokens=512, task_type="validate")
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
