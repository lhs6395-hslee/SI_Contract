# 집행서 SDD — [NEEDS CLARIFICATION] 집계 (사용자 직접 확정 목록)

> 생성: 2026-06-26 · 17기능 spec.md의 `[NEEDS CLARIFICATION]` 자동 집계.
> **사용자가 사내 기준(사규·공문·단가표 등)으로 직접 확정**한다. 값 미창작: 미확정은 채우지 않고 표면화만 한다.

## 최우선 — 설계 §6-1 강제 충돌 6건 (출처 2개+ 충돌, 사용자 확정 필요)

1. **직급 단가표 3중 충돌** — company_standards.py:16(과장550만) / executor.md:101(600만) / REPORT_eps_values.md:144(650만). 귀속: EXE-03, EXE-09
2. **상여금 공식 충돌** — executor.md:109(1M/M 전액) / contract_builder.py:540(rate×months/9) / REPORT_eps_values.md:155((3/9)×단가). 귀속: EXE-09
3. **보험 요율 이원화** — 집행 4.75/4.0674/0.796% vs 정산 4.5/4.0041/0.766% (REPORT_eps_values.md:174-180). 적용 기준연도·갱신정책 미정. 귀속: EXE-03, EXE-08
4. **간접비율·일반관리비율 문서 근거** — company_standards.py 주석('윤지민과장 25년 기준')만, 공문 경로 없음. 귀속: EXE-03, EXE-08
5. **수수료 코드 1/2/3 판단 기준** — planner.md '[추측] 가능'으로만, 정량 기준 없음. 귀속: EXE-01, EXE-07
6. **하도급노무비율 수치** — executor.md:153 공식엔 등장하나 % 미명시. 귀속: EXE-08, EXE-09

## 기능별 전체 [NEEDS CLARIFICATION] 목록

### EXE-01 (5)
- SC-003**: `category: "unknown"` + `confidence < 0.5` 인 경우 프론트엔드 폴백 적용 후 `category` 값이 `"unknown"` 이외의 값으로 갱신되는 비율 — [NEEDS CLARIFICATION: 파일명에 키워드가 없는 경우 폴백도 "unknown"을 반환할 수 있음. 목표 커버리지 수치 미정].
- SC-005**: AI 호출 실패 시 폴백 분류 결과 반환까지 소요 시간 ≤ [NEEDS CLARIFICATION: 타임아웃 상한 미명시. `ai_core.py`의 Bedrock `read_timeout=60` (`ai_core.py:26`) 이후 fallback 반환].
- 1. **[NEEDS CLARIFICATION] 신뢰도 임계값 결정 근거**: `upload-page.tsx:185`의 `confidence < 0.5` 임계값은 코드에서 임의로 설정된 것으로 보이며, 설계 문서·운영 정책 내 수치 근거 없음. 사용자가 사내 기준으로 직접 확정 필요.
- 2. **[NEEDS CLARIFICATION] 6종 taxonomy 공식 운영 정의**: 현재 6종(`contract/internal/vendor/insurance/execution_plan/unknown`) 정의는 AI 프롬프트 내 자연어 설명만 존재 (`ai_core.py:184-192`). 기획서·공식 운영 정책 문서의 별도 정의 여부 미확인.
- 3. **[NEEDS CLARIFICATION] 분류 정확도 SC 목표 수치**: SC-003의 폴백 커버리지, SC-005의 타임아웃 상한이 미정. 베이스라인 측정 후 목표 수치 결정 필요.

### EXE-02 (5)
- 단일 출처 값만 인용; 출처 없음 또는 충돌 시 `[NEEDS CLARIFICATION]`.
- SC-005**: 추출 정확도(검증 사례셋 대비 필드 정확 일치율) 목표 — `[NEEDS CLARIFICATION: 베이스라인 측정 후 목표 수치 확정. 현재 단일 출처 없음.]`
- SC-006**: `/api/extract-costs` 응답 시간(P95) — `[NEEDS CLARIFICATION: 부하 테스트 기준선 미정.]`
- 클라이언트 파일 크기 제한**: `_check_upload_size` 적용 (`main.py:550`). 제한 수치는 `[NEEDS CLARIFICATION: main.py의 상한값 직접 확인 필요 — 이 spec 작성 범위에서 해당 라인 미읽음]`.
- 이 기능에 `[NEEDS CLARIFICATION]` 강제 항목(설계 §6-1)은 없다. 추출 동작은 코드로 확정됨.

