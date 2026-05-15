const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function addFileContent(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any[], idx: number, filename: string,
  opts: { file?: File; projectId?: string; revision?: number },
) {
  const ext = filename.split(".").pop()?.toLowerCase();
  let text = "";

  if (opts.file) {
    try {
      const f = new FormData();
      f.append("file", opts.file);
      const r = await fetch(`${FASTAPI}/api/parse`, { method: "POST", body: f });
      if (r.ok) text = (await r.json()).text || "";
    } catch { /* */ }
  } else if (opts.projectId) {
    try {
      const revParam = opts.revision != null ? `?revision=${opts.revision}` : "";
      const r = await fetch(`${FASTAPI}/api/parse-stored/${opts.projectId}/${encodeURIComponent(filename)}${revParam}`, { method: "POST" });
      if (r.ok) text = (await r.json()).text || "";
    } catch { /* */ }
  }

  const isImagePDF = ext === "pdf" && (!text.trim() || text.includes("Vision"));
  if (isImagePDF) {
    let images: string[] = [];
    if (opts.file) {
      try {
        const f = new FormData();
        f.append("file", opts.file);
        const r = await fetch(`${FASTAPI}/api/parse-images`, { method: "POST", body: f });
        if (r.ok) images = (await r.json()).images || [];
      } catch { /* */ }
    } else if (opts.projectId) {
      try {
        const revParam = opts.revision != null ? `?revision=${opts.revision}` : "";
        const r = await fetch(`${FASTAPI}/api/parse-stored-images/${opts.projectId}/${encodeURIComponent(filename)}${revParam}`, { method: "POST" });
        if (r.ok) images = (await r.json()).images || [];
      } catch { /* */ }
    }
    if (images.length > 0) {
      content.push({ type: "text", text: `\n[문서 ${idx}: ${filename} — 스캔 ${images.length}페이지]` });
      for (const img of images.slice(0, 5)) {
        content.push({ type: "image", source: { type: "base64", media_type: "image/png", data: img } });
      }
      return;
    }
  }

  if (text) {
    content.push({ type: "text", text: `\n[문서 ${idx}: ${filename}]\n${text}` });
  }
}

export function parseFormFiles(formData: FormData): {
  files: File[];
  storedFiles: { projectId: string; filenames: string[]; revision?: number } | null;
} {
  const files = formData.getAll("files") as File[];
  const storedFilesRaw = formData.get("stored_files") as string | null;
  let storedFiles: { projectId: string; filenames: string[]; revision?: number } | null = null;
  if (storedFilesRaw) {
    try { storedFiles = JSON.parse(storedFilesRaw); } catch { /* */ }
  }
  return { files, storedFiles };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function buildContent(files: File[], storedFiles: { projectId: string; filenames: string[]; revision?: number } | null): Promise<any[]> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const content: any[] = [];
  let idx = 1;
  if (storedFiles) {
    for (const fname of storedFiles.filenames) {
      await addFileContent(content, idx++, fname, { projectId: storedFiles.projectId, revision: storedFiles.revision });
    }
  }
  for (const file of files) {
    await addFileContent(content, idx++, file.name, { file });
  }
  return content;
}
