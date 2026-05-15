import { NextRequest, NextResponse } from "next/server";
import { getClient, parseJSON } from "@/lib/claude-client";

export const maxDuration = 120; // seconds
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";

const SYSTEM_PROMPT = `당신은 GS네오텍 SI/MSP 사업의 집행계획서 값 추출 전문가입니다.

## 할루시네이션 방지 (최우선 규칙)
- **문서에 적힌 텍스트와 숫자만 사용하세요.** 존재하지 않는 이름, 금액, 항목을 절대 만들어내지 마세요.
- 확신이 없으면 null 또는 빈 배열로 두세요. 빠뜨리는 것이 만들어내는 것보다 낫습니다.
- 스캔 문서에서 글자를 정확히 읽을 수 없으면 confidence: "guess"로 표시하세요.
- **취소선이 그어진 항목은 삭제된 것입니다. 절대 추출하지 마세요.** 가로줄이 텍스트를 가로지르면 취소선입니다.

## 문서 우선순위 (중요)
동일 정보가 여러 문서에 있으면 다음 순서로 우선 적용:
1. **표준계약검토서** — 사업명(계약명), 발주처/계약처, 계약방법, 수금조건, 계약금액, 계약기간의 최종 확정 문서
2. **견적품의서** — 매출/매입/영업이익 금액, 사업특성, 추진사유
3. **계약서/부속계약서** — 계약기간, 업무범위
4. **견적서** — 단가, 수량

## 중요 규칙
1. **사업명(projectName)** = 표준계약검토서의 "계약명" 필드를 최우선 사용. 없으면 견적품의서 프로젝트명.
2. **발주처/계약처** = 표준계약검토서의 "고객(발주처)"/"고객(계약처)" 사용. **법인격 접미사(주식회사, ㈜ 등)를 제거하고 약칭만 사용** (예: "퀘이사존 주식회사" → "퀘이사존").
3. **매출(revenue)** = 발주처가 GS네오텍에 지급하는 **계약 총 금액** (VAT 별도). 견적품의서의 "총 매출" 또는 견적서의 "계약기간 총 금액" 참조. 월 금액이면 ×계약월수로 환산.
4. **매입(cost)** = GS네오텍이 외부(협력사/AWS 등)에 지출하는 비용 합계. 견적품의서의 "합계" 또는 "총 매입" 참조.
5. **영업이익(profit)** = 견적품의서에 명시된 영업이익 금액을 직접 추출. 매출-매입으로 단순 계산하지 마세요. 간접비+일반관리비가 차감된 후의 값.
6. 견적서에 "인건비 합계"와 "견적 합계"가 별도로 있으면, **견적 합계(전체)** 가 매출이지 인건비 소계가 아님.
7. **계약방법(contractType)** = "수의", "경쟁", "제안", "지명" 등 **간결하게** 표기. 표준계약검토서의 체크박스(■ 수의) 또는 견적품의서 상단 체크박스 참조. "수의계약"이 아니라 "수의"로.
8. **PM** = 프로젝트 매니저/현장소장. "PM", "현장소장", "Project Manager"로 명확히 표기된 경우만 추출. **영업담당자와 다른 사람임에 주의.**
9. **영업담당자(salesOwner)** = 견적서 "영업담당"/"견적 및 영업담당" 란의 이름. PM과는 다른 역할. 견적서나 수정견적서 하단의 "담당자"/"매니저" 이름.
10. **수금조건(paymentTerms)** = 대금 수금 방식. 견적품의서 공사개요 시트의 "수금 조건" 필드를 최우선 사용 (예: "전자세금계산서 발행 후 30일 이내 현금 지급"). 없으면 표준계약검토서 "지불조건" → 계약서 대금지급 조항 순으로. 확실하지 않으면 null.
11. 금액 단위 주의: 천원 단위면 ×1000으로 원 단위 환산.
12. **costItems(산출내역)**: 견적서/견적품의서에서 개별 비용 항목(수수료, 인건비, 재료비 등)을 모두 추출. 행별 품명/규격/수량/단가/금액을 그대로.
13. **staffPlan(인원투입계획)**: 실제 투입 인원만 추출. **할루시네이션 금지**: 문서에 적힌 실명만 name에 기입. 이름이 없거나 읽을 수 없으면 "TBD". 이름을 절대 만들어내지 마세요. **견적서의 등급별(특급/고급/중급/초급) 단가표는 단가 기준표이지 실제 투입인력 목록이 아닙니다.** 계약서의 참여자/서명란/출입자 명단에서 실제 인원을 확인하세요. 확신 없으면 빠뜨리는 것이 만들어내는 것보다 낫습니다.
14. **schedule(공정표)**: 공종별 시작/종료 월. 문서에 없으면 빈 배열.
15. **rates(요율)**: 간접비율, 일반관리비율, 4대보험 요율. 보험료율 공문이나 견적품의서에서.
16. **organization(현장조직)**: 역할별 담당자. 계약서 서명란/참여자 목록/조직도에서만 추출. **이름을 만들어내지 마세요.** 문서에 없으면 빈 배열.`;

