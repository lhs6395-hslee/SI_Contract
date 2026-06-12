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
    images: list[str] | None = None,
    temperature: float = 0.0,
) -> dict:
    """공용 Bedrock invoke — LLM Gateway 통과 (모델 라우팅).

    images: base64-encoded PNG 목록. 지정 시 멀티모달(텍스트+이미지) 메시지로 전송
            (스캔 PDF Vision 추출용 — Claude Messages API image content block).
    """
    from services.llm_gateway import route_model

    if not model_id:
        model_id = route_model(task_type, user_id)

    if images:
        content: list = [{"type": "text", "text": prompt}]
        for b64 in images[:8]:  # 토큰/비용 상한
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": b64},
            })
    else:
        content = prompt

    client = get_bedrock_client()
    body_dict = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,  # 추출/분류 결정론화 (기본 0 — 같은 입력=같은 출력)
        "messages": [{"role": "user", "content": content}],
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


def _call_claude(prompt: str, max_tokens: int = 2048, task_type: str = "sonnet", user_id: str = "default", images: list[str] | None = None) -> str:
    """Bedrock Claude 단일 호출 — LLM Gateway 경유. images 지정 시 Vision 멀티모달."""
    result = invoke_bedrock(prompt, max_tokens, task_type=task_type, user_id=user_id, images=images)
    return result["content"][0]["text"]


def _collect_images(documents: list[dict]) -> list[str]:
    """문서들에서 Vision용 base64 이미지를 모은다 (스캔 PDF 페이지)."""
    imgs: list[str] = []
    for d in documents:
        imgs.extend(d.get("images") or [])
    return imgs


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
  "client":        {{"value": "발주처(고객사, 갑)","source": "...", "confidence": "..."}},
  "contractor":    {{"value": "수행사(을)",      "source": "...", "confidence": "..."}},
  "contractType":  {{"value": "수의계약/경쟁입찰 등", "source": "...", "confidence": "..."}},
  "paymentTerms":  {{"value": "수금조건",       "source": "...", "confidence": "..."}},
  "pm":            {{"value": "PM 이름/직급",   "source": "...", "confidence": "..."}},
  "salesOwner":    {{"value": "영업담당자",     "source": "...", "confidence": "..."}},
  "startDate":     {{"value": "YYYY.MM.DD",     "source": "...", "confidence": "..."}},
  "endDate":       {{"value": "YYYY.MM.DD",     "source": "...", "confidence": "..."}},
  "revenue":          {{"value": 0, "unit": "원", "source": "...", "confidence": "..."}},
  "quoteMaterial":    {{"value": 0, "unit": "원", "source": "...", "confidence": "..."}},
  "quoteLabor":       {{"value": 0, "unit": "원", "source": "...", "confidence": "..."}},
  "quoteOutsourcing": {{"value": 0, "unit": "원", "source": "...", "confidence": "..."}},
  "cost":             {{"value": 0, "unit": "원", "source": "...", "confidence": "..."}},
  "profit":           {{"value": 0, "unit": "원", "source": "...", "confidence": "..."}},
  "profitRate":       {{"value": 0, "unit": "%", "source": "...", "confidence": "..."}},
  "scope":         {{"value": "사업범위 내용",  "source": "...", "confidence": "..."}},
  "specialNotes":  {{"value": "특기사항",       "source": "...", "confidence": "..."}},
  "fiscalYear":    {{"value": "YYYY (4자리 연도, 예: 2026)", "source": "...", "confidence": "..."}},
  "writtenDate":   {{"value": "YYYY.MM.DD",     "source": "...", "confidence": "..."}}
}}

발주처/수행사 (혼동 금지):
- **client(발주처)는 고객사(갑)입니다.** 계약서의 '갑'/'발주기관'/고객 법인명(예: 퀘이사존, 지에스이피에스).
- **GS네오텍/지에스네오텍은 항상 수행사(을)** — contractor에 넣고, **client에 절대 넣지 마세요.**

