import { NextRequest, NextResponse } from "next/server";
import { getClient, parseJSON } from "@/lib/claude-client";
import { parseFormFiles, buildContent } from "@/lib/parse-docs";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const maxDuration = 120;

const SYSTEM_PROMPT = `당신은 GS네오텍 SI/MSP 사업의 집행계획서 인원투입계획 추출 전문가입니다.

소스 문서(견적서, 견적품의서, 계약서)에서 **실제 투입 인원**을 추출하세요.

## 할루시네이션 방지 (최우선 규칙)
1. **문서에 적힌 텍스트만 사용하세요.** 존재하지 않는 이름, 역할, 숫자를 절대 만들어내지 마세요.
2. 이름이 문서에 없으면 → name: "TBD". 추측 금지.
3. 이름을 정확히 읽을 수 없으면 → name: "TBD", confidence: "guess". 비슷한 이름을 지어내지 마세요.
4. 확신이 없으면 포함하지 마세요. 빠뜨리는 것이 만들어내는 것보다 낫습니다.

## 취소선/삭제된 항목 (중요)
- **취소선이 그어진 행은 삭제된 항목입니다. 절대 추출하지 마세요.**
- 스캔 문서에서 가로줄이 텍스트 위를 가로지르면 취소선입니다.
- 취소선이 있는 인원/금액/항목은 최종 확정에서 제외된 것이므로 무시하세요.

## 인원 vs 단가표 구분 (중요)
- 견적서에 등급별(특급/고급/중급/초급) 단가표가 있으면 → 이것은 **단가 기준표**이지 실제 투입인력 목록이 아닙니다.
- 실제 투입인원은 계약서의 참여자 목록, 서명란, 출입자 명단, 인력배치표에서 확인하세요.
- 단가표의 행 수 ≠ 투입 인원 수. 단가표에 4등급이 있다고 4명이 아닙니다.
- 계약서에 "이용인원: N명"이 있으면 그 수를 기준으로 하세요.

## type 구분
- "직접" = GS네오텍 소속 자사 인원. GS네오텍 견적서/계약서에 기재된 인력 (파견 포함)
- "간접" = 외부 협력사 소속 인원. GS네오텍이 아닌 다른 회사 소속

## M/M이 없는 인원 (NOC, 야간관제 등)
- 산출내역서에 금액만 있고 M/M이 없는 항목(예: AWS MSP 야간, NOC)도 투입인원으로 포함하세요.
- 이 경우 months는 전부 0으로 설정하세요: [0,0,0,0,0,0,0,0,0,0,0,0]
- name은 "TBD", role은 문서에 적힌 업무명(예: "AWS MSP 야간관제(NOC)")을 사용하세요.

## 기타 규칙
- 역할, 등급은 문서에 명시된 경우만 기입
- 월별 M/M은 문서에 명시된 경우만. 없으면 0으로 설정 (추측해서 1.0으로 채우지 마세요)
- monthlyRate는 월 단가(원). 문서에 명시된 금액 사용
- 금액은 원 단위 정수`;

const JSON_SCHEMA = `다음 JSON 형식으로만 응답:
{
  "staffPlan": [
    {
      "name": "이름",
      "role": "역할 (PM/운영/개발 등)",
      "grade": "등급 (특급/고급/중급/초급)",
      "type": "직접|간접",
      "company": "소속회사 (자사면 'GS네오텍', 외부면 협력사명: 마이데이터, LSC시스템즈 등)",
      "months": [0,0,0,0,0,0,0,0,0,0,0,0],
      "monthlyRate": 0,
      "source": "출처"
    }
  ]
}

인원이 없으면 {"staffPlan": []}`;

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const { files, storedFiles } = parseFormFiles(formData);
    const content = await buildContent(files, storedFiles);
    content.push({ type: "text", text: `\n\n위 문서들에서 인원투입계획을 추출하세요.\n${JSON_SCHEMA}` });

    const { client, model } = getClient();
    const msg = await client.messages.create({
      model,
      max_tokens: 2000,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content }],
    });

    const raw = msg.content[0].type === "text" ? msg.content[0].text : "";
    const result = parseJSON(raw, { staffPlan: [] });
    return NextResponse.json(result);
  } catch (err) {
    console.error("[extract-people] error:", err);
    return NextResponse.json({ staffPlan: [], error: String(err) }, { status: 500 });
  }
}
