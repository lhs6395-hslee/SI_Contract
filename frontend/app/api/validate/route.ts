import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8001";

export async function POST(req: NextRequest) {
  try {
    const data = await req.json();

    // 백엔드로 프록시 (JSON body)
    const res = await fetch(`${FASTAPI}/api/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    const result = await res.json();
    return NextResponse.json(result, { status: res.status });
  } catch (err) {
    console.error("[validate] proxy error:", err);
    return NextResponse.json({ conflicts: [] }, { status: 200 });
  }
}
