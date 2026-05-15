import type { Project } from "./types";

export const SAMPLE_PROJECTS: Project[] = [
  { id: "p1", name: "퀘이사존 클라우드 운영", client: "퀘이사존", status: "in-progress", revision: 0, maxRevision: 0, revenue: 156600000, updated: "방금" },
  { id: "p2", name: "선진산업 AWS MSP", client: "선진산업", status: "in-progress", revision: 1, maxRevision: 1, revenue: 248000000, updated: "2시간 전" },
  { id: "p3", name: "한울제약 Azure 재판매", client: "한울제약", status: "done", revision: 2, maxRevision: 2, revenue: 98400000, updated: "어제" },
  { id: "p4", name: "동성화학 데이터 마이그레이션", client: "동성화학", status: "urgent", revision: 0, maxRevision: 0, revenue: 312000000, updated: "3일 전" },
];
