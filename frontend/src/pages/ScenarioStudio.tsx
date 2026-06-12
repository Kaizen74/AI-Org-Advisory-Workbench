import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { Scenario, ScenarioDelta } from "../types";
import { Button, Card, Empty, ErrorNote } from "../components/ui";

const HEADLINE = [
  ["total_employees", "Employees"],
  ["total_managers", "Managers"],
  ["manager_ratio_pct", "Manager %"],
  ["average_span", "Avg span"],
  ["organizational_layers", "Layers"],
  ["total_cost", "Total cost"],
];

function buildParams(moveType: string, f: Record<string, string>): Record<string, unknown> {
  const num = (v: string) => (v === "" ? undefined : Number(v));
  switch (moveType) {
    case "DELETE_POSITION":
    case "SET_DOCKING_STATION":
      return { employee_key: f.employee_key };
    case "REPARENT":
      return { employee_key: f.employee_key, new_manager_key: f.manager_key };
    case "CHANGE_GRADE":
      return { employee_key: f.employee_key, grade: f.grade, level: num(f.level) };
    case "ADD_POSITION":
      return {
        employee_key: f.employee_key, manager_key: f.manager_key, grade: f.grade,
        level: num(f.level), salary: num(f.salary), department: f.department,
      };
    case "MERGE_UNITS":
      return { source_manager_key: f.employee_key, target_manager_key: f.manager_key };
    case "SET_ANCHOR_LAYER":
      return { level: num(f.level) };
    default:
      return { employee_key: f.employee_key };
  }
}

