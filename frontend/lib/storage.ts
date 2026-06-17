/**
 * 영속 저장소 — 서버(FastAPI) 우선, localStorage를 캐시/fallback으로 유지
 *
 * Async 함수: 서버 우선 → 실패 시 localStorage fallback
 * 동기 함수: localStorage 캐시 전용 (오프라인/속도)
 */

import type { Project, ExtractedData } from "./types";

import { apiFetch } from "./api-fetch";

const STORAGE_KEY = "si_contract";
const FASTAPI_BASE = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000";

export interface ProjectData {
  id: string;
  name: string;
  client: string;
  status: "in-progress" | "done" | "urgent" | "locked";
  revision: number;
  maxRevision: number;
  revenue: number;
  updated: string;
  created_at?: string;  // 서버 UTC ISO (최초 생성 1회, 읽기전용)
  extracted: ExtractedData | null;
  revisions?: Record<string, ExtractedData>;  // revision별 데이터: { "0": {...}, "1": {...} }
  locked?: boolean;
}

interface StorageData {
  projects: ProjectData[];
  lastProjectId: string | null;
}

function getStorage(): StorageData {
  if (typeof window === "undefined") return { projects: [], lastProjectId: null };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* corrupt data */ }
  return { projects: [], lastProjectId: null };
}

function setStorage(data: StorageData) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

// ─── Public API ───

export function loadProjects(): { projects: ProjectData[]; lastProjectId: string | null } {
  return getStorage();
}

export function saveProject(project: ProjectData) {
  const data = getStorage();
  const idx = data.projects.findIndex((p) => p.id === project.id);
  if (idx >= 0) {
    data.projects[idx] = project;
  } else {
    data.projects.unshift(project);
  }
  data.lastProjectId = project.id;
  setStorage(data);
}

export function deleteProjectFromStorage(id: string) {
  const data = getStorage();
  data.projects = data.projects.filter((p) => p.id !== id);
  if (data.lastProjectId === id) {
    data.lastProjectId = data.projects[0]?.id || null;
  }
  setStorage(data);
}

export function loadProjectData(id: string): ProjectData | null {
  const data = getStorage();
  return data.projects.find((p) => p.id === id) || null;
}

export function toProject(pd: ProjectData): Project {
  return {
    id: pd.id,
    name: pd.name,
    client: pd.client,
    status: pd.locked ? "locked" : pd.status,
    revision: pd.revision,
    maxRevision: pd.maxRevision || pd.revision,
    revenue: pd.revenue,
    updated: pd.updated,
    locked: pd.locked,
  };
}

// ─── localStorage 캐시 동기화 ───

function syncToLocalStorage(projects: ProjectData[], lastProjectId: string | null) {
  setStorage({ projects, lastProjectId });
}

// ─── Async API (서버 우선 + localStorage fallback) ───

export async function loadProjectsAsync(): Promise<{ projects: ProjectData[]; lastProjectId: string | null }> {
  try {
    const res = await apiFetch(`${FASTAPI_BASE}/api/projects`);
    if (res.ok) {
      const data = await res.json();
      const projects: ProjectData[] = data.projects || [];
      const lastId = data.lastProjectId || (projects[0]?.id ?? null);
      syncToLocalStorage(projects, lastId);
      return { projects, lastProjectId: lastId };
    }
    // 비-2xx(401은 api-fetch가 리다이렉트 처리) — stale 캐시 fallback을 가시화
    console.warn(`[storage] 프로젝트 목록 서버 응답 ${res.status} — 로컬 캐시로 표시(최신 아닐 수 있음)`);
  } catch { /* 네트워크 실패 — 조용히 fallback */ }
  return loadProjects();
}

export async function saveProjectAsync(project: ProjectData): Promise<boolean> {
  let ok = false;
  try {
    const res = await apiFetch(`${FASTAPI_BASE}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(project),
    });
    ok = res.ok;
    if (!ok) console.warn(`[storage] 프로젝트 저장 서버 응답 ${res.status} — 로컬에만 저장됨`);
  } catch { /* 서버 접근 불가 */ }
  // localStorage 캐시도 업데이트 (서버 저장 성공 여부와 무관하게 로컬 보존)
  saveProject(project);
  return ok;
}

export async function loadProjectDataAsync(id: string): Promise<ProjectData | null> {
  try {
    const res = await apiFetch(`${FASTAPI_BASE}/api/projects/${id}`);
    if (res.ok) {
      const project = await res.json();
      return project;
    }
    console.warn(`[storage] 프로젝트(${id}) 서버 응답 ${res.status} — 로컬 캐시로 표시(최신 아닐 수 있음)`);
  } catch { /* 네트워크 실패 — 조용히 fallback */ }
  return loadProjectData(id);
}

export async function deleteProjectAsync(id: string): Promise<void> {
  try {
    await apiFetch(`${FASTAPI_BASE}/api/projects/${id}`, { method: "DELETE" });
  } catch { /* 서버 접근 불가 */ }
  deleteProjectFromStorage(id);
}
