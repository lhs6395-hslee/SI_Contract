"""AI Service — 독립 FastAPI 서비스. AI 로직은 backend와 공유하는 ai_core를 그대로 사용.

backend(모놀리스)와 동일 코드(ai_core)를 쓰므로 USE_AI_SERVICE 토글 시 동작이 100% 같다.
엔드포인트: classify / extract / extract-{costs,people,schedule,rates,org} / import / validate / chat.
"""

import os
import logging
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# ai_core는 컨테이너 빌드 시 같은 디렉토리로 복사된다(Dockerfile). 소스 트리에서
# 단독 실행(개발/테스트)할 때는 backend/services/ai_core.py를 path에 추가해 import.
try:
    import ai_core
except ModuleNotFoundError:
    _here = os.path.dirname(os.path.abspath(__file__))
    _backend_services = os.path.normpath(os.path.join(_here, "..", "..", "backend", "services"))
    if os.path.isfile(os.path.join(_backend_services, "ai_core.py")):
        sys.path.insert(0, _backend_services)
    import ai_core

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger("ai-service")

app = FastAPI(title="SI AI Service", version="1.0.0")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "X-Internal-Secret"],
)

# 내부 호출 검증 — backend가 보내는 shared secret 일치 시에만 허용 (설정된 경우)
INTERNAL_SERVICE_SECRET = os.getenv("INTERNAL_SERVICE_SECRET", "")


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


# AI 미가용(자격증명/스로틀 등) → backend 전역 핸들러와 동일하게 502+코드로 매핑
@app.exception_handler(ai_core.AIUnavailableError)
async def _ai_unavailable(request, exc):
    return JSONResponse({"error": str(exc), "code": "AI_UNAVAILABLE"}, status_code=502)


# ─── Health ────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-service", "model": ai_core.BEDROCK_MODEL_ID}


# ─── Classify ─────────────────────────────────────────

@app.post("/classify")
async def classify(data: dict):
    return ai_core.classify_document(data.get("filename", ""), data.get("text", ""))


# ─── Extract (전체 필드) ───────────────────────────────

@app.post("/extract")
async def extract(data: dict):
    return ai_core.extract_all_fields(data.get("documents", []))


# ─── Extract (탭별 granular) ───────────────────────────

@app.post("/extract-costs")
async def extract_costs(data: dict):
    return ai_core.extract_costs(data.get("documents", []))


@app.post("/extract-people")
async def extract_people(data: dict):
    return ai_core.extract_people(data.get("documents", []))


@app.post("/extract-schedule")
async def extract_schedule(data: dict):
    return ai_core.extract_schedule(data.get("documents", []))


@app.post("/extract-rates")
async def extract_rates(data: dict):
    return ai_core.extract_rates(data.get("documents", []))


@app.post("/extract-org")
async def extract_org(data: dict):
    return ai_core.extract_org(data.get("documents", []))


# ─── Import (완성 집행계획서 역추출 → 0차) ──────────────

@app.post("/import")
async def import_execution_plan(data: dict):
    return ai_core.import_execution_plan(data.get("documents", []))


# ─── Validate ─────────────────────────────────────────

@app.post("/validate")
async def validate(data: dict):
    return {"conflicts": ai_core.cross_validate(data)}


# ─── Chat (순수 추론 — system/message는 backend가 구성) ─

@app.post("/chat")
async def chat(data: dict):
    message = data.get("message", "")
    system = data.get("system", "")
    if not message:
        raise HTTPException(422, "message required")
    result = ai_core.chat_complete(
        message, system=system,
        max_tokens=data.get("max_tokens", 1024),
        user_id=data.get("user_id", "anonymous"),
    )
    usage = result.get("usage", {})
    return {
        "role": "assistant",
        "content": result["content"][0]["text"],
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
    }
