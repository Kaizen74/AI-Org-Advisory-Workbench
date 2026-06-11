import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../services/api";
import type { ActivatorScreen, DiagnosticsSummary } from "../types";
import { Button, Card, Empty, ErrorNote, Spinner, StatCard } from "../components/ui";

const HEADLINE: { code: string; label: string; unit?: string }[] = [
  { code: "total_employees", label: "Employees" },
  { code: "total_managers", label: "Managers" },
  { code: "manager_ratio_pct", label: "Manager ratio", unit: "%" },
  { code: "average_span", label: "Avg span" },
  { code: "organizational_layers", label: "Layers" },
  { code: "total_cost", label: "Total cost", unit: "$" },
];

function fmt(value: number | undefined, unit?: string): string {
  if (value === undefined) return "—";
  if (unit === "$") return value.toLocaleString();
  return String(value);
}

export default function Diagnostics({
  datasetId,
  title,
}: {
  datasetId: string | null;
  title: string;
}) {
  const [summary, setSummary] = useState<DiagnosticsSummary | null>(null);
  const [screen, setScreen] = useState<ActivatorScreen | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    if (!datasetId) return;
    setLoading(true);
    setError("");
    try {
      const s = await api.summary(datasetId);
      setSummary(s);
      if (s.computed) setScreen(await api.activatorScreen(datasetId));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setLoading(false);
    }
  }

  async function runCompute() {
    if (!datasetId) return;
    setLoading(true);
    setError("");
    try {
      const s = await api.compute(datasetId);
      setSummary(s);
      setScreen(await api.activatorScreen(datasetId));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setSummary(null);
    setScreen(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  if (!datasetId) {
    return <Empty message="Open a dataset from the Engagements tab to run diagnostics." />;
  }

  const metrics = summary?.metrics ?? {};
  const chartData = HEADLINE.filter((h) => h.unit !== "$").map((h) => ({
    name: h.label,
    value: metrics[h.code] ?? 0,
  }));

  return (
    <div className="space-y-5">
      {error && <ErrorNote message={error} />}

      <Card
        title={`Diagnostics — ${title}`}
        actions={
          <Button onClick={runCompute} disabled={loading}>
            {loading ? "Computing…" : summary?.computed ? "Recompute" : "Compute metrics"}
          </Button>
        }
      >
        {loading && <Spinner label="Computing metrics…" />}
        {!loading && !summary?.computed && (
          <Empty message="Metrics not computed yet. Click “Compute metrics”." />
        )}
        {!loading && summary?.computed && (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {HEADLINE.map((h) => (
              <StatCard
                key={h.code}
                label={h.label}
                value={fmt(metrics[h.code], h.unit)}
                unit={h.unit}
              />
            ))}
          </div>
        )}
      </Card>

      {summary?.computed && (
        <Card title="Structure at a glance">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#475569" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {screen && (
        <Card title={`Activator pre-screen — ${screen.triggered_count}/5 flagged`}>
          <div className="space-y-2">
            {screen.flags.map((f) => (
              <div
                key={f.activator}
                className={`rounded-md border p-3 text-sm ${
                  f.triggered ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    A{f.activator} · {f.name}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      f.triggered ? "bg-amber-200 text-amber-800" : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {f.triggered ? "Flagged" : "OK"}
                  </span>
                </div>
                <div className="mt-1 text-slate-600">{f.rationale}</div>
                <div className="mt-1 text-xs text-slate-400">
                  {f.signal_metric} = {f.value} (threshold {f.threshold})
                </div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs italic text-slate-400">{screen.caveat}</p>
        </Card>
      )}
    </div>
  );
}
