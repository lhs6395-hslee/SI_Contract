import { NextRequest, NextResponse } from "next/server";
import { fetchBackend } from "@/lib/fetch-with-retry";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export async function POST(req: NextRequest) {
  try {
    const data = await req.json();

    const res = await fetchBackend("/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }, { auth: req.headers.get("authorization") });
    const result = await res.json();
    return NextResponse.json(result, { status: res.status });
  } catch (err) {
    console.error("[validate] proxy error:", err);
    return NextResponse.json({ conflicts: [], error: `서버 오류: ${err instanceof Error ? err.message : "unknown"}` }, { status: 500 });
  }
}
