"""SI 집행계획서 자동화 — FastAPI 백엔드"""
import os
import json
import uuid
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
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
)

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

# API Key 인증 (내부 통신은 K8s 서비스 디스커버리로 보호, 외부는 API Key 필수)
API_KEY = os.getenv("API_KEY", "")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        # health check, CORS preflight는 인증 스킵
        if request.url.path == "/api/health" or request.method == "OPTIONS":
            return await call_next(request)
        # 내부 통신 (K8s 서비스 → 서비스)은 X-Internal 헤더로 스킵
        if request.headers.get("X-Internal") == "true":
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

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        with _rate_lock:
            _rate_store[client_ip] = [t for t in _rate_store[client_ip] if now - t < RATE_WINDOW]
            if len(_rate_store[client_ip]) >= RATE_LIMIT:
                from starlette.responses import JSONResponse
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
            _rate_store[client_ip].append(now)

        return await call_next(request)

app.add_middleware(RateLimitMiddleware)

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
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    return {"status": "ok", "claude_api": "configured" if has_key else "missing"}


# ─── 프로젝트별 파일 저장 ─────────────────────────────────

@app.post("/api/files/{project_id}/upload")
async def upload_project_files(
    project_id: str,
    files: list[UploadFile] = File(...),
    revision: Optional[int] = None,
):
    """프로젝트에 파일 저장 (S3 또는 로컬). revision 지정 시 rev{N}/ 경로에 저장."""
    saved = []
    for f in files:
        content = await f.read()
        result = s3_upload(project_id, f.filename, content, revision=revision)
        saved.append({"filename": result["filename"], "size": result["size"]})
    return {"project_id": project_id, "files": saved}


@app.get("/api/files/{project_id}")
async def list_project_files(project_id: str, revision: Optional[int] = None):
    """프로젝트의 저장된 파일 목록. revision 지정 시 해당 차수 파일만."""
    files = s3_list(project_id, revision=revision)
    return {"project_id": project_id, "files": files}


@app.get("/api/files/{project_id}/{filename}")
async def download_project_file(project_id: str, filename: str, revision: Optional[int] = None):
    """프로젝트 파일 다운로드. revision 지정 시 해당 차수 경로 우선 탐색."""
    # Path traversal 방지
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    try:
        content = s3_get(project_id, filename, revision=revision)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

    if is_s3_enabled():
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    # 로컬 fallback — FileResponse 사용 (기존 동작 유지)
    file_path = _project_dir(project_id) / filename
    return FileResponse(str(file_path), filename=filename)


