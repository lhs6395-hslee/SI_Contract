# Tasks: EXE-17 — 계정 격리·인가

**Feature Branch**: `EXE-17-account-isolation`
**Created**: 2026-06-26
**Status**: Draft
**Spec**: `specs/EXE-17/spec.md`
**Plan**: `specs/EXE-17/plan.md`

> 이 tasks.md는 사람이 읽는 검증 산출물이다. 현행 코드가 이미 구현되어 있으므로 각 task는
> "spec을 검증하는 테스트가 존재하는가, 없으면 어떻게 추가하는가"를 중심으로 구성된다.
> 구현 우선순위는 명시된 Priority(P1/P2)를 따른다.

---

## Task 1: 인증 게이트 — require_auth 단위 검증 (FR-001, FR-003, FR-004, FR-013a, FR-013b)

**수용기준**: Authorization 헤더 없는 요청·만료 토큰·kid 없는 Cognito 토큰·잘못된 iss·Basic Auth 만료 토큰 모두 HTTP 401 반환.

**Priority**: P1

### Step 1: 실패 테스트 작성

`tests/test_auth.py` (또는 기존 auth 테스트 파일)에 다음 시나리오를 추가:

```python
# TC-1-1: Authorization 헤더 없음 → 401
def test_no_auth_header():
    resp = client.get("/api/projects")
    assert resp.status_code == 401

# TC-1-2: 만료된 Cognito 토큰(exp < now) → 401
def test_expired_cognito_token():
    token = make_cognito_token(exp=time.time() - 1)
    resp = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401

# TC-1-3: kid 없는 토큰 → 401
def test_no_kid_token():
    token = make_cognito_token(kid=None)
    resp = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401

# TC-1-4: JWKS에 없는 kid → 401
def test_unknown_kid_token():
    token = make_cognito_token(kid="unknown-kid")
    resp = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401

# TC-1-5: 만료된 Basic Auth 세션 토큰 → 401
def test_expired_basic_token():
    expired_token = _create_basic_token_with_expiry("admin", time.time() - 1)
    resp = client.get("/api/projects", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
```

**예상**: 현행 구현이 없으면 모두 FAIL.

### Step 2: 최소 구현 확인

- `cognito_auth.py:87-89` — exp 검증 (`time.time() > exp` 이면 None 반환) 확인
- `cognito_auth.py:94-96` — `not kid or kid not in keys` 이면 None 반환 확인
- `main.py:1084` — `int(expires) < int(time.time())` Basic Auth 만료 확인
- 모두 구현 완료 상태. 테스트 미존재 시 위 TC를 추가하여 커버.

### Step 3: 통과 기준

- TC-1-1 ~ TC-1-5 모두 HTTP 401 반환.
- `verify_cognito_token` 단위 테스트에서 각 거부 케이스가 None 반환.

### Step 4: 커밋

```bash
git add tests/test_auth.py
git commit -m "test(EXE-17): auth gate — no_header/expired/kid scenarios"
```

---

## Task 2: admin 권한 판별 — resolve_role 단위 검증 (FR-002)

**수용기준**: `provider="basic" AND email=ADMIN_USERNAME`만 "admin". Cognito 사용자는 이메일이 "admin"이어도 "user".

**Priority**: P1

### Step 1: 실패 테스트 작성

```python
# TC-2-1: basic admin → "admin"
def test_resolve_role_basic_admin():
    assert resolve_role("admin", "basic") == "admin"

# TC-2-2: Cognito 사용자(email="admin") → "user"
def test_resolve_role_cognito_admin_email():
    assert resolve_role("admin", "cognito") == "user"

# TC-2-3: basic test user → "user"
def test_resolve_role_basic_test():
    assert resolve_role("test", "basic") == "user"

# TC-2-4: 임의 이메일 → "user"
def test_resolve_role_arbitrary():
    assert resolve_role("lhs6395@gsneotek.com", "cognito") == "user"
```

### Step 2: 최소 구현 확인

- `cognito_auth.py:24-26` 현행 구현으로 TC-2-1 ~ TC-2-4 모두 통과 예상.

### Step 3: 통과 기준

- 4개 TC 모두 통과.

### Step 4: 커밋

```bash
git add tests/test_auth.py
git commit -m "test(EXE-17): resolve_role — admin/user discrimination"
```

---

## Task 3: 프로젝트 인가 게이트 — 비소유자 404 검증 (FR-005, FR-006, FR-007)

**수용기준**: 비소유자의 타인 프로젝트 접근 시 HTTP 404. 레거시(owner 없음) 프로젝트는 일반 user에게 404.

**Priority**: P1

### Step 1: 실패 테스트 작성

