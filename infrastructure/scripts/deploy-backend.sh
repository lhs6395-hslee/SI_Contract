#!/bin/bash
set -e
REGION=ap-northeast-2
ACCOUNT_ID=264594923212
REPO=${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/si-contract/backend
TAG=${1:-latest}

cd "$(git rev-parse --show-toplevel)"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
docker buildx build --platform linux/amd64 -t ${REPO}:${TAG} -f infrastructure/docker/backend/Dockerfile --push .
kubectl set image deployment/backend backend=${REPO}:${TAG} -n si-contract
kubectl rollout status deployment/backend -n si-contract --timeout=180s
echo "✓ Backend deployed: ${TAG}"
