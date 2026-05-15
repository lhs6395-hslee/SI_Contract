import { NextRequest, NextResponse } from "next/server";
import { getClient, parseJSON } from "@/lib/claude-client";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const maxDuration = 120;

const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";

const SYSTEM_PROMPT = `당신은 GS네오텍 SI/MSP 사업의 집행계획서 산출내역 추출 전문가입니다.

소스 문서(견적서, 견적품의서, 계약서)에서 비용 항목을 추출하세요.

## 카테고리
- fee: 수수료 (협력사 용역비, MSP 수수료, 유지보수비 등)
- material: 재료비 (장비, 라이선스, 자재 등)
- labor: 노무비 (인건비 — 자사 인원, 파견 인력 등)
- supply: 소모품비 (사무용품, 소모품 등)
- line: 회선비/통신비
- travel: 여비교통비, 차량유지비
- other: 기타 경비

## 단위 규칙 (중요)
- 문서에 명시된 단위를 그대로 사용하세요
- MSP, 운영, 야간관제 등 월 단위 용역 → "월" (M/M 아님)
- 인력 투입 → "M/M"
- 수량이 1이고 총액만 있으면 → "식"
- 장비/라이선스 개별 항목 → "EA" 또는 "대"
- 문서에 단위가 명시되어 있으면 그 단위를 우선 사용

## 할루시네이션 방지 (최우선 규칙)
- **문서에 적힌 항목만 추출하세요.** 존재하지 않는 품명, 금액, 수량을 절대 만들어내지 마세요.
- 확신이 없으면 빠뜨리는 것이 만들어내는 것보다 낫습니다.
- **취소선이 그어진 항목은 삭제된 것입니다. 절대 추출하지 마세요.**

## 일할계산 규칙 (매우 중요)
- 계약 시작일이 월 중간이면 해당 월은 **일할 계산**합니다.
- 예: 3/23 투입, 30일 기준 → 3월분 = 시작일부터 월말까지 실제 투입일수 / 30일
- 특기사항에 "일할 계산" 언급이 있으면 반드시 적용하세요.
- 수량(M/M)은 일할 적용된 값을 사용합니다 (예: 7일/30일 + 9개월 = 9.233... → 반올림 9.2)
- **금액 = 일할수량 × 단가** (반올림하지 않은 정확한 일할수량 사용)

## 규칙
- 계약 금액(매출)과 집행 금액(매입)을 구분하세요
- 월 단가면 ×계약월수로 연간 금액 환산 (일할 적용 시 해당 월 일할 반영)
- 금액은 원 단위 정수`;

const JSON_SCHEMA = `다음 JSON 형식으로만 응답:
{
  "items": [
    {
      "category": "fee|material|labor|supply|line|travel|other",
      "name": "품명",
      "spec": "규격/설명",
      "unit": "단위 (월, EA, 식 등)",
      "contractQty": 수량(계약),
      "contractPrice": 단가(계약, 원),
      "contractAmount": 금액(계약, 원),
      "executionQty": 수량(집행),
      "executionPrice": 단가(집행, 원),
      "executionAmount": 금액(집행, 원),
      "source": "출처",
      "confidence": "verified|guess"
    }
  ]
}

항목이 없으면 {"items": []}`;

async function addFileContent(
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

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const files = formData.getAll("files") as File[];
    const storedFilesRaw = formData.get("stored_files") as string | null;
    let storedFiles: { projectId: string; filenames: string[]; revision?: number } | null = null;
    if (storedFilesRaw) {
      try { storedFiles = JSON.parse(storedFilesRaw); } catch { /* */ }
    }

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

    content.push({ type: "text", text: `\n\n위 문서들에서 산출내역(비용 항목)을 추출하세요.\n${JSON_SCHEMA}` });

    const { client, model } = getClient();
    const msg = await client.messages.create({
      model,
      max_tokens: 2000,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content }],
    });

    const raw = msg.content[0].type === "text" ? msg.content[0].text : "";
    const result = parseJSON(raw, { items: [] });

    return NextResponse.json(result);
  } catch (err) {
    console.error("[extract-costs] error:", err);
    return NextResponse.json({ items: [], error: String(err) }, { status: 500 });
  }
}
