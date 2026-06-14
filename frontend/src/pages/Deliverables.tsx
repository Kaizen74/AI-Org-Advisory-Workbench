import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { DeliverableInfo, Scenario } from "../types";
import { Button, Card, Empty, ErrorNote, Spinner } from "../components/ui";

const DATASET_TYPES: { type: string; label: string }[] = [
  { type: "PPTX_DIAGNOSTIC", label: "Diagnostic deck (.pptx)" },
  { type: "PPTX_AI_ROADMAP", label: "AI roadmap (.pptx)" },
  { type: "DOCX_TOM", label: "TOM narrative (.docx)" },
  { type: "XLSX_METRICS", label: "Metrics pack (.xlsx)" },
];

export default function Deliverables({
  datasetId,
  engagementId,
}: {
  datasetId: string | null;
  engagementId: string | null;
}) {
  const [items, setItems] = useState<DeliverableInfo[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState<string>("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    if (!engagementId) return;
    try {
      setItems((await api.listDeliverables(engagementId)).deliverables);
      setScenarios(await api.listScenarios(engagementId));
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engagementId]);

  async function gen(type: string, opts: { datasetId?: string; scenarioId?: string }) {
    if (!engagementId) return;
    setBusy(type);
    setError("");
    try {
      await api.generateDeliverable(engagementId, type, opts);
      await refresh();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setBusy("");
    }
  }

  if (!engagementId) {
    return <Empty message="Open a dataset from the Engagements tab to generate deliverables." />;
  }

  return (
    <div className="space-y-5">
      {error && <ErrorNote message={error} />}

      <Card title="Generate (modern-minimalist template)">
        <p className="mb-3 text-xs text-slate-500">
          Deliverables are built from saved, reviewed data. Unreviewed AI-guessed content is
          automatically excluded and disclosed; every file carries a provenance page.
        </p>
        <div className="flex flex-wrap gap-2">
          {DATASET_TYPES.map((d) => (
            <Button
              key={d.type}
              onClick={() => gen(d.type, { datasetId: datasetId ?? undefined })}
              disabled={!datasetId || !!busy}
            >
              {busy === d.type ? "Generating…" : d.label}
            </Button>
          ))}
          <Button onClick={() => gen("PPTX_SCENARIOS", {})} disabled={!!busy}>
            {busy === "PPTX_SCENARIOS" ? "Generating…" : "Scenario comparison (.pptx)"}
          </Button>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <select
            value={scenarioId}
            onChange={(e) => setScenarioId(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="">Select scenario…</option>
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <Button
            variant="ghost"
            onClick={() => gen("XLSX_TRANSITION", { scenarioId })}
            disabled={!scenarioId || !!busy}
          >
            Transition register (.xlsx)
          </Button>
        </div>
      </Card>

      {busy && <Spinner label="Generating deliverable…" />}

      <Card title="Generated deliverables">
        {items.length === 0 ? (
          <Empty message="Nothing generated yet." />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th className="py-2">Type</th>
                <th>Template</th>
                <th>Client-ready</th>
                <th>Blocked</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id} className="border-b border-slate-100">
                  <td className="py-1 font-medium">{d.type}</td>
                  <td>{d.template}</td>
                  <td>
                    {d.provenance_summary
                      ? `${d.provenance_summary.client_ready}/${d.provenance_summary.total}`
                      : "—"}
                  </td>
                  <td className="text-amber-600">
                    {d.provenance_summary?.excluded_unreviewed_model_inferred ?? 0}
                  </td>
                  <td>
                    <a
                      href={api.deliverableDownloadUrl(d.id)}
                      className="rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                    >
                      Download
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
