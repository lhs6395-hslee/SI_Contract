/**
 * API 클라이언트
 * - AI 호출 (분류/추출/검증): Next.js API Route (/api/*)
 * - 파일 저장/조회, 엑셀 생성: FastAPI 백엔드 (별도 서버)
 */

const FASTAPI_BASE = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";

// ─── AI 호출 → Next.js API Route (Vertex/Bedrock) ───

export async function apiClassify(file: File): Promise<{
  category: string;
  confidence: number;
  reason: string;
}> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/classify", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`분류 실패: ${res.status}`);
  return res.json();
}

export async function apiExtract(
  files: File[],
  storedFiles?: { projectId: string; filenames: string[]; revision?: number },
): Promise<Record<string, { value: unknown; source: string; confidence: string }>> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  // 저장된 파일도 포함해서 추출하도록 메타데이터 전달
  if (storedFiles && storedFiles.filenames.length > 0) {
    formData.append("stored_files", JSON.stringify(storedFiles));
  }
  const res = await fetch("/api/extract", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`추출 실패: ${res.status}`);
  return res.json();
}

export async function apiValidate(data: Record<string, unknown>) {
  const res = await fetch("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`검증 실패: ${res.status}`);
  return res.json();
}

import type { CostItem } from "./types";
export type { CostItem } from "./types";

export async function apiExtractCosts(
  files: File[],
  storedFiles?: { projectId: string; filenames: string[]; revision?: number },
): Promise<{ items: CostItem[] }> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  if (storedFiles && storedFiles.filenames.length > 0) {
    formData.append("stored_files", JSON.stringify(storedFiles));
  }
  const res = await fetch("/api/extract-costs", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`산출내역 추출 실패: ${res.status}`);
  return res.json();
}

import type { StaffMember, ScheduleItem, Rates, OrgMember } from "./types";

async function tabExtract<T>(endpoint: string, fallback: T, storedFiles?: { projectId: string; filenames: string[]; revision?: number }): Promise<T> {
  const formData = new FormData();
  if (storedFiles && storedFiles.filenames.length > 0) {
    formData.append("stored_files", JSON.stringify(storedFiles));
  }
  const res = await fetch(endpoint, { method: "POST", body: formData });
  if (!res.ok) throw new Error(`추출 실패: ${res.status}`);
  return res.json();
}

export async function apiExtractPeople(
  storedFiles?: { projectId: string; filenames: string[]; revision?: number },
): Promise<{ staffPlan: StaffMember[] }> {
  return tabExtract("/api/extract-people", { staffPlan: [] }, storedFiles);
}

export async function apiExtractSchedule(
  storedFiles?: { projectId: string; filenames: string[]; revision?: number },
): Promise<{ schedule: ScheduleItem[] }> {
  return tabExtract("/api/extract-schedule", { schedule: [] }, storedFiles);
}

export async function apiExtractRates(
  storedFiles?: { projectId: string; filenames: string[]; revision?: number },
): Promise<{ rates: Rates | null }> {
  return tabExtract("/api/extract-rates", { rates: null }, storedFiles);
}

export async function apiExtractOrg(
  storedFiles?: { projectId: string; filenames: string[]; revision?: number },
): Promise<{ organization: OrgMember[] }> {
  return tabExtract("/api/extract-org", { organization: [] }, storedFiles);
}

// ─── 파일 저장/조회 → FastAPI 백엔드 (추후 S3 교체) ───

export async function apiUploadFiles(projectId: string, files: File[], revision?: number): Promise<{ filename: string; size: number }[]> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  const url = revision != null
    ? `${FASTAPI_BASE}/api/files/${projectId}/upload?revision=${revision}`
    : `${FASTAPI_BASE}/api/files/${projectId}/upload`;
  const res = await fetch(url, { method: "POST", body: formData });
  if (!res.ok) throw new Error(`파일 저장 실패: ${res.status}`);
  const data = await res.json();
  return data.files;
}

export async function apiListFiles(projectId: string, revision?: number): Promise<{ filename: string; size: number }[]> {
  const url = revision != null
    ? `${FASTAPI_BASE}/api/files/${projectId}?revision=${revision}`
    : `${FASTAPI_BASE}/api/files/${projectId}`;
  const res = await fetch(url);
  if (!res.ok) return [];
  const data = await res.json();
  return data.files;
}

export async function apiDeleteFile(projectId: string, filename: string, revision?: number) {
  const url = revision != null
    ? `${FASTAPI_BASE}/api/files/${projectId}/${encodeURIComponent(filename)}?revision=${revision}`
    : `${FASTAPI_BASE}/api/files/${projectId}/${encodeURIComponent(filename)}`;
  await fetch(url, { method: "DELETE" });
}

// ─── 엑셀 생성 → FastAPI 백엔드 ───

export async function apiExport(data: Record<string, unknown>): Promise<Blob> {
  const res = await fetch(`${FASTAPI_BASE}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`엑셀 생성 실패: ${res.status}`);
  return res.blob();
}

// ─── 하네스 파이프라인 → FastAPI 백엔드 ───

export interface PipelineResult {
  projectId: string;
  status: string;
  steps: Record<string, { sheet: string; status: string; notes: string }>;
  review: { verdict: string; score: number; issues: string[]; checklist: Record<string, unknown> } | null;
  outputFile: string | null;
  error: string | null;
}

export async function apiStartPipeline(
  projectId: string,
  extractedData: Record<string, unknown>,
  revision: number = 0,
): Promise<PipelineResult> {
  const res = await fetch(`${FASTAPI_BASE}/api/pipeline/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ projectId, extractedData, revision }),
  });
  if (!res.ok) throw new Error(`파이프라인 실패: ${res.status}`);
  return res.json();
}

export async function apiPipelineResult(projectId: string): Promise<Blob> {
  const res = await fetch(`${FASTAPI_BASE}/api/pipeline/${projectId}/result`);
  if (!res.ok) throw new Error(`결과 다운로드 실패: ${res.status}`);
  return res.blob();
}

// ─── 프로젝트 CRUD → FastAPI 백엔드 ───

import type { ProjectData } from "./storage";

export async function apiGetProjects(): Promise<{ projects: ProjectData[]; lastProjectId: string | null }> {
  const res = await fetch(`${FASTAPI_BASE}/api/projects`);
  if (!res.ok) throw new Error(`프로젝트 목록 실패: ${res.status}`);
  return res.json();
}

export async function apiGetProject(projectId: string): Promise<ProjectData> {
  const res = await fetch(`${FASTAPI_BASE}/api/projects/${projectId}`);
  if (!res.ok) throw new Error(`프로젝트 조회 실패: ${res.status}`);
  return res.json();
}

export async function apiSaveProject(project: ProjectData): Promise<void> {
  const res = await fetch(`${FASTAPI_BASE}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(project),
  });
  if (!res.ok) throw new Error(`프로젝트 저장 실패: ${res.status}`);
}

export async function apiSyncRevision(
  projectId: string,
  revision: number,
  extractedData: Record<string, unknown>,
): Promise<void> {
  const res = await fetch(`${FASTAPI_BASE}/api/projects/${projectId}/revision/${revision}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ extractedData }),
  });
  if (!res.ok) throw new Error(`차수 저장 실패: ${res.status}`);
}

export async function apiDeleteProject(projectId: string): Promise<void> {
  const res = await fetch(`${FASTAPI_BASE}/api/projects/${projectId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`프로젝트 삭제 실패: ${res.status}`);
}
