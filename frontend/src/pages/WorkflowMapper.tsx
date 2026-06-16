import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { OpportunityMatrix, ProcessInfo, StepInfo, TaskItem } from "../types";
import { Button, Card, Empty, ErrorNote, Spinner, StatCard } from "../components/ui";

const AGENCY_BANDS = ["H0", "H1", "H2", "H3", "H4", "H5"];

export default function WorkflowMapper({
  datasetId,
  engagementId,
}: {
  datasetId: string | null;
  engagementId: string | null;
}) {
  const [processes, setProcesses] = useState<ProcessInfo[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [activeProc, setActiveProc] = useState<string>("");
  const [steps, setSteps] = useState<StepInfo[]>([]);
  const [stepId, setStepId] = useState<string>("");
  const [selectedTasks, setSelectedTasks] = useState<Set<string>>(new Set());
  const [matrix, setMatrix] = useState<OpportunityMatrix | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [newProc, setNewProc] = useState("");
  const [newStep, setNewStep] = useState("");

  async function refresh() {
    if (!engagementId) return;
    try {
      setProcesses(await api.listProcesses(engagementId));
    } catch (e) {
      setError(String(e));
    }
  }

  async function loadSteps(procId: string) {
    try {
      setSteps((await api.listSteps(procId)).steps);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  useEffect(() => {
    refresh();
    if (datasetId) api.tasks(datasetId).then((t) => setTasks(t.tasks)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engagementId, datasetId]);

  // When the active process changes, load its steps and reset step/matrix selection.
  useEffect(() => {
    setStepId("");
    setMatrix(null);
    setSelectedTasks(new Set());
    if (activeProc) loadSteps(activeProc);
    else setSteps([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProc]);

  async function addProcess() {
    if (!engagementId || !newProc.trim()) return;
    const p = await api.createProcess(engagementId, newProc.trim()).catch((e) => setError(String(e)));
    setNewProc("");
    await refresh();
    if (p) setActiveProc(p.id);
  }

  async function addStep() {
    if (!activeProc || !newStep.trim()) return;
    const s = await api.addStep(activeProc, newStep.trim()).catch((e) => setError(String(e)));
    setNewStep("");
    if (s) {
      await loadSteps(activeProc);
      setStepId(s.id);
      setNote(`Added step "${s.name}". Select tasks below and link them.`);
    }
  }

  async function map() {
    if (!stepId || selectedTasks.size === 0) return;
    const r = await api
      .mapTasks(stepId, [...selectedTasks])
      .catch((e) => setError(String((e as Error).message ?? e)));
    setSelectedTasks(new Set());
    await loadSteps(activeProc);
    if (r) setNote(`Linked ${r.linked} task(s) to this step.`);
  }

  async function runMatrix() {
    if (!activeProc) return;
    setError("");
    setRunning(true);
    try {
      setMatrix(await api.opportunityMatrix(activeProc));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setRunning(false);
    }
  }

  if (!datasetId || !engagementId) {
    return <Empty message="Open a dataset from the Engagements tab to map workflows." />;
  }

  const activeStep = steps.find((s) => s.id === stepId);
  const totalLinked = steps.reduce((n, s) => n + s.linked_tasks, 0);

  // Mapping coverage (no API key needed): which CSV-derived tasks are linked into this process,
  // which are still unlinked ("what's left"), and which steps have no tasks ("what's missing").
  const linkedIds = new Set(steps.flatMap((s) => s.linked_task_ids ?? []));
  const unlinkedTasks = tasks.filter((t) => !linkedIds.has(t.id));
  const emptySteps = steps.filter((s) => s.linked_tasks === 0);
  const coveragePct = tasks.length ? Math.round((linkedIds.size / tasks.length) * 100) : 0;

  return (
    <div className="space-y-5">
      {error && <ErrorNote message={error} />}
      {note && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {note}
        </div>
      )}
      <div className="grid gap-5 md:grid-cols-3">
        <Card title="Processes & steps">
          <p className="mb-2 text-xs text-slate-500">
            Processes and steps are <b>labels you author here</b> — the value-stream / workflow
            structure isn't in the uploaded org CSV. You then <b>link existing tasks</b> (extracted
            from the CSV in Task Intelligence) onto each step.
          </p>
          {processes.length === 0 ? (
            <Empty message="No processes yet." />
          ) : (
            <ul className="space-y-1">
              {processes.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => setActiveProc(p.id)}
                    className={`w-full rounded px-2 py-1 text-left text-sm ${
                      activeProc === p.id ? "bg-slate-800 text-white" : "hover:bg-slate-100"
                    }`}
                  >
                    {p.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex gap-2">
            <input
              value={newProc}
              onChange={(e) => setNewProc(e.target.value)}
              placeholder="New process"
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <Button onClick={addProcess}>Add</Button>
          </div>

          {activeProc && (
            <div className="mt-4 border-t border-slate-100 pt-3">
              <div className="mb-1 text-xs font-medium uppercase text-slate-500">Steps</div>
              {steps.length === 0 ? (
                <p className="text-xs text-slate-400">No steps yet — add one below.</p>
              ) : (
                <ul className="space-y-1">
                  {steps.map((s) => (
                    <li key={s.id}>
                      <button
                        onClick={() => setStepId(s.id)}
                        className={`flex w-full items-center justify-between rounded px-2 py-1 text-left text-sm ${
                          stepId === s.id ? "bg-slate-200 font-medium" : "hover:bg-slate-100"
                        }`}
                      >
                        <span>
                          {s.seq}. {s.name}
                        </span>
                        <span className="text-xs text-slate-500">{s.linked_tasks} task(s)</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-2 flex gap-2">
                <input
                  value={newStep}
                  onChange={(e) => setNewStep(e.target.value)}
                  placeholder="New step"
                  className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
                />
                <Button variant="ghost" onClick={addStep}>
                  Add step
                </Button>
              </div>
            </div>
          )}
        </Card>

        <Card title={activeStep ? `Map tasks → "${activeStep.name}"` : "Map tasks to step"}>
          {!stepId ? (
            <Empty message="Select (or add) a step, then choose tasks to link." />
          ) : tasks.length === 0 ? (
            <Empty message="No extracted tasks. Run Task Intelligence → Extract first." />
          ) : (
            <>
              <div className="max-h-64 overflow-auto">
                {tasks.map((t) => (
                  <label key={t.id} className="flex items-start gap-2 py-1 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedTasks.has(t.id)}
                      onChange={() => {
                        const n = new Set(selectedTasks);
                        n.has(t.id) ? n.delete(t.id) : n.add(t.id);
                        setSelectedTasks(n);
                      }}
                    />
                    <span>{t.task_text}</span>
                  </label>
                ))}
              </div>
              <Button onClick={map} disabled={selectedTasks.size === 0}>
                Link {selectedTasks.size} task(s)
              </Button>
            </>
          )}
        </Card>

        <Card
          title="AI opportunity matrix"
          actions={
            <Button onClick={runMatrix} disabled={!activeProc || running}>
              {running ? "Running…" : "Run"}
            </Button>
          }
        >
          {running ? (
            <Spinner label="Scoring AI opportunity for this process…" />
          ) : !matrix ? (
            <Empty message="Run the matrix for the selected process (needs an API key)." />
          ) : (
            <div className="space-y-2 text-sm">
              {totalLinked === 0 && (
                <p className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">
                  No tasks linked to this process yet — link tasks to a step for a meaningful matrix.
                </p>
              )}
              <p className="text-xs text-slate-500">
                AI potential by Human Agency Scale — lower H = more AI-amenable; H0 = no
                software-agent overlay (robotics/GSE lever).
              </p>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
                {AGENCY_BANDS.map((h) => (
                  <div key={h} className="rounded border border-slate-200 p-2 text-center">
                    <div className="text-xs text-slate-500">{h}</div>
                    <div className="text-lg font-semibold">{matrix.agency_matrix?.[h] ?? 0}</div>
                  </div>
                ))}
              </div>
              <div className="rounded bg-slate-50 p-2">
                Priority: <b>{matrix.assessment.priority}</b> · Complexity:{" "}
                <b>{matrix.assessment.complexity}</b>
                <p className="mt-1 text-xs text-slate-500">{matrix.assessment.rationale}</p>
              </div>
              {/* Tie the numbers to actual linked tasks so the matrix is clearly connected. */}
              {AGENCY_BANDS.filter((h) => (matrix.agency_evidencing?.[h] ?? []).length > 0).map(
                (h) => (
                  <div key={h} className="text-xs">
                    <span className="font-medium text-slate-600" title={matrix.human_agency_scale?.[h]}>
                      {h} tasks:
                    </span>{" "}
                    <span className="text-slate-500">{matrix.agency_evidencing[h].join("; ")}</span>
                  </div>
                ),
              )}
              <p className="text-xs italic text-amber-600">{matrix.caveats[0]}</p>
            </div>
          )}
        </Card>
      </div>

      {activeProc && (
        <Card title="Mapping coverage">
          {tasks.length === 0 ? (
            <Empty message="No extracted tasks yet — run Task Intelligence → Extract first." />
          ) : (
            <div className="space-y-4">
              {/* Progress: how much of the work has been mapped onto this process. */}
              <div>
                <div className="mb-1 flex justify-between text-xs text-slate-500">
                  <span>
                    {linkedIds.size} of {tasks.length} extracted tasks linked into this process
                  </span>
                  <span>{coveragePct}%</span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-emerald-500 transition-all"
                    style={{ width: `${coveragePct}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <StatCard label="Steps" value={String(steps.length)} />
                <StatCard label="Linked tasks" value={String(linkedIds.size)} />
                <StatCard label="Unlinked (left)" value={String(unlinkedTasks.length)} />
                <StatCard label="Empty steps (missing)" value={String(emptySteps.length)} />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <div className="mb-1 text-xs font-medium uppercase text-slate-500">
                    Unlinked tasks — what's left
                  </div>
                  {unlinkedTasks.length === 0 ? (
                    <p className="rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-700">
                      Every extracted task is linked into this process. ✓
                    </p>
                  ) : (
                    <ul className="max-h-48 space-y-0.5 overflow-auto text-sm text-slate-600">
                      {unlinkedTasks.map((t) => (
                        <li key={t.id} className="border-b border-slate-50 py-0.5">
                          {t.task_text}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <div className="mb-1 text-xs font-medium uppercase text-slate-500">
                    Steps with no tasks — what's missing
                  </div>
                  {emptySteps.length === 0 ? (
                    <p className="rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-700">
                      {steps.length === 0
                        ? "No steps yet — add steps to structure the process."
                        : "Every step has at least one task linked. ✓"}
                    </p>
                  ) : (
                    <ul className="max-h-48 space-y-0.5 overflow-auto text-sm text-amber-700">
                      {emptySteps.map((s) => (
                        <li key={s.id} className="border-b border-amber-50 py-0.5">
                          {s.seq}. {s.name}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