### EXE-03 (2)
- staffPlan 인원의 grade가 GRADE_RATES 테이블에 없는 경우(예: "수석") → `[NEEDS CLARIFICATION: GRADE_RATES 미정의 직급에 대한 fallback 처리 정책]`
- EXE-03에 귀속되는 강제 `[NEEDS CLARIFICATION]` 항목 (설계서 §6-1). SC-05~08이 이 항목들에 귀속되며, 각 NC 해소 후 해당 SC를 추가한다.

### EXE-04 (2)
- SC-003**: revision 변경 후 `confirmedTabs` React state가 `extractedData.confirmedTabs` 기준으로 재동기화되는 지연 = `useEffect` 1 render cycle 이내(브라우저 환경 기준 `[NEEDS CLARIFICATION: 목표 지연 ms 수치 — 현재 useEffect 동기화이므로 render cycle 수로만 측정 가능]`).
- SC-006**: `[NEEDS CLARIFICATION: 탭 배지 색상 대비 기준(WCAG 수치) 미명시 — 디자인 시스템 기준 확인 전까지 측정형 SC로 등재 불가. Clarifications Retained 항목으로 관리하며 수치 확정 후 SC로 승격한다]`

### EXE-05 (5)
- 견적서 내 동일 품명 중복(유형 C): `[NEEDS CLARIFICATION: 유형 C는 cross_validate 프롬프트(ai_core.py:509-519)의 "mismatch|missing|warning" 분류로 커버되는지, 별도 프론트 처리가 있는지 확인 필요]`
- `[NEEDS CLARIFICATION: 익스포트 차단의 정확한 구현 위치 — review-page.tsx에서 export 버튼의 disabled 조건을 코드로 재확인 필요]`
- SC-001**: `/api/validate` 응답 시간이 `[NEEDS CLARIFICATION: 목표 응답 시간 미정. Bedrock 호출 포함 시 P95 기준 수립 필요]` 이하.
- SC-002**: 유형 A/A'/B/C/D 각각에 대한 검증 사례셋 테스트 케이스에서 **감지율 100%** (0건 누락 FAIL). 검증 사례셋 건수: `[NEEDS CLARIFICATION: 검증 사례셋 정의 미완]`.
- SC-004**: 충돌이 1건 이상인 상태에서 익스포트를 시도하는 경우 차단 성공률 **100%** (프론트엔드 UI 게이트 기준). `[NEEDS CLARIFICATION: 익스포트 버튼 disabled 조건의 정확한 구현 위치(review-page.tsx 해당 라인) 확인 후 측정 기준 및 테스트 추가 필요]`

