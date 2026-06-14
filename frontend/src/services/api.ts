// Typed API client for the Advisory Workbench backend.
// In dev, Vite proxies /api -> http://127.0.0.1:8000 (see vite.config.ts).
import type {
  ActivatorScreen,
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
  RollupResult,
  Scenario,
  ScenarioDelta,
  TaskItem,
  TransitionResult,
} from "../types";

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, init);
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

export const api = {
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
  pulseInstrumentUrl: (datasetId: string) =>
    `/api/v1/task-intel/pulse/instrument.xlsx?dataset_id=${encodeURIComponent(datasetId)}`,
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
  addStep: (processId: string, name: string) =>
    request<{ id: string; seq: number; name: string }>(`/workflows/${processId}/steps`, json({ name })),
  mapTasks: (stepId: string, taskIds: string[]) =>
    request<{ linked: number }>(`/workflows/steps/${stepId}/map-tasks`, json({ task_ids: taskIds })),
  opportunityMatrix: (processId: string) =>
    request<OpportunityMatrix>(`/workflows/${processId}/opportunity-matrix`, { method: "POST" }),

  // Transition
  transitionCompute: (scenarioId: string) =>
    request<TransitionResult>(
      `/transition/compute?scenario_id=${encodeURIComponent(scenarioId)}`,
      { method: "POST" },
    ),
  transitionRegisterUrl: (scenarioId: string) =>
    `/api/v1/transition/register.xlsx?scenario_id=${encodeURIComponent(scenarioId)}`,

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
  deliverableDownloadUrl: (id: string) => `/api/v1/deliverables/${id}/download`,

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
  brandLogoUrl: () => `/api/v1/settings/brand-logo?t=${Date.now()}`,
  testLlm: () =>
    request<{ ok: boolean; provider: string; sample: string }>("/settings/test-llm", {
      method: "POST",
    }),
};
