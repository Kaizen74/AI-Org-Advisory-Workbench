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
  const [note, setNote] = useState("");
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
      setBusy("Scoring AI opportunity (curated benchmarks)…");
      await api.aiOpportunity(datasetId);
      setBusy("Benchmarking unmatched tasks (WORKBank HAS rubric)…");
      await api.inferPotential(datasetId);
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

      <Card title="Local desirability (manual scoring for tasks with no benchmark)">
        <p className="mb-3 text-xs text-slate-500">
          When a task has no valid benchmark, score it by hand. Download the template (it lists those
          tasks, pre-keyed by id — no need to match the org CSV), fill <b>desire_rating</b> (1 = keep
          human … 5 = automate), and re-upload. These become consultant-approved (client-ready) H-bands.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            disabled={!datasetId || !!busy}
            onClick={() =>
              api
                .downloadDesirabilityTemplate(datasetId!)
                .catch((e) => setError(String((e as Error).message ?? e)))
            }
          >
            Download template (.csv)
          </Button>
          <label className="text-sm">
            <span className="cursor-pointer rounded-md border border-slate-300 px-3 py-1.5 font-medium text-slate-600 hover:bg-slate-100">
              {busy === "desirability" ? "Applying…" : "Upload filled CSV"}
            </span>
            <input
              type="file"
              accept=".csv,.xlsx"
              className="hidden"
              disabled={!datasetId || !!busy}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file || !datasetId) return;
                setBusy("desirability");
                setError("");
                try {
                  const r = await api.applyDesirability(datasetId, file);
                  setNote(`Applied ${r.applied} manual score(s); ${r.desire_only} desire-only; ${r.skipped} skipped.`);
                  setRollup(await api.rollup(datasetId));
                } catch (err) {
                  setError(String((err as Error).message ?? err));
                } finally {
                  setBusy("");
                  e.target.value = "";
                }
              }}
            />
          </label>
        </div>
        {note && <p className="mt-2 text-xs text-emerald-700">{note}</p>}
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

          <Card title="Benchmark coverage (how AI potential was derived)">
            <p className="mb-3 text-xs text-slate-500">
              Curated/WORKBank benchmarks are authoritative; AI-inferred tasks use the WORKBank Human
              Agency rubric and stay unreviewed (export-blocked) until you approve them in the
              Validation Queue. A high AI-inferred share means a relevant benchmark overlay would help.
            </p>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <StatCard label="Curated / WORKBank" value={String(rollup!.source_mix?.overlay ?? 0)} />
              <StatCard label="AI-inferred (rubric)" value={String(rollup!.source_mix?.ai_inferred ?? 0)} />
              <StatCard label="Robotics / GSE levers" value={String(rollup!.source_mix?.robotics ?? 0)} />
              <StatCard label="Unclassified" value={String(rollup!.source_mix?.unclassified ?? 0)} />
            </div>
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
