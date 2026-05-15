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

export type FileCategory = "contract" | "internal" | "vendor" | "insurance" | "unknown";

export interface ExtractedField {
  value: string | number | null;
  source: string;
  confidence: "verified" | "guess" | "null";
  unit?: string;
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
  revisionReason?: string;
  revisionType?: string;
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
