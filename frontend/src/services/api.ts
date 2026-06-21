// Typed API client for the Advisory Workbench backend.
// In dev, Vite proxies /api -> http://127.0.0.1:8000 (see vite.config.ts).
import type {
  ActivatorScreen,
  AIInferResult,
  AIOpportunityResult,
  AppSettings,
  ArchetypeSummary,
  BenchmarkResult,
  Client,
  Dataset,
  DiagnosticsSummary,
  Engagement,
  ExtractResult,
  PulseImportResult,
  QueueResult,
  QuickStats,
  ReviewAction,
  ReviewResult,
  DeliverableInfo,
  OpportunityMatrix,
  ProcessInfo,
  StepInfo,
  RollupResult,
  Scenario,
  ScenarioDelta,
  TaskItem,
  TransitionResult,
  WorkflowBoard,
} from "../types";

// In dev, Vite proxies "/api" to the backend. In production (frontend on Vercel, backend on
// Railway), set VITE_API_BASE_URL to the backend's URL so calls reach the right origin.
const API_ORIGIN = import.meta.env.VITE_API_BASE_URL ?? "";
const BASE = `${API_ORIGIN}/api/v1`;

// ── Auth token (D13) ─────────────────────────────────────────────────────────
let authToken: string | null = localStorage.getItem("token");
let onUnauthorized: () => void = () => {};

export function setAuthToken(t: string | null): void {
  authToken = t;
  if (t) localStorage.setItem("token", t);
  else localStorage.removeItem("token");
}
export function getAuthToken(): string | null {
  return authToken;
}
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch(`${BASE}${path}`, { ...init, headers });
  if (resp.status === 401 && !path.startsWith("/auth/login")) {
    setAuthToken(null);
    onUnauthorized();
    throw new Error("Your session expired — please sign in again.");
  }
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return (await resp.json()) as T;
}

