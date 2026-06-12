// Typed API client for the Advisory Workbench backend.
// In dev, Vite proxies /api -> http://127.0.0.1:8000 (see vite.config.ts).
import type {
  ActivatorScreen,
  AIOpportunityResult,
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
  RollupResult,
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
};
