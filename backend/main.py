"""SI 집행계획서 자동화 — FastAPI 백엔드"""
import os
import re
import json
import uuid
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from dotenv import load_dotenv

load_dotenv()

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

from services.s3_storage import (
    upload_file as s3_upload,
    list_files as s3_list,
    get_file as s3_get,
    delete_file as s3_delete,
    is_s3_enabled,
)
from services.project_store import (
    save_project,
    load_project,
    list_projects,
    delete_project,
    save_pipeline_state,
    load_pipeline_state,
    is_dynamo_enabled,
    acquire_edit_lock,
    release_edit_lock,
    get_edit_lock_status,
    list_projects_cached,
)
from services.cognito_auth import require_auth, resolve_role, LEGACY_OWNER
from services import cognito_auth as _cognito_auth_module
from services.claude_api import AIUnavailableError

import logging
import sys

# Structured JSON logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger("si-contract")

app = FastAPI(title="SI 집행계획서 API", version="0.1.0")


# ─── 전역 예외 핸들러 ──────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """잘못된 요청 본문/파라미터 → 500 대신 422."""
    return JSONResponse(status_code=422, content={"error": "요청 형식이 올바르지 않습니다", "detail": exc.errors()})


@app.exception_handler(AIUnavailableError)
async def ai_unavailable_handler(request, exc: AIUnavailableError):
    """AI 호출 실패 — raw AWS 예외 노출 금지, 일반 메시지로 래핑."""
    return JSONResponse(status_code=502, content={"error": str(exc) or "AI 서비스 일시적 오류", "code": "AI_UNAVAILABLE"})


@app.exception_handler(json.JSONDecodeError)
async def json_decode_handler(request, exc: json.JSONDecodeError):
    """잘못된 JSON body → 500 대신 422."""
    return JSONResponse(status_code=422, content={"error": "잘못된 JSON 형식입니다"})


from botocore.exceptions import ClientError as _BotoClientError


@app.exception_handler(_BotoClientError)
async def boto_client_error_handler(request, exc: _BotoClientError):
    """AWS(DynamoDB/S3) 클라이언트 오류 → raw 노출 금지. item 크기 초과는 413, 그 외 502."""
    code = exc.response.get("Error", {}).get("Code", "")
    msg = str(exc.response.get("Error", {}).get("Message", ""))
    logger.warning("AWS ClientError: code=%s msg=%s", code, msg)
    if code == "ValidationException" and "item size" in msg.lower():
        return JSONResponse(status_code=413, content={"error": "데이터가 너무 큽니다(저장 한도 초과). 차수/내역을 줄여 주세요."})
    return JSONResponse(status_code=502, content={"error": "저장소 일시적 오류. 잠시 후 다시 시도해 주세요."})


# 프로젝트 ID 유효성 — path/XSS injection 방지
PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _validate_project_id(project_id: str) -> str:
    if not PROJECT_ID_RE.match(project_id or ""):
        raise HTTPException(status_code=422, detail="프로젝트 ID는 영문/숫자/_/- 1~64자만 허용됩니다")
    return project_id


def _validate_revision(revision):
    """revision 범위 검증 — None 허용, 그 외 0~MAX_REVISION 정수. 음수/초과/비정수는 422."""
    if revision is None:
        return None
    from services.company_standards import MAX_REVISION
    if not isinstance(revision, int) or revision < 0 or revision > MAX_REVISION:
        raise HTTPException(status_code=422, detail=f"revision은 0~{MAX_REVISION} 범위 정수여야 합니다")
    return revision

from telemetry import init_telemetry
init_telemetry(app)

# Request ID 미들웨어
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestIDMiddleware)

# CORS — 허용된 도메인만
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://si.rayhli.com").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# API Key 인증 (외부는 API Key 필수)
API_KEY = os.getenv("API_KEY", "")

# 내부 서비스 간 통신 식별 — 환경변수로 주입된 shared secret.
# 클라이언트가 임의로 보낼 수 있는 X-Internal 헤더는 신뢰하지 않는다 (스푸핑 가능).
INTERNAL_SERVICE_SECRET = os.getenv("INTERNAL_SERVICE_SECRET", "")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        # health check, CORS preflight는 인증 스킵
        if request.url.path == "/api/health" or request.method == "OPTIONS":
            return await call_next(request)
        # 내부 통신: shared secret 일치 시에만 스킵 (secret 미설정 시 내부 우회 경로 없음)
        if INTERNAL_SERVICE_SECRET:
            import hmac
            provided = request.headers.get("X-Internal-Secret", "")
            if provided and hmac.compare_digest(provided, INTERNAL_SERVICE_SECRET):
                return await call_next(request)
        # API Key 검증 (설정된 경우에만)
        if API_KEY:
            key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
            if key != API_KEY:
                from starlette.responses import JSONResponse
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)