function json(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

// Authenticated binary fetch. Browser-direct downloads (<a href>, <img src>) cannot send the
// Authorization header, so file endpoints (gated since D13) must be fetched here with the Bearer
// token and turned into a blob — otherwise the server replies 401 "Not authenticated".
async function authedBlob(url: string): Promise<Blob> {
  const headers = new Headers();
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const resp = await fetch(url, { headers });
  if (resp.status === 401) {
    setAuthToken(null);
    onUnauthorized();
    throw new Error("Your session expired — please sign in again.");
  }
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return resp.blob();
}

async function downloadBlob(url: string, filename: string): Promise<void> {
  const blob = await authedBlob(url);
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}

export const api = {
  // Auth + access (D13)
  login: async (email: string, passcode: string) => {
    const data = await request<{ token: string; email: string; owner: boolean }>(
      "/auth/login", json({ email, passcode }),
    );
    setAuthToken(data.token);
    return data;
  },
  me: () => request<{ email: string; owner: boolean }>("/auth/me"),
  logout: () => setAuthToken(null),
  listAccess: () =>
    request<{ users: { email: string; is_owner: boolean }[] }>("/access"),
  addAccess: (email: string, passcode: string, is_owner: boolean) =>
    request<{ email: string }>("/access", json({ email, passcode, is_owner })),
  removeAccess: (email: string) =>
    request<{ removed: string }>(`/access/${encodeURIComponent(email)}`, { method: "DELETE" }),

  // Clients
  listClients: () => request<Client[]>("/engagements/clients"),
  createClient: (name: string, industry?: string) =>
    request<Client>("/engagements/clients", json({ name, industry })),

  // Engagements
  listEngagements: (clientId?: string) =>
    request<Engagement[]>(
      `/engagements${clientId ? `?client_id=${encodeURIComponent(clientId)}` : ""}`,
    ),
  createEngagement: (clientId: string, name: string) =>
    request<Engagement>("/engagements", json({ client_id: clientId, name })),

  // Datasets
  listDatasets: (engagementId: string) =>
    request<Dataset[]>(`/engagements/${engagementId}/datasets`),
  uploadDataset: (engagementId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Dataset>(`/engagements/${engagementId}/datasets`, {
      method: "POST",
      body: form,
    });
  },
  purgeEngagement: (engagementId: string) =>
    request<{ purged: string }>(`/engagements/${engagementId}/purge`, { method: "DELETE" }),
  deleteClient: (clientId: string) =>
    request<{ deleted: string }>(`/engagements/clients/${clientId}`, { method: "DELETE" }),
  deleteEngagement: (engagementId: string) =>
    request<{ deleted: string }>(`/engagements/${engagementId}`, { method: "DELETE" }),
  deleteDataset: (datasetId: string) =>
    request<{ deleted: string }>(`/engagements/datasets/${datasetId}`, { method: "DELETE" }),

  // Diagnostics
  compute: (datasetId: string) =>
    request<DiagnosticsSummary>(
      `/diagnostics/compute?dataset_id=${encodeURIComponent(datasetId)}`,
      { method: "POST" },
    ),
  summary: (datasetId: string) =>
    request<DiagnosticsSummary>(
      `/diagnostics/summary?dataset_id=${encodeURIComponent(datasetId)}`,
    ),
  activatorScreen: (datasetId: string) =>
    request<ActivatorScreen>(
      `/diagnostics/activator-screen?dataset_id=${encodeURIComponent(datasetId)}`,
    ),
  archetypes: () => request<{ archetypes: ArchetypeSummary[] }>("/diagnostics/archetypes"),

  // Task Intelligence
  quick: (datasetId: string) =>
    request<QuickStats>(`/task-intel/quick?dataset_id=${encodeURIComponent(datasetId)}`),
  extract: (datasetId: string) =>
    request<ExtractResult>(`/task-intel/extract?dataset_id=${encodeURIComponent(datasetId)}`, {
      method: "POST",
    }),
  benchmark: (datasetId: string) =>
    request<BenchmarkResult>(`/task-intel/benchmark?dataset_id=${encodeURIComponent(datasetId)}`, {
      method: "POST",
    }),
  aiOpportunity: (datasetId: string) =>
    request<AIOpportunityResult>(
      `/task-intel/ai-opportunity?dataset_id=${encodeURIComponent(datasetId)}`,
      { method: "POST" },
    ),
  inferPotential: (datasetId: string) =>
    request<AIInferResult>(
      `/task-intel/infer-potential?dataset_id=${encodeURIComponent(datasetId)}`,
      { method: "POST" },
    ),
  rollup: (datasetId: string) =>
    request<RollupResult>(`/task-intel/rollup?dataset_id=${encodeURIComponent(datasetId)}`),

  // Validation
  validationQueue: (datasetId?: string, maxConfidence?: number, includeReviewed = false) => {
    const p = new URLSearchParams();
    if (datasetId) p.set("dataset_id", datasetId);
    if (maxConfidence !== undefined) p.set("max_confidence", String(maxConfidence));
    if (includeReviewed) p.set("include_reviewed", "true");
    return request<QueueResult>(`/validation/queue?${p.toString()}`);
  },
  review: (actions: ReviewAction[]) =>
    request<ReviewResult>("/validation/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(actions),
    }),

  // Desire pulse
  downloadPulseInstrument: (datasetId: string) =>
    downloadBlob(
      `${BASE}/task-intel/pulse/instrument.xlsx?dataset_id=${encodeURIComponent(datasetId)}`,
      `desire-pulse-instrument.xlsx`,
    ),
  pulseImport: (engagementId: string, datasetId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<PulseImportResult>(
      `/task-intel/pulse/responses?engagement_id=${encodeURIComponent(
        engagementId,
      )}&dataset_id=${encodeURIComponent(datasetId)}`,
      { method: "POST", body: form },
    );
  },
  downloadDesirabilityTemplate: (datasetId: string) =>
    downloadBlob(
      `${BASE}/task-intel/desirability-template.csv?dataset_id=${encodeURIComponent(datasetId)}`,
      `local-desirability-template.csv`,
    ),
  manualScore: (taskId: string, rating: number) =>
    request<{ task_id: string; human_agency_level: string; zone: string; review_state: string }>(
      "/validation/manual-score",
      json({ task_id: taskId, rating }),
    ),
  applyDesirability: (datasetId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ applied: number; desire_only: number; skipped: number }>(
      `/task-intel/desirability?dataset_id=${encodeURIComponent(datasetId)}`,
      { method: "POST", body: form },
    );
  },

  // Scenarios
  listScenarios: (engagementId: string) =>
    request<Scenario[]>(`/scenarios?engagement_id=${encodeURIComponent(engagementId)}`),
  createScenario: (engagementId: string, datasetId: string, name: string) =>
    request<Scenario>("/scenarios", json({ engagement_id: engagementId, dataset_id: datasetId, name })),
  moveTypes: () => request<{ move_types: string[] }>("/scenarios/move-types"),
  addMove: (scenarioId: string, moveType: string, params: Record<string, unknown>, rationale?: string) =>
    request<{ id: string; seq: number; move_type: string }>(
      `/scenarios/${scenarioId}/moves`,
      json({ move_type: moveType, params, rationale }),
    ),
  removeMove: (scenarioId: string, seq: number) =>
    request<{ removed_seq: number }>(`/scenarios/${scenarioId}/moves/${seq}`, { method: "DELETE" }),
  scenarioDelta: (scenarioId: string) =>
    request<ScenarioDelta>(`/scenarios/${scenarioId}/delta`),
  compareScenarios: (ids: string[]) =>
    request<{ scenarios: ScenarioDelta[] }>(`/scenarios/compare?ids=${ids.join(",")}`),
  presentScenario: (scenarioId: string) =>
    request<Scenario>(`/scenarios/${scenarioId}/present`, { method: "POST" }),
  forkScenario: (scenarioId: string) =>
    request<Scenario>(`/scenarios/${scenarioId}/fork`, { method: "POST" }),

  // Task list (for workflow mapping)
  tasks: (datasetId: string) =>
    request<{ tasks: TaskItem[] }>(`/task-intel/tasks?dataset_id=${encodeURIComponent(datasetId)}`),

  // Workflows
  listProcesses: (engagementId: string) =>
    request<ProcessInfo[]>(`/workflows?engagement_id=${encodeURIComponent(engagementId)}`),
  createProcess: (engagementId: string, name: string, valueStream?: string) =>
    request<ProcessInfo>("/workflows", json({ engagement_id: engagementId, name, value_stream: valueStream })),
  listSteps: (processId: string) =>
    request<{ steps: StepInfo[] }>(`/workflows/${processId}/steps`),
  addStep: (processId: string, name: string) =>
    request<StepInfo>(`/workflows/${processId}/steps`, json({ name })),
  mapTasks: (stepId: string, taskIds: string[]) =>
    request<{ linked: number }>(`/workflows/steps/${stepId}/map-tasks`, json({ task_ids: taskIds })),
  opportunityMatrix: (processId: string) =>
    request<OpportunityMatrix>(`/workflows/${processId}/opportunity-matrix`, { method: "POST" }),

  // Workflow Mapper board (no AI key required)
  workflowBoard: (processId: string, datasetId: string) =>
    request<WorkflowBoard>(
      `/workflows/${processId}/board?dataset_id=${encodeURIComponent(datasetId)}`,
    ),
  moveTask: (processId: string, taskId: string, toStepId: string) =>
    request<{ task_id: string; step_id: string }>(
      `/workflows/${processId}/move-task`,
      json({ task_id: taskId, to_step_id: toStepId }),
    ),
  unmapTask: (processId: string, taskId: string) =>
    request<{ task_id: string; unmapped: number }>(
      `/workflows/${processId}/unmap-task`,
      json({ task_id: taskId }),
    ),
  exportWorkflowCsv: (engagementId: string, datasetId: string) =>
    downloadBlob(
      `${BASE}/workflows/export.csv?engagement_id=${encodeURIComponent(engagementId)}&dataset_id=${encodeURIComponent(datasetId)}`,
      `workflow_map.csv`,
    ),
  exportWorkflowPptx: (engagementId: string, datasetId: string) =>
    downloadBlob(
      `${BASE}/workflows/export.pptx?engagement_id=${encodeURIComponent(engagementId)}&dataset_id=${encodeURIComponent(datasetId)}`,
      `workflow_map.pptx`,
    ),
  deleteProcess: (processId: string) =>
    request<{ deleted: string }>(`/workflows/${processId}`, { method: "DELETE" }),
  deleteStep: (stepId: string) =>
    request<{ deleted: string }>(`/workflows/steps/${stepId}`, { method: "DELETE" }),
  resetBoard: (processId: string) =>
    request<{ process_id: string; unmapped: number }>(
      `/workflows/${processId}/reset-board`,
      { method: "POST" },
    ),

  // Transition
  transitionCompute: (scenarioId: string) =>
    request<TransitionResult>(
      `/transition/compute?scenario_id=${encodeURIComponent(scenarioId)}`,
      { method: "POST" },
    ),
  downloadTransitionRegister: (scenarioId: string) =>
    downloadBlob(
      `${BASE}/transition/register.xlsx?scenario_id=${encodeURIComponent(scenarioId)}`,
      `transition-register.xlsx`,
    ),

  // Deliverables
  generateDeliverable: (
    engagementId: string,
    type: string,
    opts: { datasetId?: string; scenarioId?: string; template?: string } = {},
  ) => {
    const p = new URLSearchParams({ engagement_id: engagementId, type });
    if (opts.template) p.set("template", opts.template);
    if (opts.datasetId) p.set("dataset_id", opts.datasetId);
    if (opts.scenarioId) p.set("scenario_id", opts.scenarioId);
    return request<DeliverableInfo>(`/deliverables/generate?${p.toString()}`, { method: "POST" });
  },
  listDeliverables: (engagementId: string) =>
    request<{ deliverables: DeliverableInfo[] }>(
      `/deliverables/list?engagement_id=${encodeURIComponent(engagementId)}`,
    ),
  downloadDeliverable: (id: string, filename: string) =>
    downloadBlob(`${BASE}/deliverables/${id}/download`, filename),

  // Settings
  getSettings: () => request<AppSettings>("/settings"),
  updateSettings: (updates: Record<string, string>) =>
    request<AppSettings>("/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    }),
  uploadBrandLogo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ brand_logo_path: string }>("/settings/brand-logo", {
      method: "POST",
      body: form,
    });
  },
  // Returns an object URL for the brand logo (auth-gated; <img src> can't send the token).
  // Caller is responsible for URL.revokeObjectURL when replacing/unmounting.
  brandLogoObjectUrl: () => authedBlob(`${BASE}/settings/brand-logo?t=${Date.now()}`).then(URL.createObjectURL),
  testLlm: () =>
    request<{ ok: boolean; provider: string; sample: string }>("/settings/test-llm", {
      method: "POST",
    }),
};
