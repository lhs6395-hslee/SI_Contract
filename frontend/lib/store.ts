"use client";

import { createContext, useContext } from "react";
import type { Project, Route, ExtractedData } from "./types";

export interface AppState {
  route: Route;
  setRoute: (r: Route) => void;
  projectId: string | null;
  setProjectId: (id: string) => void;
  projects: Project[];
  setProjects: React.Dispatch<React.SetStateAction<Project[]>>;
  deleteProject: (id: string) => void;
  isNewProject: boolean;
  setIsNewProject: (v: boolean) => void;
  extractedData: ExtractedData | null;
  setExtractedData: (d: ExtractedData | null | ((prev: ExtractedData | null) => ExtractedData | null)) => void;
  revision: number;
  setRevision: (r: number | ((prev: number) => number)) => void;
  maxRevision: number;
  setMaxRevision: (r: number | ((prev: number) => number)) => void;
  locked: boolean;
  setLocked: (v: boolean) => void;
  conflictCount: number;
  setConflictCount: (n: number) => void;
}

export const AppContext = createContext<AppState | null>(null);

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be inside AppProvider");
  return ctx;
}
