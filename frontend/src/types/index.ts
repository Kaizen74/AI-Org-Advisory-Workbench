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
  agency: Record<string, number>;
  with_overlay: number;
  robotics_levers: number;
}

export interface RollupResult {
  dataset_id: string;
  overall: RollupBucket;
  by_department: Record<string, RollupBucket>;
  by_layer: Record<string, RollupBucket>;
  human_agency_scale: Record<string, string>;
  caveats: string[];
}

export interface QueueItem {
  kind: "benchmark" | "ai_score" | "crosswalk";
  id: string;
  task_id?: string | null;
  task_text?: string | null;
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

export interface TaskItem {
  id: string;
  task_text: string;
  employee_key?: string | null;
}

export interface ProcessInfo {
  id: string;
  name: string;
  value_stream?: string | null;
}

export interface StepInfo {
  id: string;
  seq: number;
  name: string;
  linked_tasks: number;
  linked_task_ids: string[];
}

export interface OpportunityMatrix {
  process_id: string;
  name: string;
  matrix: Record<string, number>;
  agency_matrix: Record<string, number>;
  steps: {
    step_id: string;
    name: string;
    seq: number;
    level_counts: Record<string, number>;
    agency_counts: Record<string, number>;
  }[];
  evidencing_tasks: Record<string, string[]>;
  agency_evidencing: Record<string, string[]>;
  human_agency_scale: Record<string, string>;
  assessment: { priority: string; complexity: string; rationale: string; review_state: string };
  caveats: string[];
}

export interface RegisterRow {
  employee_key: string;
  display_name: string;
  job_title: string;
  impact_class: string;
  skill_gaps: string[];
  suggested_pathway: string;
  source: string;
  review_state: string;
}

export interface TransitionResult {
  scenario_id: string;
  name: string;
  summary: Record<string, number>;
  register: RegisterRow[];
  caveats: string[];
}

export interface ProvenanceSummary {
  by_source: Record<string, number>;
  total: number;
  client_ready: number;
  excluded_unreviewed_model_inferred: number;
  caveats: string[];
}

export interface DeliverableInfo {
  id: string;
  type: string;
  template: string;
  file_path?: string | null;
  provenance_summary?: ProvenanceSummary | null;
  generated_at?: string;
  bytes?: number;
}

export interface AppSettings {
  llm_provider: string;
  anthropic_api_key_set: boolean;
  anthropic_api_key_last4: string;
  local_api_key_set: boolean;
  local_api_key_last4: string;
  model_extract: string;
  model_synth: string;
  local_base_url: string;
  local_model: string;
  brand_name: string;
  brand_palette: string;
  brand_logo_path: string;
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
