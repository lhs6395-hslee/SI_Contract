"""S3 파일 저장 서비스 — S3 미설정 시 로컬 filesystem fallback."""

import os
import unicodedata
from pathlib import Path
from typing import Optional

S3_FILES_BUCKET = os.getenv("S3_FILES_BUCKET", "")
S3_TEMPLATES_BUCKET = os.getenv("S3_TEMPLATES_BUCKET", "")

# 로컬 fallback 경로 (기존 main.py와 동일)
_STORAGE_DIR = Path(__file__).parent.parent / "storage"
_STORAGE_DIR.mkdir(exist_ok=True)

_TEMPLATE_DIR = Path(__file__).parent / "excel"


_s3 = None


def _s3_client():
    # boto3 client는 생성 비용이 큼 → 모듈 싱글톤 재사용 (스레드세이프).
    global _s3
    if _s3 is None:
        import boto3
        _s3 = boto3.client("s3")
    return _s3


def is_s3_enabled() -> bool:
    """S3 버킷이 설정되어 있으면 True."""
    return bool(S3_FILES_BUCKET)


def _project_prefix(project_id: str, revision: Optional[int] = None, owner: Optional[str] = None) -> str:
    """S3 key prefix. 계정별 폴더 분리: owner 지정 시 projects/{owner}/{id}/...

    owner=None이면 레거시 경로(projects/{id}/...) — 마이그레이션 전 데이터 및
    하위호환 fallback용. revision이 있으면 rev{N}/ 하위 경로.
    """
    base = f"projects/{owner}/{project_id}" if owner else f"projects/{project_id}"
    if revision is not None:
        return f"{base}/rev{revision}/"
    return f"{base}/"


# ─── 로컬 헬퍼 ──────────────────────────────────────────────

def _local_project_dir(project_id: str, revision: Optional[int] = None) -> Path:
    if revision is not None:
        d = _STORAGE_DIR / project_id / f"rev{revision}"
    else:
        d = _STORAGE_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ─── 공개 API ────────────────────────────────────────────────

def upload_file(project_id: str, filename: str, content: bytes, revision: Optional[int] = None,
                owner: Optional[str] = None) -> dict:
    """파일 업로드. S3 또는 로컬 저장. owner 지정 시 계정별 폴더에 저장."""
    if is_s3_enabled():
        key = f"{_project_prefix(project_id, revision, owner)}{filename}"
        _s3_client().put_object(
            Bucket=S3_FILES_BUCKET,
            Key=key,
            Body=content,
        )
        return {"filename": filename, "size": len(content), "storage": "s3"}

    # 로컬 fallback
    file_path = _local_project_dir(project_id, revision) / filename
    file_path.write_bytes(content)
    return {"filename": filename, "size": len(content), "storage": "local"}


def list_files(project_id: str, revision: Optional[int] = None, owner: Optional[str] = None) -> list[dict]:
    """프로젝트 파일 목록. revision이 있으면 해당 차수만, 없으면 전체(루트 레벨만).

    owner 지정 시 계정별 폴더 우선 조회, 비어 있으면 레거시 경로 fallback(하위호환).
    """
    if is_s3_enabled():
        s3 = _s3_client()
        # owner 경로 우선, 결과 없으면 레거시(owner 없는) 경로 fallback
        prefixes = []
        if owner:
            prefixes.append(_project_prefix(project_id, revision, owner))
        prefixes.append(_project_prefix(project_id, revision, None))
        for prefix in prefixes:
            resp = s3.list_objects_v2(Bucket=S3_FILES_BUCKET, Prefix=prefix)
            files = []
            for obj in resp.get("Contents", []):
                name = obj["Key"].removeprefix(prefix)
                # 하위 디렉토리 항목 제외 (revision=None일 때 rev0/, rev1/ 등 스킵)
                if name and not name.startswith(".") and "/" not in name:
                    files.append({"filename": name, "size": obj["Size"]})
            if files:
                return files
        return []

    # 로컬 fallback
    project_dir = _local_project_dir(project_id, revision)
    files = []
    for f in sorted(project_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            files.append({"filename": f.name, "size": f.stat().st_size})
    return files


def get_file(project_id: str, filename: str, revision: Optional[int] = None,
             owner: Optional[str] = None) -> bytes:
    """파일 다운로드. NFC/NFD 인코딩 둘 다 시도.
    owner 경로 우선 → 레거시 경로 fallback, revision 경로 우선 → 루트 fallback (하위호환).
    """
    if is_s3_enabled():
        import botocore.exceptions
        s3 = _s3_client()

        # 시도할 prefix 목록: (owner 경로, 레거시 경로) × (rev 경로, 루트)
        prefixes_to_try = []
        for own in ([owner, None] if owner else [None]):
            if revision is not None:
                prefixes_to_try.append(_project_prefix(project_id, revision, own))
            prefixes_to_try.append(_project_prefix(project_id, None, own))

        for prefix in prefixes_to_try:
            for form in ("NFC", "NFD"):
                normalized = unicodedata.normalize(form, filename)
                key = f"{prefix}{normalized}"
                try:
                    resp = s3.get_object(Bucket=S3_FILES_BUCKET, Key=key)
                    return resp["Body"].read()
                except botocore.exceptions.ClientError as e:
                    if e.response["Error"]["Code"] == "NoSuchKey":
                        continue
                    raise

        raise FileNotFoundError(f"{project_id}/{filename}")

    # 로컬 fallback
    paths_to_try = []
    if revision is not None:
        paths_to_try.append(_local_project_dir(project_id, revision) / filename)
    paths_to_try.append(_local_project_dir(project_id, None) / filename)

    for file_path in paths_to_try:
        if file_path.exists():
            return file_path.read_bytes()

    raise FileNotFoundError(f"{project_id}/{filename}")


def delete_file(project_id: str, filename: str, revision: Optional[int] = None,
                owner: Optional[str] = None) -> None:
    """파일 삭제. owner 경로 + 레거시 경로 둘 다 삭제(마이그레이션 잔존 방지)."""
    if is_s3_enabled():
        s3 = _s3_client()
        for own in ([owner, None] if owner else [None]):
            s3.delete_object(
                Bucket=S3_FILES_BUCKET,
                Key=f"{_project_prefix(project_id, revision, own)}{filename}",
            )
        return

    # 로컬 fallback
    file_path = _local_project_dir(project_id, revision) / filename
    if file_path.exists():
        file_path.unlink()


def get_template() -> bytes:
    """집행계획서 템플릿 로드 — S3_TEMPLATES_BUCKET 또는 로컬."""
    if S3_TEMPLATES_BUCKET:
        s3 = _s3_client()
        resp = s3.get_object(
            Bucket=S3_TEMPLATES_BUCKET,
            Key="template.xlsx",
        )
        return resp["Body"].read()

    # 로컬 fallback — services/excel/ 디렉토리에서 로드
    template_path = _TEMPLATE_DIR / "template.xlsx"
    if not template_path.exists():
        raise FileNotFoundError("로컬 템플릿 파일을 찾을 수 없습니다")
    return template_path.read_bytes()