견적품의(원가분해) 항목 — 견적품의서/표준계약검토서의 매출원가 구성을 그대로:
- revenue=매출(공급가, 총액), quoteMaterial=재료비, quoteLabor=노무비(자사 인건비),
  quoteOutsourcing=외주비(협력사 수수료/도급), cost=**경비(여비·차량·통신 등 일반경비만)**,
  profit=영업이익, profitRate=영업이익률(%).
- **각 항목은 매출원가 구성의 '단일 라인'입니다.** revenue ≈ quoteMaterial+quoteLabor+
  quoteOutsourcing+cost+profit 으로 분해됩니다. **어떤 항목도 revenue(총액)와 같을 수 없습니다.**
- **quoteLabor는 '노무비' 한 줄만** — 매출 총액이나 총원가를 넣지 마세요. (자사인력 사업이라도
  노무비는 매출보다 작습니다. 노무비가 매출과 같으면 잘못 뽑은 것입니다.)
- **cost는 '경비'만** — 총원가나 노무비+외주비 합계 금지.
- 견적품의서에 매출/재료비/노무비/외주비/경비/영업이익 6분류가 있으면 각 칸을 그대로 매핑하세요.

값을 찾을 수 없는 항목은 {{"value": null, "source": "", "confidence": "null"}} 로 두세요.
숫자 항목은 원 단위 정수로 (천원 아님).
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
    # Vision(스캔 PDF) 추출은 출력이 길어 1024 cap에 걸려 JSON이 잘리는 문제 → 여유 상한
    raw = _call_claude(prompt, max_tokens=2048, task_type="extract_full", images=_collect_images(documents))
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

⚠️ 가장 중요 — 자사 인력 제외:
- **GS네오텍/지에스네오텍이 '공급자(을)'인 견적서의 인력 라인(PM/SA/개발 등 자사 인력)은
  아예 추출하지 마세요.** 자사 노무비는 인원(staffPlan)+사내단가가 계산하므로 fee/labor 금지.
- "fee"는 **GS네오텍이 외부 협력사/외주사에 *지급*하는 수수료**만 (공급자가 GS네오텍이 아닌
  타 업체 견적서). 예: 퀘이사존 사업의 레이어에잇 견적 = fee. EPS처럼 GS네오텍 자사 인력만 있는
  견적서는 fee 항목이 없음(빈 items 가능).

category는 **반드시 아래 영문 키 중 하나**로만 분류하세요 (다른 값 금지):
- "fee"      → **외부 협력사**에 지급하는 수수료·용역비 (자사 인력 금지). ※ 수수료 시트
- "labor"    → **외주/도급 노무비만** (협력사가 아닌 외부 인력 도급). 자사 직접인력은 금지
- "bonus"    → 상여금 (단, 자사 직접인력 상여는 금지 — 아래 규칙)
- "wage"     → 임금 (자사 직접인력 임금 금지)
- "welfare"  → 복리후생비 (자사 직접인력 복리후생 금지)
- "travel"   → 여비/출장비
- "vehicle"  → 차량유지비
- "equipment"→ 장비/기자재/HW/SW 구입
- "rent"     → 임차료/임대료
- "transport"→ 운반/운송비
- "comm"     → 통신비/회선료
- "print"    → 인쇄/출력비
- "safety"   → 안전관리비
- "etc"      → 위에 없는 일반 경비 전부 (분류 애매하면 etc)

규칙:
- **자사 직접인력의 급료·상여·임금·복리후생은 추출 금지** — 인원(staffPlan) + 사내 직급단가표로
  자동 계산되는 항목이다. 견적서의 PM/SA 등 자사 인력 라인을 labor/wage/welfare로 넣지 마세요.
  (외주/도급 인력의 노무비만 labor, 협력사 수수료는 fee.)
