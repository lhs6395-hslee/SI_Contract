# SI Contract — AWS Infrastructure (Terraform + EKS)

## Architecture

```
사용자 → Route53 → CloudFront → ALB (Ingress) → EKS Fargate
                                                   ├── Frontend (Next.js 16, port 3000)
                                                   └── Backend (FastAPI, port 8001)
                                                        ├── S3 (파일 저장)
                                                        ├── DynamoDB (파이프라인 상태)
                                                        └── Aurora Serverless v2 (프로젝트/사용자)
```

## Directory Structure

```
infrastructure/
├── global/              # 1회 부트스트랩 (tfstate, ECR)
├── modules/             # 재사용 가능 Terraform 모듈
├── environments/        # 환경별 구성 (dev, prod)
├── k8s/                 # Kubernetes 매니페스트
└── docker/              # Dockerfiles
```

## Deployment Order

```bash
# 1. Bootstrap (1회)
cd global/tfstate-backend && terraform init && terraform apply
cd global/ecr && terraform init && terraform apply

# 2. Docker build & push
docker build -f docker/frontend/Dockerfile -t <ecr-url>/frontend:latest .
docker build -f docker/backend/Dockerfile -t <ecr-url>/backend:latest .
docker push <ecr-url>/frontend:latest
docker push <ecr-url>/backend:latest

# 3. Infrastructure
cd environments/dev && terraform init && terraform apply

# 4. K8s deploy
aws eks update-kubeconfig --name si-contract-dev --region ap-northeast-2
kubectl apply -f k8s/
```

## Cost Estimate (Monthly, ap-northeast-2)

| Component | Cost |
|-----------|------|
| EKS Cluster | ~$73 |
| Fargate (2 pods) | ~$15 |
| ALB | ~$16 |
| NAT Gateway (1x) | ~$34 |
| Aurora Serverless v2 | ~$43 |
| S3 + DynamoDB + Secrets | ~$2 |
| CloudWatch + Route53 | ~$2 |
| **Total** | **~$185/month** |
