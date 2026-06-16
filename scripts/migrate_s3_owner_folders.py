#!/usr/bin/env python3
"""S3 계정 격리 마이그레이션 — 레거시 projects/{id}/... → projects/{owner}/{id}/...

owner는 DynamoDB 프로젝트 레코드에서 조회한다. owner가 없는 레코드는 ADMIN_EMAIL
소유로 간주(백엔드 필터와 동일 규칙). 이미 owner 폴더로 옮겨진 객체는 건너뛴다.

사용:
  python3 scripts/migrate_s3_owner_folders.py --dry-run   # 무엇이 옮겨질지만 출력
  python3 scripts/migrate_s3_owner_folders.py             # 실제 복사
  python3 scripts/migrate_s3_owner_folders.py --delete-old # 복사 후 원본 삭제(검증 후 권장)

복사(copy_object)만 하고 원본은 기본 보존 — 안전 확인 후 --delete-old로 정리.
멱등: 재실행해도 이미 이동된 건은 스킵.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import boto3

from services.s3_storage import S3_FILES_BUCKET, is_s3_enabled
from services.project_store import list_projects_full, is_dynamo_enabled
from services.cognito_auth import ADMIN_EMAIL

LEGACY_PREFIX = "projects/"


def _owner_map() -> dict:
    """{project_id: owner} — owner 없으면 ADMIN_EMAIL."""
    m = {}
    for p in list_projects_full():
        pid = p.get("id")
        if pid:
            m[pid] = p.get("owner") or ADMIN_EMAIL
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="복사 없이 계획만 출력")
    ap.add_argument("--delete-old", action="store_true", help="복사 후 레거시 원본 삭제")
    args = ap.parse_args()

    if not is_s3_enabled():
        print("S3 미설정(S3_FILES_BUCKET 없음) — 중단", file=sys.stderr)
        return 2
    if not is_dynamo_enabled():
        print("DynamoDB 미설정 — owner 조회 불가, 중단", file=sys.stderr)
        return 2

    owners = _owner_map()
    print(f"프로젝트 {len(owners)}개 owner 매핑 로드 (admin fallback={ADMIN_EMAIL})")

    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")

    copied = skipped = orphaned = deleted = 0
    for page in paginator.paginate(Bucket=S3_FILES_BUCKET, Prefix=LEGACY_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            rest = key[len(LEGACY_PREFIX):]
            parts = rest.split("/", 1)
            if len(parts) < 2:
                continue
            pid, tail = parts[0], parts[1]
            # 이미 owner 폴더 구조면(첫 세그먼트가 알려진 project_id가 아니라 이메일) 스킵
            if pid not in owners:
                # pid가 이메일 형태(owner 폴더)거나 미지의 프로젝트
                if "@" in pid:
                    skipped += 1  # 이미 마이그레이션됨
                else:
                    orphaned += 1
                    print(f"  [orphan] {key} — DynamoDB에 project_id={pid} 없음(건너뜀)")
                continue

            owner = owners[pid]
            new_key = f"{LEGACY_PREFIX}{owner}/{pid}/{tail}"
            if new_key == key:
                skipped += 1
                continue

            # 대상이 이미 있으면 복사는 스킵(멱등). 단 --delete-old면 레거시 원본은 삭제.
            already = False
            try:
                s3.head_object(Bucket=S3_FILES_BUCKET, Key=new_key)
                already = True
            except s3.exceptions.ClientError:
                pass

            if already:
                skipped += 1
                if args.delete_old and not args.dry_run:
                    s3.delete_object(Bucket=S3_FILES_BUCKET, Key=key)
                    deleted += 1
                    print(f"  del(legacy, already-copied): {key}")
                continue

            print(f"  copy: {key}\n     -> {new_key}")
            if not args.dry_run:
                s3.copy_object(
                    Bucket=S3_FILES_BUCKET,
                    CopySource={"Bucket": S3_FILES_BUCKET, "Key": key},
                    Key=new_key,
                )
                if args.delete_old:
                    s3.delete_object(Bucket=S3_FILES_BUCKET, Key=key)
                    deleted += 1
            copied += 1

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"\n[{mode}] 복사 {copied} / 스킵 {skipped} / 고아 {orphaned}"
          + (f" / 원본삭제 {deleted}" if args.delete_old else ""))
    if orphaned and not args.dry_run:
        print("⚠️ 고아 객체(매핑 없는 project_id)는 손대지 않음 — 수동 확인 필요")
    return 0


if __name__ == "__main__":
    sys.exit(main())