```python
# TC-3-1: 계정 A 프로젝트를 계정 B가 GET → 404
def test_cross_account_get_returns_404():
    # 계정 A로 프로젝트 생성
    proj_a = save_project({"id": "p_test_a"}, owner="a@test.com")
    # 계정 B 컨텍스트로 접근
    user_b = {"email": "b@test.com", "role": "user"}
    with pytest.raises(HTTPException) as exc:
        _assert_project_access("p_test_a", user_b)
    assert exc.value.status_code == 404

# TC-3-2: admin은 모든 프로젝트 접근 가능
def test_admin_can_access_any_project():
    save_project({"id": "p_test_b"}, owner="b@test.com")
    admin_user = {"email": "admin", "role": "admin"}
    result = _assert_project_access("p_test_b", admin_user)
    assert result["id"] == "p_test_b"

# TC-3-3: owner 없는 레거시 프로젝트 → 일반 user 404
def test_legacy_project_hidden_from_user():
    # owner 필드 없이 저장
    save_project({"id": "p_legacy"}, owner=None)
    user = {"email": "user@test.com", "role": "user"}
    with pytest.raises(HTTPException) as exc:
        _assert_project_access("p_legacy", user)
    assert exc.value.status_code == 404

# TC-3-4: 존재하지 않는 project_id → 404
def test_nonexistent_project_returns_404():
    user = {"email": "user@test.com", "role": "user"}
    with pytest.raises(HTTPException) as exc:
        _assert_project_access("nonexistent", user)
    assert exc.value.status_code == 404
```

### Step 2: 최소 구현 확인

- `main.py:827-840` `_assert_project_access` 현행 구현.
- `main.py:837` `project.get("owner") or LEGACY_OWNER` 레거시 귀속.

### Step 3: 통과 기준

- TC-3-1 ~ TC-3-4 모두 통과.
- HTTP 엔드포인트 통합 테스트: `GET /api/projects/{타인 id}` → HTTP 404.

### Step 4: 커밋

```bash
git add tests/test_project_access.py
git commit -m "test(EXE-17): _assert_project_access — cross-account 404 + legacy"
```

---

## Task 4: 프로젝트 목록 owner 필터 검증 (FR-008)

**수용기준**: `GET /api/projects` 응답에 타인 프로젝트 0건 포함. admin은 전체 반환.

**Priority**: P1

### Step 1: 실패 테스트 작성

```python
# TC-4-1: 계정 A의 목록에 계정 B 프로젝트 미포함
def test_list_excludes_other_accounts():
    save_project({"id": "p_a1"}, owner="a@test.com")
    save_project({"id": "p_b1"}, owner="b@test.com")
    result = list_projects_cached(owner="a@test.com", is_admin=False)
    ids = [p["id"] for p in result]
    assert "p_a1" in ids
    assert "p_b1" not in ids

# TC-4-2: admin은 전체 반환
def test_list_admin_returns_all():
    result = list_projects_cached(owner="admin", is_admin=True)
    ids = [p["id"] for p in result]
    assert "p_a1" in ids
    assert "p_b1" in ids

# TC-4-3: owner=None & not admin → 빈 목록
def test_list_no_owner_returns_empty():
    result = list_projects_cached(owner=None, is_admin=False)
    assert result == []
```

### Step 2: 최소 구현 확인

- `project_store.py:99-121` 현행 구현.
- 버전 스탬프 캐시: `_bump_projects_version` → `_get_projects_version` 일관성 확인.

### Step 3: 통과 기준

- TC-4-1 ~ TC-4-3 모두 통과.
- `GET /api/projects` HTTP 통합 테스트: user 계정은 본인 프로젝트만 수신.

### Step 4: 커밋

```bash
git add tests/test_project_store.py
git commit -m "test(EXE-17): list_projects_cached — owner filter + admin pass"
```

---

## Task 5: S3 계정별 경로 격리 검증 (FR-009)

**수용기준**: owner 지정 시 S3 key가 `projects/{owner}/{project_id}/` prefix를 포함. owner 없으면 레거시 경로.

**Priority**: P1

### Step 1: 실패 테스트 작성

```python
# TC-5-1: owner 있을 때 prefix 확인
def test_project_prefix_with_owner():
    from services.s3_storage import _project_prefix
    prefix = _project_prefix("p_test", revision=None, owner="user@test.com")
    assert prefix == "projects/user@test.com/p_test/"

# TC-5-2: owner 없을 때 레거시 경로
def test_project_prefix_no_owner():
    from services.s3_storage import _project_prefix
    prefix = _project_prefix("p_test", revision=None, owner=None)
    assert prefix == "projects/p_test/"

# TC-5-3: revision 있을 때 경로
def test_project_prefix_with_revision():
    from services.s3_storage import _project_prefix
    prefix = _project_prefix("p_test", revision=2, owner="user@test.com")
    assert prefix == "projects/user@test.com/p_test/rev2/"
```