if API_KEY:
    app.add_middleware(APIKeyMiddleware)

# Rate Limiting — Claude API 호출 비용 보호 (분당 30회)
from collections import defaultdict
import threading

_rate_store: dict[str, list[float]] = defaultdict(list)
_rate_lock = threading.Lock()
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))
RATE_WINDOW = 60  # seconds

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        # AI 호출 엔드포인트만 제한
        ai_paths = {"/api/extract", "/api/classify", "/api/validate", "/api/pipeline/start",
                    "/api/extract-costs", "/api/extract-people", "/api/extract-schedule",
                    "/api/extract-rates", "/api/extract-org", "/api/chat"}
        if request.url.path not in ai_paths:
            return await call_next(request)

        # ALB(target-type=ip) 뒤에서는 request.client.host가 ALB IP → 모든 사용자가 한 버킷을
        # 공유해 false 429. X-Forwarded-For의 첫 IP(실제 클라이언트)로 버킷팅.
        xff = request.headers.get("x-forwarded-for", "")
        client_ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
        now = time.time()

        with _rate_lock:
            _rate_store[client_ip] = [t for t in _rate_store[client_ip] if now - t < RATE_WINDOW]
            if len(_rate_store[client_ip]) >= RATE_LIMIT:
                from starlette.responses import JSONResponse
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
            _rate_store[client_ip].append(now)

        return await call_next(request)

app.add_middleware(RateLimitMiddleware)

# Oversized payload 차단 — 413
MAX_BODY_SIZE = int(os.getenv("MAX_BODY_SIZE", str(20 * 1024 * 1024)))  # 기본 20MB

class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        content_length = request.headers.get("Content-Length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(status_code=413, content={"error": "요청 본문이 너무 큽니다", "max_bytes": MAX_BODY_SIZE})
        return await call_next(request)

app.add_middleware(BodySizeLimitMiddleware)

SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'",
}

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 업로드 파일 크기 제한 (개별 파일)
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024)))  # 기본 20MB


def _check_upload_size(filename: str, content: bytes) -> None:
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"파일이 너무 큽니다: {filename} ({len(content) // (1024*1024)}MB > {MAX_UPLOAD_SIZE // (1024*1024)}MB)",
        )


def _content_disposition(filename: str) -> str:
    """RFC 6266/5987 Content-Disposition — 한글 등 비-ASCII 파일명 안전 처리.
    HTTP 헤더는 latin-1만 허용하므로 ASCII fallback + filename*=UTF-8'' 둘 다 제공."""
    from urllib.parse import quote
    ascii_name = filename.encode("ascii", "ignore").decode().strip() or "download.xlsx"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _safe_extract_text(filename: str, content: bytes) -> str:
    """파일 파싱 — 손상/빈/미지원 파일은 500 대신 422로 응답."""
    from services.file_parser import extract_text
    if not content:
        raise HTTPException(status_code=422, detail=f"빈 파일입니다: {filename}")
    try:
        return extract_text(filename, content)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("파일 파싱 실패 %s: %s", filename, e)
        raise HTTPException(status_code=422, detail=f"파일을 읽을 수 없습니다(손상/미지원 형식): {filename}")

# 로컬 파일 저장소 (s3_storage 내부에서도 사용하지만, parse-stored 등에서 직접 경로 필요)
STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


def _project_dir(project_id: str) -> Path:
    """프로젝트별 파일 저장 디렉토리 (로컬 전용 — parse-stored에서 사용)."""
    d = STORAGE_DIR / project_id
    d.mkdir(exist_ok=True)
    return d


def _sanitize_surrogates(obj):
    """깨진 유니코드 surrogate 문자를 재귀적으로 제거/치환."""
    if isinstance(obj, str):
        return obj.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    if isinstance(obj, dict):
        return {k: _sanitize_surrogates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_surrogates(i) for i in obj]
    return obj


async def _safe_json_body(request: StarletteRequest) -> dict:
    """surrogate-safe JSON 파싱 — 깨진 유니코드가 있어도 400 에러 없이 처리."""
    raw = await request.body()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # surrogate 포함 가능성 — surrogatepass로 디코딩 후 재파싱
        text = raw.decode("utf-8", errors="surrogatepass")
        # surrogate 문자를 replacement character로 치환
        text = text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
        return json.loads(text)


@app.get("/")
async def root():
    return {"message": "SI 집행계획서 API", "docs": "/docs"}


@app.get("/api/health")
async def health():
    """Bedrock 사용 — ANTHROPIC_API_KEY가 아닌 AWS credential 존재로 판정."""
    from services.claude_api import bedrock_ready
    return {"status": "ok", "claude_api": "configured" if bedrock_ready() else "missing"}


# ─── 프로젝트별 파일 저장 ─────────────────────────────────

