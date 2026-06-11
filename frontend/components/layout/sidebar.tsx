"use client";

import { useState, useEffect, useCallback } from "react";
import { useApp } from "@/lib/store";
import { SAMPLE_PROJECTS } from "@/lib/sample-data";
import type { ProjectStatus, Route } from "@/lib/types";
import {
  Plus, Trash2, FolderOpen, Bell, Settings, LogOut, Menu, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const STATUS_COLOR: Record<ProjectStatus, string> = {
  "in-progress": "bg-blue-500",
  done: "bg-emerald-500",
  locked: "bg-amber-500",
  urgent: "bg-red-500",
};

export function SidebarToggle({ onClick }: { onClick: () => void }) {
  return (
    <button
      className="md:hidden fixed top-3 left-3 z-50 flex h-10 w-10 items-center justify-center rounded-lg bg-card border border-border shadow-sm"
      onClick={onClick}
      aria-label="메뉴 열기"
    >
      <Menu className="h-5 w-5" />
    </button>
  );
}

export function Sidebar() {
  const {
    route, setRoute, projectId, setProjectId,
    projects, setProjects, deleteProject,
    isNewProject, setIsNewProject,
  } = useApp();

  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  const closeMobile = useCallback(() => setMobileOpen(false), []);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const handler = () => { if (mq.matches) setMobileOpen(false); };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const navigate = (r: Route) => {
    setRoute(r);
    closeMobile();
  };

  const loadSamples = () => {
    setProjects(SAMPLE_PROJECTS.map((p) => ({ ...p })));
    setProjectId(SAMPLE_PROJECTS[0].id);
    setIsNewProject(false);
    setRoute("review");
    closeMobile();
  };

  return (
    <>
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-40 bg-black/50" onClick={closeMobile} />
      )}
      <SidebarToggle onClick={() => setMobileOpen(true)} />
    <aside className={`
      flex w-[260px] flex-col border-r border-border bg-card
      fixed inset-y-0 left-0 z-50 transition-transform duration-200
      md:relative md:translate-x-0
      ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
    `}>
      {/* Brand */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-border">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground text-xs font-bold">
          GS
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold truncate">집행계획 자동화</div>
          <div className="text-[11px] text-muted-foreground">GS Neotek · v2.4</div>
        </div>
        <button className="md:hidden p-1 rounded hover:bg-accent" onClick={closeMobile} aria-label="메뉴 닫기">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* New Project */}
      <div className="p-3">
        <Button
          variant="outline"
          className="w-full justify-start gap-2 text-xs"
          onClick={() => { setIsNewProject(true); navigate("upload"); }}
        >
          <Plus className="h-3.5 w-3.5" /> 새 프로젝트
        </Button>
      </div>

      {/* Project List */}
      <div className="px-3 mb-1">
        <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-muted-foreground px-2 mb-1">
          <span>최근 프로젝트</span>
          <span className="text-[11px] normal-case tracking-normal">{projects.length}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 space-y-0.5">
        {projects.map((p) => {
          const active = !isNewProject && projectId === p.id && route !== "projects" && route !== "notifications";
          return (
            <div
              key={p.id}
              role="button"
              tabIndex={0}
              className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-[13px] transition-colors hover:bg-accent cursor-pointer ${active ? "bg-accent font-medium" : ""}`}
              onMouseEnter={() => setHoveredId(p.id)}
              onMouseLeave={() => setHoveredId(null)}
              onClick={() => { setProjectId(p.id); setIsNewProject(false); setRoute("review"); closeMobile(); }}
            >
              <span className={`h-2 w-2 rounded-full shrink-0 ${STATUS_COLOR[p.status]}`} />
              <span className="truncate flex-1">{p.name}</span>
              {(hoveredId === p.id || confirmId === p.id) ? (
                <button
                  className={`shrink-0 p-0.5 rounded hover:bg-destructive/10 ${confirmId === p.id ? "text-destructive" : "text-muted-foreground"}`}
                  title={confirmId === p.id ? "한 번 더 클릭하여 삭제" : "삭제"}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirmId === p.id) { deleteProject(p.id); setConfirmId(null); }
                    else { setConfirmId(p.id); setTimeout(() => setConfirmId((c) => c === p.id ? null : c), 2500); }
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              ) : (
                p.revision > 0 && <span className="text-[11px] text-muted-foreground shrink-0">{p.revision}차</span>
              )}
            </div>
          );
        })}

        {projects.length === 0 && (
          <div className="py-6 text-center">
            <p className="text-xs text-muted-foreground mb-3">프로젝트가 없습니다</p>
            <Button variant="ghost" size="sm" className="text-[11px] w-full" onClick={loadSamples}>
              예시 데이터 불러오기
            </Button>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="border-t border-border px-2 pt-2 pb-1 space-y-0.5">
        <button
          className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] hover:bg-accent ${route === "projects" ? "bg-accent font-medium" : ""}`}
          onClick={() => navigate("projects")}
        >
          <FolderOpen className="h-3.5 w-3.5" /> 프로젝트 목록
        </button>
        <button
          className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] hover:bg-accent ${route === "notifications" ? "bg-accent font-medium" : ""}`}
          onClick={() => navigate("notifications")}
        >
          <Bell className="h-3.5 w-3.5" /> 알림
        </button>
      </div>

      {/* Settings */}
      <div className="border-t border-border px-2 pb-2 pt-1">
        <button
          className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] hover:bg-accent ${route === "settings" ? "bg-accent font-medium" : ""}`}
          onClick={() => navigate("settings")}
        >
          <Settings className="h-3.5 w-3.5" /> 설정
        </button>
        <button
          className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] hover:bg-accent text-muted-foreground"
          onClick={() => { localStorage.removeItem("si_auth_token"); localStorage.removeItem("si_auth_user"); window.location.href = "/login"; }}
        >
          <LogOut className="h-3.5 w-3.5" /> 로그아웃
        </button>
      </div>
    </aside>
    </>
  );
}
