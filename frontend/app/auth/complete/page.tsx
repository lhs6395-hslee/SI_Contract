"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { setAuth } from "@/lib/auth";

function getCookie(name: string): string {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : "";
}

function deleteCookie(name: string) {
  document.cookie = `${name}=; Max-Age=0; path=/`;
}

export default function AuthComplete() {
  const router = useRouter();

  useEffect(() => {
    const token = getCookie("si_pending_token");
    const email = getCookie("si_pending_email");
    const name = getCookie("si_pending_name");

    if (token) {
      // role은 백엔드가 단일 출처로 판별 (계정 격리 — admin 여부 확정).
      const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";
      (async () => {
        let role: "admin" | "user" = "user";
        let resolvedEmail = email;
        try {
          const res = await fetch(`${FASTAPI}/api/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (res.ok) {
            const me = await res.json();
            role = me.role === "admin" ? "admin" : "user";
            resolvedEmail = me.email || email;
          }
        } catch {
          /* 네트워크 실패 시 안전 기본값(user) 유지 */
        }
        setAuth(token, { email: resolvedEmail, name: name || resolvedEmail, role, provider: "cognito" });
        deleteCookie("si_pending_token");
        deleteCookie("si_pending_email");
        deleteCookie("si_pending_name");
        router.replace("/");
      })();
    } else {
      router.replace("/login?error=no_token");
    }
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-sm text-muted-foreground">로그인 처리 중...</div>
    </div>
  );
}
