"use client";

import { useState, useEffect } from "react";
import { useApp } from "@/lib/store";
import { fmt } from "@/lib/format";
import type { ProjectStatus } from "@/lib/types";
import {
  Check, X, ArrowRight, ArrowLeft, Download,
  Pencil, Plus, ChevronRight, Loader2, CloudUpload, Lock, AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Textarea } from "@/components/ui/textarea";
import { apiExport, apiStartPipeline, apiPipelineResult, apiSyncRevision } from "@/lib/api";
import type { PipelineResult } from "@/lib/api";

// ─── Conflicts ───
export function ConflictsPage() {
  const { setRoute, setConflictCount, extractedData, setExtractedData } = useApp();
  const rawConflicts = extractedData?.conflicts || [];

  // picks: conflict index → "A" | "B" | "custom"
  const [picks, setPicks] = useState<Record<number, "A" | "B" | "custom">>({});
  const [customValues, setCustomValues] = useState<Record<number, string>>({});
  const [showCustom, setShowCustom] = useState<Record<number, boolean>>({});

  // 충돌이 없으면 안내
  if (rawConflicts.length === 0) {
    return (
      <div className="space-y-5">
        <div>
          <h1 className="text-xl font-bold">충돌 해결</h1>
          <p className="text-sm text-muted-foreground mt-1">견적서 간 값이 다른 항목입니다.</p>
        </div>
        <Card>
          <div className="py-16 text-center">
            <Check className="mx-auto h-8 w-8 text-emerald-500 mb-3" />
            <div className="text-sm font-semibold">충돌이 없습니다</div>
            <div className="text-xs text-muted-foreground mt-1">AI 추출 결과에서 값 충돌이 감지되지 않았습니다.</div>
            <Button className="mt-4" variant="outline" onClick={() => setRoute("review")}>리뷰로 돌아가기</Button>
          </div>
        </Card>
      </div>
    );
  }

  const resolvedCount = Object.keys(picks).length;
  const allResolved = resolvedCount === rawConflicts.length;

  const handleResolve = () => {
    // 선택된 값으로 extractedData 업데이트
    if (!extractedData) return;
    const updated = { ...extractedData };
    rawConflicts.forEach((c, i) => {
      const pick = picks[i];
      if (!pick || !c.field) return;
      let resolvedValue: unknown;
      if (pick === "A") resolvedValue = c.valueA ?? c.values?.[0];
      else if (pick === "B") resolvedValue = c.valueB ?? c.values?.[1];
      else resolvedValue = customValues[i];

      if (c.field && updated.extracted?.[c.field]) {
        updated.extracted = {
          ...updated.extracted,
          [c.field]: { ...updated.extracted[c.field], value: resolvedValue as string | number | null, confidence: "verified" as const },
        } as typeof updated.extracted;
      }
    });
    updated.conflicts = [];
    setExtractedData(updated);
    setConflictCount(0);
    setRoute("review");
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold">충돌 해결</h1>
        <p className="text-sm text-muted-foreground mt-1">견적서 간 값이 다른 항목입니다. 사용할 값을 선택하거나 직접 입력해 주세요.</p>
      </div>

      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>{rawConflicts.length}건의 충돌이 감지되었습니다</AlertTitle>
        <AlertDescription>모든 충돌을 해결해야 익스포트할 수 있습니다.</AlertDescription>
      </Alert>

      <div className="space-y-3">
        {rawConflicts.map((c, i) => {
          const optA = { src: c.sourceA || c.sources?.[0] || "출처 A", v: c.valueA ?? c.values?.[0] };
          const optB = { src: c.sourceB || c.sources?.[1] || "출처 B", v: c.valueB ?? c.values?.[1] };
          const isCustomOpen = showCustom[i];
          return (
            <Card key={i}>
              <CardHeader>
                <CardTitle className="text-base">{c.field || c.message || `충돌 항목 ${i + 1}`}</CardTitle>
                {c.message && c.field && <p className="text-xs text-muted-foreground mt-1">{c.message}</p>}
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3">
                  {[{ opt: optA, key: "A" as const }, { opt: optB, key: "B" as const }].map(({ opt, key }) => {
                    const active = picks[i] === key;
                    const displayVal = typeof opt.v === "number" ? fmt(opt.v) + " 원" : String(opt.v ?? "-");
                    return (
                      <button key={key} onClick={() => { setPicks((p) => ({ ...p, [i]: key })); setShowCustom((s) => ({ ...s, [i]: false })); }}
                        className={`rounded-lg border-2 p-4 text-left transition-colors ${
                          active ? "border-primary bg-primary/5" : "border-border hover:border-muted-foreground/30"
                        }`}>
                        <div className="flex items-center gap-2 mb-2">
                          <div className={`h-4 w-4 rounded-full border-2 flex items-center justify-center shrink-0 ${active ? "border-primary" : "border-muted-foreground/30"}`}>
                            {active && <div className="h-2 w-2 rounded-full bg-primary" />}
                          </div>
                          <span className="text-xs font-semibold text-muted-foreground truncate">{opt.src}</span>
                        </div>
                        <div className="text-lg font-bold font-mono">{displayVal}</div>
                      </button>
                    );
                  })}
                </div>
                <div className="mt-2">
                  {isCustomOpen ? (
                    <div className="flex gap-2 mt-2">
                      <input
                        className="flex-1 rounded border px-2 py-1 text-sm"
                        placeholder="직접 입력"
                        value={customValues[i] ?? ""}
                        onChange={(e) => setCustomValues((v) => ({ ...v, [i]: e.target.value }))}
                        onKeyDown={(e) => { if (e.key === "Enter") setPicks((p) => ({ ...p, [i]: "custom" })); }}
                      />
                      <Button size="sm" onClick={() => setPicks((p) => ({ ...p, [i]: "custom" }))}>확인</Button>
                    </div>
                  ) : (
                    <Button variant="ghost" size="sm" onClick={() => { setShowCustom((s) => ({ ...s, [i]: true })); setPicks((p) => ({ ...p, [i]: "custom" })); }}>
                      <Pencil className="h-3 w-3 mr-1" /> 직접 입력
                    </Button>
                  )}
                </div>
                {picks[i] && (
                  <p className="text-xs text-emerald-600 mt-2 font-medium">
                    ✓ {picks[i] === "A" ? optA.src : picks[i] === "B" ? optB.src : "직접 입력"} 선택됨
                  </p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="flex items-center justify-between rounded-lg border bg-card px-6 py-4">
        <span className="text-sm text-muted-foreground">{resolvedCount}/{rawConflicts.length} 해결됨</span>
        <Button onClick={handleResolve} disabled={!allResolved}>
          해결 완료 · 리뷰로 <ArrowRight className="h-3.5 w-3.5 ml-1" />
        </Button>
      </div>
    </div>
  );
}

// ─── Export ───
export function ExportPage() {
  const { setRoute, extractedData, projectId, revision, locked, setLocked } = useApp();
  const [downloaded, setDownloaded] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null);
  const [generating, setGenerating] = useState(false);
  const isAdmin = true; // TODO: 실제 권한 체크로 교체

  // 이전 파이프라인 결과 자동 로드
  useEffect(() => {
    if (!projectId) return;
    (async () => {
      try {
        const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";
        const res = await fetch(`${FASTAPI}/api/pipeline/${projectId}/status`);
        if (res.ok) {
          const state = await res.json();
          if (state?.output_file) {
            setPipelineResult({
              projectId,
              status: state.status || "completed",
              steps: state.step_results || {},
              review: state.review_results?.[state.review_results.length - 1] || null,
              outputFile: state.output_file,
              error: state.error || null,
            });
          }
        }
      } catch { /* 이전 결과 없음 */ }
    })();
  }, [projectId]);

  const E = extractedData?.extracted || {};
  const confirmed = extractedData?.confirmedTabs || [];
  const costItems = extractedData?.costItems || [];
  const staffPlan = extractedData?.staffPlan || [];
  const schedule = extractedData?.schedule || [];
  const org = extractedData?.organization || [];
  const rates = extractedData?.rates;

  const basicOk = confirmed.includes("basic") || Object.values(E).filter((v) => v?.value != null && v.value !== "").length > 5;
  const calcOk = confirmed.includes("calc") || costItems.length > 0;
  const ratesOk = confirmed.includes("rates") || (rates != null);
  const peopleOk = confirmed.includes("people") || staffPlan.length > 0;
  const scheduleOk = confirmed.includes("schedule") || schedule.length > 0;
  const orgOk = confirmed.includes("org") || org.length > 0;

  const checks = [
    { status: basicOk ? "ok" : "warn", title: "기본 정보", desc: basicOk ? "필수 항목 입력 완료" : "미입력 항목 있음", tab: "basic" },
    { status: calcOk ? "ok" : "warn", title: "산출내역", desc: calcOk ? `${costItems.length}개 항목` : "항목 없음", tab: "calc" },
    { status: ratesOk ? "ok" : "warn", title: "요율 설정", desc: ratesOk ? "입력 완료" : "미입력", tab: "rates" },
    { status: peopleOk ? "ok" : "info", title: "인원투입계획", desc: peopleOk ? `${staffPlan.length}명` : "선택사항", tab: "people" },
    { status: scheduleOk ? "ok" : "warn", title: "공정표", desc: scheduleOk ? `${schedule.length}개 공종` : "미작성", tab: "schedule" },
    { status: orgOk ? "ok" : "warn", title: "현장조직", desc: orgOk ? `${org.length}명` : "미구성", tab: "org" },
  ];
  const okCount = checks.filter((c) => c.status === "ok").length;
  const totalReq = checks.filter((c) => c.status !== "info").length;

  const doGenerate = async () => {
    if (!projectId || !extractedData) return;
    setGenerating(true);
    setDownloaded(false);
    try {
      // 파이프라인 실행 전 현재 차수 최신 데이터를 서버에 동기화
      await apiSyncRevision(projectId, revision, extractedData as unknown as Record<string, unknown>);
      const result = await apiStartPipeline(projectId, extractedData as unknown as Record<string, unknown>, revision);
      setPipelineResult(result);
      // 생성 완료 후 자동 다운로드
      const pid = result?.projectId || projectId;
      setDownloading(true);
      try {
        const blob = await apiPipelineResult(pid);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${extractedData?.projectName || "집행계획서"}_집행계획서.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setDownloaded(true);
      } catch (err) {
        alert(`다운로드 실패: ${err instanceof Error ? err.message : "unknown"}`);
      } finally {
        setDownloading(false);
      }
    } catch (err) {
      alert(`파이프라인 실패: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      setGenerating(false);
    }
  };

  const doDownload = async () => {
    // 값이 바뀌었을 수 있으므로 항상 파이프라인을 새로 돌림
    await doGenerate();
  };

  const statusColors: Record<string, string> = {
    ok: "bg-emerald-500", warn: "bg-amber-500", err: "bg-red-500", info: "bg-muted-foreground/30",
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold">검증 및 익스포트</h1>
        <p className="text-sm text-muted-foreground mt-1">집행계획서를 엑셀 양식으로 내보냅니다.</p>
      </div>

      <Alert className="border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20">
        <Check className="h-4 w-4 text-emerald-600" />
        <AlertTitle className="text-emerald-800 dark:text-emerald-200">필수 항목 {okCount}/{totalReq} 완료 · 익스포트 가능</AlertTitle>
        <AlertDescription className="text-emerald-700 dark:text-emerald-300">경고 항목이 있어도 그대로 내보낼 수 있습니다.</AlertDescription>
      </Alert>

      <div className="grid grid-cols-[1.5fr_1fr] gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">시트별 검증</CardTitle></CardHeader>
          <CardContent className="space-y-0">
            {checks.map((c, i) => (
              <div key={i} className="flex items-center gap-3 py-3 border-b last:border-0">
                <div className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-white ${statusColors[c.status]}`}>
                  {c.status === "ok" ? <Check className="h-3 w-3" /> : c.status === "info" ? <span className="text-[9px]">○</span> : <span className="text-[10px] font-bold">!</span>}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-semibold">{c.title}</div>
                  <div className="text-xs text-muted-foreground">{c.desc}</div>
                </div>
                {c.status !== "ok" && c.status !== "info" && <Button variant="ghost" size="sm" className="text-xs" onClick={() => setRoute("review")}>이동 →</Button>}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="sticky top-20 self-start">
          <div className="rounded-t-xl bg-foreground text-background px-5 py-4">
            <div className="text-[11px] opacity-60 font-semibold uppercase tracking-wider">요약</div>
            <div className="text-base font-bold mt-0.5">{extractedData?.projectName || "프로젝트"}</div>
            <div className="text-xs opacity-70">최초(0차)</div>
          </div>
          <CardContent className="pt-4 space-y-4">
            <div className="grid grid-cols-[1fr_auto] gap-y-2 text-sm">
              <span className="text-muted-foreground">매출</span><span className="text-right font-mono font-semibold">{E.revenue?.value ? fmt(E.revenue.value as number) + " 원" : "-"}</span>
              <span className="text-muted-foreground">매입</span><span className="text-right font-mono font-semibold">{E.cost?.value ? fmt(E.cost.value as number) + " 원" : "-"}</span>
              <span className="text-muted-foreground">영업이익</span><span className={`text-right font-mono font-bold ${E.profit?.value && (E.profit.value as number) > 0 ? "text-emerald-600" : E.profit?.value && (E.profit.value as number) < 0 ? "text-red-600" : ""}`}>{E.profit?.value ? fmt(E.profit.value as number) + " 원" : E.revenue?.value && E.cost?.value ? fmt((E.revenue.value as number) - (E.cost.value as number)) + " 원" : "-"}</span>
              <span className="text-muted-foreground">이익률</span><span className={`text-right font-mono font-bold ${E.profitRate?.value && (E.profitRate.value as number) > 0 ? "text-emerald-600" : ""}`}>{E.profitRate?.value ? E.profitRate.value + "%" : E.revenue?.value && E.cost?.value ? (((E.revenue.value as number) - (E.cost.value as number)) / (E.revenue.value as number) * 100).toFixed(1) + "%" : "-"}</span>
            </div>
            <div className="h-px bg-border" />

            <Button className="w-full" size="lg" onClick={doGenerate} disabled={generating || downloading}>
              {generating ? <><Loader2 className="h-4 w-4 animate-spin mr-2" /> 집행계획서 생성 중…</> :
                downloading ? <><Loader2 className="h-4 w-4 animate-spin mr-2" /> 다운로드 중…</> :
                <><Download className="h-4 w-4 mr-2" /> 결과 파일 생성 · 다운로드</>}
            </Button>

            {downloaded && <p className="text-center text-xs text-emerald-600 font-semibold">{extractedData?.projectName}_집행계획서.xlsx 다운로드 완료</p>}
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center justify-between rounded-lg border bg-card px-6 py-4">
        <Button variant="ghost" onClick={() => setRoute("review")}><ArrowLeft className="h-3.5 w-3.5 mr-1" /> 리뷰로</Button>
        {locked ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-amber-600 font-medium flex items-center gap-1"><Lock className="h-3.5 w-3.5" /> 프로젝트 잠김</span>
            {isAdmin && <Button variant="outline" size="sm" onClick={() => setLocked(false)}>잠금 해제 (관리자)</Button>}
          </div>
        ) : (
          <Button variant="outline" onClick={() => { if (confirm("프로젝트를 잠그면 수정할 수 없습니다. 관리자만 해제할 수 있습니다.\n계속하시겠습니까?")) setLocked(true); }}>완료 · 프로젝트 잠금</Button>
        )}
      </div>
    </div>
  );
}

// ─── Projects ───
export function ProjectsPage() {
  const { projects, setProjectId, setRoute, setIsNewProject } = useApp();
  const statusLabel: Record<ProjectStatus, { text: string; variant: "default" | "secondary" | "destructive" }> = {
    "in-progress": { text: "진행중", variant: "default" },
    done: { text: "완료", variant: "secondary" },
    urgent: { text: "긴급", variant: "destructive" },
    locked: { text: "잠김", variant: "secondary" },
  };
  const statusColor: Record<ProjectStatus, string> = {
    "in-progress": "bg-blue-500", done: "bg-emerald-500", urgent: "bg-red-500", locked: "bg-amber-500",
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">프로젝트 목록</h1>
          <p className="text-sm text-muted-foreground mt-1">전체 {projects.length}개 프로젝트</p>
        </div>
        <Button onClick={() => { setIsNewProject(true); setRoute("upload"); }}><Plus className="h-3.5 w-3.5 mr-1" /> 새 프로젝트</Button>
      </div>
      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-muted-foreground">
              <th className="text-left py-3 px-4 font-medium">프로젝트명</th>
              <th className="text-left py-3 px-4 font-medium">발주처</th>
              <th className="text-left py-3 px-4 font-medium">차수</th>
              <th className="text-right py-3 px-4 font-medium">매출</th>
              <th className="text-left py-3 px-4 font-medium">상태</th>
              <th className="text-left py-3 px-4 font-medium">최종 수정</th>
              <th className="py-3 px-4"></th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id} className="border-b hover:bg-muted/50 cursor-pointer"
                onClick={() => { setProjectId(p.id); setIsNewProject(false); setRoute("review"); }}>
                <td className="py-3 px-4 font-semibold">
                  <span className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${statusColor[p.status]}`} />
                    {p.name}
                  </span>
                </td>
                <td className="py-3 px-4">{p.client}</td>
                <td className="py-3 px-4"><Badge variant="secondary">{p.revision}차</Badge></td>
                <td className="py-3 px-4 text-right font-mono">{fmt(p.revenue)} 원</td>
                <td className="py-3 px-4"><Badge variant={statusLabel[p.status].variant}>{statusLabel[p.status].text}</Badge></td>
                <td className="py-3 px-4 text-xs text-muted-foreground">{p.updated}</td>
                <td className="py-3 px-4"><ChevronRight className="h-4 w-4 text-muted-foreground" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ─── Notifications ───
export function NotificationsPage() {
  return (
    <div className="space-y-5">
      <div><h1 className="text-xl font-bold">알림</h1><p className="text-sm text-muted-foreground mt-1">알림이 없습니다</p></div>
      <Card>
        <div className="py-16 text-center">
          <div className="text-sm font-semibold">새로운 알림이 없습니다</div>
          <div className="text-xs text-muted-foreground mt-1">프로젝트 기한, AI 추출 결과, 충돌 감지 등의 알림이 여기에 표시됩니다.</div>
        </div>
      </Card>
    </div>
  );
}

// ─── Add Revision Modal ───
export function AddRevisionModal({ onClose, onAdd }: {
  onClose: () => void;
  onAdd: (reason: string, type: string, files: File[]) => void;
}) {
  const [type, setType] = useState("revise");
  const [reason, setReason] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useState<HTMLInputElement | null>(null);

  const handleFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    setFiles((prev) => [...prev, ...Array.from(incoming)]);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const canSubmit = reason.trim().length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="w-full max-w-md rounded-xl border bg-card p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold">수정/이월 차수 추가</h2>
        <p className="text-sm text-muted-foreground mt-1">현재 차수의 데이터는 잠금 처리되고, 새 차수에서 변경점만 기록됩니다.</p>

        <div className="mt-5 space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">유형</label>
            <div className="flex gap-2">
              <Button variant={type === "revise" ? "default" : "outline"} size="sm" onClick={() => setType("revise")}>수정</Button>
              <Button variant={type === "carryover" ? "default" : "outline"} size="sm" onClick={() => setType("carryover")}>이월</Button>
            </div>
            {type === "carryover" && <span className="text-xs text-muted-foreground">다음 년도로 이월됩니다.</span>}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">사유 <span className="text-destructive">*</span></label>
            <Textarea
              placeholder="예) 외주업체 변경, 단가 인상"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">변경 소스 자료 (선택)</label>
            <div
              className={`rounded-lg border-2 border-dashed p-5 text-center cursor-pointer transition-colors ${dragging ? "border-primary bg-primary/5" : "hover:border-muted-foreground/30"}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => {
                const inp = document.createElement("input");
                inp.type = "file";
                inp.multiple = true;
                inp.accept = ".pdf,.xlsx,.xls,.docx,.png,.jpg,.jpeg";
                inp.onchange = () => handleFiles(inp.files);
                inp.click();
              }}
            >
              <CloudUpload className="mx-auto h-5 w-5 text-muted-foreground mb-1" />
              <div className="text-xs">{files.length > 0 ? `${files.length}개 파일 선택됨` : "파일 끌어놓기 또는 클릭"}</div>
              {files.length > 0 && (
                <div className="mt-2 space-y-0.5 text-left">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center justify-between text-[11px] text-muted-foreground px-1">
                      <span className="truncate max-w-[260px]">{f.name}</span>
                      <button className="ml-2 hover:text-destructive" onClick={(e) => { e.stopPropagation(); setFiles((prev) => prev.filter((_, j) => j !== i)); }}>
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <Button variant="ghost" onClick={onClose}>취소</Button>
          <Button disabled={!canSubmit} onClick={() => onAdd(reason.trim(), type, files)}>추가</Button>
        </div>
      </div>
    </div>
  );
}
