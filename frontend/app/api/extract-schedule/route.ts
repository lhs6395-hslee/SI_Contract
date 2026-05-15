import { NextRequest, NextResponse } from "next/server";
import { getClient, parseJSON } from "@/lib/claude-client";
import { parseFormFiles, buildContent } from "@/lib/parse-docs";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const maxDuration = 120;

const SYSTEM_PROMPT = `당신은 GS네오텍 SI/MSP 사업의 집행계획서 공정표 추출 전문가입니다.

소스 문서(견적서, 견적품의서, 계약서)에서 공종별 일정을 추출하세요.

## 할루시네이션 방지 (최우선 규칙)
- **문서에 적힌 정보만 추출하세요.** 존재하지 않는 공종명이나 일정을 만들어내지 마세요.
- 문서에 공정표가 없으면 빈 배열을 반환하세요. 추측으로 만들지 마세요.
- **취소선이 그어진 항목은 삭제된 것입니다. 절대 추출하지 마세요.**

## 규칙
- 공종명과 시작/종료 월 추출
- startMonth/endMonth는 0~11 (0=계약 시작월)
- 실제 문서에 있는 정보만 추출`;

const JSON_SCHEMA = `다음 JSON 형식으로만 응답:
{
  "schedule": [
    {
      "name": "공종명",
      "startMonth": 0,
      "endMonth": 11,
      "source": "출처"
    }
  ]
}

공종이 없으면 {"schedule": []}`;

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const { files, storedFiles } = parseFormFiles(formData);
    const content = await buildContent(files, storedFiles);
    content.push({ type: "text", text: `\n\n위 문서들에서 예정공정표 정보를 추출하세요.\n${JSON_SCHEMA}` });

    const { client, model } = getClient();
    const msg = await client.messages.create({
      model,
      max_tokens: 1000,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content }],
    });

    const raw = msg.content[0].type === "text" ? msg.content[0].text : "";
    const result = parseJSON(raw, { schedule: [] });
    return NextResponse.json(result);
  } catch (err) {
    console.error("[extract-schedule] error:", err);
    return NextResponse.json({ schedule: [], error: String(err) }, { status: 500 });
  }
}
