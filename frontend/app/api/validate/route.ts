import { NextRequest, NextResponse } from "next/server";
import { callClaude, parseJSON } from "@/lib/claude-client";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

const PROMPT = `당신은 집행계획서 교차 검증 도우미입니다.
아래 추출된 데이터에서 모순이나 누락을 찾아 보고하세요.

{data_json}

다음 JSON 배열로만 응답하세요:
[
  {"type": "mismatch|missing|warning", "field": "필드명", "message": "설명", "severity": "high|medium|low"}
]

문제가 없으면 빈 배열 [] 을 반환하세요.`;

export async function POST(req: NextRequest) {
  try {
    const data = await req.json();
    const prompt = PROMPT.replace("{data_json}", JSON.stringify(data, null, 2));
    const raw = await callClaude(prompt, 512);
    const conflicts = parseJSON<unknown[]>(raw, []);

    return NextResponse.json({ conflicts: Array.isArray(conflicts) ? conflicts : [] });
  } catch (err) {
    console.error("[validate] error:", err);
    return NextResponse.json({ conflicts: [] }, { status: 200 });
  }
}
