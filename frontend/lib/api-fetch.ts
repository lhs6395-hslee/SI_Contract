"use client";

/**
 * 인증 헤더 포함 fetch 래퍼 — FastAPI 백엔드 호출 전용.
 * localStorage의 토큰(si_auth_token)을 Authorization: Bearer로 자동 첨부한다.
 * 401(토큰 만료/무효) 응답 시 클라이언트에서는 세션을 비우고 로그인으로 보낸다.
 */

import { getToken, clearAuth } from "./auth";

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(input, { ...init, headers });

  // 토큰이 무효/만료된 경우 깨진 화면 대신 재로그인 유도 (클라이언트에서만).
  // 서버(라우트 핸들러의 fetchBackend)에서는 window가 없어 그대로 응답을 반환한다.
  if (res.status === 401 && typeof window !== "undefined") {
    const path = window.location.pathname;
    if (path !== "/login" && !path.startsWith("/auth")) {
      clearAuth();
      window.location.href = "/login?error=session_expired";
    }
  }

  return res;
}
