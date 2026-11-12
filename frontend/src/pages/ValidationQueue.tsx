import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { QueueItem } from "../types";
import { Button, Card, Empty, ErrorNote, Spinner } from "../components/ui";
import { GradeBadge, RouteBadge, TacitWarning } from "../components/Compass";

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
}: {
  datasetId: string | null;
  engagementId?: string | null;
}) {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Confidence is an OPTIONAL priority filter ("" = show every item that needs review). It must not
  // default to a hard cap: model-inferred scores ABOVE the cap are still export-blocked and still flag
  // the Workflow Mapper board as "unreviewed", yet a hard cap would hide them so they could never be
  // approved here — leaving the board stuck on "unreviewed" (the reported bug).
  const [maxConfidence, setMaxConfidence] = useState<string>("");
  const [showReviewed, setShowReviewed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const mc = maxConfidence.trim() === "" ? undefined : Number(maxConfidence);
      const q = await api.validationQueue(datasetId ?? undefined, mc, showReviewed);
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
  }, [datasetId, showReviewed]);

  function toggle(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  }

  const allSelected = items.length > 0 && items.every((i) => selected.has(i.id));
  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(items.map((i) => i.id)));
  }

  async function setManual(taskId: string, rating: number) {
    try {
      const r = await api.manualScore(taskId, rating);
      setNote(`Rated → ${r.human_agency_level} (${r.zone}), approved. ${showReviewed ? "" : "Removed from the review list."}`);
      if (showReviewed) {
        await load(); // reviewing rated items — refresh to show the new state
      } else {
        // Optimistic: the whole task is resolved, so drop its rows immediately (instant feedback).
        setItems((prev) => prev.filter((i) => i.task_id !== taskId));
      }
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function changeGrade(i: QueueItem, grade: "confirmed" | "indicated") {
    try {
      await api.setGrade(i.kind, i.id, grade);
      setNote(grade === "confirmed" ? "Raised to Confirmed." : "Set back to Indicated.");
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
            <label className="flex items-center gap-1 text-xs text-slate-500">
              <input
                type="checkbox"
                checked={showReviewed}
                onChange={(e) => setShowReviewed(e.target.checked)}
              />
              Show reviewed
            </label>
            <label className="text-xs text-slate-500">max confidence</label>
            <input
              type="number"
              step="0.05"
              min="0"
              max="1"
              placeholder="all"
              title="Optional: only show items below this confidence (leave blank to show every item that needs review)"
              value={maxConfidence}
              onChange={(e) => setMaxConfidence(e.target.value)}
              className="w-20 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <Button variant="ghost" onClick={load}>
              Filter
            </Button>
          </div>
        }
      >
        <p className="mb-3 text-xs text-slate-500">
          Every item here needs review before it is client-ready and before the Workflow Mapper marks
          it reviewed — approve or rate them to clear them. <b>Max confidence</b> is an optional
          priority filter (blank = show all); set it to focus on the least-confident items first.
          Approving a benchmark feeds a consultant-curated crosswalk back into the system; crosswalk
          rows (including the seed's 0.40 row) appear here too.
        </p>
        <p className="mb-3 text-xs text-slate-500">
          <b>Evidence grade</b> (shared with the other apps): unreviewed AI output is a{" "}
          <b>Hypothesis</b>; approving it here makes it <b>Indicated</b>; only you can raise it to{" "}
          <b>Confirmed</b> — tick <i>Show reviewed</i> to find approved items and raise them.
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
                  <th className="py-2">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleAll}
                      title="Select all shown"
                    />
                  </th>
                  <th>Kind</th>
                  <th>Item</th>
                  <th>Source</th>
                  <th>Confidence</th>
                  <th>State</th>
                  <th>Evidence grade</th>
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
                      <div className="font-medium">
                        {i.task_code && (
                          <span className="mr-1.5 font-mono text-[11px] font-normal text-slate-400">
                            {i.task_code}
                          </span>
                        )}
                        {i.task_text ?? i.label}
                      </div>
                      {(i.compass_ref || i.tacit_warning) && (
                        <div className="mt-0.5 flex items-center gap-1.5">
                          <RouteBadge route={i.compass_route} refId={i.compass_ref} />
                          <TacitWarning message={i.tacit_warning} compact />
                          {i.tacit_warning && (
                            <span className="text-[11px] text-amber-700">
                              high tacit knowledge — proposed at a low human-agency level
                            </span>
                          )}
                        </div>
                      )}
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
                      <GradeBadge grade={i.grade} />
                      {i.kind !== "crosswalk" &&
                        (i.review_state === "approved" || i.review_state === "edited") &&
                        (i.grade === "confirmed" ? (
                          <button
                            onClick={() => changeGrade(i, "indicated")}
                            className="ml-1.5 text-[11px] text-slate-400 underline hover:text-slate-600"
                          >
                            lower
                          </button>
                        ) : (
                          <button
                            onClick={() => changeGrade(i, "confirmed")}
                            title="Your judgement: you would defend this in front of a sceptic"
                            className="ml-1.5 text-[11px] text-emerald-700 underline hover:text-emerald-900"
                          >
                            raise to Confirmed
                          </button>
                        ))}
                    </td>
                    <td>
                      {i.task_id &&
                      (i.kind === "ai_score" ||
                        (i.kind === "benchmark" && i.source === "model-inferred")) ? (
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
    </div>
  );
}
