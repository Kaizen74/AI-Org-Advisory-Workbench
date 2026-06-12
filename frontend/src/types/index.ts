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

export interface QuickStats {
  positions_total: number;
  positions_with_activities: number;
  coverage_pct: number;
  departments_with_activities: number;
  estimated_batches: number;
}

export interface ExtractResult {
  dataset_id: string;
  positions_total: number;
  positions_with_activities: number;
  batches: number;
  tasks_created: number;
  caveats: string[];
}

export interface BenchmarkResult {
  dataset_id: string;
  tasks: number;
  benchmarks_created: number;
  matched: number;
  missing: number;
  caveats: string[];
}

export interface AIOpportunityResult {
  dataset_id: string;
  scored: number;
  with_overlay: number;
  robotics_levers: number;
  level_breakdown: Record<string, number>;
  caveats: string[];
}

export interface RollupBucket {
  tasks: number;
  levels: Record<string, number>;
  zones: Record<string, number>;
  has: Record<string, number>;
  with_overlay: number;
  robotics_levers: number;
}

export interface RollupResult {
  dataset_id: string;
  overall: RollupBucket;
  by_department: Record<string, RollupBucket>;
  by_layer: Record<string, RollupBucket>;
  caveats: string[];
}

export interface QueueItem {
  kind: "benchmark" | "ai_score" | "crosswalk";
  id: string;
  task_id?: string | null;
  label: string;
  source?: string | null;
  confidence?: number | null;
  review_state: string;
}

export interface QueueResult {
  count: number;
  items: QueueItem[];
}

export interface ReviewAction {
  kind: string;
  id: string;
  action: "approve" | "edit" | "reject";
  edits?: Record<string, unknown>;
}

export interface ReviewResult {
  updated: number;
  crosswalks_created: number;
}

export interface PulseImportResult {
  responses_stored: number;
  scores_updated: number;
}

export interface Scenario {
  id: string;
  name: string;
  status: string;
  parent_scenario_id?: string | null;
}

export interface DesignMove {
  id: string;
  seq: number;
  move_type: string;
}

export interface ScenarioDelta {
  scenario_id: string;
  name: string;
  status: string;
  move_count: number;
  baseline: Record<string, number>;
  scenario: Record<string, number>;
  delta: Record<string, number>;
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
