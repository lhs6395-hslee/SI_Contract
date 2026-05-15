"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { AppContext } from "@/lib/store";
import { isAuthenticated } from "@/lib/auth";
import type { Project, Route, ExtractedData } from "@/lib/types";
import { apiUploadFiles } from "@/lib/api";
import {
  loadProjects, saveProject, deleteProjectFromStorage,
  loadProjectData, toProject,
  loadProjectsAsync, saveProjectAsync, loadProjectDataAsync,
  type ProjectData,
} from "@/lib/storage";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { UploadPage } from "@/components/pages/upload-page";
import { ReviewPage } from "@/components/pages/review-page";
import {
  ConflictsPage, ExportPage, ProjectsPage,
  NotificationsPage, AddRevisionModal,
} from "@/components/pages/other-pages";
import { SettingsPage } from "@/components/pages/settings-page";
import { ChatPanel } from "@/components/chat/chat-panel";

export default function Home() {
  const router = useRouter();
  const [route, setRoute] = useState<Route>("upload");
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [isNewProject, setIsNewProject] = useState(true);
  const [extractedData, setExtractedData] = useState<ExtractedData | null>(null);
  const [revision, setRevision] = useState(0);
  const [maxRevision, setMaxRevision] = useState(0);
  const [locked, setLocked] = useState(false);
  const [conflictCount, setConflictCount] = useState(0);
  const [showAddRev, setShowAddRev] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // ref로 최신 값 추적 (useCallback 의존성 없이 접근)
  const projectIdRef = useRef(projectId);
  projectIdRef.current = projectId;
  const revisionRef = useRef(revision);
  revisionRef.current = revision;
  const maxRevisionRef = useRef(maxRevision);
  maxRevisionRef.current = maxRevision;

  // ─── 초기 로드 (서버 우선 → localStorage fallback) ───
  useEffect(() => {
    // 인증 체크
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    (async () => {
      const { projects: savedProjects, lastProjectId } = await loadProjectsAsync();
      if (savedProjects.length > 0) {
        setProjects(savedProjects.map(toProject));
        const targetId = lastProjectId || savedProjects[0].id;
        setProjectId(targetId);
        setIsNewProject(false);
        setRoute("review");
        const pdMeta = savedProjects.find((p) => p.id === targetId);
        // list_projects excludes extracted/revisions — must fetch full project
        const pd = await loadProjectDataAsync(targetId);
        const rev = pd?.revision ?? pdMeta?.revision ?? 0;
        const revData = pd?.revisions?.[String(rev)] || pd?.extracted;
        if (revData) {
          setExtractedData(revData);
          setRevision(rev);
          setMaxRevision(pd?.maxRevision || rev);
          setLocked(pd?.locked || false);
        } else if (pdMeta) {
          setRevision(pdMeta.revision);
          setMaxRevision(pdMeta.maxRevision || pdMeta.revision);
        }
      }
      setLoaded(true);
    })();
  }, []);

  // ─── extractedData 저장 (디바운스) ───
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!loaded || !extractedData || !projectId) return;
    // 과거 차수는 읽기 전용 — 저장하지 않음
    if (revision < maxRevision) return;
    // 저장을 100ms 디바운스하여 연속 업데이트 시 마지막만 저장
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      const revenue = (extractedData.extracted?.revenue?.value as number) || 0;
      // revisions에 현재 revision 데이터 저장 (서버에서 기존 revisions 가져오기)
      const existingPd = await loadProjectDataAsync(projectId);
      const revisions = existingPd?.revisions || {};
      revisions[String(revision)] = extractedData;

      const pd: ProjectData = {
        id: projectId,
        name: extractedData.projectName || "새 프로젝트",
        client: (extractedData.extracted?.client?.value as string) || "",
        status: locked ? "locked" : "in-progress",
        revision,
        maxRevision,
        revenue,
        updated: "방금",
        extracted: extractedData,
        revisions,
        locked,
      };
      saveProjectAsync(pd);
      setProjects((prev) => {
        const idx = prev.findIndex((p) => p.id === projectId);
        const updated = toProject(pd);
        if (idx >= 0) {
          const copy = [...prev];
          copy[idx] = updated;
          return copy;
        }
        return [updated, ...prev];
      });
    }, 100);
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, [extractedData, projectId, revision, maxRevision, loaded]);

  // ─── setExtractedData 래퍼 (함수형 업데이트 지원) ───
  const setExtractedDataWrapped = useCallback(
    (input: ExtractedData | null | ((prev: ExtractedData | null) => ExtractedData | null)) => {
      if (typeof input === "function") {
        setExtractedData(input);
      } else {
        setExtractedData(input);
      }
    },
    [],
  );

  // ─── revision 전환 시 해당 revision 데이터 로드 (서버에서) ───
  const prevRevisionRef = useRef(revision);
  useEffect(() => {
    if (!loaded || !projectId) return;
    if (prevRevisionRef.current === revision) return;
    prevRevisionRef.current = revision;

    (async () => {
      const pd = await loadProjectDataAsync(projectId);
      if (pd?.revisions?.[String(revision)]) {
        setExtractedData(pd.revisions[String(revision)]);
      }
    })();
  }, [revision, loaded, projectId]);

  // ─── 프로젝트 선택 ───
  const selectProject = useCallback((id: string) => {
    setProjectId(id);
    setIsNewProject(false);
    (async () => {
      const pd = await loadProjectDataAsync(id);
      if (pd) {
        const rev = pd.revision;
        const revData = pd.revisions?.[String(rev)] || pd.extracted;
        setExtractedData(revData);
        setRevision(rev);
        setMaxRevision(pd.maxRevision || rev);
        setLocked(pd.locked || false);
        setConflictCount(revData?.conflicts?.length || 0);
      }
    })();
  }, []);

  // ─── 새 프로젝트 생성 완료 ───
  const completeNewProject = useCallback(async (data: (ExtractedData & { _filesToSave?: File[] }) | null) => {
    const newId = `p_${Date.now()}`;
    setProjectId(newId);
    setIsNewProject(false);

    if (data) {
      if (data._filesToSave && data._filesToSave.length > 0) {
        try { await apiUploadFiles(newId, data._filesToSave, 0); } catch (e) { console.warn("파일 저장 실패:", e); }
      }
      const { _filesToSave, ...cleanData } = data;
      setExtractedData(cleanData);
      setConflictCount(cleanData.conflicts?.length || 0);
    }
    setRoute("review");
  }, []);

  // ─── 프로젝트 삭제 ───
  const deleteProject = useCallback((id: string) => {
    deleteProjectFromStorage(id);
    setProjects((ps) => ps.filter((p) => p.id !== id));
    if (projectIdRef.current === id) {
      setRoute("upload");
      setIsNewProject(true);
      setExtractedData(null);
    }
  }, []);

  const ctx = {
    route, setRoute,
    projectId,
    setProjectId: selectProject,
    projects, setProjects,
    deleteProject,
    isNewProject, setIsNewProject,
    extractedData,
    setExtractedData: setExtractedDataWrapped,
    revision, setRevision,
    maxRevision, setMaxRevision,
    locked, setLocked,
    conflictCount, setConflictCount,
  };

  if (!loaded) return null;

  return (
    <AppContext value={ctx}>
      <div className="flex h-screen overflow-hidden bg-background">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Topbar onAddRevision={() => setShowAddRev(true)} />
          <main className="flex-1 overflow-y-auto p-6">
            {route === "upload" && <UploadPage onComplete={completeNewProject} />}
            {route === "review" && <ReviewPage />}
            {route === "conflicts" && <ConflictsPage />}
            {route === "export" && <ExportPage />}
            {route === "projects" && <ProjectsPage />}
            {route === "notifications" && <NotificationsPage />}
            {route === "settings" && <SettingsPage />}
          </main>
        </div>
        {showAddRev && (
          <AddRevisionModal
            onClose={() => setShowAddRev(false)}
            onAdd={async (reason, revType, files) => {
              const newRev = maxRevision + 1;
              if (extractedData) {
                const copied: ExtractedData = JSON.parse(JSON.stringify(extractedData));
                copied.changedFields = {};
                copied.revisionReason = reason;
                copied.revisionType = revType;
                setExtractedData(copied);
                // 새 차수 파일 업로드
                if (projectId && files.length > 0) {
                  try { await apiUploadFiles(projectId, files, newRev); }
                  catch (e) { console.warn("차수 파일 업로드 실패:", e); }
                }
              }
              setMaxRevision(newRev);
              setRevision(newRev);
              setShowAddRev(false);
            }}
          />
        )}
        <ChatPanel />
      </div>
    </AppContext>
  );
}