### EXE-06 (14)
- `[NEEDS CLARIFICATION: revision > MAX_REVISION 시 main.py:729 HTTP 400과 contract_builder.py:307 ValueError 두 곳에서 각각 차단하는데, 어느 쪽이 단일 진입점(canonical gate)으로 확정되어야 하는가?]`
- SC-001**: `build_sprint_contract` 호출 후 SprintContract 생성 소요 시간이 AI 호출 없음을 전제로 **1초 이내**여야 한다. (결정론 함수이므로 LLM 지연 없음. 절대 상한 `[NEEDS CLARIFICATION: 실측 베이스라인 후 확정]`)
- 4. **GRADE_RATES(잠정)**: 과장 550만은 Clarifications Retained 항목 1에서 3중 충돌로 `[NEEDS CLARIFICATION]` 지정됨. 나머지 4개 직급도 동일 출처 쌍(company_standards.py vs executor.md) 간 2-way 충돌이 확인되므로 모두 `[NEEDS CLARIFICATION]` 대상이다.
- 부장: company_standards.py=750만 vs executor.md=800만 `[NEEDS CLARIFICATION]`
- 차장: company_standards.py=650만 vs executor.md=700만 `[NEEDS CLARIFICATION]`
- 대리: company_standards.py=450만 vs executor.md=500만 / REPORT=550만 `[NEEDS CLARIFICATION]`
- 사원: company_standards.py=350만 vs executor.md=450만 `[NEEDS CLARIFICATION]`
- 5. **DEFAULT_RATES(잠정)**: 간접 1.9%/관리 3.0%/국민연금 4.5%(집행기준 4.75%와 충돌)/건강보험 4.0041%(집행기준 4.0674%와 충돌)/산재 0.766%(집행기준 0.796%와 충돌)/고용보험 1.75%. (`company_standards.py:27-34` [`공식 코드`]) — 현행값은 정산 기준 추정이나 집행 기준과 충돌. Clarifications Retained 항목 4 참조 `[NEEDS CLARIFICATION]`. "윤지민과장 문의 25년 기준" 주석 근거, 공문 경로 미확정.
- 아래 항목은 설계 §6-1(강제 `[NEEDS CLARIFICATION]`)에서 이월한 미해결 충돌로, 사용자가 사내 기준으로 직접 확정 전까지 임의값 생성 금지.
- 1. **직급 단가표 2중 이상 충돌 (전 직급)** `[NEEDS CLARIFICATION]`
- 근거: "윤지민과장 25년 기준" 주석만, 공문 경로/문서 없음 → `[NEEDS CLARIFICATION]`
- DEFAULT_RATES의 현행 코드값이 어느 기준연도인지, 갱신 정책이 없음 → `[NEEDS CLARIFICATION]`
- 5. **상여금 산출 공식 충돌** `[NEEDS CLARIFICATION]`
- `contract_builder.py:512-559`(build_sprint_contract 내 상여 자동산출)가 실행되나, EXE-06 Functional Requirements에 상여 산출 FR이 없음. EXE-09 스펙과 함께 재정렬이 필요하며, 공식 확정 전까지 임의 구현 금지. (설계 §6-1 강제 `[NEEDS CLARIFICATION]` 이월)

### EXE-07 (5)
- 값을 모르면 임의로 정하지 않고 `[NEEDS CLARIFICATION: 무엇을 확인해야 하나]`.
- [NEEDS CLARIFICATION] NC-01: 수수료 코드 1/2/3 정량 판단 기준
- [NEEDS CLARIFICATION] NC-02: 수수료 시트 DATA_START_ROW/DATA_END_ROW 런타임 값
- [NEEDS CLARIFICATION] NC-03: 일할계산 소수점 수량(0.1 단위) 반올림 정책
- [NEEDS CLARIFICATION] NC-04: 수정집행 당기 열 위치 (Z열 강제 입력 조건)

### EXE-08 (8)
- 값을 모르면 임의로 정하지 않고 `[NEEDS CLARIFICATION: 무엇을 확인해야 하나]`로 표시한다.
- [NEEDS CLARIFICATION: `staff_plan` 항목에 `monthly_rate`가 없을 때 `standard_rate_for(grade)`를 fallback으로 사용하는지 여부 및 해당 시 직급 단가표 어느 값을 기준으로 하는지 — 설계 §6-1 항목 1 충돌: `company_standards.py` 과장 550만 / `executor.md:101` 600만 / `REPORT_eps_values.md:144` 650만]**
- [NEEDS CLARIFICATION: staff_plan 항목에 `monthly_rate`가 없을 때 `standard_rate_for(grade)`를 fallback으로 사용하는지 여부 및 해당 시 직급 단가표 어느 값을 기준으로 하는지 — 설계 §6-1 항목 1 충돌: `company_standards.py` 과장 550만 / `executor.md:101` 600만 / `REPORT_eps_values.md:144` 650만]**
- [NEEDS CLARIFICATION: 집행 요율과 정산 요율 중 어느 기준을 우선 적용하는지, 적용 연도 기준 및 갱신 정책 — 설계 §6-1 항목 3]**
- [NEEDS CLARIFICATION: 허용 최대 입력 셀 수(비목 블록 행 수 기반 상한값) 확정 필요]**
- 1. **[NEEDS CLARIFICATION] 보험료 요율 기준**: 집행 요율(4.75%/4.0674%/0.796%/1.75%) vs. 정산 요율(4.5%/4.0041%/0.766%/1.75%)
- 2. **[NEEDS CLARIFICATION] 간접비·일반관리비 공문 근거**: 1.9%/3.0%는 코드·REPORT 일치 확인됐으나, 원칙적인 수치 확정 근거(공문/계약서)가 없음.
- 3. **[NEEDS CLARIFICATION] 안전관리비 산출 기준**: 설계 §6-2에 "안전관리비 인원×5만"이 언급되나, 이를 확인할 수 있는 코드·REPORT 출처가 이 파일에 직접 없음.

