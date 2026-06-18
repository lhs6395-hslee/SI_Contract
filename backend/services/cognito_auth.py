"""Cognito JWT 검증 — JWKS 기반 토큰 검증 + FastAPI 인증 dependency."""

import os
import json
import time
import logging
import urllib.request
from base64 import urlsafe_b64decode

from fastapi import HTTPException, Request

logger = logging.getLogger("si-contract")

# 계정 격리 — admin은 전체 프로젝트/파일 접근, 일반 사용자는 본인 owner 것만.
# admin은 basic auth의 'admin' 계정(provider=basic, username=ADMIN_USERNAME)만.
# basic의 test 계정이나 Google(Cognito) 로그인 사용자는 전부 일반 user.
# (email 기반 아님 — 이메일은 누구나 주장 가능)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
# 레거시(owner 없는) 프로젝트의 귀속 소유자 — admin의 email 필드값(=username)과 일치해야
# admin이 레거시 항목을 본다.
LEGACY_OWNER = ADMIN_USERNAME


def resolve_role(email: str = "", provider: str = "") -> str:
    """role 판별 — basic auth의 admin 계정만 'admin', 나머지(test/cognito)는 'user'."""
    return "admin" if (provider == "basic" and email == ADMIN_USERNAME) else "user"


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
    # kid는 필수 — 없거나 JWKS에 매칭되지 않으면 거부(없으면 통과시키던 우회 차단).
    keys = {k.get("kid"): k for k in jwks.get("keys", [])}
    if not kid or kid not in keys:
        return None

    # RSA 서명 실검증 — PyJWT 가용 시 수행(없으면 클레임+kid 검증으로 폴백).
    try:
        import jwt as _pyjwt
        from jwt.algorithms import RSAAlgorithm
        public_key = RSAAlgorithm.from_jwk(json.dumps(keys[kid]))
        _pyjwt.decode(
            token, public_key, algorithms=["RS256"],
            audience=COGNITO_CLIENT_ID, issuer=expected_iss,
            options={"verify_aud": payload.get("aud") is not None},
        )
    except ImportError:
        logger.warning("PyJWT 미설치 — JWT RSA 서명 미검증(클레임+kid만). 프로덕션은 PyJWT 필요.")
    except Exception as e:
        logger.warning("JWT 서명 검증 실패: %s", e)
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
        email = payload.get("email", payload.get("cognito:username", ""))
        return {"email": email, "role": resolve_role(email, "cognito"), "provider": "cognito"}

    if basic_token_verifier:
        username = basic_token_verifier(token)
        if username:
            return {"email": username, "role": resolve_role(username, "basic"), "provider": "basic"}

    raise HTTPException(401, "Invalid token")
