"use client";

/**
 * 인증 헤더 포함 fetch 래퍼 — FastAPI 백엔드 호출 전용.
 * localStorage의 토큰(si_auth_token)을 Authorization: Bearer로 자동 첨부한다.
 */

import { getToken } from "./auth";

export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(input, { ...init, headers });
}
