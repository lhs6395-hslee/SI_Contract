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
      setAuth(token, { email, name: name || email, role: "user", provider: "cognito" });
      deleteCookie("si_pending_token");
      deleteCookie("si_pending_email");
      deleteCookie("si_pending_name");
      router.replace("/");
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