- **퇴직금·보험료·국민연금·건강보험·산재보험·고용보험은 제외** (산출내역서 수식이 자동 계산).
- **V.A.T.(부가세)는 제외**. 값이 전부 '-'(대시)인 행도 제외.
- 금액은 원 단위 정수. 계약(contract)/집행(execution) 구분되면 각각, 한쪽만 있으면 같은 값으로.
- 협력사 견적/외주 수수료는 반드시 "fee"로. 경비성 항목은 가장 가까운 키, 없으면 "etc".

다음 JSON으로만 응답:
{{"items": [
  {{"category": "fee", "name": "비목명", "spec": "규격", "unit": "단위",
    "contractQty": 0, "contractPrice": 0, "contractAmount": 0,
    "executionQty": 0, "executionPrice": 0, "executionAmount": 0,
    "vendor": "공급처", "source": "출처", "confidence": "verified|guess"}}
]}}
항목이 없으면 {{"items": []}}."""

# LLM이 빌더 어휘를 벗어나면 costItem이 통째로 폐기됨(category∉BUDGET_CATEGORIES∧≠fee).
# 흔한 변형/한글을 빌더 키로 정규화하고, 미지값은 폐기 대신 "etc"(경비)로 흡수.
_COST_CAT_ALIAS = {
    "fee": "fee", "수수료": "fee", "외주": "fee", "외주비": "fee", "outsourcing": "fee",
    "협력사": "fee", "용역": "fee", "용역비": "fee", "도급": "fee",
    "labor": "labor", "노무": "labor", "노무비": "labor", "인건비": "labor", "인력": "labor",
    "bonus": "bonus", "상여": "bonus", "상여금": "bonus",
    "wage": "wage", "임금": "wage",
    "welfare": "welfare", "복리": "welfare", "복리후생": "welfare", "복리후생비": "welfare",
    "travel": "travel", "여비": "travel", "출장": "travel", "출장비": "travel",
    "vehicle": "vehicle", "차량": "vehicle", "차량유지비": "vehicle",
    "equipment": "equipment", "장비": "equipment", "기자재": "equipment", "hw": "equipment",
    "sw": "equipment", "소프트웨어": "equipment", "하드웨어": "equipment",
    "rent": "rent", "임차": "rent", "임대": "rent", "임차료": "rent", "임대료": "rent",
    "transport": "transport", "운반": "transport", "운송": "transport", "운반비": "transport",
    "comm": "comm", "통신": "comm", "통신비": "comm", "회선": "comm", "회선료": "comm",
    "print": "print", "인쇄": "print", "인쇄비": "print", "출력": "print",
    "safety": "safety", "안전": "safety", "안전관리비": "safety",
    "etc": "etc", "기타": "etc", "기타경비": "etc", "경비": "etc", "expense": "etc", "material": "etc", "재료비": "etc",
}


def _normalize_cost_category(cat) -> str:
    if not cat:
        return "etc"
    key = str(cat).strip().lower()
    if key in _COST_CAT_ALIAS:
        return _COST_CAT_ALIAS[key]
    # 부분 일치 (예: "외주비(협력사)") — fee를 우선 보존
    for alias, target in _COST_CAT_ALIAS.items():
        if alias in key:
            return target
    return "etc"  # 미지값도 폐기하지 않고 경비로 흡수


# 비목 이름(name) 기반 결정론 강제 매핑 — 모델 category가 흔들려도(labor↔wage 등)
# 같은 이름은 항상 같은 블록에 배치되도록 고정 (재현성). (구체적 키워드 우선)
_NAME_FORCE = [
    ("복리후생", "welfare"), ("복리", "welfare"),
    ("급료", "labor"), ("급여", "labor"),
    ("임금", "wage"), ("현장", "wage"),
    ("상여", "bonus"),
    ("여비", "travel"), ("출장", "travel"),
    ("차량", "vehicle"),
    ("통신", "comm"), ("회선", "comm"),
    ("인쇄", "print"), ("출력", "print"),
    ("임차", "rent"), ("임대", "rent"),
    ("운반", "transport"), ("운송", "transport"),
    ("안전", "safety"),
]


def _force_category_by_name(name: str, fallback: str) -> str:
    """이름에 결정적 키워드가 있으면 그 카테고리로 강제, 없으면 fallback(정규화된 category)."""
    n = str(name or "")
    for kw, cat in _NAME_FORCE:
        if kw in n:
            return cat
    return fallback


PEOPLE_PROMPT = """당신은 GS네오텍 SI/MSP 집행계획서의 '투입 인원' 추출 도우미입니다.
아래 문서에서 투입 인력 계획을 추출하세요.

