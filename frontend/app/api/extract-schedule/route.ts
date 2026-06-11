import { createFormDataProxy } from "@/lib/proxy-handler";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";
export const maxDuration = 120;

export const POST = createFormDataProxy({
  path: "/api/extract-schedule",
  errorFallback: { schedule: [] },
  label: "extract-schedule",
});
