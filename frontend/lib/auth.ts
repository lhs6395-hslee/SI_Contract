"use client";

/**
 * 인증 모듈 — Cognito JWT + Basic Auth (admin)
 *
 * 로그인 방식:
 * 1. Google OAuth (Cognito Hosted UI)
 * 2. Basic Auth (admin/password) — 개발/긴급용
 */

const COGNITO_DOMAIN = "si-contract-auth.auth.ap-northeast-2.amazoncognito.com";
const CLIENT_ID = "6aarjh4rm676q8c61ll8li24h9";
const REDIRECT_URI = typeof window !== "undefined"
  ? `${window.location.origin}/api/auth/callback`
  : "https://si.rayhli.com/api/auth/callback";

const TOKEN_KEY = "si_auth_token";
const USER_KEY = "si_auth_user";

export interface AuthUser {
  email: string;
  name?: string;
  role: "admin" | "user";
  provider: "cognito" | "basic";
}

// ─── Token 관리 ───

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export function setAuth(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// ─── Google OAuth (Cognito Hosted UI) ───

export function getGoogleLoginUrl(): string {
  return `https://${COGNITO_DOMAIN}/oauth2/authorize?client_id=${CLIENT_ID}&response_type=code&scope=openid+email+profile&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&identity_provider=Google`;
}

// ─── Basic Auth (admin) ───

export async function loginWithBasicAuth(username: string, password: string): Promise<AuthUser | null> {
  const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";
  const res = await fetch(`${FASTAPI}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  const user: AuthUser = { email: username, name: "Admin", role: "admin", provider: "basic" };
  setAuth(data.token, user);
  return user;
}

// ─── Logout ───

export function logout() {
  clearAuth();
  window.location.href = "/login";
}