def _project_owner(project_id: str, current_user: dict, require_exists: bool = False) -> str:
    """소유권 확인 후 파일 저장/조회에 쓸 owner(email) 반환.

    기존 프로젝트면 인가 + 저장된 owner 사용. 신규(레코드 없음)일 때:
      - require_exists=False(업로드): 현재 사용자를 owner로 간주(생성 전 업로드 허용).
      - require_exists=True(조회/삭제): 404(미존재 프로젝트는 빈 200 대신 404로 일관).
    """
    project = load_project(project_id)
    if not project:
        if require_exists:
            raise HTTPException(404, "Project not found")
        return current_user.get("email")
    if current_user.get("role") != "admin":
        owner = project.get("owner") or LEGACY_OWNER
        if owner != current_user.get("email"):
            raise HTTPException(404, "Project not found")
    return project.get("owner") or current_user.get("email")


@app.post("/api/files/{project_id}/upload")
async def upload_project_files(
    project_id: str,
    files: list[UploadFile] = File(...),
    revision: Optional[int] = None,
    current_user: dict = Depends(require_auth),
):
    """프로젝트에 파일 저장 (S3 또는 로컬). revision 지정 시 rev{N}/ 경로에 저장."""
    _validate_revision(revision)
    owner = _project_owner(project_id, current_user)
    saved = []
    for f in files:
        content = await f.read()
        _check_upload_size(f.filename, content)
        result = s3_upload(project_id, f.filename, content, revision=revision, owner=owner)
        saved.append({"filename": result["filename"], "size": result["size"]})
    return {"project_id": project_id, "files": saved}


@app.get("/api/files/{project_id}")
async def list_project_files(project_id: str, revision: Optional[int] = None,
                             current_user: dict = Depends(require_auth)):
    """프로젝트의 저장된 파일 목록. revision 지정 시 해당 차수 파일만."""
    _validate_revision(revision)
    owner = _project_owner(project_id, current_user, require_exists=True)
    files = s3_list(project_id, revision=revision, owner=owner)
    return {"project_id": project_id, "files": files}


@app.get("/api/files/{project_id}/{filename}")
async def download_project_file(project_id: str, filename: str, revision: Optional[int] = None,
                                current_user: dict = Depends(require_auth)):
    """프로젝트 파일 다운로드. revision 지정 시 해당 차수 경로 우선 탐색."""
    # Path traversal 방지
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    _validate_revision(revision)
    owner = _project_owner(project_id, current_user, require_exists=True)
    try:
        content = s3_get(project_id, filename, revision=revision, owner=owner)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

    if is_s3_enabled():
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": _content_disposition(filename)},
        )
    # 로컬 fallback — FileResponse 사용 (기존 동작 유지)
    file_path = _project_dir(project_id) / filename
    return FileResponse(str(file_path), filename=filename)


