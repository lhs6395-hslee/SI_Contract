# 배포 핸드오프 — 검증 세션용 (2026-06-12)

> 이 문서는 **개발 세션 → 검증 세션** 핸드오프다. 검증 세션은 이걸 읽고
> `bash .pipeline/tests/run_all_suites.sh` 기준으로 회귀 확인 + 실사례/극단 테스트를 수행한다.

## 합격 기준 (가장 중요 — 실사용자 관점)

검증의 목표는 **"만든 기능이 스펙대로 도나"가 아니다.** 실제로 이 솔루션을 쓰는 사람이
실사례 시나리오를 **처음부터 끝까지** 거쳤을 때:

- **결과물(집행계획서 Excel)이 result 파일과 동일하게 나오는가**
- 수식 / 차수 로직 / 빌더 로직 때문에 **깨지거나, 누락되거나, 값이 틀리지 않는가**

→ 이게 합격 기준. 엔드포인트 200·단위테스트 green은 근거로 불충분.
(참조: 메모리 `test-philosophy-real-user`, `verify-session-split`)

### 실사례 골든 비교
| 시나리오 | 입력 문서 | 기대 산출물(result) |
|---|---|---|
| 퀘이사존 | `senario/퀘이사존/` (견적품의서/검토서/계약서/견적서) | `senario/퀘이사존/result/1. (최초) 집행계획서_퀘이사존 운영_v0.3.xlsx` |
| EPS | `senario/EPS/` (견적품의서/검토서/견적서/signed) | `senario/EPS/result/(최초)집행계획서_26년_GS EPS 3차 Migration 프로젝트(초안).xlsx` |

업로드 → 분류 → 추출(기본+산출내역/인원/공정/요율/조직) → 리뷰 → **export** →
나온 Excel을 result와 셀 단위 비교. 차수 1→2→3 수정집행도 실제로 추가하며 탭/수식 확인.

### 극단 테스트 (깨뜨리기)
- 사업명에 SQL injection / path traversal / XSS
- **스캔(이미지) PDF** (EPS 검토서 = 스캔본), 빈 파일, 초대형/깨진 파일
- 12차 초과 수정 시도, 빈 문서로 추출/export
- → 깨지거나 빈 결과면 fail

## 배포된 빌드 (이걸 테스트)
- backend: `264594923212.dkr.ecr.ap-northeast-2.amazonaws.com/si-contract/backend:v202606121055`
- frontend: `...frontend:v202606121014`
- 클러스터: EKS `si-contract-dev` (ap-northeast-2), https://si.rayhli.com / https://si-api.rayhli.com
- 로그인: basic(admin/admin) 또는 Google OAuth. 토큰 TTL 8h.

## 이번 작업 커밋 범위 `d56fd2c..894eca2`
- `0408dae` 프론트 프록시/chat 인증 헤더 전달 (chat·classify 401 해소)
- `64670d6` STS/Bedrock VPC 인터페이스 엔드포인트 + ALB 서비스별 헬스체크
- `78739e8` Bedrock 연결·모델 티어링(chat→haiku)·인증 폴백
- `bba273f` 세션 만료 UX (401 자동 재로그인 + 토큰 TTL 8h)
- `69ae8bc` deploy.sh 프론트 AWS_REGION 교정
- `fe36c1b` **탭별 추출 5종 구현** (extract-costs/people/schedule/rates/org)
- `962f266` **스캔 PDF Vision 추출 연결**
- `894eca2` Vision max_tokens 1024→2048 (JSON 잘림 방지)

## 알려진 fail 기준선(2026-06-12) → 해소 매핑 (회귀 확인 포인트)
| 기준선 fail | 조치 | 검증 세션이 확인할 것 |
|---|---|---|
| 라우트계약 5건 (extract-* 미구현) | ✅ 구현+배포 | 계약 테스트 5건 ✓ 전환 |
| UI골든 산출내역 ✗ | ✅ granular 추출 연결 | 산출내역 골든 ✓ / export 산출내역서 시트 채워짐 |
| EPS 품의서 스캔 PDF Vision 미연결 | ✅ Vision 구현+배포 | EPS 검토서(스캔) 추출 → 집행계획서 값 정상 |

## 개발 세션이 라이브 실측한 것 (참고용 — 종합 판정은 검증 세션 몫)
- chat/classify/projects: 실제 로그인 토큰으로 200, Bedrock haiku 호출 확인
- granular 5종: 라이브 200, 실 PDF로 섹션 데이터 채움
- Vision: 라이브에서 EPS 스캔 검토서 → projectName/client/revenue/기간 정상 추출

## 미해결/한계 (검증 시 인지)
- **export 골든 일치(셀 단위)는 개발 세션에서 미검증** — 검증 세션의 핵심 과제
- ai-service(MSA, USE_AI_SERVICE=true) 경로는 granular/Vision 미반영 — 현재 모놀리스(false)만 검증 대상
- classify는 텍스트 기반 (스캔 PDF는 분류 부정확 가능, UI 드롭다운 수동 지정으로 우회)
