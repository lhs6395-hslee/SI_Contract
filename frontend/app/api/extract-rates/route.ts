import { NextRequest, NextResponse } from "next/server";
import { getClient, parseJSON } from "@/lib/claude-client";
import { parseFormFiles, buildContent } from "@/lib/parse-docs";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const maxDuration = 120;

const SYSTEM_PROMPT = `당신은 GS네오텍 SI/MSP 사업의 집행계획서 요율·보증 추출 전문가입니다.

소스 문서(견적서, 견적품의서, 계약서, 보험료율 공문)에서 요율과 보증 정보를 추출하세요.

## 할루시네이션 방지 (최우선 규칙)
- **문서에 적힌 수치만 추출하세요.** 존재하지 않는 요율이나 금액을 만들어내지 마세요.
- **취소선이 그어진 항목은 삭제된 것입니다. 절대 추출하지 마세요.**

## 규칙
- 간접비율, 일반관리비율: 견적품의서 또는 내부 기준에서 추출
- 4대보험 요율: 문서에서 추출 우선. 문서에 없으면 아래 GS네오텍 템플릿 기본값을 사용하세요:
  - 국민연금: 4.5% (source: "템플릿 기본값")
  - 건강보험: 4.0041% (source: "템플릿 기본값 (25년 기준)")
  - 고용보험: 템플릿 이미지 참조 — 문서에서 못 찾으면 value: 0, source: "확인 필요"
  - 산재보험: 템플릿 이미지 참조 — 문서에서 못 찾으면 value: 0, source: "확인 필요"
- 보증 관련: 선급금보증, 계약이행보증, 하자이행보증 금액/비율`;

const JSON_SCHEMA = `다음 JSON 형식으로만 응답:
{
  "rates": {
    "indirectRate": {"value": 0, "source": "출처"},
    "adminRate": {"value": 0, "source": "출처"},
    "nationalPension": {"value": 0, "source": "출처"},
    "healthInsurance": {"value": 0, "source": "출처"},
    "employmentInsurance": {"value": 0, "source": "출처"},
    "industrialAccident": {"value": 0, "source": "출처"}
  }
}

값을 찾지 못하면 value: 0, source: ""`;

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const { files, storedFiles } = parseFormFiles(formData);
    const content = await buildContent(files, storedFiles);
    content.push({ type: "text", text: `\n\n위 문서들에서 요율 및 보증 정보를 추출하세요.\n${JSON_SCHEMA}` });

    const { client, model } = getClient();
    const msg = await client.messages.create({
      model,
      max_tokens: 500,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content }],
    });

    const raw = msg.content[0].type === "text" ? msg.content[0].text : "";
    const result = parseJSON(raw, { rates: null });
    return NextResponse.json(result);
  } catch (err) {
    console.error("[extract-rates] error:", err);
    return NextResponse.json({ rates: null, error: String(err) }, { status: 500 });
  }
}
