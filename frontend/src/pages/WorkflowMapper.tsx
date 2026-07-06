// frontend/src/pages/WorkflowMapper.tsx
//
// Visual, interactive Workflow & Task-analysis mapper. Same props ({ datasetId, engagementId }).
//
// Data: tasks are extracted from the uploaded org CSV by Task Intelligence and surfaced here via
// `GET /workflows/:id/board`. Tasks start in the "Unmapped" tray and are dragged onto process steps
// (persisted via `move-task` / `unmap-task`). The headline AI-potential per task is the WORKBank
// Human Agency Scale (H0–H5, lower H = more AI-amenable; H0 = no software-agent overlay → robotics/GSE
// lever); role (job title), zone, capability/desire and L0–L3 are real persisted fields too.
//
// Views: Flow (step columns + unmapped tray, drag-to-remap), Landscape (capability×desire with
// WORKBank zones), Roll-up (per-step H0→H5 mix + AI assessment). Plus hover role-trace, filters,
// undo (⌘/Ctrl-Z) and an inspector.

import { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import type {
  AgencyBand,
  BoardStep,
  BoardTask,
  OpportunityMatrix,
  OrgRollup,
  OrgRollupNode,
  ProcessInfo,
  WorkflowBoard,
} from "../types";
import { Empty, ErrorNote, Spinner } from "../components/ui";

type View = "flow" | "landscape" | "rollup";
type MoveOp = { taskId: string; fromStepId: string | null; toStepId: string | null };

// Headline scale: WORKBank Human Agency Scale (H0–H5). `potential` is the AI-amenability weight used
// for the opportunity index (lower H = higher potential; H0/H5 contribute 0).
const BANDS: AgencyBand[] = ["H0", "H1", "H2", "H3", "H4", "H5"];
const HAS: Record<AgencyBand, { name: string; chip: string; bar: string; potential: number }> = {
  H0: { name: "No agent overlay (robotics/GSE)", chip: "bg-[#e7eaf3] text-[#5b6b9c]", bar: "#94a3b8", potential: 0 },
  H1: { name: "AI can do it (minimal human)", chip: "bg-[#7fc0b2] text-[#0d3b34]", bar: "#2f8074", potential: 1.0 },
  H2: { name: "AI does most", chip: "bg-[#b6dbd1] text-[#1d564d]", bar: "#5fb3a6", potential: 0.75 },
  H3: { name: "Equal partnership", chip: "bg-[#dcebe7] text-[#2f6e64]", bar: "#9fcabf", potential: 0.5 },
  H4: { name: "Human leads, AI assists", chip: "bg-[#eef1f4] text-[#64748b]", bar: "#cbd5e1", potential: 0.25 },
  H5: { name: "Human-led", chip: "bg-slate-100 text-slate-500", bar: "#e2e8f0", potential: 0 },
};
const AI_AMENABLE: AgencyBand[] = ["H1", "H2"]; // strongly AI-amenable bands

// Zone = the go/no-go recommendation, DERIVED from the H-band + capability (kept coherent with H0–H5
// backend-side): GREEN = an AI-agent opportunity (H1–H2 + high capability), RED = keep human-led
// (H3–H5), ROBOTICS = physical/handling work (off the software-agent scale — a robotics/GSE lever).
const ZONE_META: Record<string, { label: string; help: string; dot: string; text: string }> = {
  GREEN_LIGHT: { label: "Green light", dot: "#2f8074", text: "text-[#1d564d]",
    help: "AI-agent opportunity — the task is AI-amenable (H1–H2) and current AI capability is high." },
  RED_LIGHT: { label: "Red light", dot: "#c2683f", text: "text-[#8a4526]",
    help: "Keep human-led — human agency dominates (H3–H5) or capability is low; not an agent opportunity now." },
  ROBOTICS_GSE_LEVER: { label: "Robotics lever", dot: "#7c8db5", text: "text-[#4a5a86]",
    help: "Physical/handling task — off the software-agent scale; assess as a robotics/GSE automation lever." },
  NO_BENCHMARK_MATCH: { label: "No benchmark", dot: "#94a3b8", text: "text-slate-500",
    help: "No matching benchmark in the loaded taxonomy yet — load/curate one or rate it manually to score it." },
};
function zoneMeta(zone?: string | null) {
  return (zone && ZONE_META[zone]) || { label: zone ?? "—", help: "", dot: "#cbd5e1", text: "text-slate-500" };
}

// ── pure helpers ─────────────────────────────────────────────────────────────
function stepOfTask(board: WorkflowBoard, taskId: string): string | null {
  for (const s of board.steps) if (s.tasks.some((t) => t.id === taskId)) return s.id;
  return null;
}

function applyMoveLocal(board: WorkflowBoard, taskId: string, toStepId: string | null): WorkflowBoard {
  let moved: BoardTask | null = null;
  const steps: BoardStep[] = board.steps.map((s) => ({
    ...s,
    tasks: s.tasks.filter((t) => {
      if (t.id === taskId) { moved = { ...t }; return false; }
      return true;
    }),
  }));
  let unmapped = board.unmapped.filter((t) => {
    if (t.id === taskId) { moved = { ...t }; return false; }
    return true;
  });
  if (!moved) return board;
  (moved as BoardTask).step_id = toStepId;
  if (toStepId) {
    const s = steps.find((x) => x.id === toStepId);
    if (s) s.tasks = [...s.tasks, moved];
  } else {
    unmapped = [...unmapped, moved];
  }
  const mapped_count = steps.reduce((n, s) => n + s.tasks.length, 0);
  return { ...board, steps, unmapped, mapped_count };
}

function aiIndex(tasks: BoardTask[]): number {
  if (!tasks.length) return 0;
  const score = tasks.reduce((n, t) => n + HAS[t.human_agency_level].potential, 0);
  return Math.round((score / tasks.length) * 100);
}

function bandBars(tasks: BoardTask[]) {
  const tot = tasks.length || 1;
  return BANDS.map((b) => {
    const c = tasks.filter((t) => t.human_agency_level === b).length;
    return { b, c, pct: (c / tot) * 100 };
  }).filter((x) => x.c > 0);
}

// Same formulas as aiIndex/bandBars but over a band-count map (used by the org-hierarchy roll-up).
function indexFromBands(bands: Record<AgencyBand, number>): number {
  const total = BANDS.reduce((n, b) => n + (bands[b] || 0), 0);
  if (!total) return 0;
  const score = BANDS.reduce((n, b) => n + (bands[b] || 0) * HAS[b].potential, 0);
  return Math.round((score / total) * 100);
}
function barsFromBands(bands: Record<AgencyBand, number>) {
  const tot = BANDS.reduce((n, b) => n + (bands[b] || 0), 0) || 1;
  return BANDS.map((b) => ({ b, c: bands[b] || 0, pct: ((bands[b] || 0) / tot) * 100 })).filter((x) => x.c > 0);
}
function sortByOpportunity(a: OrgRollupNode, b: OrgRollupNode): number {
  return (
    indexFromBands(b.rollup_bands) - indexFromBands(a.rollup_bands) ||
    b.rollup_tasks - a.rollup_tasks ||
    a.name.localeCompare(b.name)
  );
}

// ── small UI atoms ───────────────────────────────────────────────────────────
function Tool({ children, onClick, disabled, title }: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean; title?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40"
    >
      {children}
    </button>
  );
}

