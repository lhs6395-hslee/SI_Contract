# SI 집행계획서 자동화

GS네오텍 SI/MSP 사업의 집행계획서를 AI 기반으로 자동 생성하는 시스템.

계약서·견적서 등 소스 문서를 업로드하면 Claude가 자동 분류 → 필드 추출 → 교차 검증 → 엑셀 집행계획서 생성까지 처리한다.

## 프로젝트 구조

```
SI_ Contract/
├── front/            # Next.js 16 + shadcn/ui (UI)
├── backend/          # FastAPI (API 서버)
├── templates/        # 집행계획서 엑셀 템플릿
├── specs/            # 기술 스펙 문서
├── scripts/          # 자동화 스크립트
├── CLAUDE.md         # AI 에이전트 규칙
├── AGENTS.md         # 에이전트 역할 정의
└── PROJECT.md        # 프로젝트 요구사항
```

## 요구사항

- **Python** 3.12+
- **Node.js** 20+
- **Anthropic API Key** (Claude API 사용)

## 설치 및 실행

### 1. Backend

```bash
cd backend

# 가상환경 생성 및 의존성 설치
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 열어 ANTHROPIC_API_KEY 입력

# 서버 실행
./venv/bin/python3 -m uvicorn main:app --port 8000 --reload
```

### 2. Frontend

```bash
cd front

# 의존성 설치
npm install

# 환경변수 (기본값 사용 시 생략 가능)
# .env.local 에 NEXT_PUBLIC_API_URL=http://localhost:8000

# 개발 서버 실행
npm run dev
```

### 3. 접속

| 서비스 | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API 문서 (Swagger) | http://localhost:8000/docs |

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/health` | 서버 상태 및 API 키 확인 |
| POST | `/api/upload` | 파일 업로드 (임시 저장) |
| POST | `/api/classify` | 문서 종류 AI 분류 (계약서/견적서/공문 등) |
| POST | `/api/extract` | 여러 파일에서 집행계획서 필드 AI 추출 |
| POST | `/api/validate` | 추출 데이터 교차 검증 (충돌 감지) |
| POST | `/api/export` | 엑셀 집행계획서 생성 및 다운로드 |

## 사용 흐름

1. **프로젝트 생성** — 프로젝트명 입력
2. **문서 업로드** — 계약서, 견적서, 견적품의서, 보험료율 공문 등을 드래그&드롭
3. **AI 자동 분류** — 업로드된 문서를 Claude가 카테고리별로 분류
4. **필드 추출** — 사업명, 발주처, 계약금액, 기간 등 12개 항목 자동 추출
5. **리뷰 및 수정** — 추출 결과 확인, 추측 값 검토, 수동 수정
6. **충돌 해결** — 견적서 간 단가 불일치 등 검증 이슈 해결
7. **엑셀 익스포트** — 템플릿 기반 집행계획서 xlsx 다운로드

## 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, Python 3.14, Uvicorn |
| AI | Claude API (anthropic SDK) |
| 파일 처리 | PyMuPDF (PDF), python-docx (DOCX), openpyxl (XLSX) |
| 엑셀 생성 | openpyxl (템플릿 기반 값 삽입) |
