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
import type { QuickStats, RollupResult } from "../types";
import { Button, Card, Empty, ErrorNote, Spinner, StatCard } from "../components/ui";

const LEVELS = ["L0", "L1", "L2", "L3"];
const AGENCY_BANDS = ["H0", "H1", "H2", "H3", "H4", "H5"];

export default function TaskIntelligence({
  datasetId,
  title,
}: {
  datasetId: string | null;
  title: string;
}) {
  const [quick, setQuick] = useState<QuickStats | null>(null);
  const [rollup, setRollup] = useState<RollupResult | null>(null);
  const [busy, setBusy] = useState<string>("");
  const [error, setError] = useState("");

  async function loadQuick() {
    if (!datasetId) return;
    try {
      setQuick(await api.quick(datasetId));
      setRollup(await api.rollup(datasetId));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  useEffect(() => {
    setQuick(null);
    setRollup(null);
    setError("");
    loadQuick();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  async function runPipeline() {
    if (!datasetId) return;
    setError("");
    try {
      setBusy("Extracting tasks…");
      await api.extract(datasetId);
      setBusy("Benchmarking…");
      await api.benchmark(datasetId);
      setBusy("Scoring AI opportunity…");
      await api.aiOpportunity(datasetId);
      setBusy("Loading rollup…");
      setRollup(await api.rollup(datasetId));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setBusy("");
    }
  }

  if (!datasetId) {
    return <Empty message="Open a dataset from the Engagements tab to run task intelligence." />;
  }

  const overall = rollup?.overall;
  const levelData = LEVELS.map((l) => ({ name: l, value: overall?.levels[l] ?? 0 }));
  const agencyData = AGENCY_BANDS.map((h) => ({ name: h, value: overall?.agency?.[h] ?? 0 }));

  return (
    <div className="space-y-5">
      {error && <ErrorNote message={error} />}

      <Card
        title={`Task Intelligence — ${title}`}
        actions={
          <Button onClick={runPipeline} disabled={!!busy}>
            {busy || "Run pipeline (extract → benchmark → AI opportunity)"}
          </Button>
        }
      >
        <p className="mb-3 text-xs text-slate-500">
          The pipeline calls Claude — it needs an Anthropic API key configured on the server. The
          quick preview below needs no key.
        </p>
        {busy && <Spinner label={busy} />}
        {quick ? (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatCard label="Positions" value={String(quick.positions_total)} />
            <StatCard label="With activities" value={String(quick.positions_with_activities)} />
            <StatCard label="Coverage" value={String(quick.coverage_pct)} unit="%" />
            <StatCard label="Est. batches" value={String(quick.estimated_batches)} />
          </div>
        ) : (
          <Spinner label="Loading preview…" />
        )}
      </Card>

      {overall && overall.tasks > 0 ? (
        <>
          <Card title="AI potential — Human Agency Scale (H0–H5)">
            <p className="mb-2 text-xs text-slate-500">
              The headline measure of AI potential per task. Lower H = more AI-amenable (AI does more
              of the task); higher H = more human agency required. H0 = no software-agent overlay
              (assess as a robotics/GSE lever).
            </p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={agencyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#0f766e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <dl className="mt-3 grid gap-x-4 gap-y-1 text-xs text-slate-500 md:grid-cols-2">
              {AGENCY_BANDS.map((h) => (
                <div key={h} className="flex gap-2">
                  <dt className="font-semibold text-slate-600">{h}</dt>
                  <dd>{rollup!.human_agency_scale?.[h] ?? ""}</dd>
                </div>
              ))}
            </dl>
          </Card>

          <Card title="AI-opportunity levels (L0–L3) — supporting view">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={levelData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#475569" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card title="By department">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th className="py-2">Department</th>
                  <th>Tasks</th>
                  <th>With overlay</th>
                  <th>Robotics levers</th>
                  <th>L2+L3</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(rollup!.by_department).map(([dept, b]) => (
                  <tr key={dept} className="border-b border-slate-100">
                    <td className="py-2 font-medium">{dept}</td>
                    <td>{b.tasks}</td>
                    <td>{b.with_overlay}</td>
                    <td>{b.robotics_levers}</td>
                    <td>{(b.levels["L2"] ?? 0) + (b.levels["L3"] ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            <div className="mb-1 font-semibold">Caveats (must be shown to the client)</div>
            <ul className="list-inside list-disc space-y-1">
              {rollup!.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        </>
      ) : (
        <Empty message="No AI scores yet. Run the pipeline above (requires an API key)." />
      )}
    </div>
  );
}
