// 서버 전용 모듈 — "use client" 모듈(api-fetch)을 import하면 안 됨
// (이 Next 버전은 서버에서 클라이언트 함수 호출 시 런타임 에러).
// 인증은 호출부가 opts.auth로 브라우저의 Authorization 헤더를 전달한다.
const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8001";
const DEFAULT_TIMEOUT_MS = 90_000;
const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1_000;

export async function fetchBackend(
  path: string,
  init: RequestInit,
  opts?: { timeoutMs?: number; retries?: number; auth?: string | null },
): Promise<Response> {
  const timeout = opts?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const maxRetries = opts?.retries ?? MAX_RETRIES;
  let lastError: unknown;

  // 서버(라우트 핸들러)에서는 localStorage 토큰이 없으므로 브라우저가 보낸
  // Authorization 헤더를 그대로 전달해야 함 — 누락 시 백엔드 require_auth가 401
  if (opts?.auth) {
    const headers = new Headers(init.headers);
    if (!headers.has("Authorization")) {
      headers.set("Authorization", opts.auth);
    }
    init = { ...init, headers };
  }

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);

    try {
      const res = await fetch(`${FASTAPI}${path}`, {
        ...init,
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (res.status === 429 && attempt < maxRetries) {
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
        continue;
      }
      if (res.status >= 500 && attempt < maxRetries) {
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
        continue;
      }

      return res;
    } catch (err) {
      clearTimeout(timer);
      lastError = err;
      if (attempt < maxRetries) {
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
        continue;
      }
    }
  }

  const msg =
    lastError instanceof DOMException && lastError.name === "AbortError"
      ? `백엔드 응답 시간 초과 (${timeout / 1000}초)`
      : `백엔드 연결 실패: ${lastError instanceof Error ? lastError.message : "unknown"}`;
  throw new Error(msg);
}