### EXE-09 (4)
- `[NEEDS CLARIFICATION]` **상여 공식 3중 충돌**:
- `[NEEDS CLARIFICATION]` 출처 A `company_standards.py:16-22` — 과장 5,500,000원
- SC-008**: 상여 공식 확정 후 — 상여 산출 결과값과 확정 공식 계산값의 오차 **0원**. [NEEDS CLARIFICATION: 공식 미확정으로 목표 수치 보류]
- 이 기능에서 해소 전까지 코드 구현을 잠정 적용하는 `[NEEDS CLARIFICATION]` 항목:

### EXE-10 (6)
- 3. **Given** cf.revenue, cf.cost, cf.profit, contract.rates 모두 존재, **When** _verify_cover_sheet()가 실행되면, **Then** 영업이익 역산(revenue - cost - overhead)과 cf.profit의 차이가 `[잠정] max(abs(revenue)×0.01, 1,000)` 이하인 경우에만 검증 통과. (`[잠정, 코드 현행값]` — `reviewer.py:478`; 권위 출처 미확정 시 `[NEEDS CLARIFICATION]`)
- `[NEEDS CLARIFICATION: revision=0 시 집계표 참조 수식이 템플릿에 내장되어 있는지, 아니면 별도 삽입 로직이 필요한지 — cover_sheet.py 코드에서 `if revision >= 1` 조건으로 0차는 템플릿 수식을 그대로 사용함이 확인되나, 템플릿 내 수식이 올바른 셀을 참조하는지는 템플릿 파일 직접 확인이 필요하다]`
- 1. **간접·일반관리비율 문서 근거** (설계 §6-1 항목 4): 영업이익 역산(FR-009) 시 사용되는 `contract.rates.indirect_rate + admin_rate`의 값이 코드에서 `company_standards.py:28-29` 기본값(간접 1.9%·관리 3.0%)으로 초기화되나, 공문 근거가 "윤지민과장 25년 기준" 주석뿐. 해당 요율의 권위 출처 미확정이므로 `[NEEDS CLARIFICATION]`.
- 2. **보험 요율 이원화** (설계 §6-1 항목 3): `contract.rates`에 포함되는 국민연금·건강보험·산재보험·고용보험 요율이 `excel/common_sheet.py:194-208` 요율 행(17~22)에 기록되나, 집행 vs 정산 이원화(`REPORT_eps_values.md:174-180`)로 적용 기준연도·갱신정책 미확정. `[NEEDS CLARIFICATION]`.
- 3. **갑지 수식 셀 목록 완전성**: `cover_sheet.py` 주석 "E127/E128 수식이 참조"가 언급되나 해당 행의 수식 내용이 코드에서 직접 확인되지 않음. 템플릿 xlsx 열람으로 확인 필요. `[NEEDS CLARIFICATION]`.
- 4. **갑지 수식 체인 검증 대상 셀 범위** (구 SC-006): 행 127~149 중 수식 셀과 입력 셀의 정확한 분류, 및 수식 체인 전체 단계 수 — `cover_sheet.py` 주석에 "E127/E128 수식이 참조"가 언급되나 E127·E128의 수식 내용이 코드에서 직접 확인되지 않음. 측정형 SC 확정 전 템플릿 xlsx 파일 직접 열람 필요. `[NEEDS CLARIFICATION]`.

