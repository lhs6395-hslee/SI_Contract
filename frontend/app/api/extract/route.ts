import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const maxDuration = 120;

const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8001";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const files = formData.getAll("files") as File[];
    const storedFilesRaw = formData.get("stored_files") as string | null;

    const hasNewFiles = files.length > 0;
    const hasStoredFiles = storedFilesRaw ? JSON.parse(storedFilesRaw)?.filenames?.length > 0 : false;

    if (!hasNewFiles && !hasStoredFiles) {
      return NextResponse.json({ error: "files required" }, { status: 400 });
    }

    // 백엔드로 프록시
    const proxyForm = new FormData();
    for (const file of files) {
      proxyForm.append("files", file);
    }
    if (storedFilesRaw) {
      proxyForm.append("stored_files", storedFilesRaw);
    }

    const res = await fetch(`${FASTAPI}/api/extract`, {
      method: "POST",
      body: proxyForm,
    });

    const result = await res.json();
    return NextResponse.json(result, { status: res.status });
  } catch (err) {
    console.error("[extract] proxy error:", err);
    return NextResponse.json(
      { error: `서버 오류: ${err instanceof Error ? err.message : "unknown"}` },
      { status: 500 },
    );
  }
}