const JSON_SCHEMA = `다음 JSON 형식으로만 응답 (다른 텍스트 없이):
{
  "projectName":   {"value": "사업명", "source": "출처", "confidence": "verified|guess|null"},
  "client":        {"value": "발주처", "source": "...", "confidence": "..."},
  "contractor":    {"value": "계약처", "source": "...", "confidence": "..."},
  "contractType":  {"value": "계약방법", "source": "...", "confidence": "..."},
  "paymentTerms":  {"value": "수금조건", "source": "...", "confidence": "..."},
  "pm":            {"value": "PM", "source": "...", "confidence": "..."},
  "salesOwner":    {"value": "영업담당자", "source": "...", "confidence": "..."},
  "startDate":     {"value": "YYYY.MM.DD", "source": "...", "confidence": "..."},
  "endDate":       {"value": "YYYY.MM.DD", "source": "...", "confidence": "..."},
  "revenue":       {"value": 0, "unit": "원", "source": "...", "confidence": "..."},
  "cost":          {"value": 0, "unit": "원", "source": "...", "confidence": "..."},
  "profit":        {"value": 0, "unit": "원", "source": "...", "confidence": "..."},
  "profitRate":    {"value": 0, "unit": "%", "source": "...", "confidence": "..."},
  "indirectCost":  {"value": 0, "unit": "원", "source": "...", "confidence": "..."},
  "scope":         {"value": "사업범위", "source": "...", "confidence": "..."},
  "specialNotes":  {"value": "특기사항", "source": "...", "confidence": "..."},
  "fiscalYear":    {"value": "YYYY (4자리 연도, 숫자만)", "source": "...", "confidence": "..."},
  "writtenDate":   {"value": "YYYY.MM.DD", "source": "...", "confidence": "..."},

  "costItems": [
    {"category": "fee|material|labor|supply|line|travel|other", "name": "품명", "spec": "규격", "unit": "단위", "contractQty": 0, "contractPrice": 0, "contractAmount": 0, "executionQty": 0, "executionPrice": 0, "executionAmount": 0, "source": "출처", "confidence": "verified|guess"}
  ],

  "staffPlan": [
    {"name": "이름", "role": "역할(PM/운영/개발 등)", "grade": "등급(특급/고급/중급/초급)", "type": "직접|간접", "company": "소속회사(자사면 GS네오텍, 외부면 협력사명)", "months": [0,0,0,0,0,0,0,0,0,0,0,0], "monthlyRate": 0, "source": "출처"}
  ],

  "schedule": [
    {"name": "공종명", "startMonth": 0, "endMonth": 11, "source": "출처"}
  ],

  "rates": {
    "indirectRate": {"value": 0, "source": "..."},
    "adminRate": {"value": 0, "source": "..."},
    "nationalPension": {"value": 0, "source": "..."},
    "healthInsurance": {"value": 0, "source": "..."},
    "employmentInsurance": {"value": 0, "source": "..."},
    "industrialAccident": {"value": 0, "source": "..."}
  },

  "organization": [
    {"role": "PM|기술리드|운영|영업 등", "name": "이름", "scope": "업무범위", "lead": true|false}
  ]
}

규칙:
- null이면 {"value": null, "source": "", "confidence": "null"}
- 숫자는 **원 단위 정수**. 천원이면 ×1000.
- profit = 영업이익 (문서에 명시된 값, 단순 계산 금지)
- costItems: 개별 비용 행. fee=수수료, material=재료비, labor=노무비, supply=소모품비, line=회선비, travel=여비교통비, other=기타. 월 단가면 ×계약월수 환산.
- staffPlan: 투입 인원. months는 1월~12월 M/M 배열. monthlyRate는 월 단가(원).
- schedule: 공정표. startMonth/endMonth는 0~11 (0=계약시작월).
- rates: 요율(%). 보험료율 공문이나 견적품의서에서 추출.
- organization: 현장조직. 문서에서 역할/이름 매핑.
- fiscalYear: 계약 시작일(startDate)의 연도(4자리 숫자만, "년" 제외). 예: 시작일이 2026-03-23이면 fiscalYear = "2026".
- writtenDate: 견적서 또는 견적품의서 작성일.
- 문서에 없는 항목은 빈 배열 [] 또는 값 0으로.`;

