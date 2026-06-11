import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8001";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File | null;
    if (!file) {
      return NextResponse.json({ error: "file required" }, { status: 400 });
    }

    // 백엔드로 프록시
    const proxyForm = new FormData();
    proxyForm.append("file", file);

    const res = await fetch(`${FASTAPI}/api/classify`, {
      method: "POST",
      body: proxyForm,
    });

    const result = await res.json();
    return NextResponse.json(result, { status: res.status });
  } catch (err) {
    console.error("[classify] proxy error:", err);
    return NextResponse.json(
      { category: "unknown", confidence: 0.3, reason: `서버 오류: ${err instanceof Error ? err.message : "unknown"}` },
      { status: 200 },
    );
  }
}
