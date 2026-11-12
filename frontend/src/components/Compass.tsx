// Capability Compass hand-off UI: shared badges, the import flow (preview → confirm), and the
// Compass roles panel. Everything here is optional — with no packet the panels simply don't show.
import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { CompassPreview, CompassRole, CompassState, EvidenceGrade } from "../types";
import { Button, Card, ErrorNote } from "./ui";

const GRADE_META: Record<EvidenceGrade, { label: string; tone: string; help: string }> = {
  confirmed: {
    label: "Confirmed",
    tone: "bg-emerald-100 text-emerald-800",
    help: "You would defend this in front of a sceptic.",
  },
  indicated: {
    label: "Indicated",
    tone: "bg-sky-100 text-sky-800",
    help: "A reasonable reading of limited evidence (reviewed in the Validation Queue).",
  },
  hypothesis: {
    label: "Hypothesis",
    tone: "bg-amber-100 text-amber-800",
    help: "Not yet tested (unreviewed AI output or low confidence). Never drives a decision on its own.",
  },
};

export function GradeBadge({ grade, compact }: { grade?: EvidenceGrade | null; compact?: boolean }) {
  if (!grade) return null;
  const m = GRADE_META[grade];
  return (
    <span
      title={`Evidence grade: ${m.label} — ${m.help}`}
      className={`inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-semibold ${m.tone}`}
    >
      {compact ? m.label.charAt(0) : m.label}
    </span>
  );
}

const ROUTE_TONE: Record<string, string> = {
  critical: "bg-rose-100 text-rose-800",
  dual: "bg-violet-100 text-violet-800",
  specialist: "bg-indigo-100 text-indigo-800",
  standard: "bg-slate-100 text-slate-600",
};

export function RouteBadge({ route, refId }: { route?: string | null; refId?: string | null }) {
  if (!route && !refId) return null;
  const highTacit = route === "specialist" || route === "dual";
  return (
    <span
      title={`Capability Compass role${refId ? ` ${refId}` : ""} · route: ${route ?? "not set"}${
        highTacit ? " (high tacit knowledge — take care before automating)" : ""
      }`}
      className={`inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-semibold ${
        ROUTE_TONE[route ?? ""] ?? "bg-slate-100 text-slate-600"
      }`}
    >
      {refId ? `${refId} · ` : ""}
      {route ?? "role"}
    </span>
  );
}

export function TacitWarning({ message, compact }: { message?: string | null; compact?: boolean }) {
  if (!message) return null;
  if (compact) {
    return (
      <span title={message} className="cursor-help text-[11px] font-bold text-amber-600">
        ⚠
      </span>
    );
  }
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs leading-snug text-amber-900">
      <b>⚠ Tacit-knowledge warning.</b> {message}
    </div>
  );
}

const STATE_LABEL: Record<string, string> = {
  matched: "Matched",
  manual: "Set by you",
  near: "Near-match — please choose",
  missed: "No match",
  absent: "No one in the seat",
};

