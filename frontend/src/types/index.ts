// Shared API types (mirror the backend Pydantic schemas).

export interface Client {
  id: string;
  name: string;
  industry?: string | null;
  anonymization_default: boolean;
  created_at?: string | null;
}

export interface Engagement {
  id: string;
  client_id: string;
  name: string;
  strategy_context?: string | null;
  design_criteria?: string | null;
  default_taxonomy_code?: string | null;
  anonymized: boolean;
  created_at?: string | null;
}

export interface Dataset {
  id: string;
  engagement_id: string;
  version: number;
  filename?: string | null;
  row_count: number;
  validation_warnings?: string[] | null;
  created_at?: string | null;
}

export interface MetricRow {
  metric_code: string;
  scope: string;
  scope_key?: string | null;
  value?: number | null;
  unit?: string | null;
}

export interface DiagnosticsSummary {
  dataset_id: string;
  computed: boolean;
  metrics: Record<string, number>;
  rows: MetricRow[];
}

export interface ActivatorFlag {
  activator: number;
  name: string;
  triggered: boolean;
  signal_metric: string;
  value: number;
  threshold: number;
  rationale: string;
  basis: string;
}

export interface ActivatorScreen {
  flags: ActivatorFlag[];
  triggered_count: number;
  caveat: string;
}

export interface ArchetypeSummary {
  id: string;
  name: string;
  best_for_industries: string[];
  organizing_principle: string;
  typical_size: string;
  core_tension: string;
  example_companies: string[];
  digital_first_only: boolean;
}