### EXE-11 (5)
- 모든 Functional Requirement는 EARS 5패턴 중 하나로만 작성한다. 값은 출처 file:line이 있는 단일 값만 인용한다. 충돌값은 `[NEEDS CLARIFICATION]`으로 처리한다.
- `[잠정 — 코드 현행값]` `_calc_period_ratios`는 개월수 대신 일수(`(end - start).days + 1`)로 비율 계산. `_fiscal_year_shares`의 개월수 기반 계산과 방법론적으로 다르다(`common_sheet.py:39` vs `contract_builder.py:176`). 실무 적용 기준은 `[NEEDS CLARIFICATION]` 참조.
- [NEEDS CLARIFICATION] NC-01 — 비율 계산 방법론 이원화
- [NEEDS CLARIFICATION] NC-02 — `_mm_between` 일할 분모 30 고정
- [NEEDS CLARIFICATION] NC-03 — prev 구간 금액의 실적 반영 기준

### EXE-12 (3)
- revision > 11이면 → `[NEEDS CLARIFICATION]` (MAX_REVISION=11 초과 처리 — EXE-13과 공유, 아래 명기)
- SC-007**: MAX_REVISION 초과 처리 시 동작 — `[NEEDS CLARIFICATION]`: revision > 11일 때 EXE-12 템플릿 로드 단계에서 어떤 오류를 반환해야 하는지 미정. EXE-13에서 ValueError를 발생시키지만 EXE-12 자체에서의 처리 기준이 명시되지 않음. 확인 필요.
- [NEEDS CLARIFICATION] SC-007**: revision > 11(MAX_REVISION 초과) 시 EXE-12 템플릿 생성 단계에서의 거부/에러 처리 기준.

### EXE-13 (2)
- 원본 시트 수식에서 따옴표 없는 시트명 참조(`5.집행예산산출내역서!G8` 공백 없는 패턴) → `[NEEDS CLARIFICATION: _patch_sheet_refs_to_zero:100 조건 분기의 완전성 — 공백 포함 시트명은 따옴표 필수이나 공백 없는 경우에만 추가 패치 적용, 커버리지 범위 확인 필요]`
- 설계 §6-1에서 EXE-13에 귀속되는 강제 `[NEEDS CLARIFICATION]` 항목:

### EXE-14 (2)
- SC-007**: `/api/import` 응답 latency — [NEEDS CLARIFICATION: 현행 Bedrock 호출 실측 기준 목표값 미정. 베이스라인 측정 후 SLA 확정 필요]
- `USE_AI_SERVICE` 환경변수의 기본값은 [NEEDS CLARIFICATION: 현행 배포 환경에서의 실제 기본값 미확인 — `main.py` 상단 및 `.env` 확인 필요].

