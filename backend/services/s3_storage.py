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


def _s3_client():
    import boto3
    return boto3.client("s3")


def is_s3_enabled() -> bool:
    """S3 버킷이 설정되어 있으면 True."""
    return bool(S3_FILES_BUCKET)


def _project_prefix(project_id: str, revision: Optional[int] = None) -> str:
    """S3 key prefix. revision이 있으면 rev{N}/ 하위 경로."""
    if revision is not None:
        return f"projects/{project_id}/rev{revision}/"
    return f"projects/{project_id}/"


# ─── 로컬 헬퍼 ──────────────────────────────────────────────

def _local_project_dir(project_id: str, revision: Optional[int] = None) -> Path:
    if revision is not None:
        d = _STORAGE_DIR / project_id / f"rev{revision}"
    else:
        d = _STORAGE_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ─── 공개 API ────────────────────────────────────────────────

def upload_file(project_id: str, filename: str, content: bytes, revision: Optional[int] = None) -> dict:
    """파일 업로드. S3 또는 로컬 저장."""
    if is_s3_enabled():
        key = f"{_project_prefix(project_id, revision)}{filename}"
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


def list_files(project_id: str, revision: Optional[int] = None) -> list[dict]:
    """프로젝트 파일 목록. revision이 있으면 해당 차수만, 없으면 전체(루트 레벨만)."""
    if is_s3_enabled():
        s3 = _s3_client()
        prefix = _project_prefix(project_id, revision)
        resp = s3.list_objects_v2(Bucket=S3_FILES_BUCKET, Prefix=prefix)
        files = []
        for obj in resp.get("Contents", []):
            name = obj["Key"].removeprefix(prefix)
            # 하위 디렉토리 항목 제외 (revision=None일 때 rev0/, rev1/ 등 스킵)
            if name and not name.startswith(".") and "/" not in name:
                files.append({"filename": name, "size": obj["Size"]})
        return files

    # 로컬 fallback
    project_dir = _local_project_dir(project_id, revision)
    files = []
    for f in sorted(project_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            files.append({"filename": f.name, "size": f.stat().st_size})
    return files


def get_file(project_id: str, filename: str, revision: Optional[int] = None) -> bytes:
    """파일 다운로드. NFC/NFD 인코딩 둘 다 시도.
    revision 지정 시 해당 경로 먼저, 없으면 루트 경로 fallback (하위호환).
    """
    if is_s3_enabled():
        import botocore.exceptions
        s3 = _s3_client()

        # 시도할 prefix 목록: revision 지정 → rev 경로 우선, 루트 fallback
        prefixes_to_try = []
        if revision is not None:
            prefixes_to_try.append(_project_prefix(project_id, revision))
        prefixes_to_try.append(_project_prefix(project_id, None))

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


def delete_file(project_id: str, filename: str, revision: Optional[int] = None) -> None:
    """파일 삭제."""
    if is_s3_enabled():
        _s3_client().delete_object(
            Bucket=S3_FILES_BUCKET,
            Key=f"{_project_prefix(project_id, revision)}{filename}",
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
