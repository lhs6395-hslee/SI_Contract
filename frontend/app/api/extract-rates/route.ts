import { NextRequest, NextResponse } from "next/server";
import { fetchBackend } from "@/lib/fetch-with-retry";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const maxDuration = 120;

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const files = formData.getAll("files") as File[];
    const storedFilesRaw = formData.get("stored_files") as string | null;

    const proxyForm = new FormData();
    for (const file of files) {
      proxyForm.append("files", file);
    }
    if (storedFilesRaw) {
      proxyForm.append("stored_files", storedFilesRaw);
    }

    const res = await fetchBackend("/api/extract-rates", { method: "POST", body: proxyForm });
    const result = await res.json();
    return NextResponse.json(result, { status: res.status });
  } catch (err) {
    console.error("[extract-rates] proxy error:", err);
    return NextResponse.json({ rates: null, error: `서버 오류: ${err instanceof Error ? err.message : "unknown"}` }, { status: 500 });
  }
}
