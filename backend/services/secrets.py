"""AWS Secrets Manager에서 시크릿 로드 — IRSA 인증 사용."""

import os
import json
import logging

logger = logging.getLogger("si-contract")

SECRET_NAME = os.getenv("AWS_SECRET_NAME", "si-contract-dev/app-secrets")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")

_cache: dict | None = None


def load_secrets() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    try:
        import boto3
        client = boto3.client("secretsmanager", region_name=AWS_REGION)
        resp = client.get_secret_value(SecretId=SECRET_NAME)
        _cache = json.loads(resp["SecretString"])
        logger.info("Secrets loaded from AWS Secrets Manager: %s", SECRET_NAME)
        return _cache
    except Exception as e:
        logger.warning("Secrets Manager unavailable (%s), using env vars", e)
        _cache = {}
        return _cache


def get_secret(key: str, default: str = "") -> str:
    secrets = load_secrets()
    if key in secrets:
        return secrets[key]
    return os.getenv(key, default)


def get_database_url() -> str:
    secrets = load_secrets()
    if "DATABASE_URL" in secrets:
        return secrets["DATABASE_URL"]
    host = secrets.get("DB_HOST", "")
    if host:
        port = secrets.get("DB_PORT", "5432")
        name = secrets.get("DB_NAME", "si_contract")
        user = secrets.get("DB_USERNAME", "dbadmin")
        pw = secrets.get("DB_PASSWORD", "")
        return f"postgresql://{user}:{pw}@{host}:{port}/{name}"
    return os.getenv("DATABASE_URL", "")
