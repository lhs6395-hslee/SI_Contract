#!/usr/bin/env python3
"""DynamoDB 고아 레코드 삭제 — 특수문자 ID로 생성되어 API로 삭제 불가한 레코드 정리.

QA 테스트 중 ID 유효성 검사 부재로 생성된 레코드 2건을 직접 삭제한다.
(현재는 main.py의 PROJECT_ID_RE 검증으로 재발 방지됨)

사용법:
    python3 scripts/cleanup_orphan_records.py            # dry-run (조회만)
    python3 scripts/cleanup_orphan_records.py --delete   # 실제 삭제
"""

import os
import sys

import boto3

TABLE_NAME = os.getenv("DYNAMODB_TABLE", "si-contract-dev-projects")
REGION = os.getenv("AWS_REGION", "ap-northeast-2")

ORPHAN_IDS = [
    "../../etc/passwd",
    "<script>alert(1)</script>",
    "qa-special-<script>alert(1)</script>",
    "<script>x</script>",
]


def main():
    do_delete = "--delete" in sys.argv
    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)

    for project_id in ORPHAN_IDS:
        resp = table.get_item(Key={"project_id": project_id})
        item = resp.get("Item")
        if not item:
            print(f"[skip] 존재하지 않음: {project_id!r}")
            continue

        if do_delete:
            table.delete_item(Key={"project_id": project_id})
            print(f"[deleted] {project_id!r}")
        else:
            print(f"[found] {project_id!r} (name={item.get('name')!r}) — 삭제하려면 --delete 옵션 사용")


if __name__ == "__main__":
    main()
