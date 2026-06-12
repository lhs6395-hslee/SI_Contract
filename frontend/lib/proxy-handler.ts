import { NextRequest, NextResponse } from "next/server";
import { fetchBackend } from "@/lib/fetch-with-retry";

interface ProxyOpts {
  path: string;
  errorFallback: Record<string, unknown>;
  label: string;
}

export function createFormDataProxy({ path, errorFallback, label }: ProxyOpts) {
  return async function POST(req: NextRequest) {
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

      const res = await fetchBackend(path, { method: "POST", body: proxyForm },
        { auth: req.headers.get("authorization") });
      const result = await res.json();
      return NextResponse.json(result, { status: res.status });
    } catch (err) {
      console.error(`[${label}] proxy error:`, err);
      return NextResponse.json(
        { ...errorFallback, error: `서버 오류: ${err instanceof Error ? err.message : "unknown"}` },
        { status: 500 },
      );
    }
  };
}