### Step 2: 최소 구현 확인

- `s3_storage.py:35-41` `_project_prefix` 현행 구현.
- revision prefix: `s3_storage.py:42-44` (revision 분기) 확인.

### Step 3: 통과 기준

- TC-5-1 ~ TC-5-3 모두 통과.

### Step 4: 커밋

```bash
git add tests/test_s3_storage.py
git commit -m "test(EXE-17): _project_prefix — owner/legacy/revision path isolation"
```

---

## Task 6: save_project owner 보존·원자성 검증 (FR-011a, FR-011b, FR-012)

**수용기준**: 기존 owner 덮어쓰기 0건. DynamoDB 조회 실패 시 신규 owner 기록 안 함. 동시 생성 시 선행 owner 보존.

**Priority**: P1

### Step 1: 실패 테스트 작성

```python
# TC-6-1: 기존 owner 덮어쓰기 방지
def test_save_project_preserves_existing_owner():
    save_project({"id": "p_own"}, owner="original@test.com")
    # 다른 owner로 재저장 시도
    result = save_project({"id": "p_own"}, owner="attacker@test.com")
    assert result.get("owner") == "original@test.com"

# TC-6-2: lookup_failed=True이면 신규 owner 기록 안 함 (메모리 fallback 환경에서만 모킹)
def test_save_project_lookup_fail_no_owner_write(monkeypatch):
    # load_project를 Exception 발생하도록 패치
    # owner 없는 새 프로젝트에 조회 실패 시 owner 필드가 기록되어서는 안 됨
    ...  # 구현 시 monkeypatch로 DynamoDB get_item 실패 시뮬레이션

# TC-6-3: SC-008 — 동시 생성 경합 시 선행 owner 보존 (DynamoDB 환경 통합 테스트)
# 조건: DYNAMODB_TABLE이 설정된 환경에서만 실행
@pytest.mark.skipif(not os.getenv("DYNAMODB_TABLE"), reason="DynamoDB required")
def test_concurrent_project_creation_preserves_first_owner():
    ...  # concurrent put 시뮬레이션
```

### Step 2: 최소 구현 확인

- `project_store.py:209-212` owner 보존 로직.
- `project_store.py:220-236` 조건부 put + 폴백 재조회.
- TC-6-1은 메모리 fallback으로 검증 가능.

### Step 3: 통과 기준

- TC-6-1 통과 (메모리 환경).
- TC-6-2는 monkeypatch로 lookup_failed 시나리오 검증.
- TC-6-3은 DynamoDB 통합환경에서 통과.

### Step 4: 커밋

```bash
git add tests/test_project_store.py
git commit -m "test(EXE-17): save_project — owner preservation + atomic creation"
```

---

## Task 7: import 엔드포인트 파일 접근 인가 검증 (FR-010)

**수용기준**: `stored_files`에 타인 projectId가 있으면 HTTP 404. 없으면 인가 불필요.

**Priority**: P2

### Step 1: 실패 테스트 작성

```python
# TC-7-1: stored_files에 타인 projectId → 404
def test_import_stored_files_cross_account_denied():
    save_project({"id": "p_a"}, owner="a@test.com")
    user_b_headers = auth_headers("b@test.com", role="user")
    resp = client.post(
        "/api/import",
        data={"stored_files": json.dumps({"projectId": "p_a"})},
        headers=user_b_headers,
    )
    assert resp.status_code == 404

# TC-7-2: stored_files 없이 파일 직접 업로드 → 인가 무관, 처리 진행
def test_import_no_stored_files_allowed():
    resp = client.post(
        "/api/import",
        files={"files": ("test.pdf", b"pdf content", "application/pdf")},
        headers=auth_headers("any@test.com", role="user"),
    )
    # 422(파일 내용 파싱 오류) 또는 200 — 인가 거부(404)가 아닌지 확인
    assert resp.status_code != 404
```

### Step 2: 최소 구현 확인

- `main.py:651-660` — `pid`가 있으면 `_assert_project_access` 호출.

### Step 3: 통과 기준

- TC-7-1: HTTP 404 반환.
- TC-7-2: 인가 통과(200 또는 422).

### Step 4: 커밋

```bash
git add tests/test_import.py
git commit -m "test(EXE-17): import endpoint — stored_files cross-account gate"
```

---

## Task 8: Basic Auth 토큰 발급·검증 단위 테스트 (FR-013a, FR-013b)

**수용기준**: 8시간(28800초) 만료. 상수시간 비교. 만료 후 None 반환.

**Priority**: P2

### Step 1: 실패 테스트 작성