@app.delete("/api/files/{project_id}/{filename}")
async def delete_project_file(project_id: str, filename: str, revision: Optional[int] = None):
    """프로젝트 파일 삭제."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    s3_delete(project_id, filename, revision=revision)
    return {"deleted": filename}


# ─── 텍스트 추출 (파일 파싱 전용) ─────────────────────────

@app.post("/api/parse")
async def parse_file(file: UploadFile = File(...)):
    """파일에서 텍스트만 추출 — AI 호출 없음."""
    from services.file_parser import extract_text

    content = await file.read()
    text = extract_text(file.filename, content)
    return {"filename": file.filename, "text": text}


@app.post("/api/parse-images")
async def parse_pdf_images(file: UploadFile = File(...)):
    """PDF를 페이지별 base64 이미지로 변환 (Vision API용)."""
    from services.file_parser import extract_pdf_images

    content = await file.read()
    ext = Path(file.filename).suffix.lower()
    if ext != ".pdf":
        return {"filename": file.filename, "images": [], "error": "PDF만 지원"}

    images = extract_pdf_images(content, max_pages=5)
    return {"filename": file.filename, "images": images}


@app.post("/api/parse-stored/{project_id}/{filename}")
async def parse_stored_file(project_id: str, filename: str, revision: Optional[int] = None):
    """저장된 프로젝트 파일에서 텍스트 추출. revision 지정 시 해당 차수 경로 우선."""
    from services.file_parser import extract_text
    from services.s3_storage import get_file

    try:
        content = get_file(project_id, filename, revision=revision)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

    text = extract_text(filename, content)
    return {"filename": filename, "text": text}


@app.post("/api/parse-stored-images/{project_id}/{filename}")
async def parse_stored_pdf_images(project_id: str, filename: str, revision: Optional[int] = None):
    """저장된 PDF를 이미지로 변환. revision 지정 시 해당 차수 경로 우선."""
    from services.file_parser import extract_pdf_images
    from services.s3_storage import get_file

    try:
        content = get_file(project_id, filename, revision=revision)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    images = extract_pdf_images(content, max_pages=5)
    return {"filename": filename, "images": images}


# ─── AI 문서 분류 ─────────────────────────────────────────

@app.post("/api/classify")
async def classify_file(file: UploadFile = File(...)):
    """파일을 읽고 Claude로 문서 종류 분류."""
    from services.file_parser import extract_text
    from services.claude_api import classify_document

    content = await file.read()
    text = extract_text(file.filename, content)
    result = classify_document(file.filename, text)

    return result


# ─── AI 값 추출 ───────────────────────────────────────────

@app.post("/api/extract")
async def extract_fields(files: list[UploadFile] = File(...)):
    """여러 파일에서 집행계획서 필드값 추출."""
    from services.file_parser import extract_text
    from services.claude_api import extract_all_fields

    documents = []
    for f in files:
        content = await f.read()
        text = extract_text(f.filename, content)
        documents.append({
            "filename": f.filename,
            "text": text,
        })

    result = extract_all_fields(documents)
    return result


# ─── 교차 검증 ────────────────────────────────────────────

@app.post("/api/validate")
async def validate_fields(data: dict):
    """추출된 값 교차 검증 — 충돌 감지."""
    from services.claude_api import cross_validate

    conflicts = cross_validate(data)
    return {"conflicts": conflicts}


# ─── 엑셀 Export ──────────────────────────────────────────

@app.post("/api/export")
async def export_excel(data: dict):
    """추출/수정된 데이터로 집행계획서 엑셀 생성."""
    from services.excel_writer import generate_excel

    output_path = generate_excel(data)
    return FileResponse(
        path=output_path,
        filename="집행계획서.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ─── 하네스 파이프라인 ────────────────────────────────────

@app.post("/api/pipeline/start")
async def start_pipeline(request: StarletteRequest):
    """확정된 데이터로 파이프라인 실행: Sprint_Contract 생성 → Executor → (Reviewer)."""
    from services.contract_builder import build_sprint_contract
    from services.orchestrator import run_pipeline

    data = _sanitize_surrogates(await _safe_json_body(request))
    project_id = data.get("projectId", f"p_{int(time.time() * 1000)}")
    extracted_data = data.get("extractedData", {})

    revision = data.get("revision", 0)

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
async def pipeline_status(project_id: str):
    """파이프라인 상태 조회."""
    state = load_pipeline_state(project_id)
    if not state:
        raise HTTPException(404, "Pipeline not found")
    return state


@app.get("/api/pipeline/{project_id}/result")
async def pipeline_result(project_id: str):
    """완성된 집행계획서 엑셀 다운로드 (S3 우선, 로컬 fallback)."""
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
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception:
            pass

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

@app.get("/api/projects")
async def get_projects():
    """프로젝트 목록 (extracted 포함, revisions 제외 — N+1 쿼리 방지)."""
    projects_list = list_projects()
    # 각 프로젝트의 상세 데이터 로드 (revisions 제외)
    full = []
    for p in projects_list:
        detail = load_project(p.get("id", ""))
        if detail:
            detail.pop("revisions", None)
            full.append(detail)
        else:
            full.append(p)
    return {"projects": full}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """프로젝트 상세 (extracted 포함)."""
    project = load_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@app.post("/api/projects")
async def create_project(request: StarletteRequest):
    """프로젝트 생성/수정 (upsert)."""
    data = _sanitize_surrogates(await _safe_json_body(request))
    if "id" not in data:
        data["id"] = f"p_{int(time.time() * 1000)}"
    saved = save_project(data)
    return saved


@app.patch("/api/projects/{project_id}/revision/{revision}")
async def patch_project_revision(project_id: str, revision: int, request: StarletteRequest):
    """현재 차수 데이터만 머지 저장 — 다른 차수는 그대로 유지."""
    data = _sanitize_surrogates(await _safe_json_body(request))
    existing = load_project(project_id) or {}
    revisions = existing.get("revisions", {})
    revisions[str(revision)] = data.get("extractedData", data)
    existing["id"] = project_id
    existing["revisions"] = revisions
    existing["revision"] = revision
    existing["extracted"] = data.get("extractedData", data)
    saved = save_project(existing)
    return saved


@app.delete("/api/projects/{project_id}")
async def remove_project(project_id: str):
    """프로젝트 삭제."""
    delete_project(project_id)
    return {"deleted": project_id}


# ─── 사용자 설정 (요율 기본값) ─────────────────────────────

@app.get("/api/settings")
async def get_settings():
    """사용자 설정 조회."""
    settings = load_project("__settings__")
    return settings or {"rates": {}}


@app.post("/api/settings")
async def save_settings(request: StarletteRequest):
    """사용자 설정 저장."""
    data = _sanitize_surrogates(await _safe_json_body(request))
    data["id"] = "__settings__"
    save_project(data)
    return data


# ─── 챗봇 (프로젝트 데이터 기반 질의응답) ─────────────────

@app.post("/api/chat")
async def chat(request: StarletteRequest):
    """프로젝트 데이터를 컨텍스트로 Claude와 대화 (Bedrock)."""
    import boto3

    data = _sanitize_surrogates(await _safe_json_body(request))
    project_id = data.get("projectId")
    messages = data.get("messages", [])
    revision = data.get("revision", 0)

    if not messages:
        raise HTTPException(400, "messages required")
    if not project_id:
        raise HTTPException(400, "projectId required — 프로젝트를 선택해 주세요")

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

    # Bedrock 호출
    import json as _json
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
    body = _json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": messages,
    })
    response = bedrock.invoke_model(
        modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = _json.loads(response["body"].read())

    # 토큰 사용량 추적
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
async def lock_project(project_id: str, data: dict):
    """프로젝트 편집 잠금 획득."""
    user_id = data.get("userId", "anonymous")
    return acquire_edit_lock(project_id, user_id)


@app.post("/api/projects/{project_id}/unlock")
async def unlock_project(project_id: str, data: dict):
    """프로젝트 편집 잠금 해제."""
    return release_edit_lock(project_id)


@app.get("/api/projects/{project_id}/lock-status")
async def lock_status(project_id: str):
    """프로젝트 잠금 상태 조회."""
    return get_edit_lock_status(project_id)


# ─── 인증 (Basic Auth + Cognito JWT 검증) ─────────────────

import hashlib
import secrets
import base64

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))

COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "ap-northeast-2_Wz3a01s3w")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "6aarjh4rm676q8c61ll8li24h9")


def _create_basic_token(username: str) -> str:
    """간단한 세션 토큰 생성 (Basic Auth용)."""
    import hmac
    payload = f"{username}:{int(time.time()) + 86400 * 7}"  # 7일 유효
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
        if sig != expected_sig:
            return None
        username, expires = payload.rsplit(":", 1)
        if int(expires) < int(time.time()):
            return None
        return username
    except Exception:
        return None


@app.post("/api/auth/login")
async def auth_login(data: dict):
    """Basic Auth 로그인 — admin 계정."""
    username = data.get("username", "")
    password = data.get("password", "")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        token = _create_basic_token(username)
        return {"token": token, "user": {"email": username, "role": "admin"}}

    raise HTTPException(401, "Invalid credentials")


@app.get("/api/auth/me")
async def auth_me(request: StarletteRequest):
    """현재 인증된 사용자 정보."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        username = _verify_basic_token(token)
        if username:
            return {"email": username, "role": "admin", "provider": "basic"}

    raise HTTPException(401, "Not authenticated")
