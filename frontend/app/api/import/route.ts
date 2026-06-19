import { createFormDataProxy } from "@/lib/proxy-handler";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const maxDuration = 120;

// 완성 집행계획서(PDF/xlsx) 역추출 → 0차 데이터. extract-* 와 동일한 FormData 프록시.
export const POST = createFormDataProxy({
  path: "/api/import",
  errorFallback: { extracted: {}, costItems: [], rates: null, importMeta: { unitGuessed: true, missingFields: [] } },
  label: "import",
});
