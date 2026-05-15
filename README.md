# SI 집행계획서 자동화

GS네오텍 SI/MSP 사업의 집행계획서를 AI 기반으로 자동 생성하는 시스템.

계약서·견적서 등 소스 문서를 업로드하면 Claude가 자동 분류 → 필드 추출 → 교차 검증 → 엑셀 집행계획서 생성까지 처리한다.

## 서비스 URL

| 서비스 | URL |
|--------|-----|
| Frontend | https://si.rayhli.com |
| Backend API | https://si-api.rayhli.com |
| API 문서 | https://si-api.rayhli.com/docs |

## 아키텍처

```
[사용자] → ALB (HTTPS) → EKS Fargate
                            ├── Frontend Pod (Next.js 16)
                            └── Backend Pod (FastAPI)
                                  ├── DynamoDB (프로젝트 데이터)
                                  ├── S3 (파일 저장 + 엑셀 결과)
                                  └── Bedrock Claude Sonnet (AI)
```

## 프로젝트 구조

```
SI_ Contract/
├── frontend/           # Next.js 16 + shadcn/ui
├── backend/            # FastAPI (파이프라인/AI/엑셀)
├── infrastructure/     # Terraform + K8s manifests + Dockerfile
├── templates/          # 집행계획서 엑셀 템플릿
├── specs/              # AI 에이전트 엔지니어링 스펙
├── scripts/            # 배포 스크립트
├── .kiro/              # Kiro spec 문서
├── CLAUDE.md           # AI 에이전트 규칙
└── AGENTS.md           # 멀티 에이전트 파이프라인 정의
```

## 인프라 구성

| 리소스 | 서비스 | 용도 |
|--------|--------|------|
| Compute | EKS Fargate (ap-northeast-2) | 컨테이너 실행 |
| Storage | S3 (si-contract-dev-files) | 문서 파일 + 엑셀 결과 |
| Database | DynamoDB (si-contract-dev-projects) | 프로젝트 데이터 |
| Database | DynamoDB (si-contract-dev-pipeline-state) | 파이프라인 상태 (TTL 30일) |
| AI | Bedrock Claude Sonnet 4 (us-east-1) | 문서 분류/추출/검증/챗봇 |
| Auth | Cognito User Pool | Google OAuth (gsneotek.com 제한) |
| Network | ALB + ACM | HTTPS 종단, 도메인 라우팅 |
| DNS | Route 53 | si.rayhli.com, si-api.rayhli.com |

## 보안

- HTTPS only (ALB SSL redirect)
- Security Headers (HSTS, X-Frame-Options, CSP 등)
- CORS 도메인 제한 (si.rayhli.com만 허용)
- Rate Limiting (AI 엔드포인트 분당 30회)
- NetworkPolicy (Pod 간 통신 제한)
- Path Traversal 방지
- S3 Public Access 완전 차단 + AES256 암호화 + 버전닝
- DynamoDB PITR (Point-in-time Recovery) 활성화
- IAM 최소 권한 (IRSA — Pod별 역할 분리)
- 편집 잠금 (다중 사용자 동시 수정 방지)

## 인증

| 방식 | 대상 | 설명 |
|------|------|------|
| Google OAuth (Cognito) | 일반 사용자 | gsneotek.com 도메인만 허용 |
| Basic Auth | 관리자 | admin / (env: ADMIN_PASSWORD) |

## 핵심 기능

- **AI 문서 분류** — 계약서/견적서/공문 자동 분류
- **AI 필드 추출** — 사업명, 금액, 기간 등 자동 추출
- **교차 검증** — 견적서 간 단가 불일치 감지
- **멀티 에이전트 파이프라인** — Executor → Reviewer (독립 검증)
- **엑셀 집행계획서 생성** — 템플릿 기반 14개 시트 자동 기록
- **Revision 관리** — 차수별 데이터 분리 저장/전환
- **변경 이력** — 차수별 변경점 요약 + 금액/요율 추이
- **AI 챗봇** — 프로젝트 데이터 기반 질의응답 (Sonnet)
- **실시간 자동 저장** — DynamoDB에 디바운스 저장

## 배포

```bash
# 전체 빌드+배포
./scripts/deploy.sh all

# 프론트엔드만
./scripts/deploy.sh frontend

# 백엔드만
./scripts/deploy.sh backend
```

## 로컬 개발

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload

# Frontend
cd frontend
npm install
npm run dev
```

## 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, Python 3.11, Uvicorn |
| AI | AWS Bedrock Claude Sonnet 4 |
| Infra | EKS Fargate, ALB, S3, DynamoDB, Cognito |
| IaC | Terraform |
| Container | Docker (multi-stage build) |
| CI/CD | 수동 배포 (scripts/deploy.sh) → 추후 GitHub Actions |
