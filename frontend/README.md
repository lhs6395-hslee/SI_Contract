# SI 집행계획서 — Frontend

Next.js 16 App Router 기반 프론트엔드.

## 배포 환경

- **URL**: https://si.rayhli.com
- **런타임**: EKS Fargate (Node.js 20 Alpine)
- **AI**: AWS Bedrock Claude Sonnet 4 (Next.js API Route에서 호출)

## 주요 페이지

| 경로 | 설명 |
|------|------|
| `/login` | 로그인 (Google OAuth + Basic Auth) |
| `/` | 메인 (리뷰/업로드/익스포트/설정) |

## 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `NEXT_PUBLIC_FASTAPI_URL` | 백엔드 API URL | `http://localhost:8000` |
| `CLAUDE_PROVIDER` | AI 제공자 | `bedrock` |
| `CLAUDE_MODEL` | 모델 ID | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| `AWS_REGION` | Bedrock 리전 | `us-east-1` |

## 로컬 개발

```bash
npm install
npm run dev
```

## 빌드

```bash
npm run build
```

## Docker

```bash
docker buildx build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_FASTAPI_URL=https://si-api.rayhli.com \
  -f infrastructure/docker/frontend/Dockerfile \
  -t si-contract/frontend:latest .
```
