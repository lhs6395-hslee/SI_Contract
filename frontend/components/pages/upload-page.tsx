"use client";

import { useState, useRef, useCallback } from "react";
import { useApp } from "@/lib/store";
import { apiClassify, apiExtract, apiExtractCosts, apiExtractPeople, apiExtractSchedule, apiExtractRates, apiExtractOrg, apiUploadFiles } from "@/lib/api";
import type { UploadedFile, FileCategory, ExtractedData } from "@/lib/types";
import {
  CloudUpload, Check, X, AlertTriangle, Loader2,
  ChevronDown, ArrowRight, FolderOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

const CAT_LABEL: Record<FileCategory, string> = {
  contract: "계약서",
  internal: "견적품의서",
  vendor: "협력사 견적서",
  insurance: "보험료율 공문",
  unknown: "미분류",
};

const CAT_BADGE: Record<FileCategory, string> = {
  contract: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  internal: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  vendor: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  insurance: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  unknown: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

function classifyFileFallback(filename: string) {
  const n = filename.toLowerCase();
  if (/계약서|업무위탁|sla/.test(n)) return { category: "contract" as FileCategory, confidence: 0.65 };
  if (/견적품의|품의서/.test(n)) return { category: "internal" as FileCategory, confidence: 0.62 };
  if (/보험.*요율|보험료율|공문/.test(n)) return { category: "insurance" as FileCategory, confidence: 0.70 };
  if (/견적/.test(n)) return { category: "vendor" as FileCategory, confidence: 0.55 };
  return { category: "unknown" as FileCategory, confidence: 0.30 };
}

function getFileType(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  if (["docx", "doc"].includes(ext)) return "docx";
  if (["xlsx", "xls", "csv"].includes(ext)) return "xlsx";
  if (ext === "pdf") return "pdf";
  return ext;
}

export function UploadPage({ onComplete }: { onComplete?: (data: ExtractedData | null) => void } = {}) {
  const { setRoute, setIsNewProject, setExtractedData, setConflictCount, projectId } = useApp();
  const [name, setName] = useState("");
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [step, setStep] = useState(0);
  const [stepDetail, setStepDetail] = useState("");
  const [extractError, setExtractError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback((fileList: FileList) => {
    const arr = Array.from(fileList);
    const newFiles: UploadedFile[] = arr.map((f) => ({
      id: Date.now() + Math.random(),
      file: f,
      name: f.name,
      size: f.size,
      type: getFileType(f.name),
      category: "unknown",
      confidence: 0,
      classifying: true,
      reason: "",
    }));
    setFiles((prev) => [...prev, ...newFiles]);

    // Classify each file via API
    const classify = async (item: UploadedFile) => {
      try {
        const result = await apiClassify(item.file!);
        const final = result.category === "unknown" && result.confidence < 0.5
          ? { ...classifyFileFallback(item.name), reason: result.reason || "키워드 기반 추정" }
          : { category: result.category as FileCategory, confidence: result.confidence, reason: result.reason };
        setFiles((prev) => prev.map((x) =>
          x.id === item.id ? { ...x, ...final, classifying: false } : x
        ));
      } catch {
        const fb = classifyFileFallback(item.name);
        setFiles((prev) => prev.map((x) =>
          x.id === item.id ? { ...x, ...fb, classifying: false, reason: "분석 실패 — 파일명 기반" } as UploadedFile : x
        ));
      }
    };

    // Run 3 at a time
    const runBatch = async () => {
      const inflight: Promise<void>[] = [];
      for (const item of newFiles) {
        const p = classify(item).finally(() => {
          const idx = inflight.indexOf(p);
          if (idx >= 0) inflight.splice(idx, 1);
        });
        inflight.push(p);
        if (inflight.length >= 3) await Promise.race(inflight);
      }
      await Promise.all(inflight);
    };
    runBatch();
  }, []);

  const startExtract = async () => {
    setExtracting(true);
    setExtractError("");
    setStep(0);

    try {
      setStepDetail(`${files.length}개 파일에서 텍스트 추출 중…`);
      const realFiles = files.filter((f) => f.file).map((f) => f.file!);
      setStep(1);

      if (realFiles.length === 0) {
        setStepDetail("데모 데이터 사용");
        setStep(2);
        await new Promise((r) => setTimeout(r, 600));
        setStep(3);
        setTimeout(() => {
          if (onComplete) onComplete(null);
          else { setIsNewProject(false); setRoute("review"); }
        }, 400);
        return;
      }

      const hasScanPDF = files.some((f) => f.type === "pdf");
      const startTime = Date.now();
      setStepDetail(`Claude가 ${files.length}개 문서 분석 중…${hasScanPDF ? " (스캔 PDF 포함 — 시간이 더 걸릴 수 있음)" : ""}`);

      // 경과 시간 표시
      const timer = setInterval(() => {
        const elapsed = Math.round((Date.now() - startTime) / 1000);
        setStepDetail(`Claude가 ${files.length}개 문서 분석 중… ${elapsed}초 경과${hasScanPDF ? " (스캔 PDF Vision 처리 포함)" : ""}`);
      }, 1000);

      let extracted;
      try {
        extracted = await apiExtract(realFiles);
      } finally {
        clearInterval(timer);
      }
      setStep(2);

      setStepDetail("문서 간 일치 여부 검사");
      setStep(3);

      // 탭별 데이터 분리
      const { costItems, staffPlan, schedule, rates, organization, ...fields } = extracted as Record<string, unknown>;

      // 나머지 탭 병렬 추출 (파일이 서버에 저장된 후)
      setStepDetail("산출내역·인원·공정·요율·조직 추출 중…");
      const storedFiles = projectId ? { projectId, filenames: files.map((f) => f.name), revision: 0 } : undefined;
      const [costsRes, peopleRes, scheduleRes, ratesRes, orgRes] = await Promise.allSettled([
        apiExtractCosts([], storedFiles),
        apiExtractPeople(storedFiles),
        apiExtractSchedule(storedFiles),
        apiExtractRates(storedFiles),
        apiExtractOrg(storedFiles),
      ]);

      const result = {
        projectName: name,
        extracted: fields as Record<string, { value: string | number | null; source: string; confidence: "verified" | "guess" | "null" }>,
        costItems: (costsRes.status === "fulfilled" ? costsRes.value.items : costItems as ExtractedData["costItems"]) || [],
        staffPlan: (peopleRes.status === "fulfilled" ? peopleRes.value.staffPlan : staffPlan as ExtractedData["staffPlan"]) || [],
        schedule: (scheduleRes.status === "fulfilled" ? scheduleRes.value.schedule : schedule as ExtractedData["schedule"]) || [],
        rates: (ratesRes.status === "fulfilled" ? ratesRes.value.rates : rates as ExtractedData["rates"]) || undefined,
        organization: (orgRes.status === "fulfilled" ? orgRes.value.organization : organization as ExtractedData["organization"]) || [],
        conflicts: [],
        files: files.map((f) => ({ name: f.name, category: f.category, size: f.size })),
        _filesToSave: realFiles,
      };
      if (onComplete) {
        setTimeout(() => onComplete(result), 500);
      } else {
        setExtractedData(result);
        setConflictCount(0);
        setTimeout(() => {
          setIsNewProject(false);
          setRoute("review");
        }, 500);
      }
    } catch (err) {
      setExtractError(err instanceof Error ? err.message : "추출 중 오류가 발생했습니다");
    }
  };

  const removeFile = (id: number) => setFiles((f) => f.filter((x) => x.id !== id));
  const reclassify = (id: number, cat: FileCategory) =>
    setFiles((f) => f.map((x) => x.id === id ? { ...x, category: cat, confidence: 1.0, manual: true } : x));

  const counts = {
    contract: files.filter((f) => f.category === "contract").length,
    internal: files.filter((f) => f.category === "internal").length,
    vendor: files.filter((f) => f.category === "vendor").length,
    insurance: files.filter((f) => f.category === "insurance").length,
    unknown: files.filter((f) => f.category === "unknown").length,
  };
  const hasContract = counts.contract > 0;
  const hasInternal = counts.internal > 0;
  const canStart = name && hasContract && hasInternal && counts.unknown === 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold">새 집행계획서 작성</h1>
        <p className="text-sm text-muted-foreground mt-1">관련 문서를 한 번에 올리면 AI가 자동으로 분류합니다.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">프로젝트 정보</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <label className="text-sm font-medium">프로젝트명 <span className="text-destructive">*</span></label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="예) 퀘이사존 클라우드 운영" />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">문서 일괄 업로드</label>
            <div
              className={`rounded-lg border-2 border-dashed p-9 text-center cursor-pointer transition-colors ${
                dragOver ? "border-primary bg-primary/5" : "border-border hover:border-muted-foreground/30"
              }`}
              onDragEnter={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files); }}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.png,.jpg,.jpeg"
                onChange={(e) => { if (e.target.files?.length) handleFiles(e.target.files); e.target.value = ""; }}
              />
              <CloudUpload className="mx-auto h-7 w-7 text-muted-foreground mb-2" />
              <div className="text-sm font-medium">여러 파일을 한 번에 끌어놓거나 클릭하세요</div>
              <div className="text-xs text-muted-foreground mt-1">계약서 · 견적서 · 견적품의서 · 보험료율 공문서 등 — DOCX · PDF · XLSX · 이미지 지원</div>
              <div className="text-[11.5px] text-primary font-semibold mt-3">AI가 문서 종류를 자동으로 인식하고 분류합니다</div>
            </div>
          </div>

          {files.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold">업로드된 파일 {files.length}개</span>
                <div className="h-3 w-px bg-border" />
                <CategoryChip label="계약서" count={counts.contract} required ok={hasContract} />
                <CategoryChip label="견적품의서" count={counts.internal} required ok={hasInternal} />
                <CategoryChip label="협력사 견적서" count={counts.vendor} />
                <CategoryChip label="보험료율 공문" count={counts.insurance} />
                {counts.unknown > 0 && <CategoryChip label="미분류" count={counts.unknown} warn />}
              </div>
              <div className="space-y-1.5">
                {files.map((f) => (
                  <FileRow key={f.id} f={f} onRemove={removeFile} onReclassify={reclassify} />
                ))}
              </div>
            </div>
          )}

          {counts.unknown > 0 && (
            <Alert variant="destructive" className="bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-800">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <AlertTitle className="text-amber-800 dark:text-amber-200">{counts.unknown}개 파일을 분류하지 못했습니다</AlertTitle>
              <AlertDescription className="text-amber-700 dark:text-amber-300">파일별 드롭다운에서 종류를 직접 지정해 주세요.</AlertDescription>
            </Alert>
          )}

          {!hasContract && files.length > 0 && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>계약서가 필요합니다</AlertTitle>
              <AlertDescription>최소 1개의 계약서(DOCX/PDF)가 있어야 추출을 시작할 수 있습니다.</AlertDescription>
            </Alert>
          )}

          <div className="flex items-center justify-between pt-4 border-t">
            <Button variant="ghost" size="sm">
              <FolderOpen className="h-3.5 w-3.5 mr-1.5" /> 이전 프로젝트에서 가져오기
            </Button>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">{files.length}개 파일</span>
              <Button onClick={startExtract} disabled={!canStart} size="lg">
                추출 시작 <ArrowRight className="h-4 w-4 ml-1.5" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {extracting && (
        <ExtractModal step={step} stepDetail={stepDetail} error={extractError} fileCount={files.length}
          onCancel={() => { setExtracting(false); setExtractError(""); }} />
      )}
    </div>
  );
}

