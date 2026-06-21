import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { QueueItem } from "../types";
import { Button, Card, Empty, ErrorNote, Spinner } from "../components/ui";

function SourceBadge({ source }: { source?: string | null }) {
  const s = source ?? "—";
  const tone =
    s === "SFw" || s === "WORKBank" || s === "CURATED_BY_CONSULTANT"
      ? "bg-emerald-100 text-emerald-700"
      : s === "model-inferred"
        ? "bg-amber-100 text-amber-700"
        : "bg-slate-100 text-slate-600";
  return <span className={`rounded-full px-2 py-0.5 text-xs ${tone}`}>{s}</span>;
}

export default function ValidationQueue({
  datasetId,
  engagementId,
}: {
  datasetId: string | null;
  engagementId: string | null;
}) {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [maxConfidence, setMaxConfidence] = useState<number>(0.7);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const q = await api.validationQueue(datasetId ?? undefined, maxConfidence);
      setItems(q.items);
      setSelected(new Set());
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  function toggle(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  }

  async function setManual(taskId: string, rating: number) {
    try {
      const r = await api.manualScore(taskId, rating);
      setNote(`Set manual AI opportunity → ${r.human_agency_level} (${r.zone}); approved.`);
      await load();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function bulk(action: "approve" | "reject") {
    const actions = items
      .filter((i) => selected.has(i.id))
      .map((i) => ({ kind: i.kind, id: i.id, action }));
    if (actions.length === 0) return;
    try {
      const r = await api.review(actions);
      setNote(
        `${action === "approve" ? "Approved" : "Rejected"} ${r.updated} item(s)` +
          (r.crosswalks_created ? `, learned ${r.crosswalks_created} crosswalk(s).` : "."),
      );
      await load();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function importPulse(file: File) {
    if (!engagementId || !datasetId) return;
    try {
      const r = await api.pulseImport(engagementId, datasetId, file);
      setNote(`Imported ${r.responses_stored} responses; updated ${r.scores_updated} local scores.`);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  return (
    <div className="space-y-5">
      {error && <ErrorNote message={error} />}
      {note && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {note}
        </div>
      )}

      <Card
        title="Validation queue"
        actions={
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-500">max confidence</label>
            <input
              type="number"
              step="0.05"
              min="0"
              max="1"
              value={maxConfidence}
              onChange={(e) => setMaxConfidence(Number(e.target.value))}
              className="w-20 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <Button variant="ghost" onClick={load}>
              Filter
            </Button>
          </div>
        }
      >
        <p className="mb-3 text-xs text-slate-500">
          Items below the confidence threshold need review. Approving a benchmark feeds a
          consultant-curated crosswalk back into the system. Crosswalk rows (including the seed's
          0.40 row) appear here too.
        </p>

        {loading ? (
          <Spinner label="Loading queue…" />
        ) : items.length === 0 ? (
          <Empty message="Nothing to review at this threshold." />
        ) : (
          <>
            <div className="mb-3 flex gap-2">
              <Button onClick={() => bulk("approve")} disabled={selected.size === 0}>
                Approve selected ({selected.size})
              </Button>
              <Button variant="danger" onClick={() => bulk("reject")} disabled={selected.size === 0}>
                Reject selected
              </Button>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                  <th className="py-2"></th>
                  <th>Kind</th>
                  <th>Item</th>
                  <th>Source</th>
                  <th>Confidence</th>
                  <th>State</th>
                  <th>Manual AI rating</th>
                </tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr key={`${i.kind}-${i.id}`} className="border-b border-slate-100">
                    <td className="py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(i.id)}
                        onChange={() => toggle(i.id)}
                      />
                    </td>
                    <td className="text-slate-500">{i.kind}</td>
                    <td>
                      <div className="font-medium">{i.task_text ?? i.label}</div>
                      {i.task_text && (
                        <div className="text-xs text-slate-400">{i.label}</div>
                      )}
                    </td>
                    <td>
                      <SourceBadge source={i.source} />
                    </td>
                    <td>{i.confidence ?? "—"}</td>
                    <td className="text-slate-500">{i.review_state}</td>
                    <td>
                      {i.kind !== "crosswalk" && i.source === "model-inferred" && i.task_id ? (
                        <select
                          defaultValue=""
                          title="Set the AI opportunity by hand (1=keep human .. 5=automate)"
                          onChange={(e) => e.target.value && setManual(i.task_id!, Number(e.target.value))}
                          className="rounded border border-slate-300 px-1.5 py-1 text-xs"
                        >
                          <option value="">Rate…</option>
                          <option value="1">1 · keep human (H5)</option>
                          <option value="2">2 (H4)</option>
                          <option value="3">3 · partnership (H3)</option>
                          <option value="4">4 (H2)</option>
                          <option value="5">5 · automate (H1)</option>
                        </select>
                      ) : (
                        <span className="text-xs text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Card>

      <Card title="Local desire pulse">
        {!datasetId ? (
          <Empty message="Open a dataset from Engagements first." />
        ) : (
          <div className="space-y-3 text-sm">
            <button
              onClick={() =>
                api.downloadPulseInstrument(datasetId).catch((e) =>
                  setError(String((e as Error).message ?? e)),
                )
              }
              className="inline-block rounded-md border border-slate-300 px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-100"
            >
              Download instrument (.xlsx)
            </button>
            <label className="block">
              <span className="text-slate-600">Import filled responses (CSV or xlsx)</span>
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={(e) => e.target.files?.[0] && importPulse(e.target.files[0])}
                className="mt-1 block w-full text-sm"
              />
            </label>
            <p className="text-xs text-slate-400">
              Local desire is stored separately and never overwrites the WORKBank US score.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
