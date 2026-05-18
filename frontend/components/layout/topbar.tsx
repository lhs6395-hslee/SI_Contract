"use client";

import { useState, useEffect, useRef } from "react";
import { useApp } from "@/lib/store";
import {
  Search, Moon, Sun, ChevronDown, Plus, Check, Lock, LogOut, User,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTheme } from "next-themes";
import { getUser, logout, type AuthUser } from "@/lib/auth";

const ROUTE_NAME: Record<string, string> = {
  upload: "업로드",
  review: "리뷰 및 수정",
  conflicts: "충돌 해결",
  export: "익스포트",
  projects: "프로젝트 목록",
  notifications: "알림",
};

const REV_COLORS = [
  "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200",
  "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
];

function revLabel(i: number): string {
  if (i === 0) return "최초";
  return `수정 ${i}차`;
}

export function Topbar({ onAddRevision }: { onAddRevision: () => void }) {
  const { route, setRoute, projectId, projects, isNewProject, revision, setRevision, maxRevision, locked } = useApp();
  const { theme, setTheme } = useTheme();
  const [revOpen, setRevOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setUser(getUser()); }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const initial = user?.name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || "?";

  const project = isNewProject ? null : projects.find((p) => p.id === projectId);

  return (
    <div className="flex items-center justify-between border-b border-border px-6 py-3 bg-card">
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
        {route === "projects" || route === "notifications" ? (
          <span className="font-medium text-foreground">{ROUTE_NAME[route]}</span>
        ) : (
          <>
            <button className="hover:text-foreground transition-colors" onClick={() => setRoute("projects")}>프로젝트</button>
            <span className="text-border">/</span>
            <span>{isNewProject ? "새 프로젝트" : project?.name || "신규"}</span>
            <span className="text-border">/</span>
            <span className="font-medium text-foreground">{ROUTE_NAME[route]}</span>
            {locked && <Lock className="h-3 w-3 text-amber-500 ml-1" />}
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        {route !== "projects" && route !== "notifications" && (
          <>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              저장됨
            </div>
            <div className="h-5 w-px bg-border" />

            <div className="relative">
              <button
                className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11.5px] font-medium ${REV_COLORS[revision % REV_COLORS.length]}`}
                onClick={() => setRevOpen((o) => !o)}
              >
                {revLabel(revision)} ({revision}차) <ChevronDown className="h-3 w-3" />
              </button>
              {revOpen && (
                <div
                  className="absolute right-0 top-full mt-1 w-44 rounded-md border bg-popover p-1 shadow-lg z-30"
                  onMouseLeave={() => setRevOpen(false)}
                >
                  {Array.from({ length: maxRevision + 1 }, (_, i) => (
                    <button
                      key={i}
                      className="flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-[12.5px] hover:bg-accent"
                      onClick={() => { setRevision(i); setRevOpen(false); }}
                    >
                      <Badge variant="secondary" className={`text-[10px] ${REV_COLORS[i % REV_COLORS.length]}`}>{i}차</Badge>
                      {revLabel(i)}
                      {i === revision && <Check className="ml-auto h-3 w-3" />}
                    </button>
                  ))}
                  <div className="my-1 h-px bg-border" />
                  <button
                    className="flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-[12.5px] text-primary hover:bg-accent"
                    onClick={() => { setRevOpen(false); onAddRevision(); }}
                  >
                    <Plus className="h-3 w-3" /> 수정/이월 추가
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input placeholder="프로젝트 검색…" className="h-8 w-48 pl-8 text-xs" />
          <kbd className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground bg-muted px-1 rounded">⌘K</kbd>
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>

        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setProfileOpen((v) => !v)}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold hover:opacity-80 transition-opacity"
          >
            {initial}
          </button>
          {profileOpen && (
            <div className="absolute right-0 top-10 z-50 w-56 rounded-lg border bg-popover shadow-lg p-1">
              <div className="px-3 py-2 border-b mb-1">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                    {initial}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{user?.name || user?.email || "사용자"}</div>
                    <div className="text-xs text-muted-foreground truncate">{user?.email}</div>
                  </div>
                </div>
              </div>
              <button
                onClick={() => { setProfileOpen(false); logout(); }}
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
              >
                <LogOut className="h-4 w-4" />
                로그아웃
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