```python
# TC-8-1: 유효 토큰 검증 성공
def test_basic_token_valid():
    token = _create_basic_token("testuser")
    result = _verify_basic_token(token)
    assert result == "testuser"

# TC-8-2: 만료 토큰 → None
def test_basic_token_expired():
    # 발급은 현재 시각에 수행하고, 검증 시각을 28801초 후로 패치하여 만료 시뮬레이션
    token_at_issue = _create_basic_token("testuser")
    with patch("main.time.time", return_value=time.time() + 28801):
        result = _verify_basic_token(token_at_issue)
    assert result is None

# TC-8-3: 변조 토큰 → None (HMAC 불일치)
def test_basic_token_tampered():
    token = _create_basic_token("admin")
    tampered = token[:-3] + "xyz"
    assert _verify_basic_token(tampered) is None

# TC-8-4: 유효 기간 상수값 확인 (SC-009)
def test_basic_token_expiry_constant():
    # 발급 직후와 28799초 후는 유효
    token = _create_basic_token("testuser")
    with patch("main.time.time", return_value=time.time() + 28799):
        assert _verify_basic_token(token) == "testuser"
```

### Step 2: 최소 구현 확인

- `main.py:1063-1088` 현행 구현.
- `main.py:1066` — 만료 상수 `+ 28800`.
- `main.py:1081` — `hmac.compare_digest`.

### Step 3: 통과 기준

- TC-8-1 ~ TC-8-4 모두 통과.

### Step 4: 커밋

```bash
git add tests/test_auth.py
git commit -m "test(EXE-17): basic token — expiry 28800s + tamper detection"
```

---

## Task 9: 엔드투엔드 계정 격리 통합 테스트

**수용기준**: 실제 HTTP 요청으로 계정 A·B 간 데이터 완전 격리 확인.

**Priority**: P1 (배포 전 필수)

### Step 1: 시나리오 정의

```
시나리오: 계정 격리 E2E
1. 계정 A 로그인 → 토큰 A
2. 계정 B 로그인 → 토큰 B
3. 토큰 A로 프로젝트 P1 생성
4. 토큰 B로 GET /api/projects/{P1.id} → 404 확인  (SC-001)
5. 토큰 B로 GET /api/projects            → P1 미포함 확인 (SC-007)
6. 토큰 B로 POST /api/pipeline/start (projectId=P1.id) → 404 확인
7. 토큰 A로 GET /api/projects/{P1.id} → 200 확인
8. 토큰 없이 GET /api/projects → 401 확인 (SC-002)
```

### Step 2: 최소 구현 확인

- 기존 `run_all_suites.sh`에 위 시나리오가 포함되어 있는지 확인.
- 포함되어 있지 않으면 `tests/test_e2e_isolation.py`에 추가.

### Step 3: 통과 기준

- 시나리오 1~8 모두 예상 HTTP 코드 반환.
- `grep -rn "cross.*account\|isolation" tests/` 에서 테스트 존재 확인.

### Step 4: 커밋

```bash
git add tests/test_e2e_isolation.py
git commit -m "test(EXE-17): e2e account isolation — 8-step scenario"
```

---

## Task 10: CLARIFICATION 해소 후 후속 작업 (보류)

**Priority**: 해당 CLARIFICATION 해소 후 진행

아래 항목은 `spec.md ## Clarifications Retained`에 기재된 [NEEDS CLARIFICATION] 항목이 사용자 직접 확정 후 spec·plan·tasks를 업데이트한다.

| 항목 | 대기 중인 결정 |
|------|-------------|
| PyJWT 미설치 허용 여부 | 사용자 확정 → 필수화 시 `requirements.txt` PyJWT 추가 + 폴백 제거 |
| JWT_SECRET 필수화 | 사용자 확정 → 랜덤 폴백 제거 + Secrets Manager 강제 |
| Basic Auth 토큰 유효기간 | 사용자 확정 → 28800초 유지 또는 단축 |
| DynamoDB 파티션 키 추가 | 사용자 확정 → 마이그레이션 계획 수립 |

---

## 체크리스트 (저작자 검증)

- [ ] 모든 FR(FR-001~FR-012, FR-011a, FR-011b, FR-013a, FR-013b)이 최소 1개의 Task에 매핑됨
- [ ] 모든 SC(SC-001~SC-010)가 최소 1개의 TC에서 검증됨
- [ ] 편집잠금(lock/unlock) 관련 테스트 0건 (설계 §9 비대상)
- [ ] 챗봇·OTEL·RateLimit 관련 테스트 0건 (설계 §9 비대상)
- [ ] [NEEDS CLARIFICATION] 항목 4건 모두 Task 10으로 보류 명기됨
- [ ] 모든 Task에 커밋 단위 명기됨
