# 배포 핸드오프 — 검증 세션용 (2026-06-12, 갱신)

> 개발 세션 → 검증 세션 핸드오프. 검증 세션은 이걸 읽고 실사례/극단 테스트로 재채점한다.

## 합격 기준 (실사용자 관점 — 변함없음)

목표는 "만든 기능이 스펙대로 도나"가 아니다. **실제 사용자가 실사례 시나리오를 처음부터
끝까지 거쳤을 때 result 파일과 동일한 집행계획서가 나오는가**(수식/차수/빌더 로직으로
깨지거나 누락·오류 없이). 엔드포인트 200·단위테스트·**픽스처 주입** green은 근거 불충분.
(참조: `test-philosophy-real-user`, `verify-session-split`)

⚠️ **픽스처/정답 주입 금지**: costItems/staffPlan/quoteLabor를 손으로 박거나, senario
폴더의 result 템플릿(`(최초)집행계획서…xlsx`)을 업로드 소스에 포함하면 정답이 새어
"통과"가 거짓이 된다. 인수 테스트는 **소스 문서만** 업로드 → AI 추출 경로로만 채점.

### 실사례 골든 비교 (실제 업로드 경로)
| 시나리오 | 업로드할 소스 (result 템플릿 제외) | 기대 산출물 |
|---|---|---|
| 퀘이사존(외주) | 견적품의서/표준계약검토서/레이어에잇 견적/부속계약서 | `senario/퀘이사존/result/…v0.3.xlsx` |
| EPS(자사인력) | **견적서(xlsx)**/견적품의서/표준검토서/signed | `senario/EPS/result/…(초안).xlsx` |

⚠️ **문서 세트 의존성**: EPS 견적 원가분해(노무비/경비/영업이익)는 **견적서 xlsx**에 있다.
견적품의서 PDF만 올리고 견적서를 빠뜨리면 노무비/경비가 부정확. 인수 케이스에 필수 소스
세트를 명시할 것.

### 극단 테스트 (단일 세트로 통합 권장)
- 보안/파일: SQL injection·path traversal·XSS 사업명, 빈/대형/깨진 파일, parse 500 케이스
- **극단 시나리오**: 명절상여·장기계약·연도경계 배분 (보안과 분리하지 말고 한 세트로)

## 배포된 빌드 (이걸로 재채점)
- backend: `…/si-contract/backend:v202606121150`
- frontend: `…/si-contract/frontend:v202606121146`
- 클러스터: EKS `si-contract-dev` (ap-northeast-2), https://si.rayhli.com / https://si-api.rayhli.com
- 로그인: basic(admin/admin) 또는 Google OAuth. 토큰 TTL 8h.

## 이번 작업 커밋 범위 `d56fd2c..97eaba5`
주요: 인증헤더 전달(0408dae)/STS·Bedrock VPC엔드포인트(64670d6)/모델티어링·인증폴백(78739e8)/
세션UX(bba273f)/탭별추출5종(fe36c1b)/스캔PDF Vision(962f266,894eca2)/**extract-costs category
정렬(65d7686)**/DynamoDB·S3 싱글톤 perf(971c62a)/metrics-server IaC(ca1bea2)/**프로젝트명
단일화(a168023,38aa12f)**/**EPS 견적품의 원가분해(97eaba5)**.

## 알려진 fail 기준선(2026-06-12) → 해소 매핑 (회귀 확인 포인트)
| 기준선 fail | 진짜 원인 (재진단) | 조치 | 라이브 검증 |
|---|---|---|---|
| 퀘이사존 5-4 수수료 빈값 (task_ddc92a1d) | extract-costs가 category="expense" 반환 → 빌더 fee 폐기 | COSTS_PROMPT 빌더 어휘 정렬 + 정규화 | ✅ 실문서 → `fee` 수수료 72,000천 |
| EPS 갑지 노무비=0·영업이익=0·경비 오배분 (task_84df2e99) | **별개 원인** — base extract가 quoteLabor/quoteOutsourcing/profit 미추출, cost가 총원가 | EXTRACT_PROMPT에 견적품의 6분류+profit 추가, cost=경비만 | ✅ 소스세트 → 노무비33,583/경비8,723/영업이익56,494천 |
| 라우트계약 5건 (extract-* 미구현) | 백엔드 핸들러 부재 | granular 5종 구현 | ✅ 라이브 200 |
| UI골든 산출내역 ✗ | granular 추출 미연결 + 위 2건 | 상동 | 재채점 대상 |
| 프로젝트명 UI 플로우 유실 (task_6613ffda) | 차수 저장본에 projectName 미보존 → 재로딩 유실 | ProjectData.name 단일출처 복원 | 프론트 배포됨, UI골든 재확인 |
| EPS 품의서 스캔 PDF Vision 미연결 | 이미지 PDF가 텍스트 추출 불가 | Vision 멀티모달 연결 | ✅ 스캔 검토서 추출 성공 |

## 개발 세션 라이브 실측 (종합 판정은 검증 세션)
- 퀘이사존 extract-costs → fee 72,000천 / EPS base → 노무비·경비·영업이익 result 일치 (소스 문서만, 정답 누출 없이)
- chat/classify/projects 200, granular 5종 200, Vision 스캔 PDF 추출, kubectl top (metrics-server)

## 미해결/주의
- **상여 산식 장기 과대계상** = 비즈니스 확인 건 (계산 정확성과 별개)
- 극단 17/19 — parse 500 버그 잔존 (검증 세션 확인)
- ai-service(MSA, USE_AI_SERVICE=true) 경로엔 granular/Vision/견적분해 미반영 — 현재 모놀리스(false)만 대상
- classify는 텍스트 기반 (스캔 PDF 분류 부정확 가능, UI 드롭다운 수동 지정 우회)
- export 셀 단위 골든 일치는 검증 세션의 핵심 재채점 과제
