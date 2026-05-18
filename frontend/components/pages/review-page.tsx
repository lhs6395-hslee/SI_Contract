"use client";

import React, { useState, useEffect } from "react";
import { useApp } from "@/lib/store";
import { fmt } from "@/lib/format";
import type { ExtractedData } from "@/lib/types";
import {
  AlertTriangle, Info, Check, ArrowRight, Pencil, GripVertical, Plus, X,
  CloudUpload, RefreshCw, Loader2, FolderOpen, Trash2, RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { apiExtract, apiExtractCosts, apiExtractPeople, apiExtractSchedule, apiExtractRates, apiExtractOrg, apiUploadFiles, apiListFiles, apiDeleteFile } from "@/lib/api";
import { loadProjectDataAsync } from "@/lib/storage";
import { getUser } from "@/lib/auth";
import type { CostItem } from "@/lib/types";

// 날짜/숫자 값 정규화 비교 — 포맷 차이(2026.04.06 vs 2026-04-06)로 인한 오탐 방지
const normalizeVal = (v: string | number | null): string => {
  if (v == null) return "";
  return String(v).replace(/\./g, "-").replace(/\//g, "-").trim();
};
const isSameVal = (a: string | number | null, b: string | number | null) =>
  normalizeVal(a) === normalizeVal(b);

export function ReviewPage() {
  const { setRoute, revision, maxRevision, extractedData, setExtractedData, projectId, conflictCount, setConflictCount } = useApp();
  const [tab, setTab] = useState("basic");
  const [showFilePanel, setShowFilePanel] = useState(false);
  const [filePanelTab, setFilePanelTab] = useState<"current" | "compare">("current");
  const [addedFiles, setAddedFiles] = useState<File[]>([]);
  const [selectedExisting, setSelectedExisting] = useState<Set<string>>(new Set());
  const [reExtracting, setReExtracting] = useState(false);
  const [reExtractElapsed, setReExtractElapsed] = useState(0);
  const [allRevisionFiles, setAllRevisionFiles] = useState<Record<string, { name: string; category?: string; size?: number }[]>>({});
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // 차수별 파일 비교 탭 열릴 때 전체 revision 데이터 로드
  useEffect(() => {
    if (filePanelTab !== "compare" || !projectId) return;
    (async () => {
      const pd = await loadProjectDataAsync(projectId);
      if (!pd) return;
      const result: Record<string, { name: string; category?: string; size?: number }[]> = {};
      // 현재 revision 데이터
      const revisions = pd.revisions || {};
      for (let r = 0; r <= (pd.maxRevision ?? maxRevision); r++) {
        const revData = revisions[String(r)] || (r === revision ? extractedData : null);
        if (revData?.files) {
          result[String(r)] = revData.files;
        }
      }
      setAllRevisionFiles(result);
    })();
  }, [filePanelTab, projectId, maxRevision, revision, extractedData]);

  const existingFiles = extractedData?.files || [];

  const toggleExisting = (filename: string) => {
    setSelectedExisting((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  };

  const selectAllExisting = () => {
    if (selectedExisting.size === existingFiles.length) {
      setSelectedExisting(new Set());
    } else {
      setSelectedExisting(new Set(existingFiles.map((f) => f.name)));
    }
  };
  const E = extractedData?.extracted;
  const projectName = extractedData?.projectName || E?.projectName?.value?.toString() || "새 프로젝트";
  const client = E?.client?.value?.toString() || "-";
  const contractor = E?.contractor?.value?.toString() || "-";

  // 탭별 상태 계산
  const [verifiedFields, setVerifiedFields] = useState<Set<string>>(
    new Set(extractedData?.manuallyVerified || [])
  );

  const markVerified = (key: string) => {
    setVerifiedFields((prev) => {
      const next = new Set(prev);
      next.add(key);
      return next;
    });
    // extractedData에도 반영 — 함수형 업데이트로 stale closure 방지
    setExtractedData((prev) => {
      if (!prev) return prev;
      return { ...prev, manuallyVerified: [...(prev.manuallyVerified || []), key] };
    });
  };

  const [confirmedTabs, setConfirmedTabs] = useState<Set<string>>(
    new Set(extractedData?.confirmedTabs || [])
  );

  const confirmTab = (tabId: string) => {
    setConfirmedTabs((prev) => {
      const next = new Set(prev);
      next.add(tabId);
      return next;
    });
    setExtractedData((prev) => {
      if (!prev) return prev;
      const tabs = new Set(prev.confirmedTabs || []);
      tabs.add(tabId);
      return { ...prev, confirmedTabs: [...tabs] };
    });
  };

  const unconfirmTab = (tabId: string) => {
    setConfirmedTabs((prev) => {
      const next = new Set(prev);
      next.delete(tabId);
      return next;
    });
    setExtractedData((prev) => {
      if (!prev) return prev;
      const tabs = new Set(prev.confirmedTabs || []);
      tabs.delete(tabId);
      return { ...prev, confirmedTabs: [...tabs] };
    });
  };

  const BASIC_KEYS = ["projectName", "projectCode", "client", "contractor", "contractType", "paymentTerms", "pm", "salesOwner", "startDate", "endDate", "revenue", "cost", "profit", "profitRate", "indirectCost", "scope", "specialNotes", "fiscalYear", "writtenDate"];
  const basicFields = E ? BASIC_KEYS.filter((k) => E[k]?.value != null && E[k]?.value !== "").length : 0;
  const guessEntries = E ? Object.entries(E).filter(([k, v]) => v?.confidence === "guess" && !verifiedFields.has(k)) : [];
  const guessCount = guessEntries.length;

  const FIELD_LABELS: Record<string, string> = {
    projectName: "사업명", projectCode: "공사코드", client: "발주처", contractor: "계약처",
    contractType: "계약방법", paymentTerms: "수금조건", pm: "PM",
    salesOwner: "영업담당자", startDate: "시작일", endDate: "종료일",
    revenue: "매출", cost: "매입", profit: "영업이익", profitRate: "이익률",
    indirectCost: "간접비", scope: "사업범위", specialNotes: "특기사항",
    fiscalYear: "년도구분", writtenDate: "견적서작성일",
  };
  const guessFieldNames = guessEntries.map(([k]) => FIELD_LABELS[k] || k);

  const REQUIRED_FIELDS = ["projectName", "client", "pm", "startDate", "endDate", "revenue"];
  const missingRequired = E ? REQUIRED_FIELDS.filter((k) => {
    const v = E[k];
    return !v || v.value == null || v.value === "";
  }) : REQUIRED_FIELDS;
  const missingCount = missingRequired.length;

  const costItems = extractedData?.costItems || [];
  const costHasEmpty = costItems.some((c) => !c.name || c.contractAmount === 0 && c.executionAmount === 0);
  const staffPlan = extractedData?.staffPlan || [];
  const scheduleItems = extractedData?.schedule || [];
  const orgMembers = extractedData?.organization || [];

  const tabStatus = (id: string): "ok" | "ready" | "warn" => {
    if (confirmedTabs.has(id)) return "ok";
    if (id === "basic") return basicFields > 0 && guessCount === 0 && missingCount === 0 ? "ready" : "warn";
    if (id === "calc") return costItems.length > 0 && !costHasEmpty ? "ready" : "warn";
    if (id === "people") return staffPlan.length > 0 ? "ready" : "warn";
    if (id === "schedule") return scheduleItems.length > 0 ? "ready" : "warn";
    if (id === "rates") return extractedData?.rates != null ? "ready" : "warn";
    if (id === "org") return orgMembers.length > 0 ? "ready" : "warn";
    return "warn";
  };

  const tabs = [
    { id: "basic", label: "기본 정보", status: tabStatus("basic"), count: basicFields > 0 ? basicFields : undefined },
    { id: "calc", label: "산출내역", status: tabStatus("calc") },
    { id: "people", label: "인원투입계획", status: tabStatus("people") },
    { id: "schedule", label: "공사·공정표", status: tabStatus("schedule") },
    { id: "rates", label: "요율·보증", status: tabStatus("rates") },
    { id: "org", label: "현장조직", status: tabStatus("org") },
    ...(maxRevision >= 1 ? [{ id: "history", label: "변경 이력", status: "ok" as const }] : []),
  ];

  // ─── 탭별 개별 재추출 ───
  const [tabReExtracting, setTabReExtracting] = useState(false);
  const [tabReExtractElapsed, setTabReExtractElapsed] = useState(0);

  const doTabReExtract = async (tabId: string) => {
    if (!projectId || !extractedData?.files?.length) return;
    setTabReExtracting(true);
    setTabReExtractElapsed(0);
    const timer = setInterval(() => setTabReExtractElapsed((s) => s + 1), 1000);

    try {
      const storedFiles = { projectId, filenames: extractedData.files.map((f) => f.name) };

      if (tabId === "basic") {
        const result = await apiExtract([], storedFiles);
        const { costItems, staffPlan, schedule, rates, organization, ...restExtracted } = result as Record<string, unknown>;
        const newExtracted = restExtracted as Record<string, { value: string | number | null; source: string; confidence: "verified" | "guess" | "null" }>;
        // 함수형 업데이트로 최신 prev 참조 — stale closure 방지
        setExtractedData((prev) => {
          if (!prev) return prev;
          const currentExtracted = prev.extracted || {};
          const changedFields: Record<string, { prev: string | number | null }> = {};
          const aiSuggestions: Record<string, { value: string | number | null; source: string }> = {
            ...(prev.aiSuggestions || {}),
          };
          const merged = { ...currentExtracted };
          for (const key of Object.keys(newExtracted)) {
            const prevField = currentExtracted[key];
            const prevVal = prevField?.value ?? null;
            const newVal = newExtracted[key]?.value ?? null;
            if (newVal == null || newVal === "") continue;
            if (prevField?.source === "수동 수정" && !isSameVal(prevVal, newVal)) {
              aiSuggestions[key] = { value: newVal, source: newExtracted[key]?.source || "AI 추출" };
            } else {
              if (!isSameVal(prevVal, newVal)) changedFields[key] = { prev: prevVal };
              merged[key] = newExtracted[key];
              delete aiSuggestions[key];
            }
          }
          return {
            ...prev,
            extracted: merged as ExtractedData["extracted"],
            changedFields: Object.keys(changedFields).length > 0 ? changedFields : undefined,
            aiSuggestions: Object.keys(aiSuggestions).length > 0 ? aiSuggestions : undefined,
          };
        });
      } else if (tabId === "calc") {
        const result = await apiExtractCosts([], storedFiles);
        setExtractedData((prev) => prev ? { ...prev, costItems: result.items || [] } : prev);
      } else if (tabId === "people") {
        const result = await apiExtractPeople(storedFiles);
        setExtractedData((prev) => prev ? { ...prev, staffPlan: result.staffPlan || [] } : prev);
      } else if (tabId === "schedule") {
        const result = await apiExtractSchedule(storedFiles);
        setExtractedData((prev) => prev ? { ...prev, schedule: result.schedule || [] } : prev);
      } else if (tabId === "rates") {
        const result = await apiExtractRates(storedFiles);
        setExtractedData((prev) => prev ? { ...prev, rates: result.rates || undefined } : prev);
      } else if (tabId === "org") {
        const result = await apiExtractOrg(storedFiles);
        setExtractedData((prev) => prev ? { ...prev, organization: result.organization || [] } : prev);
      }
      unconfirmTab(tabId);
    } catch (err) {
      alert(`재추출 실패: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      clearInterval(timer);
      setTabReExtracting(false);
    }
  };

  const handleAddFiles = (fileList: FileList) => {
    setAddedFiles((prev) => [...prev, ...Array.from(fileList)]);
  };

  const removeAddedFile = (idx: number) => {
    setAddedFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  // 목록에서만 제거 (S3 유지) — 재추출 시 포함 안 됨
  const removeFromList = (filename: string) => {
    setSelectedExisting((prev) => { const next = new Set(prev); next.delete(filename); return next; });
    setExtractedData((prev) => prev ? { ...prev, files: prev.files.filter((f) => f.name !== filename) } : prev);
  };

  // 서버에서 영구 삭제
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const deleteFromServer = async (filename: string) => {
    if (!confirm(`"${filename}"\n\n서버에서 영구 삭제합니다. 복구할 수 없습니다.\n계속하시겠습니까?`)) return;
    setDeletingFile(filename);
    try {
      if (projectId) await apiDeleteFile(projectId, filename, revision);
    } finally {
      setDeletingFile(null);
    }
    setSelectedExisting((prev) => { const next = new Set(prev); next.delete(filename); return next; });
    setExtractedData((prev) => prev ? { ...prev, files: prev.files.filter((f) => f.name !== filename) } : prev);
  };

  // 서버에서 현재 차수 파일 목록 다시 불러오기
  const [reloadingFiles, setReloadingFiles] = useState(false);
  const reloadFileList = async () => {
    if (!projectId) return;
    setReloadingFiles(true);
    try {
      const serverFiles = await apiListFiles(projectId, revision);
      setExtractedData((prev) => prev ? {
        ...prev,
        files: serverFiles.map((f) => ({ name: f.filename, category: "unknown", size: f.size })),
      } : prev);
      setSelectedExisting(new Set());
    } finally {
      setReloadingFiles(false);
    }
  };

  const doReExtract = async () => {
    const totalFiles = addedFiles.length + selectedExisting.size;
    if (totalFiles === 0) return;
    setReExtracting(true);
    setReExtractElapsed(0);
    const timer = setInterval(() => setReExtractElapsed((s) => s + 1), 1000);

    try {
      // 새 파일을 서버에 저장 (현재 revision 경로에)
      if (addedFiles.length > 0 && projectId) {
        await apiUploadFiles(projectId, addedFiles, revision);
      }

      // 저장된 파일 중 선택된 것 + 새 파일로 추출 (revision 정보 포함)
      const storedFiles = projectId && selectedExisting.size > 0
        ? { projectId, filenames: Array.from(selectedExisting), revision }
        : undefined;

      const extracted = await apiExtract(addedFiles, storedFiles);
      const { costItems: newCostItems, staffPlan: newStaffPlan, schedule: newSchedule, rates: newRates, organization: newOrg, ...restExtracted } = extracted as Record<string, unknown>;
      const newExtracted = restExtracted as Record<string, { value: string | number | null; source: string; confidence: "verified" | "guess" | "null" }>;

      // 함수형 업데이트로 최신 prev 참조 — stale closure 방지
      setExtractedData((prev) => {
        if (!prev) return prev;
        const currentExtracted = prev.extracted || {};
        const changedFields: Record<string, { prev: string | number | null }> = {};
        const aiSuggestions: Record<string, { value: string | number | null; source: string }> = {
          ...(prev.aiSuggestions || {}),
        };
        const merged = { ...currentExtracted };
        for (const key of Object.keys(newExtracted)) {
          const prevField = currentExtracted[key];
          const prevVal = prevField?.value ?? null;
          const newVal = newExtracted[key]?.value ?? null;
          if (newVal == null || newVal === "") continue;
          if (prevField?.source === "수동 수정" && !isSameVal(prevVal, newVal)) {
            aiSuggestions[key] = { value: newVal, source: newExtracted[key]?.source || "AI 추출" };
          } else {
            if (!isSameVal(prevVal, newVal)) changedFields[key] = { prev: prevVal };
            merged[key] = newExtracted[key];
            delete aiSuggestions[key];
          }
        }
        return {
          projectName: prev.projectName,
          extracted: merged as ExtractedData["extracted"],
          costItems: (newCostItems as ExtractedData["costItems"]) || prev.costItems || [],
          staffPlan: (newStaffPlan as ExtractedData["staffPlan"]) || prev.staffPlan || [],
          schedule: (newSchedule as ExtractedData["schedule"]) || prev.schedule || [],
          rates: (newRates as ExtractedData["rates"]) || prev.rates,
          organization: (newOrg as ExtractedData["organization"]) || prev.organization || [],
          conflicts: [],
          files: [
            ...existingFiles,
            ...addedFiles.map((f) => ({ name: f.name, category: "unknown", size: f.size })),
          ],
          changedFields: Object.keys(changedFields).length > 0 ? changedFields : undefined,
          aiSuggestions: Object.keys(aiSuggestions).length > 0 ? aiSuggestions : undefined,
          fieldEditLog: prev.fieldEditLog,
        };
      });
      setConflictCount(0);
      setAddedFiles([]);
      setSelectedExisting(new Set());
      setShowFilePanel(false);
    } catch (err) {
      alert(`재추출 실패: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      clearInterval(timer);
      setReExtracting(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold">{projectName}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            발주처 {client} · 계약처 {contractor} · 차수 {revision}차 · 추출된 항목을 검토하고 수정해 주세요.
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => setShowFilePanel((v) => !v)}>
            {showFilePanel ? <X className="h-3.5 w-3.5 mr-1" /> : <Plus className="h-3.5 w-3.5 mr-1" />}
            {showFilePanel ? "닫기" : "파일 추가 / 재추출"}
          </Button>
        </div>
      </div>

      {showFilePanel && (
        <Card>
          <CardContent className="pt-5 space-y-4">
            {/* 파일 패널 탭 */}
            <div className="flex gap-1 border-b pb-3">
              <button
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${filePanelTab === "current" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
                onClick={() => setFilePanelTab("current")}
              >
                현재 차수 파일
              </button>
              <button
                className={`flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${filePanelTab === "compare" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
                onClick={() => setFilePanelTab("compare")}
              >
                <FolderOpen className="h-3 w-3" />
                차수별 비교
              </button>
            </div>

            {/* 차수별 파일 비교 탭 */}
            {filePanelTab === "compare" && (
              <div className="space-y-3">
                {maxRevision === 0 && Object.keys(allRevisionFiles).length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">차수 데이터가 없습니다.</p>
                ) : (
                  <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${Math.min(maxRevision + 1, 3)}, 1fr)` }}>
                    {Array.from({ length: maxRevision + 1 }, (_, r) => {
                      const files = allRevisionFiles[String(r)] || [];
                      const prevFiles = r > 0 ? new Set((allRevisionFiles[String(r - 1)] || []).map((f) => f.name)) : null;
                      const currFileNames = new Set(files.map((f) => f.name));
                      const addedSet = prevFiles ? new Set([...currFileNames].filter((n) => !prevFiles.has(n))) : new Set<string>();
                      const removedFiles = prevFiles ? [...prevFiles].filter((n) => !currFileNames.has(n)) : [];
                      return (
                        <div key={r} className={`rounded-lg border p-3 ${r === revision ? "border-primary/40 bg-primary/5" : "bg-muted/30"}`}>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-semibold">{r}차{r === revision ? " (현재)" : ""}</span>
                            <span className="text-[11px] text-muted-foreground">{files.length}개</span>
                          </div>
                          {files.length === 0 ? (
                            <p className="text-[11px] text-muted-foreground">파일 없음</p>
                          ) : (
                            <div className="space-y-1">
                              {files.map((f, i) => (
                                <div key={i} className={`flex items-center gap-1.5 text-[11px] rounded px-1.5 py-1 ${addedSet.has(f.name) ? "bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400" : ""}`}>
                                  {addedSet.has(f.name) && <span className="text-green-500 font-bold shrink-0">+</span>}
                                  <span className="truncate">{f.name}</span>
                                </div>
                              ))}
                              {removedFiles.map((name, i) => (
                                <div key={`rm-${i}`} className="flex items-center gap-1.5 text-[11px] rounded px-1.5 py-1 bg-red-50 text-red-600 line-through dark:bg-red-950/30 dark:text-red-400">
                                  <span className="font-bold shrink-0">−</span>
                                  <span className="truncate">{name}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
                <p className="text-[11px] text-muted-foreground">
                  <span className="text-green-600 font-medium">+ 초록</span>: 이전 차수 대비 추가된 파일 &nbsp;
                  <span className="text-red-500 font-medium line-through">− 빨강</span>: 제거된 파일
                </p>
              </div>
            )}

            {/* 현재 차수 파일 탭 */}
            {filePanelTab === "current" && <>
            {/* 기존 추출에 사용된 문서 목록 — 체크박스로 선택 */}
            {existingFiles.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-muted-foreground">기존 추출 문서 ({existingFiles.length}개)</div>
                  <div className="flex items-center gap-2">
                    <button
                      className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                      title="서버에서 파일 목록 다시 불러오기"
                      onClick={reloadFileList}
                      disabled={reloadingFiles}
                    >
                      <RotateCcw className={`h-3 w-3 ${reloadingFiles ? "animate-spin" : ""}`} />
                      목록 초기화
                    </button>
                    <button className="text-[11px] text-primary hover:underline" onClick={selectAllExisting}>
                      {selectedExisting.size === existingFiles.length ? "전체 해제" : "전체 선택"}
                    </button>
                  </div>
                </div>
                <div className="space-y-1">
                  {existingFiles.map((f, i) => {
                    const checked = selectedExisting.has(f.name);
                    return (
                      <div
                        key={i}
                        className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors ${
                          checked ? "bg-primary/5 border border-primary/20" : "bg-muted/50 text-muted-foreground"
                        }`}
                        onClick={() => toggleExisting(f.name)}
                      >
                        <div className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                          checked ? "bg-primary border-primary text-white" : "border-muted-foreground/30"
                        }`}>
                          {checked && <Check className="h-2.5 w-2.5" />}
                        </div>
                        <span className="flex-1 truncate">{f.name}</span>
                        <span className="text-[11px] text-muted-foreground">{f.category || ""}</span>
                        {/* 목록에서만 제거 */}
                        <button
                          className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground shrink-0"
                          title="목록에서 제거 (서버 파일 유지)"
                          onClick={(e) => { e.stopPropagation(); removeFromList(f.name); }}
                        >
                          <X className="h-3 w-3" />
                        </button>
                        {/* 서버에서 영구 삭제 */}
                        <button
                          className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive shrink-0"
                          title="서버에서 영구 삭제"
                          onClick={(e) => { e.stopPropagation(); deleteFromServer(f.name); }}
                          disabled={deletingFile === f.name}
                        >
                          {deletingFile === f.name
                            ? <Loader2 className="h-3 w-3 animate-spin" />
                            : <Trash2 className="h-3 w-3" />}
                        </button>
                      </div>
                    );
                  })}
                </div>
                <p className="text-[11px] text-muted-foreground mt-1">
                  체크 후 재추출에 포함 &nbsp;·&nbsp; <X className="inline h-2.5 w-2.5" /> 목록 제거 (서버 유지) &nbsp;·&nbsp; <Trash2 className="inline h-2.5 w-2.5" /> 서버 영구 삭제
                </p>
              </div>
            )}

            {/* 새 파일 추가 */}
            <div>
              <div className="text-xs font-semibold text-muted-foreground mb-2">파일 추가</div>
              {/* input을 div 바깥에 두어 click 이벤트 이중 트리거 방지 */}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.png,.jpg,.jpeg"
                onChange={(e) => { if (e.target.files?.length) handleAddFiles(e.target.files); e.target.value = ""; }}
              />
              <div
                className="rounded-lg border-2 border-dashed p-5 text-center cursor-pointer hover:border-muted-foreground/30 transition-colors"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files?.length) handleAddFiles(e.dataTransfer.files); }}
                onClick={() => fileInputRef.current?.click()}
              >
                <CloudUpload className="mx-auto h-5 w-5 text-muted-foreground mb-1.5" />
                <div className="text-sm font-medium">추가 문서 업로드</div>
                <div className="text-xs text-muted-foreground mt-1">새 파일과 기존 파일 목록 기준으로 재추출합니다</div>
              </div>
            </div>

            {addedFiles.length > 0 && (
              <div className="space-y-1.5">
                <div className="text-xs font-semibold text-muted-foreground">새로 추가된 파일 ({addedFiles.length}개)</div>
                {addedFiles.map((f, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-sm">
                    <Plus className="h-3 w-3 text-primary shrink-0" />
                    <span className="flex-1 truncate">{f.name}</span>
                    <span className="text-xs text-muted-foreground">{(f.size / 1024).toFixed(0)} KB</span>
                    <button className="p-1 rounded hover:bg-muted text-muted-foreground" onClick={() => removeAddedFile(i)}>
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-2">
              <Button onClick={doReExtract} disabled={reExtracting || (addedFiles.length === 0 && selectedExisting.size === 0)} className="flex-1">
                {reExtracting
                  ? <><Loader2 className="h-4 w-4 animate-spin mr-2" /> 재추출 중… {reExtractElapsed}초</>
                  : <><RefreshCw className="h-3.5 w-3.5 mr-1.5" /> 재추출 ({selectedExisting.size + addedFiles.length}개 파일)</>}
              </Button>
              <Button variant="ghost" onClick={() => { setShowFilePanel(false); setAddedFiles([]); setSelectedExisting(new Set()); }}>취소</Button>
            </div>
            </>}
          </CardContent>
        </Card>
      )}

      {extractedData?.conflicts && extractedData.conflicts.length > 0 && (
        <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950/20">
          <Check className="h-4 w-4 text-blue-600" />
          <AlertTitle className="text-blue-800 dark:text-blue-200">
            AI 추출 완료 — {Object.values(E || {}).filter((v) => v?.value).length}개 항목 추출됨
          </AlertTitle>
          <AlertDescription className="text-blue-700 dark:text-blue-300">
            {extractedData.files?.length}개 문서에서 추출 · {extractedData.conflicts.length}건의 검증 항목
          </AlertDescription>
        </Alert>
      )}

      {conflictCount > 0 && (
        <Alert className="border-amber-200 bg-amber-50 dark:bg-amber-950/20">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <AlertTitle className="text-amber-800 dark:text-amber-200">{conflictCount}건의 충돌이 감지되었습니다</AlertTitle>
          <AlertDescription className="text-amber-700 dark:text-amber-300 flex items-center justify-between">
            <span>협력사 견적서 간 매입 단가가 일치하지 않습니다.</span>
            <Button variant="outline" size="sm" onClick={() => setRoute("conflicts")}>충돌 해결 →</Button>
          </AlertDescription>
        </Alert>
      )}

      {revision > 0 && (
        <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950/20">
          <Info className="h-4 w-4 text-blue-600" />
          <AlertTitle className="text-blue-800 dark:text-blue-200">수정 {revision}차 변경 이력</AlertTitle>
          <AlertDescription className="text-blue-700 dark:text-blue-300">
            {(() => {
              const changed = extractedData?.changedFields || {};
              const changedKeys = Object.keys(changed);
              if (changedKeys.length === 0) return <span>변경 사항 없음</span>;
              const fmt2 = (v: unknown) => {
                if (v == null) return "-";
                if (typeof v === "number") return v >= 10000 ? `${(v / 1000).toLocaleString()}천원` : String(v);
                return String(v);
              };
              return (
                <div className="mt-2 space-y-1">
                  {changedKeys.map((key) => {
                    const prev = changed[key]?.prev;
                    const curr = extractedData?.extracted?.[key]?.value;
                    return (
                      <div key={key} className="flex items-center gap-2 text-xs">
                        <span className="font-medium min-w-[80px]">{FIELD_LABELS[key] || key}</span>
                        <span className="text-muted-foreground line-through">{fmt2(prev)}</span>
                        <span>→</span>
                        <span className="font-semibold">{fmt2(curr)}</span>
                      </div>
                    );
                  })}
                </div>
              );
            })()}
          </AlertDescription>
        </Alert>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              tab === t.id ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setTab(t.id)}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${t.status === "ok" ? "bg-emerald-500" : t.status === "ready" ? "bg-blue-500" : "bg-amber-500"}`} />
            {t.label}
            {t.count != null && (
              <span className="text-[11px] bg-muted text-muted-foreground px-1.5 rounded-full">{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {tab === "basic" && <TabBasic onManualEdit={markVerified} verifiedFields={verifiedFields} />}
      {tab === "calc" && <TabCalc />}
      {tab === "people" && <TabPeople />}
      {tab === "schedule" && <TabSchedule />}
      {tab === "rates" && <TabRates />}
      {tab === "org" && <TabOrg />}
      {tab === "history" && <TabHistory />}

      <TabActionBar
        tabId={tab}
        confirmed={confirmedTabs.has(tab)}
        onConfirm={() => confirmTab(tab)}
        onUnconfirm={() => unconfirmTab(tab)}
        onReExtract={() => doTabReExtract(tab)}
        reExtracting={tabReExtracting}
        reExtractElapsed={tabReExtractElapsed}
      />

      <div className="flex items-center justify-between rounded-lg border bg-card px-6 py-4">
        <div className="text-sm text-muted-foreground">
          {tab === "basic" && (
            <>
              <strong className="text-foreground">기본 정보 {basicFields}/{Object.keys(FIELD_LABELS).length}</strong>
              {missingCount > 0 && <span className="text-red-600"> · 필수 미입력 {missingCount}건: {missingRequired.map((k) => FIELD_LABELS[k] || k).join(", ")}</span>}
              {guessCount > 0 && <span className="text-amber-700"> · 확인 필요 {guessCount}건: {guessFieldNames.join(", ")}</span>}
            </>
          )}
          {tab === "calc" && (
            <strong className="text-foreground">산출내역 {costItems.length}개 항목{costHasEmpty ? <span className="text-amber-700"> · 빈 값 있음</span> : ""}</strong>
          )}
          {tab === "people" && (
            <strong className="text-foreground">투입인원 {staffPlan.length}명</strong>
          )}
          {tab === "schedule" && (
            <strong className="text-foreground">공정표 {scheduleItems.length}개 공종</strong>
          )}
          {tab === "rates" && (
            <strong className="text-foreground">요율·보증 {extractedData?.rates ? "입력됨" : "미입력"}</strong>
          )}
          {tab === "org" && (
            <strong className="text-foreground">현장조직 {orgMembers.length}명</strong>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Check className="h-3 w-3 text-emerald-500" /> 자동 저장됨
          </span>
          <Button onClick={() => setRoute("export")}>익스포트로 <ArrowRight className="h-3.5 w-3.5 ml-1" /></Button>
        </div>
      </div>
    </div>
  );
}

function KVRow({ label, value, source, confidence, isAmount, isDate, isYear, onChange, onAiAccept, changedFrom, revision, editLog, aiSuggestion }: {
  label: string; value: string | number; source?: string; confidence?: string; isAmount?: boolean; isDate?: boolean; isYear?: boolean;
  onChange?: (newValue: string) => void;
  onAiAccept?: (newValue: string) => void;
  changedFrom?: string | number | null;
  revision?: number;
  editLog?: { at: string; by: string };
  aiSuggestion?: { value: string | number | null; source: string };
}) {
  const [editing, setEditing] = useState(false);
  const guess = confidence === "guess";
  // changedFrom이 있고 값이 다르면 = 이번 차수에서 변경된 것 (재추출 or 수정)
  const changedThisRevision = changedFrom !== undefined && String(changedFrom) !== String(value);
  // source가 "수동 수정"이고 changedFrom이 없으면 = 이전 차수에서 수정된 것
  const wasEditedPrevRevision = source === "수동 수정" && !changedThisRevision;
  const wasReExtracted = changedThisRevision && source !== "수동 수정";

  const [draft, setDraft] = useState("");
  const committed = React.useRef(false);

  const toDateInput = (v: string) => {
    return v.replace(/\./g, "-").replace(/\//g, "-").slice(0, 10);
  };

  const startEdit = () => {
    committed.current = false;
    setDraft(isDate ? toDateInput(String(value)) : String(value));
    setEditing(true);
  };

  const commitEdit = () => {
    if (committed.current) return;
    committed.current = true;
    const finalVal = isDate ? draft.replace(/-/g, "-") : draft;
    if (finalVal !== String(value)) {
      onChange?.(finalVal);
    }
    setEditing(false);
  };

  const cancelEdit = () => {
    committed.current = true;
    setEditing(false);
  };

  const normalizeDate = (v: string) => v.replace(/\./g, "-").replace(/\//g, "-");

  const formatVal = (v: string) => {
    if (isAmount && !isNaN(Number(v))) return fmt(Number(v)) + " 원";
    if (isDate) return normalizeDate(v);
    if (isYear) return v.replace("년", "") + "년";
    return v;
  };

  return (
    <>
      <div className="text-sm text-muted-foreground py-3 border-b">{label}</div>
      <div
        className={`text-sm py-3 border-b flex items-center gap-2 group cursor-pointer ${guess && !changedThisRevision && !wasEditedPrevRevision ? "text-amber-700 dark:text-amber-400" : ""}`}
        onClick={() => !editing && startEdit()}
      >
        {editing ? (
          isYear ? (
            <select autoFocus value={draft}
              onChange={(e) => { setDraft(e.target.value); }}
              onBlur={commitEdit}
              className="h-8 text-sm rounded-md border border-input bg-background px-3 py-1 shadow-sm focus:outline-none focus:ring-1 focus:ring-ring">
              {Array.from({ length: 10 }, (_, i) => {
                const y = new Date().getFullYear() - 3 + i;
                return <option key={y} value={String(y)}>{y}년</option>;
              })}
            </select>
          ) : isDate ? (
            <input type="date" autoFocus value={draft}
              onChange={(e) => { setDraft(e.target.value); }}
              onBlur={commitEdit}
              onKeyDown={(e) => { if (e.key === "Escape") cancelEdit(); }}
              className="h-8 text-sm rounded-md border border-input bg-background px-3 py-1 shadow-sm focus:outline-none focus:ring-1 focus:ring-ring" />
          ) : (
            <Input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={(e) => { if (e.key === "Enter") commitEdit(); if (e.key === "Escape") cancelEdit(); }}
              className="h-8 text-sm" />
          )
        ) : (
          <>
            <span className={isAmount ? "font-mono" : ""}>
              {formatVal(String(value)) || <span className="text-muted-foreground italic">비어있음</span>}
            </span>
            {wasReExtracted && (
              <Badge variant="outline" className="text-[10px] text-emerald-600 border-emerald-300 gap-1">
                변경됨
              </Badge>
            )}
            {changedThisRevision && source === "수동 수정" && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">{revision && revision > 0 ? `${revision}차 수정됨` : "수정됨"}</Badge>}
            {wasEditedPrevRevision && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">수정됨</Badge>}
            {guess && !changedThisRevision && !wasEditedPrevRevision && <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-300">추측</Badge>}
            {wasReExtracted && changedFrom != null && String(changedFrom) !== "" && (
              <span className="text-[10px] text-muted-foreground line-through">{formatVal(String(changedFrom))}</span>
            )}
            {changedThisRevision && source === "수동 수정" && changedFrom != null && String(changedFrom) !== "" && (
              <span className="text-[10px] text-muted-foreground line-through">{formatVal(String(changedFrom))}</span>
            )}
            {aiSuggestion && aiSuggestion.value != null && !isSameVal(aiSuggestion.value, value) && (
              <button
                className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 border border-blue-200 text-[11px] text-blue-700 hover:bg-blue-100 transition-colors shrink-0"
                title={`AI 제안값으로 교체: ${aiSuggestion.value}`}
                onClick={(e) => { e.stopPropagation(); (onAiAccept ?? onChange)?.(String(aiSuggestion.value)); }}
              >
                <span className="font-medium">AI 제안</span>
                <span className="opacity-70">→ {formatVal(String(aiSuggestion.value))}</span>
              </button>
            )}
            <span className="text-[11px] text-muted-foreground ml-auto flex flex-col items-end gap-0.5">
              {source && <span>{source}</span>}
              {editLog && <span className="text-[10px] opacity-70">{editLog.at} · {editLog.by}</span>}
            </span>
            <Pencil className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity ml-1" />
          </>
        )}
      </div>
    </>
  );
}

function TabBasic({ onManualEdit, verifiedFields }: { onManualEdit: (key: string) => void; verifiedFields: Set<string> }) {
  const { extractedData, setExtractedData, revision } = useApp();
  const E = extractedData?.extracted || {};
  const changed = extractedData?.changedFields || {};
  const editLog = extractedData?.fieldEditLog || {};
  const aiSuggestions = extractedData?.aiSuggestions || {};

  const DATE_FIELDS = new Set(["startDate", "endDate", "writtenDate"]);

  // 필드 수정 시 extractedData에 즉시 반영 — 함수형 업데이트로 stale closure 방지
  const updateField = React.useCallback((key: string, newValue: string, source = "수동 수정") => {
    let normalized = newValue;
    if (DATE_FIELDS.has(key)) {
      normalized = newValue.replace(/\./g, "-").replace(/\//g, "-");
    }
    const user = getUser();
    const logEntry = {
      at: new Date().toLocaleString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }),
      by: user?.name || user?.email || "알 수 없음",
    };
    setExtractedData((prev) => {
      if (!prev) return prev;
      const newAiSuggestions = prev.aiSuggestions ? { ...prev.aiSuggestions } : undefined;
      if (newAiSuggestions) delete newAiSuggestions[key];
      return {
        ...prev,
        extracted: {
          ...prev.extracted,
          [key]: { ...prev.extracted[key], value: normalized, source, confidence: "verified" as const },
        },
        fieldEditLog: { ...(prev.fieldEditLog || {}), [key]: logEntry },
        aiSuggestions: newAiSuggestions && Object.keys(newAiSuggestions).length > 0 ? newAiSuggestions : undefined,
      };
    });
    onManualEdit(key);
  }, [setExtractedData, onManualEdit]);

  const fld = (key: string, fallback: string, fallbackSource = "") => {
    const v = E[key];
    const isVerified = verifiedFields.has(key);
    if (v && v.value != null && v.value !== "") {
      return { value: v.value, source: v.source || "AI 추출", confidence: isVerified ? "verified" as const : (v.confidence || "verified"), changedFrom: changed[key]?.prev, key, editLog: editLog[key], aiSuggestion: aiSuggestions[key] };
    }
    return { value: fallback, source: fallbackSource, confidence: "verified" as const, changedFrom: undefined, key, editLog: editLog[key], aiSuggestion: aiSuggestions[key] };
  };

  // source에서 "문서1:", "문서2:" 등 접두어 제거
  const cleanSource = (s?: string) => s?.replace(/^문서\d+[:\s]*/g, "").replace(/^문서\d+\s*/g, "").trim() || "";

  const [revenueVal, setRevenueVal] = useState((E.revenue?.value as number) ?? 0);
  const [costVal, setCostVal] = useState((E.cost?.value as number) ?? 0);
  const [profitVal, setProfitVal] = useState((E.profit?.value as number) ?? 0);
  const [indirectVal, setIndirectVal] = useState((E.indirectCost?.value as number) ?? 0);
  const profitRate = revenueVal > 0 ? (profitVal / revenueVal * 100).toFixed(1) : "-";
  const costPct = revenueVal > 0 ? (costVal / revenueVal * 100).toFixed(1) : "-";

  // 추출 데이터 변경 시 동기화
  React.useEffect(() => {
    setRevenueVal((E.revenue?.value as number) ?? 0);
    setCostVal((E.cost?.value as number) ?? 0);
    setProfitVal((E.profit?.value as number) ?? 0);
    setIndirectVal((E.indirectCost?.value as number) ?? 0);
  }, [E.revenue?.value, E.cost?.value, E.profit?.value, E.indirectCost?.value]);

  const projectName = fld("projectName", "", "");
  const projectCode = fld("projectCode", "", "");
  const clientName = fld("client", "", "");
  const contractor = fld("contractor", "", "");
  const contractType = fld("contractType", "", "");
  const paymentTerms = fld("paymentTerms", "", "");
  const pm = fld("pm", "", "");
  const salesOwner = fld("salesOwner", "", "");
  const startDate = fld("startDate", "", "");
  const endDate = fld("endDate", "", "");
  const scope = fld("scope", "", "");
  const specialNotes = fld("specialNotes", "", "");
  const fiscalYear = fld("fiscalYear", "", "");
  const writtenDate = fld("writtenDate", "", "");

  return (
    <div className="space-y-4">
      {/* Stats — 클릭하여 수정 가능 */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <Card className="p-5">
          <div className="text-xs text-muted-foreground font-medium flex items-center gap-1">매출{E.revenue?.source === "수동 수정" && changed.revenue && String(changed.revenue.prev) !== String(revenueVal) && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">{revision > 0 ? `${revision}차 수정됨` : "수정됨"}</Badge>}{E.revenue?.source === "수동 수정" && !changed.revenue && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">수정됨</Badge>}</div>
          <div className="mt-1 flex items-baseline gap-1">
            <EditableCell value={Math.round(revenueVal / 1000)} onChange={(v) => { const n = Number(v.replace(/,/g, "")) * 1000; setRevenueVal(n); updateField("revenue", String(n)); }} align="left" mono className="text-2xl font-bold" />
            <span className="text-sm font-normal text-muted-foreground">천원</span>
          </div>
          <div className="text-xs text-muted-foreground mt-1">{cleanSource(E.revenue?.source) || "VAT 별도"}</div>
        </Card>
        <Card className="p-5">
          <div className="text-xs text-muted-foreground font-medium flex items-center gap-1">매입{E.cost?.source === "수동 수정" && changed.cost && String(changed.cost.prev) !== String(costVal) && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">{revision > 0 ? `${revision}차 수정됨` : "수정됨"}</Badge>}{E.cost?.source === "수동 수정" && !changed.cost && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">수정됨</Badge>}</div>
          <div className="mt-1 flex items-baseline gap-1">
            <EditableCell value={Math.round(costVal / 1000)} onChange={(v) => { const n = Number(v.replace(/,/g, "")) * 1000; setCostVal(n); updateField("cost", String(n)); }} align="left" mono className="text-2xl font-bold" />
            <span className="text-sm font-normal text-muted-foreground">천원</span>
          </div>
          <div className="text-xs text-muted-foreground mt-1">{cleanSource(E.cost?.source) || "매출 대비"} · <span className="font-mono font-semibold">{costPct}%</span></div>
        </Card>
        <Card className="p-5">
          <div className="text-xs text-muted-foreground font-medium flex items-center gap-1">간접비+일반관리비{E.indirectCost?.source === "수동 수정" && changed.indirectCost && String(changed.indirectCost.prev) !== String(indirectVal) && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">{revision > 0 ? `${revision}차 수정됨` : "수정됨"}</Badge>}{E.indirectCost?.source === "수동 수정" && !changed.indirectCost && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">수정됨</Badge>}</div>
          <div className="mt-1 flex items-baseline gap-1">
            <EditableCell value={Math.round(indirectVal / 1000)} onChange={(v) => { const n = Number(v.replace(/,/g, "")) * 1000; setIndirectVal(n); updateField("indirectCost", String(n)); }} align="left" mono className="text-2xl font-bold" />
            <span className="text-sm font-normal text-muted-foreground">천원</span>
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            {cleanSource(E.indirectCost?.source) || "간접비 + 일반관리비"}
            {revenueVal > 0 && <> · <span className="font-mono font-semibold">{(indirectVal / revenueVal * 100).toFixed(1)}%</span></>}
          </div>
        </Card>
        <Card className="p-5 border-emerald-200 dark:border-emerald-800">
          <div className="text-xs text-muted-foreground font-medium flex items-center gap-1">영업이익{E.profit?.source === "수동 수정" && changed.profit && String(changed.profit.prev) !== String(profitVal) && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">{revision > 0 ? `${revision}차 수정됨` : "수정됨"}</Badge>}{E.profit?.source === "수동 수정" && !changed.profit && <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">수정됨</Badge>}</div>
          <div className="mt-1 flex items-baseline gap-1">
            <EditableCell value={Math.round(profitVal / 1000)} onChange={(v) => { const n = Number(v.replace(/,/g, "")) * 1000; setProfitVal(n); updateField("profit", String(n)); }} align="left" mono className="text-2xl font-bold text-emerald-600" />
            <span className="text-sm font-normal text-muted-foreground">천원</span>
          </div>
          <div className="text-xs text-muted-foreground mt-1">{cleanSource(E.profit?.source) ? `${cleanSource(E.profit?.source)} · ` : ""}이익률 <span className="font-mono font-semibold text-emerald-600">{profitRate}%</span></div>
        </Card>
        <Card className="p-5">
          <div className="text-xs text-muted-foreground font-medium">검증</div>
          <div className="text-xs mt-2 space-y-1">
            <div className={`font-mono ${revenueVal - costVal - indirectVal - profitVal === 0 ? "text-emerald-600" : "text-destructive font-semibold"}`}>
              매출-매입-간접비 = {fmt(Math.round((revenueVal - costVal - indirectVal) / 1000))}천원
            </div>
            <div className={`font-mono ${Math.abs(revenueVal - costVal - indirectVal - profitVal) < 1000 ? "text-emerald-600" : "text-destructive"}`}>
              {Math.abs(revenueVal - costVal - indirectVal - profitVal) < 1000 ? "영업이익 일치" : `차이: ${fmt(Math.round((revenueVal - costVal - indirectVal - profitVal) / 1000))}천원`}
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">계약 정보</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-[100px_1fr]">
              <KVRow label="사업명" value={projectName.value as string} source={projectName.source} confidence={projectName.confidence} changedFrom={projectName.changedFrom} revision={revision} editLog={editLog["projectName"]} aiSuggestion={aiSuggestions["projectName"]} onChange={(v) => updateField("projectName", v)} onAiAccept={(v) => updateField("projectName", v, "AI 제안")} />
              <KVRow label="공사코드" value={projectCode.value as string} source={projectCode.source} confidence={projectCode.confidence} changedFrom={projectCode.changedFrom} revision={revision} editLog={editLog["projectCode"]} aiSuggestion={aiSuggestions["projectCode"]} onChange={(v) => updateField("projectCode", v)} onAiAccept={(v) => updateField("projectCode", v, "AI 제안")} />
              <KVRow label="발주처" value={clientName.value as string} source={clientName.source} confidence={clientName.confidence} changedFrom={clientName.changedFrom} revision={revision} editLog={editLog["client"]} aiSuggestion={aiSuggestions["client"]} onChange={(v) => updateField("client", v)} onAiAccept={(v) => updateField("client", v, "AI 제안")} />
              <KVRow label="계약처" value={contractor.value as string} source={contractor.source} confidence={contractor.confidence} changedFrom={contractor.changedFrom} revision={revision} editLog={editLog["contractor"]} aiSuggestion={aiSuggestions["contractor"]} onChange={(v) => updateField("contractor", v)} onAiAccept={(v) => updateField("contractor", v, "AI 제안")} />
              <KVRow label="계약방법" value={contractType.value as string} source={contractType.source} confidence={contractType.confidence} changedFrom={contractType.changedFrom} revision={revision} editLog={editLog["contractType"]} aiSuggestion={aiSuggestions["contractType"]} onChange={(v) => updateField("contractType", v)} onAiAccept={(v) => updateField("contractType", v, "AI 제안")} />
              <KVRow label="수금조건" value={paymentTerms.value as string} source={paymentTerms.source} confidence={paymentTerms.confidence} changedFrom={paymentTerms.changedFrom} revision={revision} editLog={editLog["paymentTerms"]} aiSuggestion={aiSuggestions["paymentTerms"]} onChange={(v) => updateField("paymentTerms", v)} onAiAccept={(v) => updateField("paymentTerms", v, "AI 제안")} />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">인원 / 기간</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-[100px_1fr]">
              <KVRow label="PM" value={pm.value as string} source={pm.source} confidence={pm.confidence} changedFrom={pm.changedFrom} revision={revision} editLog={editLog["pm"]} aiSuggestion={aiSuggestions["pm"]} onChange={(v) => updateField("pm", v)} onAiAccept={(v) => updateField("pm", v, "AI 제안")} />
              <KVRow label="영업담당자" value={salesOwner.value as string} source={salesOwner.source} confidence={salesOwner.confidence} changedFrom={salesOwner.changedFrom} revision={revision} editLog={editLog["salesOwner"]} aiSuggestion={aiSuggestions["salesOwner"]} onChange={(v) => updateField("salesOwner", v)} onAiAccept={(v) => updateField("salesOwner", v, "AI 제안")} />
              <KVRow label="시작일" value={startDate.value as string} source={startDate.source} confidence={startDate.confidence} changedFrom={startDate.changedFrom} isDate revision={revision} editLog={editLog["startDate"]} aiSuggestion={aiSuggestions["startDate"]} onChange={(v) => updateField("startDate", v)} onAiAccept={(v) => updateField("startDate", v, "AI 제안")} />
              <KVRow label="종료일" value={endDate.value as string} source={endDate.source} confidence={endDate.confidence} changedFrom={endDate.changedFrom} isDate revision={revision} editLog={editLog["endDate"]} aiSuggestion={aiSuggestions["endDate"]} onChange={(v) => updateField("endDate", v)} onAiAccept={(v) => updateField("endDate", v, "AI 제안")} />
              <KVRow label="년도구분" value={fiscalYear.value as string} source={fiscalYear.source} confidence={fiscalYear.confidence} changedFrom={fiscalYear.changedFrom} isYear revision={revision} editLog={editLog["fiscalYear"]} aiSuggestion={aiSuggestions["fiscalYear"]} onChange={(v) => updateField("fiscalYear", v)} onAiAccept={(v) => updateField("fiscalYear", v, "AI 제안")} />
              <KVRow label="견적서작성일" value={writtenDate.value as string} source={writtenDate.source} confidence={writtenDate.confidence} changedFrom={writtenDate.changedFrom} isDate revision={revision} editLog={editLog["writtenDate"]} aiSuggestion={aiSuggestions["writtenDate"]} onChange={(v) => updateField("writtenDate", v)} onAiAccept={(v) => updateField("writtenDate", v, "AI 제안")} />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="pt-6 space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">사업범위</label>
            <Textarea defaultValue={scope.value as string} rows={4} />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-2">
              특기사항
              {specialNotes.confidence === "guess" && <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-300">추측</Badge>}
            </label>
            <Textarea defaultValue={specialNotes.value as string} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── 편집 가능한 셀 컴포넌트 ───
function EditableCell({ value, onChange, className = "", align = "left", mono = false, edited = false, source }: {
  value: string | number; onChange: (v: string) => void; className?: string; align?: "left" | "right" | "center"; mono?: boolean; edited?: boolean; source?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const committed = React.useRef(false);

  const startEdit = () => {
    committed.current = false;
    setDraft(String(value));
    setEditing(true);
  };

  const commit = () => {
    if (committed.current) return;
    committed.current = true;
    if (draft !== String(value)) onChange(draft);
    setEditing(false);
  };

  const cancel = () => {
    committed.current = true;
    setEditing(false);
  };

  if (editing) {
    return (
      <Input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
        onBlur={commit} onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") cancel(); }}
        className={`h-7 text-xs w-full ${align === "right" ? "text-right" : align === "center" ? "text-center" : ""} ${mono ? "font-mono" : ""}`} />
    );
  }

  const display = mono && typeof value === "number" ? fmt(value) : String(value);
  const textAlign = align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";

  return (
    <div
      className={`group/cell cursor-pointer rounded px-1 py-0.5 hover:bg-primary/5 hover:ring-1 hover:ring-primary/20 transition-all ${textAlign} ${mono ? "font-mono" : ""} ${edited ? "bg-blue-50 dark:bg-blue-950/30 ring-1 ring-blue-200 dark:ring-blue-800" : ""} ${className}`}
      onClick={startEdit}
    >
      <span className={`flex items-center gap-1 ${align === "right" ? "justify-end" : ""}`}>
        {display}
        {edited && <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" title="수동 수정" />}
      </span>
      {source && !edited && (
        <span className="block text-[10px] leading-tight mt-0.5 text-muted-foreground truncate">{source}</span>
      )}
      {edited && (
        <span className="block text-[10px] leading-tight mt-0.5 text-blue-500">수동 수정</span>
      )}
    </div>
  );
}

function TabCalc() {
  const { extractedData, setExtractedData, projectId } = useApp();
  const [sub, setSub] = useState("fee");
  const initialItems = (extractedData?.costItems || []) as CostItem[];
  const [items, setItems] = useState<CostItem[]>(initialItems);
  const [originalItems, setOriginalItems] = useState<CostItem[]>(initialItems.map((i) => ({ ...i })));
  const [extracting, setExtracting] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const syncingFromContext = React.useRef(false);

  // extractedData.costItems가 외부에서 바뀌면 동기화 (추출 등)
  React.useEffect(() => {
    const newItems = extractedData?.costItems || [];
    if (newItems.length > 0 && newItems !== items) {
      syncingFromContext.current = true;
      setItems(newItems as CostItem[]);
      setOriginalItems(newItems.map((i) => ({ ...i } as CostItem)));
    }
  }, [extractedData?.costItems]);

  // items 수정 시 extractedData에 반영 → page.tsx 디바운스 자동저장 트리거
  React.useEffect(() => {
    if (items.length === 0) return;
    if (syncingFromContext.current) {
      syncingFromContext.current = false;
      return;
    }
    setExtractedData((prev) => {
      if (!prev) return prev;
      if (prev.costItems === items) return prev;
      return { ...prev, costItems: items };
    });
  }, [items]);

  const isCellEdited = (rowIdx: number, field: keyof CostItem): boolean => {
    const row = rows[rowIdx];
    const globalIdx = items.indexOf(row);
    const orig = originalItems[globalIdx];
    if (!orig) return false;
    return String(row[field]) !== String(orig[field]);
  };

  const CAT_LABELS: Record<string, string> = {
    fee: "수수료", material: "재료비", labor: "노무비", line: "회선비",
    supply: "소모품비", travel: "여비교통비", other: "기타",
  };

  const cats = Object.keys(CAT_LABELS);
  const countByCategory = (cat: string) => items.filter((i) => i.category === cat).length;
  const rows = items.filter((i) => i.category === sub);
  const total = rows.reduce((s, r) => s + (r.executionAmount || r.contractAmount || 0), 0);

  const doExtract = async () => {
    setExtracting(true);
    setElapsed(0);
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    try {
      const storedFiles = projectId && extractedData?.files
        ? { projectId, filenames: extractedData.files.map((f) => f.name) }
        : undefined;
      const result = await apiExtractCosts([], storedFiles);
      const extracted = (result.items || []) as CostItem[];
      setItems(extracted);
      setOriginalItems(extracted.map((i) => ({ ...i })));
    } catch (err) {
      console.error("산출내역 추출 실패:", err);
    } finally {
      clearInterval(timer);
      setExtracting(false);
    }
  };

  const removeRow = (idx: number) => {
    const globalIdx = items.indexOf(rows[idx]);
    if (globalIdx >= 0) setItems((prev) => prev.filter((_, i) => i !== globalIdx));
  };

  const updateRow = (idx: number, field: keyof CostItem, val: string) => {
    const globalIdx = items.indexOf(rows[idx]);
    if (globalIdx < 0) return;
    const numericFields = ["contractQty", "contractPrice", "contractAmount", "executionQty", "executionPrice", "executionAmount"] as const;
    const isNumeric = (numericFields as readonly string[]).includes(field);
    const parsed = isNumeric ? Number(val.replace(/,/g, "")) : val;
    if (isNumeric && isNaN(parsed as number)) return;
    setItems((prev) => prev.map((item, i) => {
      if (i !== globalIdx) return item;
      const updated = { ...item, [field]: parsed };
      if (field === "contractQty" || field === "contractPrice") {
        updated.contractAmount = updated.contractQty * updated.contractPrice;
      }
      if (field === "executionQty" || field === "executionPrice") {
        updated.executionAmount = updated.executionQty * updated.executionPrice;
      }
      return updated;
    }));
  };

  return (
    <div className="space-y-4">
      {items.length === 0 && !extracting && (
        <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950/20">
          <Info className="h-4 w-4 text-blue-600" />
          <AlertTitle className="text-blue-800 dark:text-blue-200">산출내역 추출</AlertTitle>
          <AlertDescription className="text-blue-700 dark:text-blue-300 flex items-center justify-between">
            <span>업로드된 문서에서 비용 항목을 AI로 추출합니다.</span>
            <Button variant="outline" size="sm" onClick={doExtract}>
              <RefreshCw className="h-3.5 w-3.5 mr-1" /> 추출 시작
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {extracting && (
        <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950/20">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
          <AlertTitle className="text-blue-800 dark:text-blue-200">산출내역 추출 중… {elapsed}초</AlertTitle>
          <AlertDescription className="text-blue-700 dark:text-blue-300">문서에서 비용 항목을 분석하고 있습니다.</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="flex gap-1 bg-muted rounded-lg p-0.5 flex-wrap">
            {cats.map((cat) => {
              const count = countByCategory(cat);
              return (
                <button key={cat}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${sub === cat ? "bg-card shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                  onClick={() => setSub(cat)}
                >
                  {CAT_LABELS[cat]} ({count})
                </button>
              );
            })}
          </div>
          <div className="flex gap-2">
            {items.length > 0 && (
              <Button variant="ghost" size="sm" onClick={doExtract}>
                <RefreshCw className="h-3 w-3 mr-1" /> 재추출
              </Button>
            )}
            <Button variant="outline" size="sm"><Plus className="h-3 w-3 mr-1" /> 행 추가</Button>
          </div>
        </CardHeader>
        <CardContent>
          {rows.length === 0 ? (
            <div className="py-16 text-center">
              <div className="text-sm font-semibold">데이터가 없습니다</div>
              <div className="text-xs text-muted-foreground mt-1">
                {items.length === 0 ? "상단 '추출 시작'으로 문서에서 추출하거나 행을 직접 추가하세요." : "이 카테고리에 해당하는 항목이 없습니다."}
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="text-left py-2 px-3 font-medium min-w-[180px]">품명</th>
                    <th className="text-left py-2 px-3 font-medium">규격</th>
                    <th className="text-left py-2 px-3 font-medium">단위</th>
                    <th className="text-right py-2 px-3 font-medium" colSpan={3}>계약</th>
                    <th className="text-right py-2 px-3 font-medium border-l" colSpan={3}>집행</th>
                    <th className="text-left py-2 px-3 font-medium">협력사</th>
                    <th className="py-2 px-1"></th>
                  </tr>
                  <tr className="border-b text-muted-foreground text-xs">
                    <th></th><th></th><th></th>
                    <th className="text-right py-1 px-2">수량</th>
                    <th className="text-right py-1 px-2">단가</th>
                    <th className="text-right py-1 px-2">금액</th>
                    <th className="text-right py-1 px-2 border-l">수량</th>
                    <th className="text-right py-1 px-2">단가</th>
                    <th className="text-right py-1 px-2">금액</th>
                    <th></th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i} className="border-b hover:bg-muted/50">
                      <td className="py-1 px-1">
                        <EditableCell value={r.name} onChange={(v) => updateRow(i, "name", v)} edited={isCellEdited(i, "name")} source={r.source} className="text-xs font-medium" />
                      </td>
                      <td className="py-1 px-1">
                        <EditableCell value={r.spec} onChange={(v) => updateRow(i, "spec", v)} edited={isCellEdited(i, "spec")} className="text-xs" />
                      </td>
                      <td className="py-1 px-1">
                        <EditableCell value={r.unit} onChange={(v) => updateRow(i, "unit", v)} edited={isCellEdited(i, "unit")} className="text-xs" />
                      </td>
                      <td className="py-1 px-1">
                        <EditableCell value={r.contractQty} onChange={(v) => updateRow(i, "contractQty", v)} edited={isCellEdited(i, "contractQty")} align="right" mono className="text-xs" />
                      </td>
                      <td className="py-1 px-1">
                        <EditableCell value={r.contractPrice} onChange={(v) => updateRow(i, "contractPrice", v)} edited={isCellEdited(i, "contractPrice")} align="right" mono className="text-xs" />
                      </td>
                      <td className="py-1 px-1">
                        <EditableCell value={r.contractAmount} onChange={(v) => updateRow(i, "contractAmount", v)} edited={isCellEdited(i, "contractAmount")} align="right" mono className="text-xs" />
                      </td>
                      <td className="py-1 px-1 border-l">
                        <EditableCell value={r.executionQty} onChange={(v) => updateRow(i, "executionQty", v)} edited={isCellEdited(i, "executionQty")} align="right" mono className="text-xs" />
                      </td>
                      <td className="py-1 px-1">
                        <EditableCell value={r.executionPrice} onChange={(v) => updateRow(i, "executionPrice", v)} edited={isCellEdited(i, "executionPrice")} align="right" mono className="text-xs" />
                      </td>
                      <td className="py-1 px-1">
                        <EditableCell value={r.executionAmount} onChange={(v) => updateRow(i, "executionAmount", v)} edited={isCellEdited(i, "executionAmount")} align="right" mono className="text-xs font-medium" />
                      </td>
                      <td className="py-1 px-1">
                        <EditableCell value={r.vendor || ""} onChange={(v) => updateRow(i, "vendor", v)} edited={isCellEdited(i, "vendor")} className="text-xs" />
                      </td>
                      <td className="py-2 px-1">
                        <button className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive" onClick={() => removeRow(i)}>
                          <X className="h-3 w-3" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2">
                    <td colSpan={5} className="py-2.5 px-3 text-right font-semibold">합계</td>
                    <td className="py-2.5 px-2 text-right font-mono font-bold text-xs">{fmt(rows.reduce((s, r) => s + (r.contractAmount || 0), 0))}</td>
                    <td colSpan={2} className="border-l"></td>
                    <td className="py-2.5 px-2 text-right font-mono font-bold text-xs">{fmt(total)}</td>
                    <td></td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function TabPeople() {
  const { extractedData } = useApp();
  const mapCat = (type: string) => type === "간접" || type === "외부" ? "외부" : "자사";
  const initPeople = (extractedData?.staffPlan || []).map((s) => ({
    name: s.name, role: s.role, grade: s.grade || "", cat: mapCat(s.type || "직접"), company: s.company || (mapCat(s.type || "직접") === "자사" ? "GS네오텍" : ""), values: s.months?.length === 12 ? s.months : Array(12).fill(0),
  }));
  type Person = { name: string; role: string; grade: string; cat: string; company: string; values: number[] };
  const [people, setPeople] = useState<Person[]>(initPeople);
  const [originalPeople, setOriginalPeople] = useState<Person[]>(initPeople.map((p) => ({ ...p, values: [...p.values] })));
  const [showAdd, setShowAdd] = useState(false);

  // extractedData.staffPlan이 재추출로 바뀌면 동기화
  React.useEffect(() => {
    const newPlan = extractedData?.staffPlan || [];
    if (newPlan.length === 0) return;
    const mapped = newPlan.map((s) => ({
      name: s.name, role: s.role, grade: s.grade || "", cat: mapCat(s.type || "직접"),
      company: s.company || (mapCat(s.type || "직접") === "자사" ? "GS네오텍" : ""),
      values: s.months?.length === 12 ? s.months : Array(12).fill(0),
    }));
    setPeople(mapped);
    setOriginalPeople(mapped.map((p) => ({ ...p, values: [...p.values] })));
  }, [extractedData?.staffPlan]);
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState("");
  const [newCat, setNewCat] = useState("자사");
  const startDateStr = (extractedData?.extracted?.startDate?.value as string) || "";
  const startMonth = startDateStr ? parseInt(startDateStr.replace(/[^0-9.]/g, "").split(".")[1] || "1", 10) : 1;
  const months = Array.from({ length: 12 }, (_, i) => `${((startMonth - 1 + i) % 12) + 1}월`);

  const addPerson = () => {
    if (!newName.trim()) return;
    setPeople((prev) => [...prev, { name: newName, role: newRole, grade: "", cat: newCat, company: newCat === "자사" ? "GS네오텍" : "", values: Array(12).fill(0) }]);
    setNewName(""); setNewRole(""); setNewCat("자사"); setShowAdd(false);
  };

  const removePerson = (idx: number) => setPeople((prev) => prev.filter((_, i) => i !== idx));

  const updateMM = (personIdx: number, monthIdx: number, val: string) => {
    const num = parseFloat(val);
    if (isNaN(num)) return;
    setPeople((prev) => prev.map((p, i) =>
      i === personIdx ? { ...p, values: p.values.map((v, j) => j === monthIdx ? num : v) } : p
    ));
  };

  const isPersonEdited = (idx: number, field: "name" | "role" | "cat"): boolean => {
    const orig = originalPeople[idx];
    if (!orig) return false;
    return people[idx][field] !== orig[field];
  };

  const isMMEdited = (personIdx: number, monthIdx: number): boolean => {
    const orig = originalPeople[personIdx];
    if (!orig) return false;
    return people[personIdx].values[monthIdx] !== orig.values[monthIdx];
  };

  const internalCount = people.filter((p) => p.cat === "자사").length;
  const externalCount = people.filter((p) => p.cat === "외부").length;
  const totalMM = people.reduce((s, p) => s + p.values.reduce((a, v) => a + v, 0), 0);

  return (
    <div className="space-y-4">
      {people.length > 0 && (
        <div className="grid grid-cols-4 gap-4">
          <Card className="p-5">
            <div className="text-xs text-muted-foreground">총 투입 인원</div>
            <div className="text-2xl font-bold mt-1">{people.length}<span className="text-sm font-normal text-muted-foreground ml-1">명</span></div>
          </Card>
          <Card className="p-5">
            <div className="text-xs text-muted-foreground">자사 인원</div>
            <div className="text-2xl font-bold mt-1 text-blue-600">{internalCount}<span className="text-sm font-normal text-muted-foreground ml-1">명</span></div>
          </Card>
          <Card className="p-5">
            <div className="text-xs text-muted-foreground">외부 인원</div>
            <div className="text-2xl font-bold mt-1 text-amber-600">{externalCount}<span className="text-sm font-normal text-muted-foreground ml-1">명</span></div>
          </Card>
          <Card className="p-5">
            <div className="text-xs text-muted-foreground">총 M/M</div>
            <div className="text-2xl font-bold mt-1">{totalMM.toFixed(1)}<span className="text-sm font-normal text-muted-foreground ml-1">M/M</span></div>
          </Card>
        </div>
      )}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base">월별 M/M 배분</CardTitle>
            <CardDescription>자사 = GS네오텍 소속 직원 · 외부 = 협력사/파견 인력</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => setShowAdd(true)}><Plus className="h-3 w-3 mr-1" /> 인원 추가</Button>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {people.length === 0 ? (
            <div className="py-16 text-center">
              <div className="text-sm font-semibold">투입 인원이 없습니다</div>
              <div className="text-xs text-muted-foreground mt-1">인원 추가 버튼으로 투입 인원을 등록하세요.</div>
              <Button variant="outline" size="sm" className="mt-4" onClick={() => setShowAdd(true)}><Plus className="h-3 w-3 mr-1" /> 인원 추가</Button>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-left py-2 px-2 font-medium min-w-[160px]">성명 / 직위</th>
                  <th className="text-left py-2 px-2 font-medium">구분</th>
                  {months.map((m) => <th key={m} className="text-center py-2 px-1 font-medium text-xs">{m}</th>)}
                  <th className="text-center py-2 px-2 font-medium">합계</th>
                  <th className="py-2 px-1"></th>
                </tr>
              </thead>
              <tbody>
                {people.map((p, i) => (
                  <tr key={i} className="border-b">
                    <td className="py-1 px-1">
                      <div className="flex items-center gap-1.5">
                        <EditableCell value={p.name} onChange={(v) => setPeople((prev) => prev.map((pp, pi) => pi === i ? { ...pp, name: v } : pp))} edited={isPersonEdited(i, "name")} className="text-xs font-medium" />
                        {p.grade && <span className="text-[10px] text-muted-foreground shrink-0">({p.grade})</span>}
                      </div>
                      <EditableCell value={p.role} onChange={(v) => setPeople((prev) => prev.map((pp, pi) => pi === i ? { ...pp, role: v } : pp))} edited={isPersonEdited(i, "role")} className="text-xs" />
                    </td>
                    <td className="py-1 px-2">
                      <Badge
                        variant="secondary"
                        className={`cursor-pointer ${p.cat === "자사" ? "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300" : "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"}`}
                        onClick={() => setPeople((prev) => prev.map((pp, pi) => pi === i ? { ...pp, cat: pp.cat === "자사" ? "외부" : "자사" } : pp))}
                      >
                        {p.cat}
                      </Badge>
                      {p.company && p.company !== "GS네오텍" && (
                        <div className="text-[10px] text-muted-foreground mt-0.5">{p.company}</div>
                      )}
                    </td>
                    {p.values.map((v, j) => (
                      <td key={j} className="py-1 px-0.5">
                        <EditableCell value={v.toFixed(1)} onChange={(val) => updateMM(i, j, val)} edited={isMMEdited(i, j)} align="center" mono className="text-xs" />
                      </td>
                    ))}
                    <td className="text-center py-2 px-2 font-mono font-bold">{p.values.reduce((s, v) => s + v, 0).toFixed(1)}</td>
                    <td className="py-2 px-1">
                      <button className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive" onClick={() => removePerson(i)}>
                        <X className="h-3 w-3" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowAdd(false)}>
          <div className="w-full max-w-sm rounded-xl border bg-card p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-bold mb-4">인원 추가</h3>
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-sm font-medium">성명 <span className="text-destructive">*</span></label>
                <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="예) 홍길동 책임" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">역할</label>
                <Input value={newRole} onChange={(e) => setNewRole(e.target.value)} placeholder="예) PM, 운영, 개발" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">구분</label>
                <div className="flex gap-2">
                  <Button variant={newCat === "자사" ? "default" : "outline"} size="sm" onClick={() => setNewCat("자사")}>자사</Button>
                  <Button variant={newCat === "외부" ? "default" : "outline"} size="sm" onClick={() => setNewCat("외부")}>외부</Button>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <Button variant="ghost" onClick={() => setShowAdd(false)}>취소</Button>
              <Button onClick={addPerson} disabled={!newName.trim()}>추가</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TabSchedule() {
  const { extractedData } = useApp();
  const startDateStr = (extractedData?.extracted?.startDate?.value as string) || "";
  const startMonth = startDateStr ? parseInt(startDateStr.replace(/[^0-9.]/g, "").split(".")[1] || "1", 10) : 1;
  const months = Array.from({ length: 12 }, (_, i) => `${((startMonth - 1 + i) % 12) + 1}월`);
  const colors = ["bg-blue-500", "bg-purple-500", "bg-emerald-500", "bg-amber-500", "bg-red-500", "bg-cyan-500"];
  const initItems = (extractedData?.schedule || []).map((s, i) => ({
    name: s.name, start: s.startMonth, end: s.endMonth, color: colors[i % colors.length],
  }));
  const [items, setItems] = useState<{ name: string; start: number; end: number; color: string }[]>(initItems);

  React.useEffect(() => {
    const newSchedule = extractedData?.schedule || [];
    if (newSchedule.length === 0) return;
    setItems(newSchedule.map((s, i) => ({
      name: s.name, start: s.startMonth, end: s.endMonth, color: colors[i % colors.length],
    })));
  }, [extractedData?.schedule]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">예정공정표</CardTitle>
        <Button variant="outline" size="sm"><Plus className="h-3 w-3 mr-1" /> 공종 추가</Button>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="py-16 text-center">
            <div className="text-sm font-semibold">공종이 없습니다</div>
            <div className="text-xs text-muted-foreground mt-1">공종 추가 버튼으로 예정공정표를 작성하세요.</div>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-muted-foreground">
                <th className="text-left py-2 px-3 font-medium">공종명</th>
                {months.map((m) => <th key={m} className="text-center py-2 px-1 font-medium text-xs min-w-[50px]">{m}</th>)}
              </tr>
            </thead>
            <tbody>
              {items.map((c, i) => (
                <tr key={i}>
                  <td className="py-1 px-3 text-xs font-medium">{c.name}</td>
                  {Array.from({ length: 12 }).map((_, m) => (
                    <td key={m} className="p-0">
                      <div className="h-8 px-0.5 flex items-center">
                        {m >= c.start && m <= c.end && (
                          <div className={`h-5 w-full ${c.color} opacity-85 ${
                            m === c.start && m === c.end ? "rounded" : m === c.start ? "rounded-l" : m === c.end ? "rounded-r" : ""
                          }`} />
                        )}
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function RateInput({ label, placeholder, committed, edited, source, onCommit }: {
  label: string; placeholder: string; committed: string;
  edited: boolean; source: string; onCommit: (v: string) => void;
}) {
  const [local, setLocal] = React.useState(committed);
  React.useEffect(() => { setLocal(committed); }, [committed]);

  return (
    <div className="space-y-1">
      <label className="text-sm font-medium">{label}</label>
      <Input
        value={local}
        placeholder={placeholder}
        onChange={(e) => {
          const v = e.target.value;
          // 숫자, 소수점, 빈값만 허용
          if (v === "" || /^\d*\.?\d*$/.test(v)) setLocal(v);
        }}
        onBlur={() => onCommit(local)}
        className={edited ? "border-blue-300 bg-blue-50/50" : ""}
      />
      <div className="flex items-center gap-2">
        {source && <span className={`text-[11px] ${edited ? "text-blue-500" : "text-muted-foreground"}`}>{source}</span>}
        {edited && <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500" />}
      </div>
    </div>
  );
}

function TabRates() {
  const { extractedData, setExtractedData } = useApp();
  const r = extractedData?.rates;

  const applyDefaults = () => {
    const { loadDefaultRates } = require("@/components/pages/settings-page");
    const defaults = loadDefaultRates();
    const keyMap: Record<string, string> = {
      nationalPension: "nationalPension", healthInsurance: "healthInsurance",
      industrialAccident: "industrialAccident", employmentInsurance: "employmentInsurance",
      indirectRate: "indirectRate", adminRate: "adminRate",
    };
    setExtractedData((prev: ExtractedData | null) => {
      if (!prev) return prev;
      const rates = prev.rates || { indirectRate: { value: 0, source: "" }, adminRate: { value: 0, source: "" }, nationalPension: { value: 0, source: "" }, healthInsurance: { value: 0, source: "" }, employmentInsurance: { value: 0, source: "" }, industrialAccident: { value: 0, source: "" } };
      const updated = { ...rates };
      for (const [dk, rk] of Object.entries(keyMap)) {
        const dv = defaults[dk as keyof typeof defaults];
        const existing = (updated as Record<string, { value: number; source: string }>)[rk];
        if (dv && (!existing?.value || existing.value === 0)) {
          (updated as Record<string, { value: number; source: string }>)[rk] = { value: dv, source: "기본값" };
        }
      }
      return { ...prev, rates: updated };
    });
  };

  type RateKey = "indirectRate" | "adminRate" | "nationalPension" | "healthInsurance" | "employmentInsurance" | "industrialAccident";
  const fields: { key: RateKey; label: string; placeholder: string }[] = [
    { key: "indirectRate", label: "간접비 요율 (%)", placeholder: "입력" },
    { key: "adminRate", label: "일반관리비 요율 (%)", placeholder: "입력" },
    { key: "nationalPension", label: "국민연금 (%)", placeholder: "4.5" },
    { key: "healthInsurance", label: "건강보험 (%)", placeholder: "인사팀 공지 참조" },
    { key: "employmentInsurance", label: "고용보험 (%)", placeholder: "인사팀 공지 참조" },
    { key: "industrialAccident", label: "산재보험 (%)", placeholder: "안전보건팀 공지 참조" },
  ];

  const updateRate = (key: RateKey, val: string) => {
    // 입력 중인 상태("1.", "1.7" 등) 허용 — onBlur에서 최종 저장
    const num = parseFloat(val);
    setExtractedData((prev) => {
      if (!prev) return prev;
      const rates = prev.rates || { indirectRate: { value: 0, source: "" }, adminRate: { value: 0, source: "" }, nationalPension: { value: 0, source: "" }, healthInsurance: { value: 0, source: "" }, employmentInsurance: { value: 0, source: "" }, industrialAccident: { value: 0, source: "" } };
      return { ...prev, rates: { ...rates, [key]: { value: val === "" ? 0 : isNaN(num) ? 0 : num, source: "수동 수정" } } };
    });
  };

  return (
    <div className="grid grid-cols-2 gap-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">요율</CardTitle>
          <Button variant="outline" size="sm" onClick={applyDefaults}>기본값 적용</Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {fields.map((f) => {
            const entry = r?.[f.key];
            const committed = entry?.value ? String(entry.value) : "";
            const source = entry?.source || "";
            const edited = source === "수동 수정";
            return (
              <RateInput
                key={f.key}
                label={f.label}
                placeholder={f.placeholder}
                committed={committed}
                edited={edited}
                source={source}
                onCommit={(v) => updateRate(f.key, v)}
              />
            );
          })}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle className="text-base">보증 / 수금</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold">선급금</div>
              <div className="text-xs text-muted-foreground">비율과 보증금액을 설정하세요</div>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold">계약이행</div>
              <div className="text-xs text-muted-foreground">비율과 보증금액을 설정하세요</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function TabOrg() {
  const { extractedData } = useApp();
  const initMembers = (extractedData?.organization || []).map((o) => ({
    role: o.role, name: o.name, scope: o.scope, lead: o.lead,
  }));
  const [members, setMembers] = useState<{ role: string; name: string; scope: string; lead?: boolean }[]>(initMembers);
  const [originalMembers, setOriginalMembers] = useState(initMembers.map((m) => ({ ...m })));

  React.useEffect(() => {
    const newOrg = extractedData?.organization || [];
    if (newOrg.length === 0) return;
    const mapped = newOrg.map((o) => ({ role: o.role, name: o.name, scope: o.scope, lead: o.lead }));
    setMembers(mapped);
    setOriginalMembers(mapped.map((m) => ({ ...m })));
  }, [extractedData?.organization]);

  const isMemberEdited = (idx: number, field: "role" | "name" | "scope"): boolean => {
    const orig = originalMembers[idx];
    if (!orig) return false;
    return members[idx][field] !== orig[field];
  };

  const updateMember = (idx: number, field: "role" | "name" | "scope", val: string) => {
    setMembers((prev) => prev.map((m, i) => i === idx ? { ...m, [field]: val } : m));
  };

  const removeMember = (idx: number) => {
    setMembers((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">현장조직 / 업무분장</CardTitle>
        <Button variant="outline" size="sm"><Plus className="h-3 w-3 mr-1" /> 인원 추가</Button>
      </CardHeader>
      <CardContent>
        {members.length === 0 ? (
          <div className="py-16 text-center">
            <div className="text-sm font-semibold">등록된 인원이 없습니다</div>
            <div className="text-xs text-muted-foreground mt-1">인원 추가 버튼으로 현장조직을 구성하세요.</div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {members.map((m, i) => (
              <div key={i} className={`rounded-lg border p-4 relative group ${m.lead ? "border-blue-200 bg-blue-50/50 dark:bg-blue-950/20" : ""}`}>
                <button className="absolute top-2 right-2 p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity" onClick={() => removeMember(i)}>
                  <X className="h-3 w-3" />
                </button>
                <div className="flex items-center gap-2 mb-1">
                  <EditableCell value={m.role} onChange={(v) => updateMember(i, "role", v)} edited={isMemberEdited(i, "role")} className="text-xs" />
                  <EditableCell value={m.name} onChange={(v) => updateMember(i, "name", v)} edited={isMemberEdited(i, "name")} className="text-sm font-semibold" />
                </div>
                <EditableCell value={m.scope} onChange={(v) => updateMember(i, "scope", v)} edited={isMemberEdited(i, "scope")} className="text-xs" />
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TabActionBar({ tabId, confirmed, onConfirm, onUnconfirm, onReExtract, reExtracting, reExtractElapsed }: {
  tabId: string; confirmed: boolean;
  onConfirm: () => void; onUnconfirm: () => void; onReExtract: () => void;
  reExtracting: boolean; reExtractElapsed: number;
}) {
  const TAB_NAMES: Record<string, string> = {
    basic: "기본 정보", calc: "산출내역", people: "인원투입계획",
    schedule: "공사·공정표", rates: "요율·보증", org: "현장조직",
  };

  return (
    <div className={`flex items-center justify-between rounded-lg border px-5 py-3 ${
      confirmed ? "border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20" : "bg-card"
    }`}>
      <div className="flex items-center gap-3">
        {confirmed ? (
          <>
            <Check className="h-4 w-4 text-emerald-600" />
            <span className="text-sm font-medium text-emerald-700 dark:text-emerald-300">
              {TAB_NAMES[tabId]} 확인 완료
            </span>
            <Button variant="ghost" size="sm" className="text-xs text-muted-foreground" onClick={onUnconfirm}>
              확인 취소
            </Button>
          </>
        ) : (
          <span className="text-sm text-muted-foreground">
            {TAB_NAMES[tabId]} 내용을 검토한 후 확인해 주세요.
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onReExtract} disabled={reExtracting}>
          {reExtracting ? (
            <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> 재추출 중… {reExtractElapsed}초</>
          ) : (
            <><RefreshCw className="h-3.5 w-3.5 mr-1" /> 이 탭만 재추출</>
          )}
        </Button>
        {!confirmed && (
          <Button size="sm" onClick={onConfirm}>
            <Check className="h-3.5 w-3.5 mr-1" /> 확인 완료
          </Button>
        )}
      </div>
    </div>
  );
}


// ─── 변경 이력 탭 (전체 차수별 변경 내역 요약) ───

function TabHistory() {
  const { projectId, maxRevision, revision: currentRevision, extractedData } = useApp();
  const [serverRevisions, setServerRevisions] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  const FIELD_LABELS: Record<string, string> = {
    projectName: "사업명", client: "발주처", contractor: "계약처",
    contractType: "계약방법", paymentTerms: "수금조건", pm: "PM",
    salesOwner: "영업담당자", startDate: "시작일", endDate: "종료일",
    revenue: "매출", cost: "매입", profit: "영업이익",
    indirectCost: "간접비", fiscalYear: "년도구분", writtenDate: "견적서작성일",
  };

  useEffect(() => {
    if (!projectId) return;
    (async () => {
      try {
        const FASTAPI = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";
        const res = await fetch(`${FASTAPI}/api/projects/${projectId}`);
        if (res.ok) {
          const data = await res.json();
          setServerRevisions(data.revisions || {});
        }
      } catch {}
      setLoading(false);
    })();
  }, [projectId]);

  // 현재 차수는 메모리(extractedData)로 덮어씀 — 저장 전 변경사항도 즉시 반영
  const revisions = { ...serverRevisions };
  if (extractedData && currentRevision != null) {
    revisions[String(currentRevision)] = extractedData;
  }

  if (loading) return <div className="text-center py-8 text-muted-foreground">로딩 중...</div>;

  const revNums = Object.keys(revisions).map(Number).sort();
  if (revNums.length < 2) return <div className="text-center py-8 text-muted-foreground">변경 이력이 없습니다.</div>;

  const fmtVal = (v: unknown) => {
    if (v == null || v === "") return "-";
    if (typeof v === "number") return v >= 10000 ? `${(v / 1000).toLocaleString()}천원` : String(v);
    return String(v);
  };

  return (
    <div className="space-y-6">
      {/* 차수별 타임라인 */}
      <Card>
        <CardHeader><CardTitle className="text-base">차수별 변경 요약</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-4">
            {revNums.map((revNum) => {
              const revData = revisions[String(revNum)];
              const ext = revData?.extracted || revData || {};
              // changedFields가 없으면 이전 차수와 직접 비교
              const prevRevData = revNum > 0 ? revisions[String(revNum - 1)] : null;
              const prevExt = prevRevData?.extracted || prevRevData || {};
              const storedChanged = revData?.changedFields || {};
              const changed: Record<string, { prev: unknown }> = Object.keys(storedChanged).length > 0
                ? storedChanged
                : prevRevData
                  ? Object.fromEntries(
                      Object.keys(FIELD_LABELS).filter((k) => {
                        const curr = ext[k]?.value ?? null;
                        const prev = prevExt[k]?.value ?? null;
                        return curr != null && prev != null && String(curr) !== String(prev);
                      }).map((k) => [k, { prev: prevExt[k]?.value }])
                    )
                  : {};
              const changedKeys = Object.keys(changed);
              const files = revData?.files || [];
              const costItems = revData?.costItems || [];

              // 이전 차수 파일과 비교
              const prevRevNum = revNum > 0 ? revNum - 1 : null;
              const prevFiles = prevRevNum != null ? (revisions[String(prevRevNum)]?.files || []) : [];
              const prevFileNames = new Set(prevFiles.map((f: any) => f.name));
              const currFileNames = new Set(files.map((f: any) => f.name));
              const addedFiles = files.filter((f: any) => !prevFileNames.has(f.name));
              const removedFiles = prevFiles.filter((f: any) => !currFileNames.has(f.name));

              return (
                <div key={revNum} className="border rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      revNum === 0 ? "bg-gray-100 text-gray-700" : "bg-blue-100 text-blue-700"
                    }`}>
                      {revNum}차 {revNum === 0 ? "(최초)" : "(수정)"}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      매출 {fmtVal(ext.revenue?.value)} · 매입 {fmtVal(ext.cost?.value)} · 이익 {fmtVal(ext.profit?.value)}
                    </span>
                  </div>

                  {/* 변경된 필드 */}
                  {changedKeys.length > 0 && (
                    <div className="mb-3">
                      <div className="text-xs font-medium text-muted-foreground mb-1">변경 항목 ({changedKeys.length}건)</div>
                      <div className="grid grid-cols-1 gap-1">
                        {changedKeys.map((key) => (
                          <div key={key} className="flex items-center gap-2 text-xs">
                            <span className="font-medium min-w-[70px]">{FIELD_LABELS[key] || key}</span>
                            <span className="text-muted-foreground line-through">{fmtVal(changed[key]?.prev)}</span>
                            <span>→</span>
                            <span className="font-semibold">{fmtVal(ext[key]?.value)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 파일 변경 */}
                  {revNum > 0 && (addedFiles.length > 0 || removedFiles.length > 0) && (
                    <div className="mb-3">
                      <div className="text-xs font-medium text-muted-foreground mb-1">파일 변경</div>
                      {addedFiles.map((f: any) => (
                        <div key={f.name} className="text-xs text-emerald-600">+ {f.name}</div>
                      ))}
                      {removedFiles.map((f: any) => (
                        <div key={f.name} className="text-xs text-red-500">- {f.name}</div>
                      ))}
                    </div>
                  )}

                  {/* 파일 목록 */}
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-1">파일 ({files.length}건)</div>
                    <div className="flex flex-wrap gap-1">
                      {files.map((f: any) => (
                        <span key={f.name} className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-[10px]">
                          {f.name}
                        </span>
                      ))}
                      {files.length === 0 && <span className="text-[10px] text-muted-foreground italic">파일 없음</span>}
                    </div>
                  </div>

                  {/* 산출내역 요약 */}
                  {costItems.length > 0 && (
                    <div className="mt-2">
                      <div className="text-xs font-medium text-muted-foreground mb-1">산출내역 ({costItems.length}건)</div>
                      {costItems.map((item: any, i: number) => (
                        <div key={i} className="text-[10px] text-muted-foreground">
                          {item.name} {item.spec} — 계약 {fmtVal(item.contractPrice)}×{item.contractQty} / 집행 {fmtVal(item.executionPrice)}×{item.executionQty} ({item.vendor})
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* 금액 변동 추이 */}
      <Card>
        <CardHeader><CardTitle className="text-base">금액 변동 추이</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 pr-4">항목</th>
                  {revNums.map((r) => <th key={r} className="text-right py-2 px-2">{r}차</th>)}
                </tr>
              </thead>
              <tbody>
                {["revenue", "cost", "indirectCost", "profit"].map((key) => (
                  <tr key={key} className="border-b">
                    <td className="py-2 pr-4 font-medium">{FIELD_LABELS[key]}</td>
                    {revNums.map((r) => {
                      const ext = revisions[String(r)]?.extracted || revisions[String(r)] || {};
                      const val = ext[key]?.value;
                      return <td key={r} className="text-right py-2 px-2 font-mono">{val ? `${(val / 1000).toLocaleString()}천원` : "-"}</td>;
                    })}
                  </tr>
                ))}
                <tr>
                  <td className="py-2 pr-4 font-medium">이익률</td>
                  {revNums.map((r) => {
                    const ext = revisions[String(r)]?.extracted || revisions[String(r)] || {};
                    const rev = ext.revenue?.value || 0;
                    const profit = ext.profit?.value || 0;
                    const rate = rev > 0 ? ((profit / rev) * 100).toFixed(1) : "-";
                    return <td key={r} className="text-right py-2 px-2 font-mono">{rate}%</td>;
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* 요율 변동 */}
      <Card>
        <CardHeader><CardTitle className="text-base">요율 변동</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 pr-4">요율</th>
                  {revNums.map((r) => <th key={r} className="text-right py-2 px-2">{r}차</th>)}
                </tr>
              </thead>
              <tbody>
                {["indirectRate", "adminRate", "nationalPension", "healthInsurance", "industrialAccident", "employmentInsurance"].map((key) => {
                  const labels: Record<string, string> = {
                    indirectRate: "간접비", adminRate: "일반관리비",
                    nationalPension: "국민연금", healthInsurance: "건강보험",
                    industrialAccident: "산재보험", employmentInsurance: "고용보험",
                  };
                  return (
                    <tr key={key} className="border-b">
                      <td className="py-2 pr-4 font-medium">{labels[key]}</td>
                      {revNums.map((r) => {
                        const rates = revisions[String(r)]?.rates || {};
                        const val = rates[key]?.value;
                        return <td key={r} className="text-right py-2 px-2 font-mono">{val != null ? `${val}%` : "-"}</td>;
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