{doc_block}

규칙:
- **견적서/투입표의 모든 인력 행을 빠짐없이 추출하세요.** 상주/비상주, 부분 투입(0.5MM),
  안정화·운영 등 짧은 라인도 누락 금지. (예: PM, SA 구축, SA 안정화 3명이면 3명 모두.)
- monthlyRate는 **급료(월 인건비/원가 단가)** 를 사용. **견적서의 매출 단가는 절대 쓰지 마세요.**
  견적서에 매출단가만 있으면 monthlyRate=0 (사내 직급단가표가 계산). 직급(grade)은 꼭 채우세요.
- totalMM에 각 인력의 총 투입 M/M(월수 합, 예 0.5+1+1+0.5=3)을 넣으세요.
- type은 자사 직접 투입이면 "직접", 외주/협력사면 "간접". company는 간접일 때 소속사명.
- months는 길이 12의 0/1 배열(해당 월 투입 시 1). 기간/월별 MM이 있으면 그 월들을 1로.
- grade는 직급(부장/차장/과장/대리/사원 등), role은 역할(PM/SA/개발/운영 등).

다음 JSON으로만 응답:
{{"staffPlan": [
  {{"name": "이름", "role": "역할", "grade": "직급", "type": "직접", "company": "",
    "months": [0,0,0,0,0,0,0,0,0,0,0,0], "totalMM": 0, "monthlyRate": 0, "source": "출처"}}
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
    raw = _call_claude(COSTS_PROMPT.format(doc_block=_doc_block(documents)), max_tokens=2048, task_type="extract_costs", images=_collect_images(documents))
    result = _parse_json(raw, fallback={"items": []})
    # category 결정론화: ① 빌더 어휘로 정규화 → ② 이름 키워드로 강제 매핑(재현성).
    # 모델이 같은 입력에 labor↔wage로 흔들려도, 이름(급료/임금/복리후생 등)으로 블록 고정.
    for item in result.get("items", []) or []:
        if isinstance(item, dict):
            norm = _normalize_cost_category(item.get("category"))
            item["category"] = _force_category_by_name(item.get("name"), norm)
    return result


def extract_people(documents: list[dict]) -> dict:
    raw = _call_claude(PEOPLE_PROMPT.format(doc_block=_doc_block(documents)), max_tokens=2048, task_type="extract_people", images=_collect_images(documents))
    return _parse_json(raw, fallback={"staffPlan": []})


def extract_schedule(documents: list[dict]) -> dict:
    raw = _call_claude(SCHEDULE_PROMPT.format(doc_block=_doc_block(documents)), max_tokens=1024, task_type="extract_schedule", images=_collect_images(documents))
    return _parse_json(raw, fallback={"schedule": []})


def extract_rates(documents: list[dict]) -> dict:
    raw = _call_claude(RATES_PROMPT.format(doc_block=_doc_block(documents)), max_tokens=512, task_type="extract_rates", images=_collect_images(documents))
    return _parse_json(raw, fallback={"rates": None})


def extract_org(documents: list[dict]) -> dict:
    raw = _call_claude(ORG_PROMPT.format(doc_block=_doc_block(documents)), max_tokens=1024, task_type="extract_org", images=_collect_images(documents))
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
