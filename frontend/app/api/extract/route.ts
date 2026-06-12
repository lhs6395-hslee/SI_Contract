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

    const hasNewFiles = files.length > 0;
    const hasStoredFiles = storedFilesRaw ? JSON.parse(storedFilesRaw)?.filenames?.length > 0 : false;

    if (!hasNewFiles && !hasStoredFiles) {
      return NextResponse.json({ error: "files required" }, { status: 400 });
    }

    const proxyForm = new FormData();
    for (const file of files) {
      proxyForm.append("files", file);
    }
    if (storedFilesRaw) {
      proxyForm.append("stored_files", storedFilesRaw);
    }

    const res = await fetchBackend("/api/extract", { method: "POST", body: proxyForm },
      { auth: req.headers.get("authorization") });
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
