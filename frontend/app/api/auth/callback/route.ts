import { NextRequest, NextResponse } from "next/server";

const COGNITO_DOMAIN = "si-contract-auth.auth.ap-northeast-2.amazoncognito.com";
const CLIENT_ID = "6aarjh4rm676q8c61ll8li24h9";
const CLIENT_SECRET = process.env.COGNITO_CLIENT_SECRET || "";
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "https://si.rayhli.com";
const REDIRECT_URI = `${APP_URL}/api/auth/callback`;

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const code = searchParams.get("code");
  const error = searchParams.get("error");

  if (error) {
    return NextResponse.redirect(`${APP_URL}/login?error=${encodeURIComponent(error)}`);
  }

  if (!code) {
    return NextResponse.redirect(`${APP_URL}/login?error=no_code`);
  }

  const tokenEndpoint = `https://${COGNITO_DOMAIN}/oauth2/token`;
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: CLIENT_ID,
    code,
    redirect_uri: REDIRECT_URI,
  });

  const headers: Record<string, string> = {
    "Content-Type": "application/x-www-form-urlencoded",
  };
  if (CLIENT_SECRET) {
    const credentials = Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString("base64");
    headers["Authorization"] = `Basic ${credentials}`;
  }

  let tokenData: { id_token?: string; access_token?: string; error?: string };
  try {
    const res = await fetch(tokenEndpoint, { method: "POST", headers, body: body.toString() });
    tokenData = await res.json();
  } catch {
    return NextResponse.redirect(new URL("/login?error=token_exchange_failed", req.url));
  }

  if (tokenData.error || !tokenData.id_token) {
    return NextResponse.redirect(
      `${APP_URL}/login?error=${encodeURIComponent(tokenData.error || "no_id_token")}`
    );
  }

  let email = "";
  let name = "";
  try {
    const payload = JSON.parse(Buffer.from(tokenData.id_token.split(".")[1], "base64url").toString());
    email = payload.email || "";
    name = payload.name || payload["cognito:username"] || email;
  } catch { /* 파싱 실패해도 계속 */ }

  // 쿠키로 토큰 전달 — 클라이언트에서 읽어 localStorage에 저장
  const response = NextResponse.redirect(`${APP_URL}/auth/complete`);
  response.cookies.set("si_pending_token", tokenData.id_token, {
    httpOnly: false, // 클라이언트 JS에서 읽어야 함
    secure: true,
    sameSite: "lax",
    maxAge: 60, // 60초 내 처리
    path: "/",
  });
  response.cookies.set("si_pending_email", email, {
    httpOnly: false, secure: true, sameSite: "lax", maxAge: 60, path: "/",
  });
  response.cookies.set("si_pending_name", name, {
    httpOnly: false, secure: true, sameSite: "lax", maxAge: 60, path: "/",
  });

  return response;
}
