import { NextRequest, NextResponse } from "next/server";
import { fetchBackend } from "@/lib/fetch-with-retry";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File | null;
    if (!file) {
      return NextResponse.json({ error: "file required" }, { status: 400 });
    }

    const proxyForm = new FormData();
    proxyForm.append("file", file);

    const res = await fetchBackend("/api/classify", { method: "POST", body: proxyForm },
      { auth: req.headers.get("authorization") });
    const result = await res.json();
    return NextResponse.json(result, { status: res.status });
  } catch (err) {
    console.error("[classify] proxy error:", err);
    return NextResponse.json(
      { category: "unknown", confidence: 0.3, reason: `서버 오류: ${err instanceof Error ? err.message : "unknown"}` },
      { status: 500 },
    );
  }
}
