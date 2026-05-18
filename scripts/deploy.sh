#!/bin/bash
# SI Contract 빌드+배포 스크립트
# 사용법: ./scripts/deploy.sh [frontend|backend|all]

set -e

REGION="ap-northeast-2"
ACCOUNT="264594923212"
REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
NAMESPACE="si-contract"
CACHE_DIR="/tmp/si-contract-buildcache"

# ECR 로그인
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REGISTRY 2>/dev/null

# 버전 자동 생성 (타임스탬프 기반)
VERSION="v$(date +%Y%m%d%H%M)"

build_frontend() {
  echo "🔨 Frontend 빌드 ($VERSION)..."
  cp .dockerignore.frontend .dockerignore
  docker build --platform linux/amd64 \
    --build-arg NEXT_PUBLIC_FASTAPI_URL=https://si-api.rayhli.com \
    -f infrastructure/docker/frontend/Dockerfile \
    -t ${REGISTRY}/si-contract/frontend:${VERSION} \
    . || { cp .dockerignore.backend .dockerignore; echo "❌ Frontend 빌드 실패"; exit 1; }
  cp .dockerignore.backend .dockerignore
  docker push ${REGISTRY}/si-contract/frontend:${VERSION} || { echo "❌ Frontend ECR push 실패"; exit 1; }
  echo "✅ Frontend ${VERSION} pushed"
}

build_backend() {
  echo "🔨 Backend 빌드 ($VERSION)..."
  cp .dockerignore.backend .dockerignore
  docker build --platform linux/amd64 \
    -f infrastructure/docker/backend/Dockerfile \
    -t ${REGISTRY}/si-contract/backend:${VERSION} \
    . || { echo "❌ Backend 빌드 실패"; exit 1; }
  docker push ${REGISTRY}/si-contract/backend:${VERSION} || { echo "❌ Backend ECR push 실패"; exit 1; }
  echo "✅ Backend ${VERSION} pushed"
}

deploy_frontend() {
  kubectl set image deployment/frontend frontend=${REGISTRY}/si-contract/frontend:${VERSION} -n $NAMESPACE
  kubectl set env deployment/frontend AWS_REGION=us-east-1 -n $NAMESPACE
  echo "🚀 Frontend ${VERSION} 배포됨"
}

deploy_backend() {
  kubectl set image deployment/backend backend=${REGISTRY}/si-contract/backend:${VERSION} -n $NAMESPACE
  echo "🚀 Backend ${VERSION} 배포됨"
}

wait_ready() {
  local app=$1
  echo "⏳ ${app} Pod 준비 대기..."
  kubectl rollout status deployment/${app} -n $NAMESPACE --timeout=180s 2>/dev/null || true
  echo "✅ ${app} Ready"
}

case "${1:-all}" in
  frontend)
    build_frontend && deploy_frontend && wait_ready frontend
    ;;
  backend)
    build_backend && deploy_backend && wait_ready backend
    ;;
  all)
    build_frontend & FE_PID=$!
    build_backend  & BE_PID=$!
    wait $FE_PID || { echo "❌ Frontend 빌드 실패 — 배포 중단"; kill $BE_PID 2>/dev/null; exit 1; }
    wait $BE_PID || { echo "❌ Backend 빌드 실패 — 배포 중단"; exit 1; }
    deploy_frontend
    deploy_backend
    wait_ready frontend
    wait_ready backend
    ;;
  *)
    echo "Usage: $0 [frontend|backend|all]"
    exit 1
    ;;
esac

echo ""
echo "📋 배포 완료 — 버전: ${VERSION}"
kubectl get pods -n $NAMESPACE --no-headers
