export type Domain =
  | "infrastructure"
  | "supply"
  | "communication"
  | "execution"
  | "security"
  | "finance"
  | "manufacturing"
  | "tabular";
export type Role = "admin" | "approver" | "analyst" | "viewer";

export interface User { id: string; name: string; email: string; role: Role }
export interface Project { id: string; name: string; description: string; created_at: string }
export interface Me {
  user: User;
  organization: string;
  llm_enabled: boolean;
  demo_enabled: boolean;
  max_upload_bytes?: number;
  max_upload_size_mb?: number;
}
export interface Finding {
  agent: string; domain: Domain; kind: string; title: string; detail: string; severity: string;
  confidence: number; method: string; data: Record<string, unknown>; evidence_ids: string[];
}
export interface Hypothesis {
  source: string; target: string; source_domain: Domain; target_domain: Domain; relation: string;
  explanation: string; status: "observed" | "inferred"; confidence: number; evidence_ids: string[];
}
export interface Risk {
  usable_units: number; daily_demand: number; days_of_cover: number | null; replenishment_days: number;
  coverage_gap_days: number; units_short: number; risk_level: string; formula: string;
}
export interface Assessment {
  sku: string; name: string; supplier_id: string; unit_price: number; current: Risk; baseline: Risk; worst_case: Risk;
  delay_days: number; held_units: number; revenue_at_risk: number; revenue_at_risk_worst: number;
}
export interface Incident {
  id: string; project_id: string; title: string; status: string; severity: string; risk_score: number; summary: string;
  narrative_method: string; error: string; created_at: string; updated_at: string;
  findings?: Finding[]; hypotheses?: Hypothesis[]; uncertainties?: string[]; supply_assessments?: Assessment[];
  active_agents?: string[]; confidence?: number | null; event_count?: number;
}
export interface Overview {
  event_counts: Partial<Record<Domain, number>>; pending_approvals: number; open_tasks: number; active_investigations: number;
  incidents: Incident[]; latest: Incident | null; business_risks: Assessment[];
}
export interface ToolCall { tool: string; inputs: Record<string, unknown>; status: string; output: string; duration_ms: number }
export interface AgentRun {
  id: string; agent: string; status: string; sequence: number; note: string; method: string; error: string;
  tool_calls: ToolCall[]; findings: Finding[]; started_at: string; finished_at: string | null;
}
export interface Recommendation {
  id: string; incident_id: string; action_type: string; title: string; rationale: string; domain: Domain; priority: number;
  risk_level: string; confidence: number; required_role: Role; status: string; params: Record<string, unknown>; evidence_ids: string[];
  policy_result: { allowed: boolean; reasons: string[] }; execution: { connector?: string; note?: string; task_id?: string };
  verification: { status?: string; reason?: string }; executed_at: string | null;
  approval: { decision: string; comment: string; by: string; at: string } | null;
}
export interface Task { id: string; title: string; owner: string; deadline: string; status: string }
export interface EvidenceItem { id: string; kind: string; domain: Domain; claim: string; excerpt: string; source_file: string; source_locator: string }
export interface GraphData {
  nodes: { id: string; label: string; domain: Domain }[];
  edges: Omit<Hypothesis, "source_domain" | "target_domain">[];
}
export interface UploadedFileRecord {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: "processed" | "failed" | "partial";
  events_count: number;
  dependencies_count: number;
  error_message?: string;
  created_by: string;
  created_at: string;
}
export interface UploadResult {
  id?: string;
  file: string;
  kind?: string;
  file_size?: number;
  events_added?: number;
  dependencies_added?: number;
  duplicates_skipped?: number;
  rejected?: { locator: string; reason: string }[];
  rejected_count?: number;
  error?: string;
}
export interface AuditEntry { sequence: number; actor: string; action: string; entity_type: string; detail: Record<string, unknown>; created_at: string; hash: string }
export interface Report {
  title: string; project: string; status: string; severity: string; risk_score: number; summary: string; narrative_method: string; created_at: string;
  findings: Finding[]; hypotheses: Hypothesis[]; uncertainties: string[];
  recommendations: { title: string; status: string; risk_level: string; connector: string | null; verification: { status?: string; reason?: string } }[];
  tasks: { title: string; owner: string; deadline: string; status: string }[];
  evidence: { kind: string; claim: string; excerpt: string; source_file: string; source_locator: string }[];
}

const TOKEN_KEY = "nexus.token";
let onUnauthorized: () => void = () => {};
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn; };

export function getToken(): string | null {
  try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch { /* Storage blocked: the session lasts until reload. */ }
}

function detailOf(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "");
  return `The request failed (${status}).`;
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers });
  } catch {
    throw new Error("Can't reach the NEXUS server. Check that the backend is running.");
  }
  if (res.status === 401 && token) onUnauthorized();
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(detailOf(body, res.status));
  }
  return res;
}

export const get = async <T,>(path: string): Promise<T> => (await send(path)).json();
export const post = async <T,>(path: string, body?: unknown): Promise<T> =>
  (await send(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) })).json();
export const patch = async <T,>(path: string, body: unknown): Promise<T> =>
  (await send(path, { method: "PATCH", body: JSON.stringify(body) })).json();
export const upload = async (projectId: string, files: File[]): Promise<{ results: UploadResult[] }> => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return (await send(`/projects/${projectId}/uploads`, { method: "POST", body: form })).json();
};
export const listFiles = (projectId: string): Promise<UploadedFileRecord[]> =>
  get<UploadedFileRecord[]>(`/projects/${projectId}/files`);
export const deleteFile = (projectId: string, fileId: string): Promise<{ ok: boolean }> =>
  send(`/projects/${projectId}/files/${fileId}`, { method: "DELETE" }).then((r) => r.json());
export async function downloadReport(incidentId: string) {
  const res = await send(`/incidents/${incidentId}/report?format=markdown`);
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `nexus-report-${incidentId.slice(0, 8)}.md`;
  link.click();
  URL.revokeObjectURL(url);
}
