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
  compass_key?: string | null;   // set when imported from Capability Compass (e.g. MERIDIAN)
}

// ── Shared language with the other three apps (Capability Compass hand-off) ──
/** The shared evidence grade, shown alongside this app's own source/confidence/review state. */
export type EvidenceGrade = "confirmed" | "indicated" | "hypothesis";

/** Compass fields attached to a task or role row. All null when there is no Compass packet. */
export interface CompassTag {
  compass_ref?: string | null;         // e.g. RL-014 — exactly as received
  compass_route?: string | null;       // critical | dual | specialist | standard
  compass_cluster_ref?: string | null; // e.g. CAP-04
  tacit_warning?: string | null;       // set when a high-tacit role's task is proposed at H1–H2
}

export interface CompassRole {
  ref: string;
  title: string;
  cluster_ref?: string | null;
  cluster_name?: string;
  route?: string | null;
  status?: string | null;              // exists | thin | absent
  match_state: string;                 // matched | manual | near | missed | absent
  matched_job_title?: string | null;
  candidates: string[];
  positions: number;
  note?: string | null;
  // stored-state extras
  tasks?: number;
  suggestion?: string | null;
  seat?: string;
  criticality_index?: number | null;
  tacit_intensity?: number | null;
}

export interface CompassPreview {
  ok: boolean;
  errors: string[];
  warnings: string[];
  engagement?: {
    action: "create" | "update";
    id?: string | null;
    key: string;
    name: string;
    current_name?: string | null;
    client_name: string;
  };
  dataset_id?: string | null;
  job_titles?: string[];
  roles?: CompassRole[];
  match_counts?: Record<string, number>;
  changes?: string[];
  asks?: { field: string; question: string }[];
}

export interface CompassApplyResult {
  engagement_id: string;
  client_id: string;
  name: string;
  key: string;
  roles: number;
  warnings: string[];
}

export interface CompassState {
  engagement_id: string;
  imported: boolean;
  key?: string | null;
  generated_at?: string | null;
  imported_at?: string | null;
  readiness?: { ready: boolean; verdict?: string; open?: string[] } | null;
  reference_model: { ref: string; name: string }[];
  leapfrog_gate: { ref: string; test: string }[];
  dataset_id?: string | null;
  job_titles: string[];
  roles: CompassRole[];
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
  unclassified: number;
  level_breakdown: Record<string, number>;
  caveats: string[];
}

export interface AIInferResult {
  dataset_id: string;
  candidates: number;
  updated: number;
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
  source_mix: Record<string, number>;
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
  task_code?: string | null;     // shared displayed ID, e.g. T-014
  grade?: EvidenceGrade;
  compass_ref?: string | null;
  compass_route?: string | null;
  compass_cluster_ref?: string | null;
  tacit_warning?: string | null;
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
  code?: string | null;
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
  pms_step_id?: string | null;   // Process Map Studio step code (S-nn), optional
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

// ── Workflow Mapper board (drag-to-remap) ────────────────────────────────────
export type AgencyBand = "H0" | "H1" | "H2" | "H3" | "H4" | "H5";
export type AiLevel = "L0" | "L1" | "L2" | "L3";

/** One task as shown on the Workflow Mapper board. All fields are real persisted data:
 *  role/department from the source Position; human_agency_level/ai_level/zone/scores from TaskAIScore. */
export interface BoardTask extends CompassTag {
  id: string;
  code?: string | null;          // shared displayed ID, e.g. T-014 (never reused)
  grade?: EvidenceGrade;         // shared evidence grade
  text: string;
  role: string;                 // Position.job_title (or "Unassigned")
  department?: string | null;
  employee_key?: string | null;
  human_agency_level: AgencyBand; // WORKBank HAS band — headline AI-potential (defaults "H0")
  has_level?: number | null;      // raw 1..5 (null => no overlay)
  ai_level: AiLevel;              // TaskAIScore.ai_opportunity_level — secondary detail (defaults "L0")
  zone?: string | null;          // WORKBank zone, when scored
  capability_score?: number | null;
  desire_score?: number | null;  // local desire pulse if present, else US score
  confidence?: number | null;
  review_state: string;          // "approved" | "unreviewed" | ...
  rationale?: string | null;
  step_id?: string | null;       // null => unmapped
}

export interface BoardStep {
  id: string;
  name: string;
  seq: number;
  tasks: BoardTask[];
  pms_step_id?: string | null;   // Process Map Studio step code (S-nn), optional
}

export interface WorkflowBoard {
  process_id: string;
  name: string;
  value_stream?: string | null;
  steps: BoardStep[];
  unmapped: BoardTask[];
  task_count: number;
  mapped_count: number;
  human_agency_scale: Record<string, string>;
  caveats: string[];
}

// ── Org-hierarchy AI roll-up (Roll-up org chart) ─────────────────────────────
/** Where a task sits in the finalized workflow (a task may be mapped in more than one process). */
export interface OrgTaskPlacement {
  process?: string | null;
  step: string;
  step_seq: number;
}

/** One of a role's OWN tasks, as shown when a role is expanded in the roll-up. */
export interface OrgRollupTask {
  id: string;
  code?: string | null;
  grade?: EvidenceGrade;
  tacit_warning?: string | null;
  text: string;
  human_agency_level: AgencyBand;
  zone?: string | null;
  review_state: string;
  mapped: OrgTaskPlacement[]; // [] => not yet mapped to any process step
}

/** One position in the reporting hierarchy with its own AI-band mix and the cumulative mix rolled
 *  up through everyone beneath it (self + all reports), so AI exposure aggregates to dept heads. */
export interface OrgRollupNode {
  employee_key: string;
  name: string;                 // pseudonym when the engagement is anonymized
  job_title: string;
  department?: string | null;
  level: number;
  manager_key?: string | null;  // null => a root (top of org / unattached)
  self_bands: Record<AgencyBand, number>;
  self_tasks: number;
  self_reviewed: number;
  rollup_bands: Record<AgencyBand, number>;
  rollup_tasks: number;
  rollup_reviewed: number;
  direct_reports: number;
  total_reports: number;        // all descendants
  tasks: OrgRollupTask[];       // this role's OWN tasks (not the rolled-up ones)
  compass_ref?: string | null;
  compass_route?: string | null;
  compass_cluster_ref?: string | null;
}

export interface OrgRollup {
  dataset_id: string;
  nodes: OrgRollupNode[];
  roots: string[];
  human_agency_scale: Record<string, string>;
  caveats: string[];
}
