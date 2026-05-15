import { NextRequest, NextResponse } from "next/server";
import { getClient, parseJSON } from "@/lib/claude-client";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";

const CLASSIFY_SYSTEM = `당신은 SI/MSP 사업 문서 분류 도우미입니다. 파일 종류를 판정하세요.

다음 5개 카테고리 중 하나로 분류:
- contract: 계약서, 업무위탁계약서, SLA, 부속계약서, 서명된 계약문서
- internal: 내부 견적품의서, 사내 기안 문서 (GS네오텍 자체 양식)
- vendor: 외부 협력사가 제출한 견적서
- insurance: 보험료율 공문, 4대 보험료율 안내 공문서
- unknown: 위 어디에도 해당하지 않거나 판단 불가

JSON 형식으로만 응답:
{"category":"contract|internal|vendor|insurance|unknown","confidence":0.0~1.0,"reason":"한 줄 사유"}`;

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File | null;
    if (!file) {
      return NextResponse.json({ error: "file required" }, { status: 400 });
    }

    const ext = file.name.split(".").pop()?.toLowerCase();
    const isPDF = ext === "pdf";

    // 1) FastAPI로 텍스트 추출
    let text = "";
    let pdfImages: string[] = [];

    try {
      const parseForm = new FormData();
      parseForm.append("file", file);
      const parseRes = await fetch(`${FASTAPI}/api/parse`, { method: "POST", body: parseForm });
      if (parseRes.ok) {
        const parsed = await parseRes.json();
        text = parsed.text || "";
      }
    } catch { /* FastAPI 연결 실패 */ }

    // 2) 이미지 PDF면 Vision용 이미지도 가져옴
    const isImagePDF = isPDF && (!text.trim() || text.includes("Vision 분석 필요"));
    if (isImagePDF) {
      try {
        const imgForm = new FormData();
        imgForm.append("file", file);
        const imgRes = await fetch(`${FASTAPI}/api/parse-images`, { method: "POST", body: imgForm });
        if (imgRes.ok) {
          const imgData = await imgRes.json();
          pdfImages = imgData.images || [];
        }
      } catch { /* */ }
    }

    // 3) Claude 호출 — Vision 또는 텍스트
    const { client, model } = getClient();

    const content: Array<{ type: string; text?: string; source?: { type: string; media_type: string; data: string } }> = [];

    if (pdfImages.length > 0) {
      // Vision: 이미지 + 텍스트 프롬프트
      for (const img of pdfImages.slice(0, 3)) {
        content.push({
          type: "image",
          source: { type: "base64", media_type: "image/png", data: img },
        });
      }
      content.push({ type: "text", text: `파일명: ${file.name}\n\n위 이미지는 이 PDF 문서의 페이지입니다. 문서 종류를 분류하세요.` });
    } else {
      content.push({
        type: "text",
        text: `파일명: ${file.name}\n\n문서 내용:\n"""\n${(text || "(텍스트 추출 불가 — 파일명만으로 판단)").slice(0, 3000)}\n"""`,
      });
    }

    const msg = await client.messages.create({
      model,
      max_tokens: 256,
      system: CLASSIFY_SYSTEM,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      messages: [{ role: "user", content: content as any }],
    });

    const raw = msg.content[0].type === "text" ? msg.content[0].text : "";
    const result = parseJSON(raw, { category: "unknown", confidence: 0.3, reason: "파싱 실패" });

    return NextResponse.json(result);
  } catch (err) {
    console.error("[classify] error:", err);
    return NextResponse.json(
      { category: "unknown", confidence: 0.3, reason: `서버 오류: ${err instanceof Error ? err.message : "unknown"}` },
      { status: 200 },
    );
  }
}
