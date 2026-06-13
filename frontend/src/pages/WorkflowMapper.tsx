import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { OpportunityMatrix, ProcessInfo, TaskItem } from "../types";
import { Button, Card, Empty, ErrorNote } from "../components/ui";

const LEVELS = ["L0", "L1", "L2", "L3"];

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
  const [stepId, setStepId] = useState<string>("");
  const [selectedTasks, setSelectedTasks] = useState<Set<string>>(new Set());
  const [matrix, setMatrix] = useState<OpportunityMatrix | null>(null);
  const [error, setError] = useState("");
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

  useEffect(() => {
    refresh();
    if (datasetId) api.tasks(datasetId).then((t) => setTasks(t.tasks)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engagementId, datasetId]);

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
    if (s) setStepId(s.id);
  }

  async function map() {
    if (!stepId || selectedTasks.size === 0) return;
    await api.mapTasks(stepId, [...selectedTasks]).catch((e) => setError(String(e)));
    setSelectedTasks(new Set());
  }

  async function runMatrix() {
    if (!activeProc) return;
    setError("");
    try {
      setMatrix(await api.opportunityMatrix(activeProc));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  if (!datasetId || !engagementId) {
    return <Empty message="Open a dataset from the Engagements tab to map workflows." />;
  }

  return (
    <div className="space-y-5">
      {error && <ErrorNote message={error} />}
      <div className="grid gap-5 md:grid-cols-3">
        <Card title="Processes">
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
            <div className="mt-3 flex gap-2">
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
          )}
        </Card>

        <Card title="Map tasks to step">
          {!stepId ? (
            <Empty message="Add a step, then select tasks to link." />
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
            <Button onClick={runMatrix} disabled={!activeProc}>
              Run
            </Button>
          }
        >
          {!matrix ? (
            <Empty message="Run the matrix for the selected process (needs an API key)." />
          ) : (
            <div className="space-y-2 text-sm">
              <div className="grid grid-cols-4 gap-2">
                {LEVELS.map((l) => (
                  <div key={l} className="rounded border border-slate-200 p-2 text-center">
                    <div className="text-xs text-slate-500">{l}</div>
                    <div className="text-lg font-semibold">{matrix.matrix[l] ?? 0}</div>
                  </div>
                ))}
              </div>
              <div className="rounded bg-slate-50 p-2">
                Priority: <b>{matrix.assessment.priority}</b> · Complexity:{" "}
                <b>{matrix.assessment.complexity}</b>
                <p className="mt-1 text-xs text-slate-500">{matrix.assessment.rationale}</p>
              </div>
              <p className="text-xs italic text-amber-600">{matrix.caveats[0]}</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