function RoleMatchSelect({
  role,
  jobTitles,
  value,
  onChange,
}: {
  role: CompassRole;
  jobTitles: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  const suggested = role.candidates ?? [];
  const rest = jobTitles.filter((t) => !suggested.includes(t));
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full max-w-[260px] rounded border border-slate-300 px-1.5 py-1 text-xs"
    >
      <option value="">— not matched —</option>
      {suggested.length > 0 && (
        <optgroup label="Similar job titles">
          {suggested.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </optgroup>
      )}
      <optgroup label="All job titles in the org file">
        {rest.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </optgroup>
    </select>
  );
}

/** Engagement Hub: "Import from Capability Compass" — choose file → preview → confirm. */
export function CompassImport({
  selectedEngagementId,
  selectedEngagementName,
  onImported,
}: {
  selectedEngagementId?: string | null;
  selectedEngagementName?: string;
  onImported: (r: { engagement_id: string; client_id: string; name: string }) => void;
}) {
  const [packet, setPacket] = useState<unknown>(null);
  const [fileName, setFileName] = useState("");
  const [intoSelected, setIntoSelected] = useState(false);
  const [preview, setPreview] = useState<CompassPreview | null>(null);
  const [matches, setMatches] = useState<Record<string, string>>({});
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  function reset() {
    setPacket(null);
    setFileName("");
    setPreview(null);
    setMatches({});
    setAnswers({});
    setError("");
  }

  async function runPreview(p: unknown, into: boolean) {
    setBusy(true);
    setError("");
    try {
      const pv = await api.compassPreview(p, into ? selectedEngagementId : null);
      setPreview(pv);
      const m: Record<string, string> = {};
      (pv.roles ?? []).forEach((r) => (m[r.ref] = r.matched_job_title ?? ""));
      setMatches(m);
      setAnswers({});
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function onFile(file: File) {
    reset();
    setDone("");
    setFileName(file.name);
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      setError(
        "This file could not be read. Choose the hand-off file exported from Capability Compass (its name ends in _compass_handoff.json).",
      );
      return;
    }
    setPacket(parsed);
    await runPreview(parsed, intoSelected && !!selectedEngagementId);
  }

  async function confirm() {
    if (!packet || !preview?.ok) return;
    setBusy(true);
    setError("");
    try {
      const chosen: Record<string, string | null> = {};
      Object.entries(matches).forEach(([ref, title]) => (chosen[ref] = title || null));
      const r = await api.compassApply(packet, {
        engagementId: preview.engagement?.id ?? null,
        matches: chosen,
        overwriteName: !!answers.overwrite_name,
        confirmKeyChange: !!answers.confirm_key_change,
      });
      setDone(`Imported ${r.roles} role(s) into "${r.name}" (key ${r.key}).`);
      reset();
      onImported(r);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  }

  const needsKeyConfirm =
    (preview?.asks ?? []).some((a) => a.field === "confirm_key_change") && !answers.confirm_key_change;

  return (
    <Card title="Import from Capability Compass (optional)">
      <p className="mb-3 text-xs text-slate-500">
        Reads the hand-off file from Capability Compass (<code>&lt;key&gt;_compass_handoff.json</code>).
        You see a preview first; nothing is created or changed until you confirm. The app works
        without this — skip it to run standalone.
      </p>
      {error && <ErrorNote message={error} />}
      {done && (
        <div className="mb-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {done}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm">
          <span className="cursor-pointer rounded-md border border-slate-300 px-3 py-1.5 font-medium text-slate-600 hover:bg-slate-100">
            {busy ? "Reading…" : "Choose hand-off file"}
          </span>
          <input
            type="file"
            accept=".json,application/json"
            className="hidden"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (f) onFile(f);
            }}
          />
        </label>
        {fileName && <span className="text-xs text-slate-500">{fileName}</span>}
        {selectedEngagementId && (
          <label className="flex items-center gap-1.5 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={intoSelected}
              onChange={(e) => {
                setIntoSelected(e.target.checked);
                if (packet) runPreview(packet, e.target.checked);
              }}
            />
            Import into the selected engagement ("{selectedEngagementName}") instead of the one named in
            the file
          </label>
        )}
      </div>

      {preview && !preview.ok && (
        <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <div className="font-semibold">This file cannot be imported.</div>
          <ul className="mt-1 list-inside list-disc space-y-1">
            {preview.errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {preview?.ok && (
        <div className="mt-4 space-y-3">
          {preview.warnings.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <div className="font-semibold">Please note</div>
              <ul className="mt-1 list-inside list-disc space-y-1">
                {preview.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
            <div className="font-semibold">If you confirm, this will happen</div>
            <ul className="mt-1 list-inside list-disc space-y-1">
              {(preview.changes ?? []).map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
          {(preview.asks ?? []).map((a) => (
            <label key={a.field} className="flex items-start gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={!!answers[a.field]}
                onChange={(e) => setAnswers({ ...answers, [a.field]: e.target.checked })}
              />
              {a.question}
            </label>
          ))}

          <div>
            <div className="mb-1 text-xs font-semibold text-slate-700">
              Roles — check each match to the org file by job title
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-left uppercase text-slate-500">
                    <th className="py-1.5">Compass role</th>
                    <th>Route</th>
                    <th>Cluster</th>
                    <th>Result</th>
                    <th>Job title in the org file</th>
                  </tr>
                </thead>
                <tbody>
                  {(preview.roles ?? []).map((r) => (
                    <tr key={r.ref} className="border-b border-slate-100 align-top">
                      <td className="py-1.5">
                        <span className="font-mono text-[11px] text-slate-500">{r.ref}</span>{" "}
                        <span className="font-medium text-slate-800">{r.title}</span>
                        {r.note && <div className="text-[11px] text-slate-400">{r.note}</div>}
                      </td>
                      <td>
                        <RouteBadge route={r.route} />
                      </td>
                      <td className="text-slate-500" title={r.cluster_name}>
                        {r.cluster_ref}
                      </td>
                      <td
                        className={
                          r.match_state === "near"
                            ? "font-semibold text-amber-700"
                            : r.match_state === "missed"
                              ? "text-red-600"
                              : "text-slate-600"
                        }
                      >
                        {STATE_LABEL[r.match_state] ?? r.match_state}
                      </td>
                      <td>
                        <RoleMatchSelect
                          role={r}
                          jobTitles={preview.job_titles ?? []}
                          value={matches[r.ref] ?? ""}
                          onChange={(v) => setMatches({ ...matches, [r.ref]: v })}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              Near-matches are never applied on their own — pick a job title or leave the role
              unmatched. Roles with no one in the seat are listed but not analysed.
            </p>
          </div>

          <div className="flex gap-2">
            <Button onClick={confirm} disabled={busy || needsKeyConfirm}>
              {busy ? "Importing…" : "Confirm import"}
            </Button>
            <Button variant="ghost" onClick={reset} disabled={busy}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

/** The engagement's Compass roles, in work order, with route badges. Lets the consultant correct a
 *  match. Renders nothing when the engagement has no Compass packet (standalone use). */
export function CompassRolesPanel({
  engagementId,
  datasetId,
  title = "Capability Compass roles — start with these",
  refreshKey,
}: {
  engagementId: string | null | undefined;
  datasetId?: string | null;
  title?: string;
  refreshKey?: unknown;
}) {
  const [state, setState] = useState<CompassState | null>(null);
  const [error, setError] = useState("");

  async function load() {
    if (!engagementId) {
      setState(null);
      return;
    }
    try {
      setState(await api.compassState(engagementId, datasetId));
    } catch {
      setState(null); // never block the page on the optional Compass panel
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engagementId, datasetId, refreshKey]);

  if (!state || !state.imported) return null;

  async function setMatch(ref: string, title: string) {
    if (!engagementId) return;
    setError("");
    try {
      await api.setCompassRoleMatch(engagementId, ref, title || null);
      await load();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  const present = state.roles.filter((r) => r.status !== "absent" || r.matched_job_title);
  const absent = state.roles.filter((r) => r.status === "absent" && !r.matched_job_title);

  return (
    <Card title={title}>
      {error && <ErrorNote message={error} />}
      <p className="mb-2 text-xs text-slate-500">
        Engagement key <b className="font-mono">{state.key}</b>. Roles are listed in the order
        Capability Compass set; their tasks are offered first in Task Intelligence and the Workflow
        Mapper. IDs are kept exactly as received.
        {state.readiness && state.readiness.ready === false && (
          <span className="ml-1 font-semibold text-amber-700">
            Compass marked this hand-off as not ready.
          </span>
        )}
      </p>
      {state.job_titles.length === 0 && (
        <p className="mb-2 text-xs text-amber-700">
          No org file is loaded yet — upload the org CSV to match these roles to positions.
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-200 text-left uppercase text-slate-500">
              <th className="py-1.5">Role</th>
              <th>Route</th>
              <th>Cluster</th>
              <th>Seat</th>
              <th>Matched job title</th>
              <th className="text-right">Positions</th>
              <th className="text-right">Tasks</th>
            </tr>
          </thead>
          <tbody>
            {present.map((r) => (
              <tr key={r.ref} className="border-b border-slate-100">
                <td className="py-1.5">
                  <span className="font-mono text-[11px] text-slate-500">{r.ref}</span>{" "}
                  <span className="font-medium text-slate-800">{r.title}</span>
                </td>
                <td>
                  <RouteBadge route={r.route} />
                </td>
                <td className="text-slate-500">{r.cluster_ref}</td>
                <td className="text-slate-500">{r.seat}</td>
                <td>
                  <RoleMatchSelect
                    role={r}
                    jobTitles={state.job_titles}
                    value={r.matched_job_title ?? ""}
                    onChange={(v) => setMatch(r.ref, v)}
                  />
                  {!r.matched_job_title && r.suggestion && (
                    <button
                      onClick={() => setMatch(r.ref, r.suggestion!)}
                      className="mt-0.5 block text-[11px] text-teal-700 underline hover:text-teal-900"
                    >
                      Same title found in the org file — use "{r.suggestion}"
                    </button>
                  )}
                  {!r.matched_job_title && !r.suggestion && r.candidates.length > 0 && (
                    <div className="text-[11px] text-amber-700">Similar titles found — please choose.</div>
                  )}
                </td>
                <td className="text-right tabular-nums">{r.positions}</td>
                <td className="text-right tabular-nums">{r.tasks ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {absent.length > 0 && (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <b>No one in the seat (not analysed):</b>{" "}
          {absent.map((r) => `${r.ref} ${r.title}`).join(" · ")}
        </div>
      )}
    </Card>
  );
}
