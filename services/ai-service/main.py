"""AI Service — 독립 FastAPI 서비스 (classify/extract/validate)."""

import os
import json
import logging
import sys

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger("ai-service")

app = FastAPI(title="SI AI Service", version="0.1.0")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST"],
    allow_headers=["Content-Type", "X-Internal-Secret"],
)

# 내부 호출 검증 — backend가 보내는 shared secret 일치 시에만 허용 (설정된 경우)
INTERNAL_SERVICE_SECRET = os.getenv("INTERNAL_SERVICE_SECRET", "")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class InternalSecretMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/health" or request.method == "OPTIONS":
            return await call_next(request)
        import hmac
        provided = request.headers.get("X-Internal-Secret", "")
        if not (provided and hmac.compare_digest(provided, INTERNAL_SERVICE_SECRET)):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)


if INTERNAL_SERVICE_SECRET:
    app.add_middleware(InternalSecretMiddleware)


# ─── Bedrock Client (공유) ─────────────────────────────
import boto3
from botocore.config import Config

# ap-northeast-2에는 us.* inference profile이 없음 — global.* 프로필만 유효
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
BEDROCK_REGION = os.getenv("AWS_REGION", "ap-northeast-2")

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            region_name=BEDROCK_REGION,
            config=Config(retries={"max_attempts": 3, "mode": "adaptive"}, read_timeout=60),
        )
    return _client


def _call_claude(prompt: str, max_tokens: int = 2048) -> str:
    client = _get_client()
    try:
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
    except Exception as e:
        # raw AWS 예외는 로그에만 — 클라이언트에는 일반 메시지
        logger.error("Bedrock call failed: %s", e)
        raise HTTPException(502, {"error": "AI 서비스 일시적 오류", "code": "AI_UNAVAILABLE"})


def _parse_json(text: str, fallback=None):
    import re
    m = re.search(r"[\[{][\s\S]*[\]}]", text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return fallback


# ─── Health ────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-service", "model": BEDROCK_MODEL_ID}


# ─── Classify ─────────────────────────────────────────

CLASSIFY_PROMPT = """당신은 SI/MSP 사업 문서 분류 도우미입니다. 아래 파일의 종류를 판정하세요.

파일명: {filename}

문서 내용 (앞부분):
\"\"\"
{text}
\"\"\"

다음 5개 카테고리 중 하나로 분류하세요:
- contract: 계약서, 업무위탁계약서, SLA, 부속계약서
- internal: 내부 견적품의서, 사내 기안 문서
- vendor: 외부 협력사가 제출한 견적서
- insurance: 보험료율 공문, 4대 보험료율 안내 공문서
- unknown: 위 어디에도 해당하지 않거나 판단 불가

JSON 형식으로만 응답:
{{"category":"contract|internal|vendor|insurance|unknown","confidence":0.0~1.0,"reason":"한 줄 사유"}}"""


@app.post("/classify")
async def classify(data: dict):
    filename = data.get("filename", "")
    text = data.get("text", "")[:2000]
    prompt = CLASSIFY_PROMPT.format(filename=filename, text=text or "(텍스트 없음)")
    raw = _call_claude(prompt, max_tokens=256)
    return _parse_json(raw, fallback={"category": "unknown", "confidence": 0.3, "reason": "파싱 실패"})


# ─── Extract ──────────────────────────────────────────

EXTRACT_PROMPT = """당신은 GS네오텍 SI/MSP 사업의 집행계획서 추출 도우미입니다.
아래 문서들에서 주요 항목을 추출하세요.

{doc_block}

다음 JSON 형식으로만 응답:
{{
  "projectName":   {{"value": "사업명", "source": "출처", "confidence": "verified|guess|null"}},
  "client":        {{"value": "발주처(법인명)", "source": "...", "confidence": "..."}},
  "contractor":    {{"value": "계약처", "source": "...", "confidence": "..."}},
  "contractType":  {{"value": "수의계약/경쟁입찰 등", "source": "...", "confidence": "..."}},
  "paymentTerms":  {{"value": "수금조건", "source": "...", "confidence": "..."}},
  "pm":            {{"value": "PM 이름/직급", "source": "...", "confidence": "..."}},
  "salesOwner":    {{"value": "영업담당자", "source": "...", "confidence": "..."}},
  "startDate":     {{"value": "YYYY.MM.DD", "source": "...", "confidence": "..."}},
  "endDate":       {{"value": "YYYY.MM.DD", "source": "...", "confidence": "..."}},
  "revenue":       {{"value": 0, "unit": "원", "source": "...", "confidence": "..."}},
  "cost":          {{"value": 0, "unit": "원", "source": "...", "confidence": "..."}},
  "scope":         {{"value": "사업범위", "source": "...", "confidence": "..."}},
  "specialNotes":  {{"value": "특기사항", "source": "...", "confidence": "..."}},
  "fiscalYear":    {{"value": "YYYY", "source": "...", "confidence": "..."}},
  "writtenDate":   {{"value": "YYYY.MM.DD", "source": "...", "confidence": "..."}}
}}"""


@app.post("/extract")
async def extract(data: dict):
    documents = data.get("documents", [])
    doc_block = "\n\n".join(
        f"[문서 {i+1}: {d.get('filename','')}]\n{d.get('text','')[:2000]}"
        for i, d in enumerate(documents)
    )
    prompt = EXTRACT_PROMPT.format(doc_block=doc_block)
    raw = _call_claude(prompt, max_tokens=1024)
    return _parse_json(raw, fallback={"error": "추출 실패"})


# ─── Validate ─────────────────────────────────────────

VALIDATE_PROMPT = """당신은 집행계획서 교차 검증 도우미입니다.
아래 추출된 데이터에서 모순이나 누락을 찾아 보고하세요.

{data_json}

JSON 배열로만 응답:
[{{"type": "mismatch|missing|warning", "field": "필드명", "message": "설명", "severity": "high|medium|low"}}]

문제가 없으면 빈 배열 [] 을 반환하세요."""


@app.post("/validate")
async def validate(data: dict):
    prompt = VALIDATE_PROMPT.format(data_json=json.dumps(data, ensure_ascii=False, indent=2))
    raw = _call_claude(prompt, max_tokens=512)
    result = _parse_json(raw, fallback=[])
    return {"conflicts": result if isinstance(result, list) else []}