export default function ScenarioStudio({
  datasetId,
  engagementId,
}: {
  datasetId: string | null;
  engagementId: string | null;
}) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [active, setActive] = useState<string>("");
  const [delta, setDelta] = useState<ScenarioDelta | null>(null);
  const [moveTypes, setMoveTypes] = useState<string[]>([]);
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
  const [comparison, setComparison] = useState<ScenarioDelta[]>([]);
  const [error, setError] = useState("");
  const [newName, setNewName] = useState("");
  const [moveType, setMoveType] = useState("CHANGE_GRADE");
  const [form, setForm] = useState<Record<string, string>>({});

  async function refresh() {
    if (!engagementId) return;
    try {
      setScenarios(await api.listScenarios(engagementId));
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
    api.moveTypes().then((m) => setMoveTypes(m.move_types)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engagementId]);

  async function loadDelta(id: string) {
    setActive(id);
    setError("");
    try {
      setDelta(await api.scenarioDelta(id));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function create() {
    if (!engagementId || !datasetId || !newName.trim()) return;
    try {
      const s = await api.createScenario(engagementId, datasetId, newName.trim());
      setNewName("");
      await refresh();
      loadDelta(s.id);
    } catch (e) {
      setError(String(e));
    }
  }

  async function addMove() {
    if (!active) return;
    try {
      await api.addMove(active, moveType, buildParams(moveType, form));
      setForm({});
      await loadDelta(active);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function doPresent() {
    if (!active) return;
    await api.presentScenario(active).catch((e) => setError(String(e)));
    await refresh();
    await loadDelta(active);
  }

  async function doFork() {
    if (!active) return;
    const f = await api.forkScenario(active).catch((e) => setError(String(e)));
    await refresh();
    if (f) loadDelta(f.id);
  }

  async function runCompare() {
    const ids = [...compareIds].slice(0, 3);
    if (ids.length === 0) return;
    setComparison((await api.compareScenarios(ids)).scenarios);
  }

  function set(field: string, value: string) {
    setForm({ ...form, [field]: value });
  }

  if (!datasetId || !engagementId) {
    return <Empty message="Open a dataset from the Engagements tab to design scenarios." />;
  }

  const fmt = (v?: number) => (v === undefined ? "—" : v.toLocaleString());
  const activeScenario = scenarios.find((s) => s.id === active);
  const locked = activeScenario?.status === "PRESENTED";

  return (
    <div className="space-y-5">
      {error && <ErrorNote message={error} />}

      <div className="grid gap-5 md:grid-cols-3">
        <Card title="Scenarios">
          {scenarios.length === 0 ? (
            <Empty message="No scenarios yet." />
          ) : (
            <ul className="space-y-1">
              {scenarios.map((s) => (
                <li key={s.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={compareIds.has(s.id)}
                    onChange={() => {
                      const n = new Set(compareIds);
                      n.has(s.id) ? n.delete(s.id) : n.add(s.id);
                      setCompareIds(n);
                    }}
                  />
                  <button
                    onClick={() => loadDelta(s.id)}
                    className={`flex-1 rounded px-2 py-1 text-left text-sm ${
                      active === s.id ? "bg-slate-800 text-white" : "hover:bg-slate-100"
                    }`}
                  >
                    {s.name}{" "}
                    <span className="text-xs opacity-70">
                      {s.status}
                      {s.parent_scenario_id ? " · fork" : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex gap-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New scenario name"
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <Button onClick={create}>Add</Button>
          </div>
          <div className="mt-3 flex gap-2">
            <Button variant="ghost" onClick={runCompare} disabled={compareIds.size === 0}>
              Compare ({compareIds.size})
            </Button>
          </div>
        </Card>

        <Card title="Move builder">
          {!active ? (
            <Empty message="Select or create a scenario." />
          ) : locked ? (
            <div className="space-y-2">
              <p className="text-sm text-amber-600">This scenario is presented (locked).</p>
              <Button variant="ghost" onClick={doFork}>
                Fork to edit
              </Button>
            </div>
          ) : (
            <div className="space-y-2 text-sm">
              <select
                value={moveType}
                onChange={(e) => setMoveType(e.target.value)}
                className="w-full rounded border border-slate-300 px-2 py-1"
              >
                {moveTypes.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              {["employee_key", "manager_key", "grade", "level", "salary", "department"].map((fld) => (
                <input
                  key={fld}
                  value={form[fld] ?? ""}
                  onChange={(e) => set(fld, e.target.value)}
                  placeholder={fld}
                  className="w-full rounded border border-slate-300 px-2 py-1"
                />
              ))}
              <Button onClick={addMove}>Add move</Button>
              <div className="flex gap-2 pt-2">
                <Button variant="ghost" onClick={doPresent}>
                  Present (lock)
                </Button>
                <Button variant="ghost" onClick={doFork}>
                  Fork
                </Button>
              </div>
            </div>
          )}
        </Card>

        <Card title="Live delta vs baseline">
          {!delta ? (
            <Empty message="Select a scenario." />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th className="py-1">Metric</th>
                  <th>Base</th>
                  <th>Scenario</th>
                  <th>Δ</th>
                </tr>
              </thead>
              <tbody>
                {HEADLINE.map(([code, label]) => {
                  const d = delta.delta[code] ?? 0;
                  return (
                    <tr key={code} className="border-b border-slate-100">
                      <td className="py-1">{label}</td>
                      <td>{fmt(delta.baseline[code])}</td>
                      <td>{fmt(delta.scenario[code])}</td>
                      <td className={d > 0 ? "text-red-600" : d < 0 ? "text-green-600" : "text-slate-400"}>
                        {d > 0 ? "+" : ""}
                        {fmt(d)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      {comparison.length > 0 && (
        <Card title="Scenario comparison (Δ vs baseline)">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th className="py-2">Metric</th>
                {comparison.map((c) => (
                  <th key={c.scenario_id}>{c.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {HEADLINE.map(([code, label]) => (
                <tr key={code} className="border-b border-slate-100">
                  <td className="py-1">{label}</td>
                  {comparison.map((c) => {
                    const d = c.delta[code] ?? 0;
                    return (
                      <td
                        key={c.scenario_id}
                        className={d > 0 ? "text-red-600" : d < 0 ? "text-green-600" : "text-slate-400"}
                      >
                        {d > 0 ? "+" : ""}
                        {d.toLocaleString()}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