@app.delete("/api/files/{project_id}/{filename}")
async def delete_project_file(project_id: str, filename: str, revision: Optional[int] = None,
                              current_user: dict = Depends(require_auth)):
    """프로젝트 파일 삭제."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    _validate_revision(revision)
    owner = _project_owner(project_id, current_user, require_exists=True)
    s3_delete(project_id, filename, revision=revision, owner=owner)
    return {"deleted": filename}


# ─── 텍스트 추출 (파일 파싱 전용) ─────────────────────────

@app.post("/api/parse")
async def parse_file(file: UploadFile = File(...)):
    """파일에서 텍스트만 추출 — AI 호출 없음."""
    content = await file.read()
    _check_upload_size(file.filename, content)
    text = _safe_extract_text(file.filename, content)
    return {"filename": file.filename, "text": text}


@app.post("/api/parse-images")
async def parse_pdf_images(file: UploadFile = File(...)):
    """PDF를 페이지별 base64 이미지로 변환 (Vision API용)."""
    from services.file_parser import extract_pdf_images

    content = await file.read()
    _check_upload_size(file.filename, content)
    ext = Path(file.filename).suffix.lower()
    if ext != ".pdf":
        return {"filename": file.filename, "images": [], "error": "PDF만 지원"}
    if not content:
        raise HTTPException(status_code=422, detail=f"빈 파일입니다: {file.filename}")
    try:
        images = extract_pdf_images(content, max_pages=5)
    except Exception as e:
        logger.warning("PDF 이미지 변환 실패 %s: %s", file.filename, e)
        raise HTTPException(status_code=422, detail=f"PDF를 읽을 수 없습니다(손상): {file.filename}")
    return {"filename": file.filename, "images": images}


@app.post("/api/parse-stored/{project_id}/{filename}")
async def parse_stored_file(project_id: str, filename: str, revision: Optional[int] = None,
                            current_user: dict = Depends(require_auth)):
    """저장된 프로젝트 파일에서 텍스트 추출. revision 지정 시 해당 차수 경로 우선."""
    from services.file_parser import extract_text
    from services.s3_storage import get_file

    _validate_revision(revision)
    owner = _project_owner(project_id, current_user, require_exists=True)
    try:
        content = get_file(project_id, filename, revision=revision, owner=owner)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

    _check_upload_size(filename, content)
    text = _safe_extract_text(filename, content)  # 손상 파일 500 누출 방지(422로 래핑)
    return {"filename": filename, "text": text}


@app.post("/api/parse-stored-images/{project_id}/{filename}")
async def parse_stored_pdf_images(project_id: str, filename: str, revision: Optional[int] = None,
                                  current_user: dict = Depends(require_auth)):
    """저장된 PDF를 이미지로 변환. revision 지정 시 해당 차수 경로 우선."""
    from services.file_parser import extract_pdf_images
    from services.s3_storage import get_file

    _validate_revision(revision)
    owner = _project_owner(project_id, current_user, require_exists=True)
    try:
        content = get_file(project_id, filename, revision=revision, owner=owner)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    _check_upload_size(filename, content)
    try:
        images = extract_pdf_images(content, max_pages=5)
    except Exception as e:
        logger.warning("저장 PDF 이미지 변환 실패 %s: %s", filename, e)
        raise HTTPException(status_code=422, detail=f"PDF를 읽을 수 없습니다(손상): {filename}")
    return {"filename": filename, "images": images}


# ─── AI Service 라우팅 (Feature Flag) ──────────────────────
USE_AI_SERVICE = os.getenv("USE_AI_SERVICE", "false").lower() == "true"
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-service.si-contract.svc.cluster.local:8001")


def _internal_headers() -> dict:
    """내부 서비스 호출용 shared secret 헤더 (설정 시에만)."""
    return {"X-Internal-Secret": INTERNAL_SERVICE_SECRET} if INTERNAL_SERVICE_SECRET else {}


# ─── AI 문서 분류 ─────────────────────────────────────────

@app.post("/api/classify", dependencies=[Depends(require_auth)])
async def classify_file(file: UploadFile = File(...)):
    """파일을 읽고 Claude로 문서 종류 분류."""
    content = await file.read()
    _check_upload_size(file.filename, content)
    text = _safe_extract_text(file.filename, content)

    if USE_AI_SERVICE:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{AI_SERVICE_URL}/classify", json={"filename": file.filename, "text": text}, headers=_internal_headers())
            return resp.json()

    from services.claude_api import classify_document
    return classify_document(file.filename, text)


# ─── AI 값 추출 ───────────────────────────────────────────

def _doc_from_content(filename: str, content: bytes) -> dict:
    """파일 1건 → {filename, text, images}. 스캔(이미지) PDF면 Vision용 이미지 첨부."""
    from services.file_parser import extract_pdf_images, needs_vision
    text = _safe_extract_text(filename, content)
    images: list[str] = []
    if filename.lower().endswith(".pdf") and needs_vision(text):
        try:
            images = extract_pdf_images(content, max_pages=8)
        except Exception as e:
            logger.warning("Vision 이미지 변환 실패 %s: %s", filename, e)
    return {"filename": filename, "text": text, "images": images}


@app.post("/api/extract", dependencies=[Depends(require_auth)])
async def extract_fields(files: list[UploadFile] = File(...)):
    """여러 파일에서 집행계획서 필드값 추출."""
    documents = []
    for f in files:
        content = await f.read()
        _check_upload_size(f.filename, content)
        documents.append(_doc_from_content(f.filename, content))

    if USE_AI_SERVICE:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{AI_SERVICE_URL}/extract", json={"documents": documents}, headers=_internal_headers())
            return resp.json()

    from services.claude_api import extract_all_fields
    return extract_all_fields(documents)


# ─── 탭별(섹션) 추출 ───────────────────────────────────────

async def _documents_from_request(files: list[UploadFile], stored_files: str) -> list[dict]:
    """업로드 파일 또는 저장된 파일(stored_files JSON)에서 문서를 로드한다.
    스캔 PDF는 Vision용 이미지를 함께 첨부(_doc_from_content)."""
    documents: list[dict] = []

    for f in files or []:
        content = await f.read()
        _check_upload_size(f.filename, content)
        documents.append(_doc_from_content(f.filename, content))

    if stored_files:
        from services.s3_storage import get_file
        try:
            sf = json.loads(stored_files)
        except (ValueError, TypeError):
            sf = {}
        project_id = sf.get("projectId")
        revision = sf.get("revision")
        for fn in sf.get("filenames", []):
            if not project_id:
                break
            try:
                content = get_file(project_id, fn, revision=revision)
                documents.append(_doc_from_content(fn, content))
            except FileNotFoundError:
                continue

    return documents


async def _tab_extract(section: str, documents: list[dict]) -> dict:
    """섹션별 추출 — USE_AI_SERVICE면 ai-service로 위임, 아니면 모놀리스(ai_core) 직접 호출.

    ai-service는 backend와 동일한 ai_core를 쓰므로 결과가 같다.
    """
    if USE_AI_SERVICE:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{AI_SERVICE_URL}/extract-{section}",
                json={"documents": documents}, headers=_internal_headers(),
            )
            return resp.json()

    from services import claude_api
    return claude_api.extract_section(section, documents)


@app.post("/api/extract-costs", dependencies=[Depends(require_auth)])
async def extract_costs_endpoint(files: list[UploadFile] = File(default=[]), stored_files: str = Form(default="")):
    """산출내역(비목) 추출."""
    return await _tab_extract("costs", await _documents_from_request(files, stored_files))


@app.post("/api/extract-people", dependencies=[Depends(require_auth)])
async def extract_people_endpoint(files: list[UploadFile] = File(default=[]), stored_files: str = Form(default="")):
    """투입 인원 추출."""
    return await _tab_extract("people", await _documents_from_request(files, stored_files))


@app.post("/api/extract-schedule", dependencies=[Depends(require_auth)])
async def extract_schedule_endpoint(files: list[UploadFile] = File(default=[]), stored_files: str = Form(default="")):
    """공정(일정) 추출."""
    return await _tab_extract("schedule", await _documents_from_request(files, stored_files))


@app.post("/api/extract-rates", dependencies=[Depends(require_auth)])
async def extract_rates_endpoint(files: list[UploadFile] = File(default=[]), stored_files: str = Form(default="")):
    """요율 추출."""
    return await _tab_extract("rates", await _documents_from_request(files, stored_files))


@app.post("/api/extract-org", dependencies=[Depends(require_auth)])
async def extract_org_endpoint(files: list[UploadFile] = File(default=[]), stored_files: str = Form(default="")):
    """수행 조직 추출."""
    return await _tab_extract("org", await _documents_from_request(files, stored_files))


# ─── 교차 검증 ────────────────────────────────────────────

@app.post("/api/validate", dependencies=[Depends(require_auth)])
async def validate_fields(data: dict):
    """추출된 값 교차 검증 — 충돌 감지."""
    if USE_AI_SERVICE:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{AI_SERVICE_URL}/validate", json=data, headers=_internal_headers())
            return resp.json()

    from services.claude_api import cross_validate
    conflicts = cross_validate(data)
    return {"conflicts": conflicts}


# ─── 엑셀 Export ──────────────────────────────────────────

@app.post("/api/export", dependencies=[Depends(require_auth)])
async def export_excel(data: dict):
    """추출/수정된 데이터로 집행계획서 엑셀 생성."""
    from services.excel_writer import generate_excel

    if not data:
        raise HTTPException(status_code=422, detail="export할 데이터가 비어 있습니다")

    output_path = generate_excel(data)
    return FileResponse(
        path=output_path,
        filename="집행계획서.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ─── 하네스 파이프라인 ────────────────────────────────────

@app.post("/api/pipeline/start")
async def start_pipeline(request: StarletteRequest, current_user: dict = Depends(require_auth)):
    """확정된 데이터로 파이프라인 실행: Sprint_Contract 생성 → Executor → (Reviewer)."""
    from services.contract_builder import build_sprint_contract
    from services.orchestrator import run_pipeline

    data = _sanitize_surrogates(await _safe_json_body(request))
    project_id = _validate_project_id(data.get("projectId", f"p_{int(time.time() * 1000)}"))
    # 기존 프로젝트면 소유권 확인(신규 project_id면 통과 — 본인이 생성).
    if load_project(project_id):
        _assert_project_access(project_id, current_user)
    extracted_data = data.get("extractedData", {})
    if not extracted_data:
        raise HTTPException(status_code=422, detail="extractedData가 필요합니다")

    revision = data.get("revision", 0)

    # 차수 상한: 양식 구조 한계 (공통 차수열 E~P = 0~11차)
    from services.company_standards import MAX_REVISION
    if revision > MAX_REVISION:
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"error": f"수정집행은 최대 {MAX_REVISION}차까지 가능합니다 (요청: {revision}차)."},
        )

    # 이전 차수 데이터 가져오기 (DynamoDB에서)
    prev_revisions = {}
    if revision > 0:
        project = load_project(project_id)
        if project and "revisions" in project:
            for rev_num, rev_data in project["revisions"].items():
                if int(rev_num) < revision:
                    prev_revisions[rev_num] = rev_data

    contract = build_sprint_contract(project_id, extracted_data, revision=revision, prev_revisions=prev_revisions)
    state = await run_pipeline(project_id, contract)

    state_dict = state.model_dump()
    save_pipeline_state(project_id, state_dict)

    review = state.review_results[0] if state.review_results else None
    return {
        "projectId": project_id,
        "status": state.status.value,
        "steps": {
            str(k): {"sheet": v.sheet, "status": v.status.value, "notes": v.notes}
            for k, v in state.step_results.items()
        },
        "review": {
            "verdict": review.verdict,
            "score": review.score,
            "issues": review.issues,
            "checklist": review.checklist_results,
        } if review else None,
        "outputFile": state.output_file,
        "tokenUsage": state.token_usage,
        "error": state.error,
    }


@app.get("/api/pipeline/{project_id}/status")
async def pipeline_status(project_id: str, current_user: dict = Depends(require_auth)):
    """파이프라인 상태 조회 — 소유자/admin만(무인증 project_id 열거 차단)."""
    _validate_project_id(project_id)
    if load_project(project_id):
        _assert_project_access(project_id, current_user)
    state = load_pipeline_state(project_id)
    if not state:
        raise HTTPException(404, "Pipeline not found")
    return state


@app.get("/api/pipeline/{project_id}/result")
async def pipeline_result(project_id: str, current_user: dict = Depends(require_auth)):
    """완성된 집행계획서 엑셀 다운로드 (S3 우선, 로컬 fallback)."""
    if load_project(project_id):
        _assert_project_access(project_id, current_user)
    state = load_pipeline_state(project_id)
    if not state or not state.get("output_file"):
        raise HTTPException(404, "Result not found")
    output_key = state["output_file"]

    # S3에서 다운로드 시도
    from services.s3_storage import is_s3_enabled, _s3_client, S3_FILES_BUCKET
    if is_s3_enabled():
        try:
            s3 = _s3_client()
            resp = s3.get_object(Bucket=S3_FILES_BUCKET, Key=output_key)
            content = resp["Body"].read()
            filename = Path(output_key).name
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                # HTTP 헤더는 latin-1만 허용 → 한글 파일명은 RFC 6266/5987 filename* 사용.
                headers={"Content-Disposition": _content_disposition(filename)},
            )
        except Exception as e:
            logger.warning("pipeline result S3 fetch 실패 (key=%r): %s: %s", output_key, type(e).__name__, e)

    # 로컬 fallback (개발환경)
    local_path = Path(output_key)
    if not local_path.exists():
        local_path = RESULTS_DIR / Path(output_key).name
    if not local_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(
        path=str(local_path),
        filename=local_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ─── 프로젝트 CRUD ──────────────────────────────────────────

def _assert_project_access(project_id: str, current_user: dict) -> dict:
    """프로젝트 로드 + owner 인가. 소유자/admin이 아니면 404(존재 사실도 숨김).

    레거시(owner 없음) 레코드는 admin 소유로 간주 → 일반 사용자 접근 차단.
    """
    project = load_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if current_user.get("role") == "admin":
        return project
    owner = project.get("owner") or LEGACY_OWNER
    if owner != current_user.get("email"):
        raise HTTPException(404, "Project not found")
    return project


@app.get("/api/projects")
async def get_projects(current_user: dict = Depends(require_auth)):
    """프로젝트 목록 (extracted 포함, revisions 제외) — 본인 소유만(admin은 전체).

    버전 스탬프 캐시 — write 시 버전 증가로 모든 uvicorn 워커에서
    read-after-write 일관성 보장 (project_store.list_projects_cached).
    """
    return {"projects": list_projects_cached(
        owner=current_user.get("email"), is_admin=current_user.get("role") == "admin")}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str, current_user: dict = Depends(require_auth)):
    """프로젝트 상세 (extracted 포함) — 소유자/admin만."""
    return _assert_project_access(project_id, current_user)


@app.post("/api/projects")
async def create_project(request: StarletteRequest, current_user: dict = Depends(require_auth)):
    """프로젝트 생성/수정 (upsert) — 기존 건은 소유자/admin만 수정 가능."""
    data = _sanitize_surrogates(await _safe_json_body(request))
    if "id" not in data:
        data["id"] = f"p_{int(time.time() * 1000)}"
    _validate_project_id(data["id"])
    # 기존 프로젝트면 소유권 확인(없으면 신규 생성 — 통과).
    if load_project(data["id"]):
        _assert_project_access(data["id"], current_user)
    saved = save_project(data, owner=current_user.get("email"))
    return saved


@app.patch("/api/projects/{project_id}/revision/{revision}")
async def patch_project_revision(project_id: str, revision: int, request: StarletteRequest,
                                 current_user: dict = Depends(require_auth)):
    """현재 차수 데이터만 머지 저장 — 다른 차수는 그대로 유지. 소유자/admin만."""
    _validate_project_id(project_id)
    _validate_revision(revision)
    existing = _assert_project_access(project_id, current_user)
    data = _sanitize_surrogates(await _safe_json_body(request))
    revisions = existing.get("revisions", {})
    revisions[str(revision)] = data.get("extractedData", data)
    existing["id"] = project_id
    existing["revisions"] = revisions
    existing["revision"] = revision
    existing["extracted"] = data.get("extractedData", data)
    saved = save_project(existing, owner=current_user.get("email"))
    return saved


@app.delete("/api/projects/{project_id}")
async def remove_project(project_id: str, current_user: dict = Depends(require_auth)):
    """프로젝트 삭제 — 소유자/admin만."""
    _assert_project_access(project_id, current_user)
    delete_project(project_id)
    return {"deleted": project_id}


# ─── 사용자 설정 (요율 기본값) ─────────────────────────────

@app.get("/api/settings")
async def get_settings():
    """사용자 설정 조회."""
    settings = load_project("__settings__")
    return settings or {"rates": {}}


@app.post("/api/settings", dependencies=[Depends(require_auth)])
async def save_settings(request: StarletteRequest):
    """사용자 설정 저장."""
    data = _sanitize_surrogates(await _safe_json_body(request))
    data["id"] = "__settings__"
    save_project(data)
    return data


# ─── 챗봇 (프로젝트 데이터 기반 질의응답) ─────────────────

@app.post("/api/chat", dependencies=[Depends(require_auth)])
async def chat(request: StarletteRequest):
    """프로젝트 데이터를 컨텍스트로 Claude와 대화 (Bedrock)."""

    data = _sanitize_surrogates(await _safe_json_body(request))
    project_id = data.get("projectId")
    messages = data.get("messages", [])
    revision = data.get("revision", 0)

    if not messages:
        raise HTTPException(422, "messages required")
    if not project_id:
        raise HTTPException(422, "projectId required — 프로젝트를 선택해 주세요")

    # 프로젝트 컨텍스트 구성
    context = ""
    if project_id:
        project = load_project(project_id)
        if project:
            revisions = project.get("revisions", {})
            rev_data = revisions.get(str(revision), project.get("extracted", {}))
            extracted = rev_data.get("extracted", rev_data) if rev_data else {}

            context_parts = []
            context_parts.append(f"프로젝트: {project.get('name', '?')}")
            context_parts.append(f"현재 차수: {revision}차")

            for key, val in extracted.items():
                if isinstance(val, dict) and "value" in val and val["value"]:
                    context_parts.append(f"  {key}: {val['value']}")

            cost_items = rev_data.get("costItems", []) if rev_data else []
            if cost_items:
                context_parts.append(f"\n산출내역 ({len(cost_items)}건):")
                for item in cost_items:
                    context_parts.append(f"  - {item.get('name')} {item.get('spec','')} qty={item.get('contractQty')} 계약단가={item.get('contractPrice')} 집행단가={item.get('executionPrice')} 업체={item.get('vendor','')}")

            rates = rev_data.get("rates", {}) if rev_data else {}
            if rates:
                context_parts.append("\n요율:")
                for k, v in rates.items():
                    if isinstance(v, dict) and v.get("value"):
                        context_parts.append(f"  {k}: {v['value']}%")

            context = "\n".join(context_parts)

    system_prompt = f"""당신은 SI 집행계획서 관리 시스템의 AI 어시스턴트입니다.

