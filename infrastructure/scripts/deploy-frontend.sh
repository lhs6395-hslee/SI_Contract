#!/bin/bash
set -e
REGION=ap-northeast-2
ACCOUNT_ID=264594923212
REPO=${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/si-contract/frontend
TAG=${1:-latest}

cd "$(git rev-parse --show-toplevel)"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
docker buildx build --platform linux/amd64 -t ${REPO}:${TAG} -f infrastructure/docker/frontend/Dockerfile --push .
kubectl set image deployment/frontend frontend=${REPO}:${TAG} -n si-contract
kubectl rollout status deployment/frontend -n si-contract --timeout=180s
echo "✓ Frontend deployed: ${TAG}"
