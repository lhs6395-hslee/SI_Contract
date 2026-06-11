const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8001";
const DEFAULT_TIMEOUT_MS = 90_000;
const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1_000;

export async function fetchBackend(
  path: string,
  init: RequestInit,
  opts?: { timeoutMs?: number; retries?: number },
): Promise<Response> {
  const timeout = opts?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const maxRetries = opts?.retries ?? MAX_RETRIES;
  let lastError: unknown;

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
