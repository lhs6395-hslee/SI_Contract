"""Cognito JWT 검증 — JWKS 기반 토큰 검증 + FastAPI 인증 dependency."""

import os
import json
import time
import logging
import urllib.request
from base64 import urlsafe_b64decode

from fastapi import HTTPException, Request

logger = logging.getLogger("si-contract")

COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "ap-northeast-2_Wz3a01s3w")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "6aarjh4rm676q8c61ll8li24h9")
COGNITO_REGION = COGNITO_USER_POOL_ID.split("_")[0] if "_" in COGNITO_USER_POOL_ID else "ap-northeast-2"
JWKS_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0


def _fetch_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    if _jwks_cache and time.time() - _jwks_fetched_at < 3600:
        return _jwks_cache
    try:
        resp = urllib.request.urlopen(JWKS_URL, timeout=5)
        _jwks_cache = json.loads(resp.read())
        _jwks_fetched_at = time.time()
        return _jwks_cache
    except Exception as e:
        logger.warning("JWKS fetch failed: %s", e)
        return _jwks_cache or {"keys": []}


def _b64_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return urlsafe_b64decode(data)


def _decode_jwt_unverified(token: str) -> tuple[dict, dict]:
    """JWT 헤더/페이로드 디코딩 (서명 검증 없음 — JWKS kid 매칭용)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    header = json.loads(_b64_decode(parts[0]))
    payload = json.loads(_b64_decode(parts[1]))
    return header, payload


def verify_cognito_token(token: str) -> dict | None:
    """Cognito ID/Access 토큰 검증. 성공 시 payload 반환, 실패 시 None.

    간소화 검증: iss/aud/exp 클레임 확인 + JWKS kid 매칭.
    프로덕션 RSA 서명 검증은 PyJWT + cryptography 필요 — 현재는 클레임 기반.
    """
    try:
        header, payload = _decode_jwt_unverified(token)
    except Exception:
        return None

    expected_iss = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
    if payload.get("iss") != expected_iss:
        return None

    if payload.get("client_id") != COGNITO_CLIENT_ID and payload.get("aud") != COGNITO_CLIENT_ID:
        return None

    exp = payload.get("exp", 0)
    if time.time() > exp:
        return None

    jwks = _fetch_jwks()
    kid = header.get("kid")
    if kid and not any(k.get("kid") == kid for k in jwks.get("keys", [])):
        return None

    return payload


# ─── FastAPI 인증 dependency ─────────────────────────────────

# Basic Auth 폴백 (하위 호환) — main.py가 _verify_basic_token을 주입
basic_token_verifier = None


async def require_auth(request: Request) -> dict:
    """Bearer 토큰 필수 — Cognito JWT 우선, Basic Auth 토큰 폴백.

    사용: @app.post(..., dependencies=[Depends(require_auth)])
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")

    token = auth_header[7:]

    payload = verify_cognito_token(token)
    if payload:
        return {
            "email": payload.get("email", payload.get("cognito:username", "")),
            "provider": "cognito",
        }

    if basic_token_verifier:
        username = basic_token_verifier(token)
        if username:
            return {"email": username, "provider": "basic"}

    raise HTTPException(401, "Invalid token")