### EXE-15 (8)
- 모든 수치: 단일 출처 명기. 충돌 시 [NEEDS CLARIFICATION]
- 영업이익 역산 오차 허용: `max(abs(revenue) * 0.01, 1000)` — [NEEDS CLARIFICATION: 1% 또는 1,000원 허용의 기준 문서 출처 없음. 코드 단일 출처: `reviewer.py:478`]
- FR-013** (optional): WHERE SprintContract.rates가 존재하고 expected_salary가 0보다 클 때, THE SYSTEM SHALL 공통 시트 보험료 요율 셀(국민연금·건강보험·산재보험·고용보험)과 contract.rates의 차이가 0.0001을 초과하면 보험료 오류로 기록한다. [공식 코드: `reviewer.py:359-388`, `harness/verifier_rules.json: stages.3_breakdown.checks[2].tolerance=0.0001`] [NEEDS CLA
- FR-016** (unwanted): IF 공통 시트 P4(영업이익, 천원)와 confirmed_fields.profit의 차이가 1원을 초과하면, THEN THE SYSTEM SHALL 영업이익 오류로 기록한다. [공식 코드: `reviewer.py:436-444`] [NEEDS CLARIFICATION: SC-008 및 Edge Cases는 'max(abs(revenue)*0.01, 1000) 이내 차이는 WARN 처리, FAIL 아님'으로 더 넓은 허용 임계를 정의한다. 본 FR-016의 1원 임계와 SC-008의 동적 임계가
- FR-016b** (unwanted): IF 공통 시트 P4(영업이익, 천원)와 confirmed_fields.profit의 차이가 `max(abs(revenue) * 0.01, 1000)` 이하이면, THEN THE SYSTEM SHALL 해당 차이를 FAIL로 기록하지 않는다. [NEEDS CLARIFICATION: 허용 공식의 기준 문서 출처 없음. 단일 코드 출처: `reviewer.py:478`. FR-016의 1원 임계와 본 FR-016b의 동적 임계가 충돌. 충돌 출처: FR-016(1원) vs FR-016b/revie
- SC-003**: 보험료 요율 검증 허용 오차 — 요율(소수점 표현) 차이 **0.0001 이하**. 초과 시 FAIL. [공식 코드: `harness/verifier_rules.json: stages.3_breakdown.checks[2].tolerance=0.0001`] [NEEDS CLARIFICATION: 헌법 §IV는 '보험료 검증 오차 1,000원 이상 FAIL'(금액 단위)로 정의하나, 본 SC-003은 요율 단위(0.0001) 임계를 사용한다. 동일 보험료 검증 대상에 대해 단위·임계가 상이하여 충돌. 충돌 출처: c
- [NEEDS CLARIFICATION] 항목(강제):
- 해소 전까지 FR-013 및 SC-003 본문에 [NEEDS CLARIFICATION] 유지.

### EXE-16 (3)
- SC-006**: AI 이슈 탐지 정밀도 목표 — `[NEEDS CLARIFICATION]` (검증 사례셋 기준 베이스라인 후 목표 수립 필요. 현재 정밀도·재현율 목표 수치 없음.)
- SC-007**: Bedrock 응답 지연(p95) 목표 — `[NEEDS CLARIFICATION]` (SLA 수치 미정. read_timeout=60초 설정 있으나 p95 목표 미명시. `ai_core.py:26` 참조)
- 4. **Bedrock 비용**: Sonnet 모델 호출당 토큰 비용이 발생하며, Haiku 대비 고비용. 토큰 상한(max_tokens=256)으로 응답 비용을 제한. 비용 기준은 `[NEEDS CLARIFICATION]` (단가표 미첨부).

### EXE-17 (4)
- 1. **[NEEDS CLARIFICATION]** PyJWT 미설치 운영 환경 허용 여부 — `cognito_auth.py:108-109`는 클레임+kid 검증만으로 폴백 처리하나, 프로덕션에서 서명 미검증 상태가 허용 기준인지 정책 문서에 명시되어 있지 않음. 사용자가 사내 기준으로 직접 확정 필요 (PyJWT 의존성 설치 정책 포함).
- 2. **[NEEDS CLARIFICATION]** JWT_SECRET 미설정 시 랜덤 폴백 허용 여부 — `main.py:1055-1057`에서 WARNING 로그를 남기나, EKS 멀티워커 환경에서 실질적으로 토큰 검증 실패를 야기함. Secrets Manager 필수화 여부 미확정.
- 3. **[NEEDS CLARIFICATION]** Basic Auth 토큰 유효기간(28,800초) 운영 정책 기준 — 코드 상수값이나 보안 정책 문서 근거 없음. 사용자가 사내 보안 기준으로 직접 확정 필요.
- 4. **[NEEDS CLARIFICATION]** DynamoDB 테이블에 user별 파티션 키 추가 계획 — `project_store.py:289-290`에 "user별 파티션 키가 없어 query 전환 불가 — scan 1회로 통합" 주석이 있으나, 향후 아키텍처 전환 계획 유무 불명. 사용자가 사내 인프라 계획 문서로 직접 확정 필요.


**총 집계: 83건** (boilerplate 제외)