export default function WorkflowMapper({
  datasetId,
  engagementId,
}: {
  datasetId: string | null;
  engagementId: string | null;
}) {
  const [processes, setProcesses] = useState<ProcessInfo[]>([]);
  const [activeProc, setActiveProc] = useState<string>("");
  const [board, setBoard] = useState<WorkflowBoard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [view, setView] = useState<View>("flow");
  const allOn = (): Record<AgencyBand, boolean> =>
    Object.fromEntries(BANDS.map((b) => [b, true])) as Record<AgencyBand, boolean>;
  const [aiOn, setAiOn] = useState<Record<AgencyBand, boolean>>(allOn);
  const [reviewFilter, setReviewFilter] = useState<"all" | "reviewed" | "unreviewed">("all");

  const [selKind, setSelKind] = useState<"task" | "step" | null>(null);
  const [selId, setSelId] = useState<string | null>(null);
  const [hoverRole, setHoverRole] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<string | null>(null); // step id or "__unmapped"

  const [history, setHistory] = useState<MoveOp[]>([]);
  const [newProc, setNewProc] = useState("");
  const [newStep, setNewStep] = useState("");
  const [assessment, setAssessment] = useState<OpportunityMatrix | null>(null);
  const [assessing, setAssessing] = useState(false);

  // ── data loading ────────────────────────────────────────────────────────────
  async function refreshProcesses() {
    if (!engagementId) return;
    try {
      const ps = await api.listProcesses(engagementId);
      setProcesses(ps);
      if (ps.length && !ps.some((p) => p.id === activeProc)) setActiveProc(ps[0].id);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function loadBoard(processId: string) {
    if (!processId || !datasetId) return;
    setLoading(true);
    setError("");
    try {
      const b = await api.workflowBoard(processId, datasetId);
      setBoard(b);
      setHistory([]);
      setAssessment(null);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refreshProcesses(); /* eslint-disable-next-line */ }, [engagementId]);
  useEffect(() => { if (activeProc) loadBoard(activeProc); /* eslint-disable-next-line */ }, [activeProc, datasetId]);

  // keyboard undo
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "z" || e.key === "Z") && !e.shiftKey) {
        const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        e.preventDefault();
        undo();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    /* eslint-disable-next-line */
  }, [history, board, activeProc]);

  // ── mutations (optimistic + persisted) ───────────────────────────────────────
  function sync(taskId: string, toStepId: string | null) {
    if (!activeProc) return Promise.resolve();
    const p = toStepId ? api.moveTask(activeProc, taskId, toStepId) : api.unmapTask(activeProc, taskId);
    return p.catch((e) => {
      setError("Couldn't save change — reloading. " + String((e as Error).message ?? e));
      loadBoard(activeProc);
    });
  }

  function doMove(taskId: string, toStepId: string | null) {
    if (!board) return;
    const from = stepOfTask(board, taskId);
    if (from === toStepId) return;
    setHistory((h) => [...h, { taskId, fromStepId: from, toStepId }]);
    setBoard(applyMoveLocal(board, taskId, toStepId));
    sync(taskId, toStepId);
  }

  function undo() {
    if (!board || !history.length) return;
    const op = history[history.length - 1];
    setHistory((h) => h.slice(0, -1));
    setBoard(applyMoveLocal(board, op.taskId, op.fromStepId));
    sync(op.taskId, op.fromStepId);
  }

  async function resetBoard() {
    if (!board || !activeProc) return;
    const mapped = board.mapped_count;
    if (mapped === 0 && !history.length) return;
    if (mapped > 0 && !window.confirm(
      `Unmap all ${mapped} task(s) from "${proc?.name ?? "this process"}"? They return to the unmapped tray.`,
    )) return;
    try {
      await api.resetBoard(activeProc);
      await loadBoard(activeProc); // reload the cleared board (also clears undo history)
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function addProcess() {
    if (!engagementId || !newProc.trim()) return;
    try {
      const p = await api.createProcess(engagementId, newProc.trim());
      setNewProc("");
      await refreshProcesses();
      setActiveProc(p.id);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function addStep() {
    if (!activeProc || !newStep.trim()) return;
    try {
      await api.addStep(activeProc, newStep.trim());
      setNewStep("");
      await loadBoard(activeProc);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function deleteProcess(id: string, name: string) {
    if (!window.confirm(`Delete process "${name}" and all its steps/mappings? (Tasks return to the pool.)`)) return;
    try {
      await api.deleteProcess(id);
      const ps = await api.listProcesses(engagementId!);
      setProcesses(ps);
      if (activeProc === id) {
        setActiveProc(ps[0]?.id ?? "");
        if (!ps.length) setBoard(null);
      }
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function deleteStep(id: string, name: string) {
    if (!window.confirm(`Delete step "${name}"? Its tasks return to the unmapped tray.`)) return;
    try {
      await api.deleteStep(id);
      if (selKind === "step" && selId === id) { setSelKind(null); setSelId(null); }
      await loadBoard(activeProc);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function runAssessment() {
    if (!activeProc) return;
    setAssessing(true);
    setError("");
    try {
      setAssessment(await api.opportunityMatrix(activeProc));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setAssessing(false);
    }
  }

  // ── derived ──────────────────────────────────────────────────────────────────
  const allTasks = useMemo<BoardTask[]>(
    () => (board ? [...board.steps.flatMap((s) => s.tasks), ...board.unmapped] : []),
    [board],
  );
  const reviewMatch = (t: BoardTask) =>
    reviewFilter === "all" ||
    (reviewFilter === "reviewed" ? t.review_state === "approved" : t.review_state !== "approved");
  const pass = (t: BoardTask) => aiOn[t.human_agency_level] && reviewMatch(t);
  // Analysis (index, roll-up, landscape) computes over the filtered set so 'Reviewed only' focuses
  // the AI-opportunity read on client-ready scores. (Flow keeps all cards, dimming filtered ones.)
  const analysisTasks = allTasks.filter(pass);
  const dimOf = (t: BoardTask) => {
    if (!pass(t)) return 0.25;
    if (hoverRole && t.role !== hoverRole) return 0.4;
    return 1;
  };
  const roleTasks = hoverRole ? allTasks.filter((t) => t.role === hoverRole) : [];
  const roleSteps = new Set(roleTasks.map((t) => t.step_id || "__u"));

  const selTask = selKind === "task" ? allTasks.find((t) => t.id === selId) || null : null;
  const selStep = selKind === "step" && board ? board.steps.find((s) => s.id === selId) || null : null;

  if (!datasetId || !engagementId) {
    return <Empty message="Open a dataset from the Engagements tab to map workflows." />;
  }

  const proc = processes.find((p) => p.id === activeProc);
  const filtersActive = BANDS.some((b) => !aiOn[b]) || reviewFilter !== "all";
  const amenable = (ts: BoardTask[]) => ts.filter((t) => AI_AMENABLE.includes(t.human_agency_level)).length;

  return (
    <div className="flex h-[calc(100vh-150px)] min-h-[560px] flex-col overflow-hidden rounded-lg border border-slate-200 bg-white">
      {/* ── HEADER ── */}
      <header className="border-b border-slate-200 px-5 pt-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              <span>Workflow Mapper</span>
              {proc?.value_stream && <><span className="text-slate-300">·</span><span className="font-normal normal-case tracking-normal">{proc.value_stream}</span></>}
            </div>
            <h2 className="mt-0.5 text-xl font-semibold tracking-tight text-slate-900">{proc?.name ?? "Select a process"}</h2>
            {board && (
              <div className="mt-1 flex items-center gap-4 text-xs text-slate-500">
                <span><b className="tabular-nums text-slate-700">{board.steps.length}</b> steps</span>
                <span><b className="tabular-nums text-slate-700">{board.task_count}</b> tasks</span>
                <span><b className="tabular-nums text-slate-700">{board.unmapped.length}</b> unmapped</span>
                <span><b className="tabular-nums text-[#1d564d]">{amenable(analysisTasks)}</b> AI-amenable (H1–H2)</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="flex gap-1.5">
              <Tool onClick={() => activeProc && loadBoard(activeProc)} disabled={!activeProc || loading} title="Reload the board to pull the latest reviewed scores from the Validation Queue">↻ Refresh</Tool>
              <Tool onClick={undo} disabled={!history.length} title="Undo your last move this session (⌘Z)">↺ Undo{history.length ? ` (${history.length})` : ""}</Tool>
              <Tool onClick={resetBoard} disabled={!board || (board.mapped_count === 0 && !history.length)} title="Unmap all tasks from this process (clear the board)">Reset board</Tool>
              <Tool
                onClick={() => engagementId && datasetId && api.exportWorkflowCsv(engagementId, datasetId).catch((e) => setError(String((e as Error).message ?? e)))}
                disabled={!engagementId || !datasetId}
                title="Export every mapped task → step → process (.csv)"
              >↓ CSV</Tool>
              <Tool
                onClick={() => engagementId && datasetId && api.exportWorkflowPptx(engagementId, datasetId).catch((e) => setError(String((e as Error).message ?? e)))}
                disabled={!engagementId || !datasetId}
                title="Export a PowerPoint deck of the finalized workflow (.pptx)"
              >↓ PPTX</Tool>
            </div>
            <div className="flex gap-0.5 rounded-lg bg-slate-100 p-0.5">
              {([["flow", "Flow"], ["landscape", "Landscape"], ["rollup", "Roll-up"]] as [View, string][]).map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setView(id)}
                  className={`rounded-md px-3.5 py-1.5 text-xs font-semibold transition ${view === id ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
                >{label}</button>
              ))}
            </div>
          </div>
        </div>

        {/* process chips + filters */}
        <div className="mt-3.5 flex flex-wrap items-center justify-between gap-4 pb-3">
          <div className="flex flex-wrap items-center gap-2">
            {processes.map((p) => (
              <span
                key={p.id}
                className={`group inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium ${p.id === activeProc ? "border-slate-800 bg-slate-800 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
              >
                <button onClick={() => { setActiveProc(p.id); setSelKind(null); setSelId(null); }}>{p.name}</button>
                <button
                  onClick={() => deleteProcess(p.id, p.name)}
                  title="Delete process"
                  className={`ml-0.5 rounded-full px-1 leading-none ${p.id === activeProc ? "text-white/70 hover:text-white" : "text-slate-300 hover:text-red-600"}`}
                >×</button>
              </span>
            ))}
            <div className="flex items-center gap-1.5">
              <input
                value={newProc}
                onChange={(e) => setNewProc(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addProcess()}
                placeholder="New process"
                className="w-32 rounded-full border border-slate-300 px-3 py-1.5 text-xs outline-none focus:border-slate-400"
              />
              <button onClick={addProcess} className="rounded-full bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white">Add</button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3.5">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Agency</span>
              {BANDS.map((b) => (
                <button
                  key={b}
                  title={HAS[b].name}
                  onClick={() => setAiOn((s) => ({ ...s, [b]: !s[b] }))}
                  className={`rounded-md px-2 py-1 text-[11px] font-bold tabular-nums ${aiOn[b] ? HAS[b].chip : "bg-slate-100 text-slate-400"}`}
                >{b}</button>
              ))}
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Review</span>
              <div className="flex gap-0.5 rounded-md bg-slate-100 p-0.5">
                {([["all", "All"], ["reviewed", "Reviewed only"], ["unreviewed", "Unreviewed only"]] as
                  [typeof reviewFilter, string][]).map(([id, label]) => (
                  <button
                    key={id}
                    onClick={() => setReviewFilter(id)}
                    title={id === "reviewed"
                      ? "Analyse only consultant-approved (client-ready) scores"
                      : id === "unreviewed" ? "Show only unreviewed scores" : "Show all scores"}
                    className={`rounded px-2 py-0.5 text-[11px] font-semibold ${reviewFilter === id ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
                  >{label}</button>
                ))}
              </div>
            </div>
            {filtersActive && (
              <button onClick={() => { setAiOn(allOn()); setReviewFilter("all"); }} className="text-[11px] text-slate-400 underline underline-offset-2">Clear filters</button>
            )}
          </div>
        </div>
      </header>

      {/* ── BODY ── */}
      <div className="relative flex min-h-0 flex-1">
        <main className="min-w-0 flex-1 overflow-auto bg-[#f6f7f9] p-5">
          {error && <div className="mb-3"><ErrorNote message={error} /></div>}
          {loading ? (
            <Spinner label="Loading board…" />
          ) : !board ? (
            <Empty message="Create a process, then drag the unmapped tasks onto its steps." />
          ) : view === "flow" ? (
            <FlowView
              board={board}
              dimOf={dimOf}
              hoverRole={hoverRole}
              dragOver={dragOver}
              setDragOver={setDragOver}
              setDragId={setDragId}
              onDrop={(stepId) => { if (dragId) doMove(dragId, stepId); setDragId(null); setDragOver(null); }}
              onSelectTask={(id) => { setSelKind("task"); setSelId(id); }}
              onSelectStep={(id) => { setSelKind("step"); setSelId(id); }}
              onDeleteStep={deleteStep}
              onHoverRole={setHoverRole}
              newStep={newStep}
              setNewStep={setNewStep}
              addStep={addStep}
            />
          ) : view === "landscape" ? (
            <LandscapeView tasks={analysisTasks} dimOf={dimOf} onSelectTask={(id) => { setSelKind("task"); setSelId(id); }} onHoverRole={setHoverRole} />
          ) : (
            <RollupView datasetId={datasetId} assessment={assessment} assessing={assessing} runAssessment={runAssessment} onHoverRole={setHoverRole} />
          )}
        </main>

        {/* floating role-trace chip */}
        {hoverRole && (
          <div className="pointer-events-none absolute bottom-5 left-5 z-10 flex items-center gap-2.5 rounded-xl bg-[#10302b] px-4 py-2.5 shadow-lg">
            <span className="text-[9.5px] font-semibold uppercase tracking-wider text-[#6fb3a6]">Role</span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-[#5fb3a6] ring-4 ring-[#5fb3a6]/30" />
              <span className="text-sm font-semibold text-[#eafaf5]">{hoverRole}</span>
            </span>
            <span className="h-3.5 w-px bg-white/15" />
            <span className="text-xs tabular-nums text-[#9fd0c6]">{roleTasks.length} linked task{roleTasks.length === 1 ? "" : "s"}{roleSteps.size > 1 ? ` · ${roleSteps.size} steps` : ""}</span>
          </div>
        )}

        {/* ── INSPECTOR ── */}
        <aside className="w-[320px] flex-none overflow-auto border-l border-slate-200 bg-white p-5">
          {selTask ? (
            <TaskInspector
              task={selTask}
              steps={board?.steps ?? []}
              scale={board?.human_agency_scale}
              onBack={() => { setSelKind(null); setSelId(null); }}
              onMove={(stepId) => doMove(selTask.id, stepId)}
            />
          ) : selStep ? (
            <StepInspector
              step={selStep}
              onBack={() => { setSelKind(null); setSelId(null); }}
              onSelectTask={(id) => { setSelKind("task"); setSelId(id); }}
            />
          ) : (
            <OverviewInspector proc={proc} board={board} index={aiIndex(analysisTasks)} reviewFilter={reviewFilter} />
          )}
        </aside>
      </div>
    </div>
  );
}

// ── FLOW ───────────────────────────────────────────────────────────────────
function TaskCard({ t, dim, roleLit, draggable, onDragStart, onClick, onHoverRole }: {
  t: BoardTask; dim: number; roleLit?: boolean; draggable?: boolean;
  onDragStart?: (id: string) => void; onClick: () => void; onHoverRole: (r: string | null) => void;
}) {
  return (
    <div
      draggable={draggable}
      onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; onDragStart?.(t.id); }}
      onClick={onClick}
      onMouseEnter={() => onHoverRole(t.role)}
      onMouseLeave={() => onHoverRole(null)}
      style={{
        opacity: dim,
        borderLeftColor: HAS[t.human_agency_level].bar,
        boxShadow: roleLit ? "0 0 0 2px rgba(47,110,100,.5)" : undefined,
      }}
      className="cursor-grab rounded-lg border border-slate-200 border-l-[3px] bg-white p-2.5 shadow-sm hover:shadow"
    >
      <div className="text-[12px] font-medium leading-snug text-slate-700">{t.text}</div>
      <div className="mt-1 text-[10.5px]" style={{ color: roleLit ? "#2f6e64" : "#7a8694", fontWeight: roleLit ? 600 : 400 }}>{t.role}</div>
      <div className="mt-2 flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <span title={HAS[t.human_agency_level].name} className={`rounded px-1.5 py-0.5 text-[10px] font-bold tabular-nums ${HAS[t.human_agency_level].chip}`}>{t.human_agency_level}</span>
          {t.zone && (
            <span title={zoneMeta(t.zone).help} className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-[9.5px] font-medium text-slate-500">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: zoneMeta(t.zone).dot }} />
              {t.zone}
            </span>
          )}
        </span>
        <span title={t.review_state} className="h-1.5 w-1.5 rounded-full" style={{ background: t.review_state === "approved" ? "#3f9d77" : "#cbb24a" }} />
      </div>
    </div>
  );
}

function Column({ id, title, seq, tasks, dimOf, roleLitOf, isOver, setDragOver, onDrop, onSelectTask, onSelectStep, onDeleteStep, onHoverRole, onDragStart, tone }: {
  id: string; title: string; seq?: number; tasks: BoardTask[]; dimOf: (t: BoardTask) => number; roleLitOf: (t: BoardTask) => boolean;
  isOver: boolean; setDragOver: (v: string | null) => void; onDrop: () => void;
  onSelectTask: (id: string) => void; onSelectStep?: (id: string) => void; onDeleteStep?: (id: string, title: string) => void;
  onHoverRole: (r: string | null) => void; onDragStart: (id: string) => void; tone: "step" | "unmapped";
}) {
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(id); }}
      onDragLeave={() => setDragOver(null)}
      onDrop={(e) => { e.preventDefault(); onDrop(); }}
      className={`flex w-[236px] flex-none flex-col rounded-xl border ${tone === "unmapped" ? "border-dashed border-slate-300 bg-slate-50" : "border-slate-200 bg-[#fbfcfd]"} ${isOver ? "!border-[#8fc9bc] !bg-[#eef6f3]" : ""}`}
    >
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-3.5 py-3">
        <button onClick={() => onSelectStep?.(id)} className="flex items-center gap-2 text-left">
          {seq != null && <span className="flex h-5 w-5 flex-none items-center justify-center rounded-md bg-slate-800 text-[11px] font-semibold tabular-nums text-white">{seq}</span>}
          <span className="text-[13px] font-semibold leading-tight text-slate-800">{title}</span>
        </button>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] tabular-nums text-slate-400">{tasks.length}</span>
          {tone === "step" && onDeleteStep && (
            <button onClick={() => onDeleteStep(id, title)} title="Delete step"
              className="rounded px-1 text-sm leading-none text-slate-300 hover:text-red-600">×</button>
          )}
        </div>
      </div>
      <div className="flex min-h-[60px] flex-col gap-2 p-2.5">
        {tasks.map((t) => (
          <TaskCard key={t.id} t={t} dim={dimOf(t)} roleLit={roleLitOf(t)} draggable onDragStart={onDragStart} onClick={() => onSelectTask(t.id)} onHoverRole={onHoverRole} />
        ))}
        {tasks.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-200 px-1.5 py-3.5 text-center text-[11px] text-slate-400">Drop tasks here</div>
        )}
      </div>
    </div>
  );
}

function FlowView({ board, dimOf, hoverRole, dragOver, setDragOver, setDragId, onDrop, onSelectTask, onSelectStep, onDeleteStep, onHoverRole, newStep, setNewStep, addStep }: {
  board: WorkflowBoard; dimOf: (t: BoardTask) => number; hoverRole: string | null; dragOver: string | null;
  setDragOver: (v: string | null) => void; setDragId: (v: string | null) => void; onDrop: (stepId: string | null) => void;
  onSelectTask: (id: string) => void; onSelectStep: (id: string) => void; onDeleteStep: (id: string, title: string) => void;
  onHoverRole: (r: string | null) => void; newStep: string; setNewStep: (v: string) => void; addStep: () => void;
}) {
  const roleLitOf = (t: BoardTask) => !!hoverRole && t.role === hoverRole;
  return (
    <div className="flex w-max items-stretch gap-0">
      {/* Unmapped tray */}
      <Column
        id="__unmapped" title="Unmapped tasks" tasks={board.unmapped} tone="unmapped"
        dimOf={dimOf} roleLitOf={roleLitOf} isOver={dragOver === "__unmapped"}
        setDragOver={setDragOver} onDrop={() => onDrop(null)}
        onSelectTask={onSelectTask} onHoverRole={onHoverRole} onDragStart={setDragId}
      />
      <div className="w-7 flex-none" />
      {board.steps.map((s, i) => (
        <div key={s.id} className="flex items-stretch">
          <Column
            id={s.id} title={s.name} seq={s.seq} tasks={s.tasks} tone="step"
            dimOf={dimOf} roleLitOf={roleLitOf} isOver={dragOver === s.id}
            setDragOver={setDragOver} onDrop={() => onDrop(s.id)}
            onSelectTask={onSelectTask} onSelectStep={onSelectStep} onDeleteStep={onDeleteStep} onHoverRole={onHoverRole} onDragStart={setDragId}
          />
          {i < board.steps.length - 1 && (
            <div className="flex w-7 flex-none items-center justify-center text-slate-300">
              <svg width="18" height="14" viewBox="0 0 18 14" fill="none"><path d="M1 7h14M11 2l5 5-5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </div>
          )}
        </div>
      ))}
      {/* add step */}
      <div className="ml-7 flex w-[200px] flex-none flex-col justify-center gap-2 rounded-xl border border-dashed border-slate-300 p-3.5">
        <input value={newStep} onChange={(e) => setNewStep(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addStep()} placeholder="New step name" className="rounded-lg border border-slate-300 px-2.5 py-2 text-xs outline-none focus:border-slate-400" />
        <button onClick={addStep} className="rounded-lg bg-slate-100 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-200">+ Add step</button>
      </div>
    </div>
  );
}

// ── LANDSCAPE (capability × desire, WORKBank zones) ──────────────────────────
function LandscapeView({ tasks, dimOf, onSelectTask, onHoverRole }: {
  tasks: BoardTask[]; dimOf: (t: BoardTask) => number; onSelectTask: (id: string) => void; onHoverRole: (r: string | null) => void;
}) {
  // Plot any task with a capability score (X axis). Desire (Y) is used when captured; otherwise the
  // task is placed at a neutral desire (0.5) and drawn hollow so reviewed/inferred tasks still appear.
  const placeable = tasks.filter((t) => t.capability_score != null);
  const noDesire = placeable.filter((t) => t.desire_score == null).length;
  const unscored = tasks.length - placeable.length;
  return (
    <div className="max-w-[820px]">
      <div className="mb-4 flex items-center gap-2.5">
        <h3 className="text-sm font-semibold text-slate-800">AI opportunity landscape</h3>
        <span className="text-xs text-slate-400">automation capability × local desire · dot colour = Human Agency (H0–H5)</span>
      </div>
      {placeable.length === 0 ? (
        <Empty message="No capability scores yet. Run Task Intelligence → AI opportunity (and rate/benchmark tasks) to populate the landscape." />
      ) : (
        <>
          <div className="flex gap-3">
            <div className="flex w-5 items-center justify-center"><span className="rotate-180 text-[10.5px] font-semibold uppercase tracking-wider text-slate-400" style={{ writingMode: "vertical-rl" }}>Desire →</span></div>
            <div className="flex-1">
              <div className="relative h-[420px] rounded-xl border border-slate-200 bg-white">
                {/* quadrant guides */}
                <div className="absolute inset-0 grid grid-cols-2 grid-rows-2">
                  <div className="border-b border-r border-slate-100 p-2 text-[10px] font-semibold uppercase tracking-wide text-slate-300">Human-led</div>
                  <div className="border-b border-slate-100 p-2 text-right text-[10px] font-semibold uppercase tracking-wide text-[#9a6a18]">Augment / co-pilot</div>
                  <div className="border-r border-slate-100 p-2 text-[10px] font-semibold uppercase tracking-wide text-slate-300">Deprioritize</div>
                  <div className="p-2 text-right text-[10px] font-semibold uppercase tracking-wide text-[#3d8273]">Automate ↗</div>
                </div>
                {placeable.map((t) => {
                  const hasDesire = t.desire_score != null;
                  const y = hasDesire ? (t.desire_score as number) : 0.5;
                  return (
                    <button
                      key={t.id}
                      onClick={() => onSelectTask(t.id)}
                      onMouseEnter={() => onHoverRole(t.role)}
                      onMouseLeave={() => onHoverRole(null)}
                      title={`${t.text} — ${t.role} · ${t.human_agency_level}${hasDesire ? "" : " · desire not captured"}`}
                      style={{
                        left: `${(t.capability_score as number) * 100}%`, bottom: `${y * 100}%`,
                        opacity: dimOf(t),
                        background: hasDesire ? HAS[t.human_agency_level].bar : "#ffffff",
                        borderColor: hasDesire ? "#ffffff" : HAS[t.human_agency_level].bar,
                        transform: "translate(-50%, 50%)",
                      }}
                      className="absolute h-3.5 w-3.5 rounded-full border-2 shadow ring-1 ring-black/5"
                    />
                  );
                })}
              </div>
              <div className="mt-1.5 text-center text-[10.5px] font-semibold uppercase tracking-wider text-slate-400">Automation capability →</div>
            </div>
          </div>
          {noDesire > 0 && <p className="mt-3 text-[11px] text-slate-400">{noDesire} hollow dot{noDesire === 1 ? "" : "s"}: desire not captured — placed at neutral height. Capture it via Task Intelligence → Local desire for exact placement.</p>}
          {unscored > 0 && <p className="mt-1 text-[11px] text-slate-400">{unscored} task{unscored === 1 ? "" : "s"} not yet scored on AI capability — shown in Flow only.</p>}
        </>
      )}
    </div>
  );
}

// ── ROLLUP (org-chart hierarchy: AI exposure aggregated up the reporting lines) ──
// One node per position from the uploaded org CSV, arranged by reporting lines (manager → report).
// Each node shows the AI opportunity ROLLED UP through everyone beneath it, so exposure accumulates
// to the respective department heads — the org chart, read for AI.
function OrgNode({ node, childrenOf, collapsed, toggle, onHoverRole }: {
  node: OrgRollupNode; childrenOf: Map<string, OrgRollupNode[]>;
  collapsed: Set<string>; toggle: (k: string) => void; onHoverRole: (r: string | null) => void;
}) {
  const kids = (childrenOf.get(node.employee_key) || []).slice().sort(sortByOpportunity);
  const idx = indexFromBands(node.rollup_bands);
  const bars = barsFromBands(node.rollup_bands);
  const reviewedPct = node.rollup_tasks ? Math.round((node.rollup_reviewed / node.rollup_tasks) * 100) : 0;
  const isOpen = !collapsed.has(node.employee_key);
  return (
    <div>
      <div
        onMouseEnter={() => onHoverRole(node.job_title)}
        onMouseLeave={() => onHoverRole(null)}
        className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 shadow-sm"
      >
        <button
          onClick={() => kids.length && toggle(node.employee_key)}
          className={`flex h-5 w-5 flex-none items-center justify-center rounded-md text-[11px] font-bold ${kids.length ? "bg-slate-100 text-slate-500 hover:bg-slate-200" : "text-transparent"}`}
          title={kids.length ? (isOpen ? "Collapse reports" : "Expand reports") : ""}
        >{kids.length ? (isOpen ? "−" : "+") : "·"}</button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-[13px] font-semibold text-slate-800" title={node.job_title}>{node.job_title}</span>
            <span className="flex-none rounded bg-slate-100 px-1.5 py-0.5 text-[9.5px] font-semibold tabular-nums text-slate-400">L{node.level}</span>
          </div>
          <div className="truncate text-[11px] text-slate-400">
            {node.name}{node.department ? ` · ${node.department}` : ""}
            {node.total_reports > 0 && ` · ${node.direct_reports} direct / ${node.total_reports} total reports`}
          </div>
        </div>
        <div className="flex flex-none items-center gap-2.5">
          <div className="text-right">
            <div className="text-[14px] font-bold tabular-nums leading-none text-[#16604f]">{idx}</div>
            <div className="text-[8.5px] font-semibold uppercase tracking-wide text-slate-300">index</div>
          </div>
          <span className="flex h-2.5 w-[160px] flex-none gap-0.5 overflow-hidden rounded-full bg-slate-100" title="Rolled-up Human Agency mix (H0 → H5)">
            {bars.length
              ? bars.map((x) => <span key={x.b} title={`${x.b} · ${x.c}`} style={{ width: `${x.pct}%`, background: HAS[x.b].bar }} />)
              : <span className="w-full" />}
          </span>
          <span className="w-16 flex-none text-right text-[10px] tabular-nums text-slate-400" title="Tasks rolled up · % reviewed">
            {node.rollup_tasks} task{node.rollup_tasks === 1 ? "" : "s"}<br />{reviewedPct}% rev.
          </span>
        </div>
      </div>
      {isOpen && kids.length > 0 && (
        <div className="ml-[18px] mt-2 space-y-2 border-l border-slate-200 pl-4">
          {kids.map((k) => (
            <OrgNode key={k.employee_key} node={k} childrenOf={childrenOf} collapsed={collapsed} toggle={toggle} onHoverRole={onHoverRole} />
          ))}
        </div>
      )}
    </div>
  );
}

function RollupView({ datasetId, assessment, assessing, runAssessment, onHoverRole }: {
  datasetId: string; assessment: OpportunityMatrix | null;
  assessing: boolean; runAssessment: () => void; onHoverRole: (r: string | null) => void;
}) {
  const [org, setOrg] = useState<OrgRollup | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError("");
    api.orgRollup(datasetId)
      .then((o) => { if (live) setOrg(o); })
      .catch((e) => { if (live) setError(String((e as Error).message ?? e)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [datasetId]);

  const toggle = (k: string) =>
    setCollapsed((s) => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n; });

  // Build the reporting tree + org-wide stats from the node list.
  const { roots, childrenOf, stats, orgIndex } = useMemo(() => {
    const nodes = org?.nodes ?? [];
    const byKey = new Map(nodes.map((n) => [n.employee_key, n]));
    const childrenOf = new Map<string, OrgRollupNode[]>();
    for (const n of nodes) {
      if (n.manager_key && byKey.has(n.manager_key)) {
        const arr = childrenOf.get(n.manager_key) || [];
        arr.push(n);
        childrenOf.set(n.manager_key, arr);
      }
    }
    const roots = (org?.roots ?? [])
      .map((k) => byKey.get(k))
      .filter((n): n is OrgRollupNode => n !== undefined)
      .sort(sortByOpportunity);

    // Org-wide totals = each position's OWN tasks summed once (avoids double counting up the tree).
    const orgBands = Object.fromEntries(BANDS.map((b) => [b, 0])) as Record<AgencyBand, number>;
    let orgTasks = 0, orgReviewed = 0;
    const depts = new Set<string>();
    let layers = 0;
    for (const n of nodes) {
      for (const b of BANDS) orgBands[b] += n.self_bands[b] || 0;
      orgTasks += n.self_tasks;
      orgReviewed += n.self_reviewed;
      if (n.department) depts.add(n.department);
      if (n.level > layers) layers = n.level;
    }
    const amenable = BANDS.filter((b) => AI_AMENABLE.includes(b)).reduce((s, b) => s + (orgBands[b] || 0), 0);
    const reviewedPct = orgTasks ? Math.round((orgReviewed / orgTasks) * 100) : 0;
    const stats: [string, string][] = [
      ["People", String(nodes.length)],
      ["Reporting layers", String(layers)],
      ["AI-amenable tasks", String(amenable)],
      ["Reviewed", `${reviewedPct}%`],
    ];
    return { roots, childrenOf, stats, orgIndex: indexFromBands(orgBands) };
  }, [org]);

  if (loading) return <Spinner label="Building the org-hierarchy roll-up…" />;
  if (error) return <ErrorNote message={error} />;
  if (!org || org.nodes.length === 0) {
    return <Empty message="No org structure yet. Upload an org CSV and run Task Intelligence to populate the hierarchy roll-up." />;
  }

  return (
    <div className="max-w-[900px]">
      <div className="mb-5 grid grid-cols-4 gap-3">
        {stats.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white p-3.5">
            <div className="text-[10.5px] font-semibold uppercase tracking-wide text-slate-400">{label}</div>
            <div className="mt-1 text-2xl font-bold tabular-nums tracking-tight text-slate-800">{value}</div>
          </div>
        ))}
      </div>

      <div className="mb-4 flex items-center justify-between rounded-xl border border-[#d9ece4] bg-[#f3faf7] p-3 text-[11px] leading-snug text-[#5f8d80]">
        <span>
          <b>Org-hierarchy roll-up:</b> every role's AI opportunity is aggregated <b>up its reporting
          line</b> to the department heads — so each manager's index and Human-Agency mix reflect their
          whole team. Shows the full org structure (the Agency / Review filters apply to the Flow &
          Landscape views). Org-wide AI-opportunity index: <b className="text-[#16604f]">{orgIndex}/100</b>.
        </span>
      </div>

      <div className="space-y-2">
        {roots.map((r) => (
          <OrgNode key={r.employee_key} node={r} childrenOf={childrenOf} collapsed={collapsed} toggle={toggle} onHoverRole={onHoverRole} />
        ))}
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Process AI assessment</div>
          <button onClick={runAssessment} disabled={assessing} className="rounded-md bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50">{assessing ? "Assessing…" : "Run (needs API key)"}</button>
        </div>
        {assessment ? (
          <div className="mt-3 text-sm text-slate-600">
            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs">Priority: <b>{assessment.assessment.priority}</b></span>
            <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs">Complexity: <b>{assessment.assessment.complexity}</b></span>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">{assessment.assessment.rationale}</p>
            {assessment.caveats?.[0] && <p className="mt-2 text-[11px] italic text-amber-600">{assessment.caveats[0]}</p>}
          </div>
        ) : (
          <p className="mt-2 text-xs text-slate-400">Generate a priority / complexity narrative for the active process from its Human Agency (H0–H5) distribution.</p>
        )}
      </div>

      {org.caveats?.[0] && <p className="mt-4 text-[11px] italic leading-snug text-amber-600">{org.caveats[0]}</p>}
    </div>
  );
}

// ── INSPECTORS ────────────────────────────────────────────────────────────────
function OverviewInspector({ proc, board, index, reviewFilter }: {
  proc?: ProcessInfo; board: WorkflowBoard | null; index: number;
  reviewFilter: "all" | "reviewed" | "unreviewed";
}) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Process overview</div>
      <h3 className="mt-1.5 text-lg font-semibold tracking-tight text-slate-900">{proc?.name ?? "—"}</h3>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">{proc?.value_stream ? `Value stream: ${proc.value_stream}.` : "Drag tasks from the Unmapped tray onto steps to follow the work across the org."}</p>

      <div className="mt-5 rounded-xl border border-[#d9ece4] bg-gradient-to-b from-[#f3faf7] to-[#eef6f3] p-4">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-[#3d8273]">AI opportunity index{reviewFilter !== "all" ? ` · ${reviewFilter} only` : ""}</div>
        <div className="mt-0.5 flex items-end gap-2"><span className="text-3xl font-bold tabular-nums tracking-tight text-[#16604f]">{index}</span><span className="mb-1.5 text-sm text-[#5f8d80]">/ 100</span></div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[#dcebe4]"><div className="h-full rounded-full bg-gradient-to-r from-[#5fb3a6] to-[#2f8074]" style={{ width: `${index}%` }} /></div>
        <p className="mt-2 text-[11px] leading-snug text-[#5f8d80]">Weighted Human-Agency AI potential across this process's {reviewFilter !== "all" ? `${reviewFilter} ` : ""}tasks (lower H ⇒ higher potential; H0 = robotics lever, off the software-agent scale).</p>
        <div className="mt-2 rounded-md bg-white/70 p-2 text-[10.5px] leading-snug text-[#5f8d80]">
          <span className="font-semibold">How it's computed:</span> index = mean(weight) × 100, per task
          weight = <b>H1 1.0 · H2 0.75 · H3 0.5 · H4 0.25 · H5 0 · H0 0</b>. So 100 = every task fully
          AI-automatable (H1); 0 = all human-led / robotics.
        </div>
      </div>

      <div className="mt-5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Legend — Human Agency Scale</div>
      <div className="mt-2.5 space-y-1.5">
        {BANDS.map((b) => (
          <div key={b} className="flex items-center gap-2 text-[11px] text-slate-500">
            <span className="inline-flex w-7 justify-center rounded px-1 py-0.5 text-[10px] font-bold" style={{ background: HAS[b].bar }}><span className="text-white">{b}</span></span>
            {HAS[b].name}
          </div>
        ))}
        <div className="flex items-center gap-2 pt-1 text-[11px] text-slate-500"><span className="h-1.5 w-1.5 rounded-full" style={{ background: "#cbb24a" }} /> unreviewed score</div>
      </div>

      <div className="mt-5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Legend — Zone (go / no-go)</div>
      <div className="mt-2.5 space-y-1.5">
        {(["GREEN_LIGHT", "RED_LIGHT", "ROBOTICS_GSE_LEVER"] as const).map((z) => (
          <div key={z} className="flex items-start gap-2 text-[11px] text-slate-500">
            <span className="mt-0.5 h-2.5 w-2.5 flex-none rounded-full" style={{ background: zoneMeta(z).dot }} />
            <span><b className={zoneMeta(z).text}>{zoneMeta(z).label}</b> — {zoneMeta(z).help}</span>
          </div>
        ))}
        <p className="pt-0.5 text-[10.5px] italic leading-snug text-slate-400">Zone is derived from the H-band + capability, so it always agrees with H0–H5.</p>
      </div>
      {board?.caveats?.[0] && <p className="mt-4 text-[11px] italic leading-snug text-amber-600">{board.caveats[0]}</p>}
      <p className="mt-4 text-[11px] leading-snug text-slate-400">Drag a task between steps to re-map it. Hover a task to trace its role across the process. ⌘Z undoes.</p>
    </div>
  );
}

function StepInspector({ step, onBack, onSelectTask }: { step: BoardStep; onBack: () => void; onSelectTask: (id: string) => void }) {
  const roles = new Set(step.tasks.map((t) => t.role));
  const bars = bandBars(step.tasks);
  return (
    <div>
      <button onClick={onBack} className="mb-3 text-xs text-slate-400">← Overview</button>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Step {step.seq}</div>
      <h3 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">{step.name}</h3>
      <div className="text-xs text-slate-500">{step.tasks.length} tasks · {roles.size} roles</div>
      <div className="mt-3 flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-slate-100">
        {bars.map((x) => <span key={x.b} title={`${x.b} · ${x.c}`} style={{ width: `${x.pct}%`, background: HAS[x.b].bar }} />)}
      </div>
      <div className="mt-4 space-y-2">
        {step.tasks.map((t) => (
          <button key={t.id} onClick={() => onSelectTask(t.id)} className="block w-full rounded-lg border border-slate-200 border-l-[3px] bg-white p-2.5 text-left" style={{ borderLeftColor: HAS[t.human_agency_level].bar }}>
            <div className="text-[12px] font-medium leading-snug text-slate-700">{t.text}</div>
            <div className="mt-1.5 flex items-center justify-between"><span className="text-[10.5px] text-slate-500">{t.role}</span><span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${HAS[t.human_agency_level].chip}`}>{t.human_agency_level}</span></div>
          </button>
        ))}
        {step.tasks.length === 0 && <div className="py-4 text-center text-xs text-slate-400">No tasks mapped to this step yet.</div>}
      </div>
    </div>
  );
}

function TaskInspector({ task, steps, scale, onBack, onMove }: { task: BoardTask; steps: BoardStep[]; scale?: Record<string, string>; onBack: () => void; onMove: (stepId: string | null) => void }) {
  const stepName = steps.find((s) => s.id === task.step_id)?.name ?? "Unmapped";
  const h = task.human_agency_level;
  return (
    <div>
      <button onClick={onBack} className="mb-3 text-xs text-slate-400">← {stepName}</button>
      <div className="flex items-center gap-1.5">
        <span className={`rounded-md px-2 py-1 text-[10.5px] font-bold ${HAS[h].chip}`}>{h} · {HAS[h].name}</span>
        <span className="rounded-md bg-slate-100 px-2 py-1 text-[10.5px] font-semibold text-slate-500" title="AI-opportunity level (secondary)">{task.ai_level}</span>
      </div>
      <h3 className="mt-3 text-base font-semibold leading-snug tracking-tight text-slate-900">{task.text}</h3>
      <div className="text-xs text-slate-500">{task.role}{task.department ? ` · ${task.department}` : ""}</div>
      {scale?.[h] && <p className="mt-2 text-[11px] leading-snug text-slate-400">{scale[h]}</p>}

      <div className="mt-4 grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Zone</div>
          <div className={`mt-0.5 flex items-center gap-1.5 text-[13px] font-semibold ${zoneMeta(task.zone).text}`}>
            <span className="h-2 w-2 flex-none rounded-full" style={{ background: zoneMeta(task.zone).dot }} />
            {zoneMeta(task.zone).label}
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Confidence</div>
          <div className="mt-0.5 text-[13px] font-semibold text-slate-700">{task.confidence != null ? `${Math.round(task.confidence * 100)}%` : "—"}</div>
        </div>
      </div>
      {zoneMeta(task.zone).help && (
        <p className="mt-2 text-[11px] leading-snug text-slate-400">{zoneMeta(task.zone).help}</p>
      )}

      {task.rationale && (
        <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 p-3">
          <div className="text-[10.5px] font-semibold uppercase tracking-wide text-slate-400">Why this score</div>
          <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{task.rationale}</p>
        </div>
      )}

      <div className="mt-4">
        <div className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-slate-400">Re-map to step</div>
        <select
          value={task.step_id ?? "__unmapped"}
          onChange={(e) => onMove(e.target.value === "__unmapped" ? null : e.target.value)}
          className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs text-slate-700 outline-none focus:border-slate-400"
        >
          <option value="__unmapped">Unmapped</option>
          {steps.map((s) => <option key={s.id} value={s.id}>{s.seq}. {s.name}</option>)}
        </select>
      </div>

      <div className="mt-4 flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
        <span className="flex items-center gap-2 text-xs font-medium text-slate-600">
          <span className="h-2 w-2 rounded-full" style={{ background: task.review_state === "approved" ? "#3f9d77" : "#cbb24a" }} />
          {task.review_state === "approved" ? "Reviewed" : "Unreviewed"}
        </span>
        <span className="text-[11px] text-slate-400">set in Validation Queue</span>
      </div>
    </div>
  );
}
