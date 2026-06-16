import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { Scenario, TransitionResult } from "../types";
import { Button, Card, Empty, ErrorNote, Spinner } from "../components/ui";

const CLASS_TONE: Record<string, string> = {
  new: "bg-blue-100 text-blue-700",
  augmented: "bg-emerald-100 text-emerald-700",
  transformed: "bg-amber-100 text-amber-700",
  displaced: "bg-red-100 text-red-700",
  unchanged: "bg-slate-100 text-slate-500",
};

export default function TransitionPlanner({
  engagementId,
}: {
  engagementId: string | null;
}) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [active, setActive] = useState<string>("");
  const [result, setResult] = useState<TransitionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (engagementId) api.listScenarios(engagementId).then(setScenarios).catch((e) => setError(String(e)));
  }, [engagementId]);

  async function compute(id: string) {
    setActive(id);
    setLoading(true);
    setError("");
    try {
      setResult(await api.transitionCompute(id));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setLoading(false);
    }
  }

  if (!engagementId) {
    return <Empty message="Open a dataset from the Engagements tab first." />;
  }

  return (
    <div className="space-y-5">
      {error && <ErrorNote message={error} />}
      <Card title="Scenario">
        {scenarios.length === 0 ? (
          <Empty message="No scenarios yet — build one in Scenario Studio." />
        ) : (
          <div className="flex flex-wrap gap-2">
            {scenarios.map((s) => (
              <Button
                key={s.id}
                variant={active === s.id ? "primary" : "ghost"}
                onClick={() => compute(s.id)}
              >
                {s.name}
              </Button>
            ))}
          </div>
        )}
      </Card>

      {loading && <Spinner label="Computing transition…" />}

      {result && (
        <>
          <Card title="Impact summary">
            <div className="flex flex-wrap gap-3">
              {Object.entries(result.summary).map(([cls, n]) => (
                <div key={cls} className={`rounded-md px-3 py-1.5 text-sm ${CLASS_TONE[cls] ?? ""}`}>
                  {cls}: <b>{n}</b>
                </div>
              ))}
            </div>
          </Card>

          <Card
            title="Transition register"
            actions={
              <button
                onClick={() =>
                  api.downloadTransitionRegister(result.scenario_id).catch((e) =>
                    setError(String((e as Error).message ?? e)),
                  )
                }
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Export .xlsx
              </button>
            }
          >
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th className="py-2">Role</th>
                  <th>Impact</th>
                  <th>Skill gaps</th>
                  <th>Suggested pathway</th>
                  <th>Provenance</th>
                </tr>
              </thead>
              <tbody>
                {result.register.map((r) => (
                  <tr key={r.employee_key} className="border-b border-slate-100">
                    <td className="py-1">{r.display_name || r.employee_key}</td>
                    <td>
                      <span className={`rounded-full px-2 py-0.5 text-xs ${CLASS_TONE[r.impact_class] ?? ""}`}>
                        {r.impact_class}
                      </span>
                    </td>
                    <td>{(r.skill_gaps ?? []).join(", ") || "—"}</td>
                    <td>{r.suggested_pathway || "—"}</td>
                    <td className="text-xs text-slate-400">
                      {r.source} · {r.review_state}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs italic text-amber-600">{result.caveats[0]}</p>
          </Card>
        </>
      )}
    </div>
  );
}
