export type ProjectStatus = "in-progress" | "done" | "urgent" | "locked";

export interface Project {
  id: string;
  name: string;
  client: string;
  status: ProjectStatus;
  revision: number;
  maxRevision: number;
  revenue: number;
  updated: string;
  locked?: boolean;
}

export interface UploadedFile {
  id: number;
  file?: File;
  name: string;
  size: number;
  type: string;
  category: FileCategory;
  confidence: number;
  classifying: boolean;
  reason: string;
  manual?: boolean;
}

export type FileCategory = "contract" | "internal" | "vendor" | "insurance" | "execution_plan" | "unknown";

export interface ExtractedField {
  value: string | number | null;
  source: string;
  confidence: "verified" | "guess" | "null";
  unit?: string;
  // 집행계획서 역추출(import) 시 금액 단위 신뢰도. "low" = 단위(천원/원) 라벨 없이
  // 추정 → 사용자 단위 확정 강제(1000배 오류 방지). 일반 추출에는 없음(undefined).
  unitConfidence?: "high" | "low";
}

export interface CostItem {
  category: string;
  name: string;
  spec: string;
  unit: string;
  contractQty: number;
  contractPrice: number;
  contractAmount: number;
  executionQty: number;
  executionPrice: number;
  executionAmount: number;
  vendor: string;
  source: string;
  confidence: string;
  // import(집행계획서 역추출) 시 금액 단위 신뢰도 — "low"면 사용자 단위 확정 대상.
  unitConfidence?: "high" | "low";
}

export interface StaffMember {
  name: string;
  role: string;
  grade: string;
  type: "직접" | "간접";
  company?: string;
  months: number[];
  monthlyRate: number;
  source: string;
}

export interface ScheduleItem {
  name: string;
  startMonth: number;
  endMonth: number;
  source: string;
}

export interface Rates {
  indirectRate: { value: number; source: string };
  adminRate: { value: number; source: string };
  nationalPension: { value: number; source: string };
  healthInsurance: { value: number; source: string };
  employmentInsurance: { value: number; source: string };
  industrialAccident: { value: number; source: string };
}

export interface OrgMember {
  role: string;
  name: string;
  scope: string;
  lead: boolean;
}

export interface ExtractedData {
  projectName: string;
  extracted: Record<string, ExtractedField>;
  costItems?: CostItem[];
  staffPlan?: StaffMember[];
  schedule?: ScheduleItem[];
  rates?: Rates;
  organization?: OrgMember[];
  conflicts: Conflict[];
  files: { name: string; category: string; size: number }[];
  changedFields?: Record<string, { prev: string | number | null }>;
  fieldEditLog?: Record<string, { at: string; by: string }>;
  aiSuggestions?: Record<string, { value: string | number | null; source: string }>;
  manuallyVerified?: string[];
  confirmedTabs?: string[];
  locked?: boolean;
  createdAt?: string;  // 프로젝트 생성시각(UTC ISO, 읽기전용) — ProjectData.created_at에서 주입
  revisionReason?: string;
  revisionType?: string;
  // 완성 집행계획서 PDF 역추출(import)로 생성된 0차 데이터에만 존재. 금액 단위가
  // 추정값(unitGuessed)이거나 누락 필드가 있음을 알린다. 일반 추출에는 undefined.
  importMeta?: { unitGuessed?: boolean; missingFields?: string[] };
  // 사용자가 import된 금액의 단위(천원/원)를 확정했는지. false/undefined면 1차 진행 차단.
  unitConfirmed?: boolean;
}

export interface Conflict {
  type: string;
  message: string;
  files?: string[];
  severity?: string;
  field?: string;
  valueA?: unknown;
  valueB?: unknown;
  values?: unknown[];
  sourceA?: string;
  sourceB?: string;
  sources?: string[];
}

export type Route = "upload" | "review" | "conflicts" | "export" | "projects" | "notifications" | "settings";