function CategoryChip({ label, count, required, ok, warn }: {
  label: string; count: number; required?: boolean; ok?: boolean; warn?: boolean;
}) {
  if (count === 0 && !required) return null;
  const variant = warn ? "destructive" : required ? (ok ? "default" : "destructive") : "secondary";
  return (
    <Badge variant={variant} className="text-[11px] gap-1">
      {required && ok && <Check className="h-2.5 w-2.5" />}
      {label} {count}
    </Badge>
  );
}

function FileRow({ f, onRemove, onReclassify }: {
  f: UploadedFile; onRemove: (id: number) => void; onReclassify: (id: number, cat: FileCategory) => void;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);

  return (
    <div className="relative flex items-center gap-3 rounded-lg border px-3 py-2.5 bg-card">
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded text-[10px] font-bold uppercase
        ${f.type === "pdf" ? "bg-red-100 text-red-700" : f.type === "docx" ? "bg-blue-100 text-blue-700" : "bg-emerald-100 text-emerald-700"}`}>
        {f.type}
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium truncate">{f.name}</div>
        <div className="text-[11px] text-muted-foreground">
          {(f.size / 1024).toFixed(0)} KB · {f.classifying ? "AI 분석 중…" : f.manual ? "수동 지정" : `AI 신뢰도 ${Math.round(f.confidence * 100)}%${f.reason ? " · " + f.reason : ""}`}
        </div>
      </div>
      {f.classifying ? (
        <Badge variant="secondary" className="gap-1"><Loader2 className="h-3 w-3 animate-spin" /> 분석 중</Badge>
      ) : (
        <button
          className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium cursor-pointer ${CAT_BADGE[f.category]}`}
          onClick={() => setPickerOpen((p) => !p)}
        >
          {CAT_LABEL[f.category]} <ChevronDown className="h-3 w-3" />
        </button>
      )}
      <button className="shrink-0 p-1 rounded hover:bg-muted text-muted-foreground" onClick={() => onRemove(f.id)}>
        <X className="h-3.5 w-3.5" />
      </button>
      {pickerOpen && (
        <div
          className="absolute right-14 top-full mt-1 w-40 rounded-md border bg-popover p-1 shadow-lg z-20"
          onMouseLeave={() => setPickerOpen(false)}
        >
          {(Object.entries(CAT_LABEL) as [FileCategory, string][])
            .filter(([k]) => k !== "unknown")
            .map(([k, label]) => (
              <button
                key={k}
                className="flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-[12.5px] hover:bg-accent"
                onClick={() => { onReclassify(f.id, k); setPickerOpen(false); }}
              >
                <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] ${CAT_BADGE[k]}`}>{label}</span>
                {f.category === k && <Check className="ml-auto h-3 w-3" />}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}

function ExtractModal({ step, stepDetail, error, fileCount, onCancel }: {
  step: number; stepDetail: string; error: string; fileCount: number; onCancel: () => void;
}) {
  const steps = [
    { name: "문서 파싱", desc: "PDF/DOCX/XLSX에서 텍스트 추출" },
    { name: "AI 값 추출", desc: "Claude가 12개 항목 자동 인식" },
    { name: "교차 검증", desc: "문서 간 값 일치 여부 검사" },
  ];
  const pct = Math.min(((step + (error ? 0 : 0.4)) / 3) * 100, 100);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-2xl">
        <h2 className="text-lg font-bold">{error ? "추출 중 오류 발생" : "AI가 문서를 분석 중입니다"}</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {error ? "아래 메시지를 확인하고 다시 시도해 주세요." : `${fileCount}개 문서 처리 중`}
        </p>

        <div className="mt-5 h-2 w-full rounded-full bg-muted overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-500 ${error ? "bg-destructive" : "bg-primary"}`} style={{ width: pct + "%" }} />
        </div>

        <div className="mt-5 space-y-3">
          {steps.map((s, i) => {
            const status = error && i === step ? "error" : i < step ? "done" : i === step ? "active" : "pending";
            return (
              <div key={i} className={`flex items-start gap-3 rounded-lg px-3 py-2.5 ${
                status === "active" ? "bg-primary/5" : status === "error" ? "bg-destructive/5" : ""
              }`}>
                <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white text-[11px] font-bold ${
                  status === "done" ? "bg-emerald-500" : status === "active" ? "bg-primary" : status === "error" ? "bg-destructive" : "bg-muted text-muted-foreground"
                }`}>
                  {status === "done" ? <Check className="h-3 w-3" /> : status === "active" ? <Loader2 className="h-3 w-3 animate-spin" /> : status === "error" ? <X className="h-3 w-3" /> : i + 1}
                </div>
                <div>
                  <div className="text-sm font-semibold">{s.name}</div>
                  <div className="text-xs text-muted-foreground">{status === "active" && stepDetail ? stepDetail : s.desc}</div>
                </div>
              </div>
            );
          })}
        </div>

        {error && (
          <>
            <Alert variant="destructive" className="mt-4">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>{error}</AlertTitle>
              <AlertDescription>파일 형식이 잘못되었거나 AI 호출이 실패했을 수 있습니다.</AlertDescription>
            </Alert>
            <div className="mt-4 flex justify-end">
              <Button variant="ghost" onClick={onCancel}>닫기</Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
