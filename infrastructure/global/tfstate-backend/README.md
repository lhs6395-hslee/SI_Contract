# Terraform State Backend

Terraform remote state를 저장하기 위한 S3 버킷을 프로비저닝합니다.

> S3 native locking (`use_lockfile = true`)을 사용하므로 DynamoDB 테이블은 불필요합니다.

## 사용법

```bash
cd infrastructure/global/tfstate-backend
terraform init
terraform apply
```

이 모듈은 **다른 모든 인프라보다 먼저 1회 실행**해야 합니다.

## 생성 리소스

| 리소스 | 설명 |
|--------|------|
| `aws_s3_bucket` | Terraform state 저장 |
| `aws_s3_bucket_versioning` | State 버전 관리 (실수 복구) |
| `aws_s3_bucket_server_side_encryption_configuration` | AES256 암호화 |
| `aws_s3_bucket_public_access_block` | 퍼블릭 접근 완전 차단 |