[중요 규칙]
- 현재 프로젝트 데이터만 참조하여 답변합니다.
- 다른 프로젝트, 다른 업체의 정보는 절대 제공하지 않습니다.
- 프로젝트 데이터에 없는 정보를 추측하지 않습니다. 모르면 "해당 정보가 없습니다"라고 답변하세요.
- 금액은 천원 단위로 표시하고, 계산 근거를 명확히 설명하세요.
- 한국어로 답변하세요.

{f"[현재 프로젝트 데이터]{chr(10)}{context}" if context else "[프로젝트 데이터 없음 — 프로젝트를 선택해 주세요]"}"""

    user_id = request.headers.get("X-User-Id", "anonymous")
    user_message = messages[-1]["content"]

    # 순수 추론은 USE_AI_SERVICE면 ai-service로 위임(컨텍스트 구성은 backend 책임).
    # ai-service는 backend와 동일 ai_core를 쓰므로 응답 형식이 같다.
    if USE_AI_SERVICE:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{AI_SERVICE_URL}/chat",
                json={"message": user_message, "system": system_prompt,
                      "max_tokens": 1024, "user_id": user_id},
                headers=_internal_headers(),
            )
            return resp.json()

    from services.claude_api import invoke_bedrock
    # AIUnavailableError는 전역 핸들러가 502 {"error","code":"AI_UNAVAILABLE"}로 래핑
    result = invoke_bedrock(
        user_message, max_tokens=1024, system=system_prompt,
        task_type="chat", user_id=user_id,
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


# ─── 프로젝트 편집 잠금 (Clash 방지 — 다중 사용자 동시 수정 방지) ───

@app.post("/api/projects/{project_id}/lock")
async def lock_project(project_id: str, data: dict, current_user: dict = Depends(require_auth)):
    """프로젝트 편집 잠금 획득 — atomic conditional write, 실패 시 409."""
    _validate_project_id(project_id)
    if load_project(project_id):
        _assert_project_access(project_id, current_user)
    user_id = current_user.get("email", data.get("userId", "anonymous"))
    result = acquire_edit_lock(project_id, user_id)
    if result.get("locked"):
        return JSONResponse(status_code=409, content={"error": "다른 사용자가 편집 중입니다", "locked": True, "by": result.get("by")})
    return result


@app.post("/api/projects/{project_id}/unlock")
async def unlock_project(project_id: str, data: dict, current_user: dict = Depends(require_auth)):
    """프로젝트 편집 잠금 해제 — 소유자/admin만."""
    _validate_project_id(project_id)
    if load_project(project_id):
        _assert_project_access(project_id, current_user)
    return release_edit_lock(project_id)


@app.get("/api/projects/{project_id}/lock-status")
async def lock_status(project_id: str, current_user: dict = Depends(require_auth)):
    """프로젝트 잠금 상태 조회 — 인증 + 소유자/admin만(미인가 누수 차단)."""
    if load_project(project_id):
        _assert_project_access(project_id, current_user)
    return get_edit_lock_status(project_id)


# ─── 인증 (Basic Auth + Cognito JWT 검증) ─────────────────

import hashlib
import secrets
import base64

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
# 격리 테스트용 일반 user 계정 (basic auth, role=user)
TEST_USERNAME = os.getenv("TEST_USERNAME", "test")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "test")

# JWT_SECRET은 모든 워커/파드에서 동일해야 함 — 랜덤 폴백이면 uvicorn --workers N에서
# 워커별 시크릿이 달라 토큰 발급 워커 ≠ 검증 워커일 때 401 (env → Secrets Manager → 랜덤 순)
from services.secrets import get_secret as _get_secret
JWT_SECRET = os.getenv("JWT_SECRET") or _get_secret("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    logger.warning("JWT_SECRET 미설정 — 워커별 랜덤 시크릿 사용 (멀티워커 환경에서 토큰 검증 실패 가능)")

COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "ap-northeast-2_Wz3a01s3w")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "6aarjh4rm676q8c61ll8li24h9")


def _create_basic_token(username: str) -> str:
    """간단한 세션 토큰 생성 (Basic Auth용)."""
    import hmac
    payload = f"{username}:{int(time.time()) + 28800}"  # 8시간 유효
    sig = hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()


def _verify_basic_token(token: str) -> str | None:
    """Basic Auth 토큰 검증. 유효하면 username 반환."""
    import hmac
    try:
        decoded = base64.urlsafe_b64decode(token).decode()
        parts = decoded.rsplit(":", 1)
        if len(parts) != 2:
            return None
        payload, sig = parts
        expected_sig = hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):  # 상수시간 비교(타이밍 공격 방지)
            return None
        username, expires = payload.rsplit(":", 1)
        if int(expires) < int(time.time()):
            return None
        return username
    except Exception:
        return None


# require_auth dependency의 Basic Auth 폴백 주입 (하위 호환)
_cognito_auth_module.basic_token_verifier = _verify_basic_token


@app.post("/api/auth/login")
async def auth_login(data: dict):
    """Basic Auth 로그인.

    - admin/ADMIN_PASSWORD → 진짜 admin(전체 접근)
    - test/TEST_PASSWORD   → 일반 user(격리 테스트용)
    role은 resolve_role이 username 기준으로 판별(admin 계정만 admin).
    """
    username = data.get("username", "")
    password = data.get("password", "")

    accounts = {ADMIN_USERNAME: ADMIN_PASSWORD, TEST_USERNAME: TEST_PASSWORD}
    if username in accounts and password == accounts[username]:
        token = _create_basic_token(username)
        return {"token": token, "user": {"email": username, "role": resolve_role(username, "basic")}}

    raise HTTPException(401, "Invalid credentials")


@app.get("/api/auth/me")
async def auth_me(request: StarletteRequest):
    """현재 인증된 사용자 정보. Cognito JWT 우선 → Basic Auth fallback."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")

    token = auth_header[7:]

    from services.cognito_auth import verify_cognito_token
    payload = verify_cognito_token(token)
    if payload:
        email = payload.get("email", payload.get("cognito:username", ""))
        return {"email": email, "role": resolve_role(email, "cognito"), "provider": "cognito"}

    username = _verify_basic_token(token)
    if username:
        return {"email": username, "role": resolve_role(username, "basic"), "provider": "basic"}

    raise HTTPException(401, "Invalid token")
