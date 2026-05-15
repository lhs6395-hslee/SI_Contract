import { NextRequest, NextResponse } from "next/server";
import { getClient, parseJSON } from "@/lib/claude-client";
import { parseFormFiles, buildContent } from "@/lib/parse-docs";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const maxDuration = 120;

const SYSTEM_PROMPT = `당신은 GS네오텍 SI/MSP 사업의 집행계획서 현장조직 추출 전문가입니다.

소스 문서(견적서, 견적품의서, 계약서)에서 현장조직 및 업무분장 정보를 추출하세요.

## 할루시네이션 방지 (최우선 규칙)
1. **문서에 적힌 텍스트만 사용하세요.** 존재하지 않는 이름, 역할을 절대 만들어내지 마세요.
2. 이름이 문서에 없으면 → name: "TBD". 추측 금지.
3. 확신이 없으면 포함하지 마세요. 빠뜨리는 것이 만들어내는 것보다 낫습니다.
4. **취소선이 그어진 항목은 삭제된 것입니다. 절대 추출하지 마세요.**

## 규칙
- 역할(PM/기술리드/운영/개발/인프라/영업 등), 이름, 업무범위 추출
- lead: true = 프로젝트 리더(PM 또는 현장소장)
- 계약서의 참여자/서명란, 조직도, 업무분장표에서 추출
- 견적서의 등급별 단가표는 인원 목록이 아닙니다`;

const JSON_SCHEMA = `다음 JSON 형식으로만 응답:
{
  "organization": [
    {
      "role": "PM|기술리드|운영|영업 등",
      "name": "이름",
      "scope": "업무범위",
      "lead": true
    }
  ]
}

조직 정보가 없으면 {"organization": []}`;

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const { files, storedFiles } = parseFormFiles(formData);
    const content = await buildContent(files, storedFiles);
    content.push({ type: "text", text: `\n\n위 문서들에서 현장조직 및 업무분장을 추출하세요.\n${JSON_SCHEMA}` });

    const { client, model } = getClient();
    const msg = await client.messages.create({
      model,
      max_tokens: 1000,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content }],
    });

    const raw = msg.content[0].type === "text" ? msg.content[0].text : "";
    const result = parseJSON(raw, { organization: [] });
    return NextResponse.json(result);
  } catch (err) {
    console.error("[extract-org] error:", err);
    return NextResponse.json({ organization: [], error: String(err) }, { status: 500 });
  }
}