// 업로드된 File 또는 저장된 파일(projectId+filename)에서 텍스트/이미지 추출하여 content에 추가
async function addFileToContent(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  content: any[], docIdx: number, filename: string,
  opts: { file?: File; projectId?: string; revision?: number },
) {
  const ext = filename.split(".").pop()?.toLowerCase();

  // 텍스트 추출
  let text = "";
  if (opts.file) {
    try {
      const parseForm = new FormData();
      parseForm.append("file", opts.file);
      const parseRes = await fetch(`${FASTAPI}/api/parse`, { method: "POST", body: parseForm });
      if (parseRes.ok) { text = (await parseRes.json()).text || ""; }
    } catch { /* */ }
  } else if (opts.projectId) {
    try {
      const revParam = opts.revision != null ? `?revision=${opts.revision}` : "";
      const parseRes = await fetch(`${FASTAPI}/api/parse-stored/${opts.projectId}/${encodeURIComponent(filename)}${revParam}`, { method: "POST" });
      if (parseRes.ok) { text = (await parseRes.json()).text || ""; }
    } catch { /* */ }
  }

  // 이미지 PDF → Vision
  const isImagePDF = ext === "pdf" && (!text.trim() || text.includes("Vision 분석 필요"));
  if (isImagePDF) {
    let images: string[] = [];
    if (opts.file) {
      try {
        const imgForm = new FormData();
        imgForm.append("file", opts.file);
        const imgRes = await fetch(`${FASTAPI}/api/parse-images`, { method: "POST", body: imgForm });
        if (imgRes.ok) { images = (await imgRes.json()).images || []; }
      } catch { /* */ }
    } else if (opts.projectId) {
      try {
        const revParam = opts.revision != null ? `?revision=${opts.revision}` : "";
        const imgRes = await fetch(`${FASTAPI}/api/parse-stored-images/${opts.projectId}/${encodeURIComponent(filename)}${revParam}`, { method: "POST" });
        if (imgRes.ok) { images = (await imgRes.json()).images || []; }
      } catch { /* */ }
    }
    if (images.length > 0) {
      content.push({ type: "text", text: `\n[문서 ${docIdx}: ${filename} — 스캔 이미지 ${images.length}페이지]` });
      for (const img of images.slice(0, 5)) {
        content.push({ type: "image", source: { type: "base64", media_type: "image/png", data: img } });
      }
      return;
    }
  }

  // 텍스트 블록
  content.push({
    type: "text",
    text: text
      ? `\n[문서 ${docIdx}: ${filename}]\n${text}`
      : `\n[문서 ${docIdx}: ${filename}] (텍스트 추출 불가)`,
  });
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

    const hasNewFiles = files.length > 0;
    const hasStoredFiles = storedFiles && storedFiles.filenames.length > 0;

    if (!hasNewFiles && !hasStoredFiles) {
      return NextResponse.json({ error: "files required" }, { status: 400 });
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const content: any[] = [];
    let docIdx = 1;

    // 저장된 파일 처리
    if (storedFiles) {
      for (const fname of storedFiles.filenames) {
        await addFileToContent(content, docIdx++, fname, { projectId: storedFiles.projectId, revision: storedFiles.revision });
      }
    }

    // 새로 업로드된 파일 처리
    for (const file of files) {
      await addFileToContent(content, docIdx++, file.name, { file });
    }

    // 마지막에 추출 지시
    content.push({ type: "text", text: `\n\n위 문서들에서 집행계획서 필드를 추출하세요.\n${JSON_SCHEMA}` });

    const { client, model } = getClient();
    const msg = await client.messages.create({
      model,
      max_tokens: 8000,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content }],
    });

    const raw = msg.content[0].type === "text" ? msg.content[0].text : "";
    const result = parseJSON(raw, {} as Record<string, unknown>) as Record<string, { value: unknown; source: string; confidence: string }>;

    // 2단계: null인 필드가 있고 스캔 이미지가 포함되어 있으면 재질문
    const nullFields = Object.entries(result)
      .filter(([, v]) => v && typeof v === "object" && (v.value == null || v.value === ""))
      .map(([k]) => k);

    const hasImageContent = content.some((c: { type: string }) => c.type === "image");

    if (nullFields.length > 0 && hasImageContent) {
      const fieldLabels: Record<string, string> = {
        contractType: "계약방법 (수의계약/경쟁입찰/제안/지명 — 체크박스 확인)",
        paymentTerms: "수금조건 — '대금수금조건'이라고 적힌 항목을 찾으세요. 취소선이 그어진 값이 있고 그 옆에 손글씨가 있으면 손글씨 값이 최종값입니다. 취소선이 없으면 인쇄된 값을 사용. '대금수금조건' 항목이 없으면 이 필드를 생략하세요.",
        pm: "PM 이름과 직급 (PM, 현장소장, Project Manager로 명시된 경우만)",
        salesOwner: "영업담당자",
        scope: "사업범위",
        specialNotes: "특기사항",
      };

      const targetFields = nullFields.filter((k) => k in fieldLabels);
      if (targetFields.length > 0) {
        const followUp = targetFields.map((k) => `- ${fieldLabels[k]}`).join("\n");
        const imageContent = content.filter((c: { type: string }) => c.type === "image" || c.type === "text");

        try {
          const msg2 = await client.messages.create({
            model,
            max_tokens: 500,
            system: `스캔 문서에서 누락된 필드를 찾아주세요.

중요 규칙:
- 실제로 문서에 보이는 텍스트만 추출하세요.
- 존재하지 않는 이름, 숫자, 텍스트를 절대 만들어내지 마세요.
- 손글씨를 정확히 읽을 수 없으면 confidence를 "guess"로 표시하세요.
- 문서에서 찾을 수 없는 항목은 포함하지 마세요 (빈 JSON {} 반환 가능).`,
            messages: [{
              role: "user",
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              content: [...imageContent as any[], {
                type: "text",
                text: `다음 항목들이 아직 추출되지 않았습니다. 스캔 문서에서 실제로 보이는 텍스트에서만 찾아주세요. 찾을 수 없으면 해당 필드를 생략하세요:\n${followUp}\n\nJSON으로만 응답 (실제로 찾은 필드만, 추측 금지):\n{"필드명": {"value": "값", "source": "문서 내 정확한 위치", "confidence": "verified|guess"}}`,
              }],
            }],
          });

          const raw2 = msg2.content[0].type === "text" ? msg2.content[0].text : "";
          const extra = parseJSON(raw2, {}) as Record<string, { value: unknown; source: string; confidence: string }>;

          // 병합
          for (const [k, v] of Object.entries(extra)) {
            if (v && v.value != null && v.value !== "" && k in result) {
              result[k] = v;
            }
          }
        } catch (e) {
          console.warn("[extract] follow-up failed:", e);
        }
      }
    }

    return NextResponse.json(result);
  } catch (err) {
    console.error("[extract] error:", err);
    return NextResponse.json(
      { error: `서버 오류: ${err instanceof Error ? err.message : "unknown"}` },
      { status: 500 },
    );
  }
}
