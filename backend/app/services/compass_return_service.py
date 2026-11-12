"""The file this app writes back: `compass-return` v1.0 (D50).

One agreed shape so findings can travel to Capability Compass and onward. Three kinds of finding:
  * task_disposition — one per task (ref = T-nnn): H-level, AI capability, worker desire, zone.
  * role_impact      — one per matched Compass role (ref = RL-nnn): what changes for the role.
  * capacity         — FTE freed per matched role, AS AN ESTIMATE (always graded Hypothesis).

Rules honoured here: unreviewed model-inferred content stays blocked (A4/M6 — counted, not shown);
no names of individual people (roles are job titles only, whatever the anonymisation setting); no
API key; no raw document or transcript text. The app works with no Compass packet — the key is then
empty and `relates_to` is empty.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    CompassRole, Dataset, Engagement, Position, Process, ProcessStep, Task, TaskAIScore, TaskLink,
)
from . import compass_service
from .shared_grade import GRADE_LABELS, grade_of, weakest
from .task_intelligence_service import HUMAN_AGENCY_SCALE, human_agency_band
from .validation_service import is_client_ready

FORMAT = "compass-return"
FORMAT_VERSION = "1.0"
SOURCE_APP = "ai-org-advisory-workbench"
ZONE_LABELS = {"GREEN_LIGHT": "Green light", "RED_LIGHT": "Red light",
               "ROBOTICS_GSE_LEVER": "Robotics lever", "NO_BENCHMARK_MATCH": "No benchmark"}
AUTOMATION_BANDS = ("H1", "H2")
AUGMENTATION_BANDS = ("H3", "H4")
CAPACITY_METHOD = ("Estimate only: people in the role x the share of the role's reviewed tasks at "
                   "H1-H2. Assumes every task takes equal time; not validated by finance.")


def _num(v: Optional[float]) -> str:
    return "not captured" if v is None else f"{v:.2f}"


def _source_note(score: TaskAIScore) -> str:
    conf = "no confidence recorded" if score.confidence is None else f"confidence {score.confidence:.2f}"
    review = {"approved": "approved in the Validation Queue", "edited": "edited in the Validation Queue",
              "unreviewed": "not yet reviewed"}.get(score.review_state or "", score.review_state or "")
    raised = "; raised to Confirmed by the consultant" if score.grade_override == "confirmed" else ""
    return f"Source: {score.source or 'unknown'}; {conf}; {review}{raised}."


async def build(session: AsyncSession, engagement_id: str, dataset_id: Optional[str]) -> Optional[Dict]:
    """Assemble the return packet + a small `meta` block (meta is NOT part of the exported file)."""
    eng = await session.get(Engagement, engagement_id)
    if eng is None:
        return None
    if dataset_id is None:
        dataset_id = await compass_service._latest_dataset_id(session, engagement_id)
    ds = await session.get(Dataset, dataset_id) if dataset_id else None
    if ds is not None and ds.engagement_id != engagement_id:
        ds, dataset_id = None, None

    findings: List[Dict] = []
    meta = {"tasks_total": 0, "tasks_included": 0, "excluded_unreviewed": 0, "excluded_unscored": 0,
            "roles_matched": 0, "roles_absent": [], "roles_unmatched": []}
    role_idx = await compass_service.role_index(session, engagement_id)
    per_role: Dict[str, Dict] = {}

    if ds is not None:
        await compass_service.ensure_task_codes(session, dataset_id)
        positions = {p.id: p for p in await session.scalars(
            select(Position).where(Position.dataset_id == dataset_id))}
        tasks = list(await session.scalars(
            select(Task).where(Task.position_id.in_(list(positions))).order_by(Task.code, Task.id)
        )) if positions else []
        task_ids = [t.id for t in tasks]
        scores = {s.task_id: s for s in await session.scalars(
            select(TaskAIScore).where(TaskAIScore.task_id.in_(task_ids)))} if task_ids else {}
        # Where each task sits in the workflow (and the Process Map Studio step code, if any).
        placement: Dict[str, List[str]] = {}
        if task_ids:
            rows = await session.execute(
                select(TaskLink.task_id, ProcessStep, Process.name)
                .join(ProcessStep, TaskLink.process_step_id == ProcessStep.id)
                .join(Process, ProcessStep.process_id == Process.id)
                .where(TaskLink.task_id.in_(task_ids), Process.engagement_id == engagement_id))
            for tid, step, proc_name in rows.all():
                label = f"{proc_name} / step {step.seq} {step.name}"
                if step.pms_step_id:
                    label += f" (Process Map Studio {step.pms_step_id})"
                placement.setdefault(tid, []).append(label)

        headcount: Dict[str, int] = {}
        for p in positions.values():
            key = compass_service.normalise_title(p.job_title)
            headcount[key] = headcount.get(key, 0) + 1

        meta["tasks_total"] = len(tasks)
        for t in tasks:
            score = scores.get(t.id)
            if score is None:
                meta["excluded_unscored"] += 1
                continue
            if not is_client_ready(score.source, score.review_state):
                meta["excluded_unreviewed"] += 1  # export-block rule (A4/M6) — unchanged
                continue
            pos = positions.get(t.position_id)
            job_title = (pos.job_title if pos else None) or "Unassigned"
            band = human_agency_band(score.has_level)
            cf = compass_service.role_fields(role_idx, job_title, band)
            grade = grade_of(score)
            desire = score.desire_score_local if score.desire_score_local is not None else score.desire_score_us
            desire_kind = ("local workforce" if score.desire_score_local is not None
                           else "US benchmark preference")
            detail = [
                f"Human-agency level {band}: {HUMAN_AGENCY_SCALE.get(band, '')}",
                f"AI capability {_num(score.capability_score)} (0-1).",
                f"Worker desire {_num(desire)} (0-1"
                + (f", {desire_kind})." if desire is not None else ")."),
                f"Zone: {ZONE_LABELS.get(score.zone or '', score.zone or 'not set')}.",
                f"Role: {job_title}.",
                "Workflow: " + ("; ".join(sorted(placement[t.id])) if t.id in placement
                                else "not mapped to a step") + ".",
            ]
            if cf["tacit_warning"]:
                detail.append("Warning: " + cf["tacit_warning"])
            relates = [x for x in (cf["compass_ref"], cf["compass_cluster_ref"]) if x]
            findings.append({
                "ref": t.code or "", "kind": "task_disposition",
                "title": " ".join((t.task_text or "").split())[:160],
                "detail": " ".join(detail), "grade": grade, "figure": "",
                "relates_to": relates, "source_note": _source_note(score),
            })
            meta["tasks_included"] += 1
            if cf["compass_ref"]:
                bucket = per_role.setdefault(cf["compass_ref"], {
                    "bands": {}, "grades": [], "warnings": 0,
                    "headcount": headcount.get(compass_service.normalise_title(job_title), 0)})
                bucket["bands"][band] = bucket["bands"].get(band, 0) + 1
                bucket["grades"].append(grade)
                bucket["warnings"] += 1 if cf["tacit_warning"] else 0

    role_findings: List[Dict] = []
    capacity_findings: List[Dict] = []
    for r in await session.scalars(
            select(CompassRole).where(CompassRole.engagement_id == engagement_id)
            .order_by(CompassRole.seq, CompassRole.ref)):
        if r.status == "absent" and not r.matched_job_title:
            meta["roles_absent"].append(r.ref)
            continue
        if not r.matched_job_title:
            meta["roles_unmatched"].append(r.ref)
            continue
        meta["roles_matched"] += 1
        b = per_role.get(r.ref)
        if not b:
            continue  # matched, but no reviewed task evidence yet — say nothing rather than guess
        n = sum(b["bands"].values())
        auto = sum(b["bands"].get(x, 0) for x in AUTOMATION_BANDS)
        aug = sum(b["bands"].get(x, 0) for x in AUGMENTATION_BANDS)
        human = b["bands"].get("H5", 0)
        other = n - auto - aug - human
        relates = [x for x in (r.ref, r.cluster_ref) if x]
        detail = (f"{n} reviewed task(s) for this role: {auto} suited to automation (H1-H2), "
                  f"{aug} to human-AI augmentation (H3-H4), {human} staying human-led (H5)"
                  + (f", {other} with no software-agent overlay (H0)" if other else "") + ". "
                  f"Compass route: {r.route or 'not set'}; seat status: {r.status or 'not set'}.")
        if b["warnings"]:
            detail += (f" {b['warnings']} of the automation-suited task(s) carry a tacit-knowledge "
                       "warning — protect the judgement before automating.")
        # A roll-up is an inference from its tasks: never stronger than its weakest input, and never
        # above Indicated (Confirmed is reserved for the consultant's own judgement on an item).
        grade = weakest(b["grades"] + ["indicated"])
        role_findings.append({
            "ref": r.ref, "kind": "role_impact", "title": f"{r.title}: what changes",
            "detail": detail, "grade": grade,
            "figure": f"{round(auto / n * 100)}% of reviewed tasks at H1-H2" if n else "",
            "relates_to": relates,
            "source_note": f"Rolled up from {n} reviewed task disposition(s) in this file.",
        })
        if auto and b["headcount"]:
            fte = round(b["headcount"] * auto / n, 1)
            capacity_findings.append({
                "ref": r.ref, "kind": "capacity", "title": f"{r.title}: capacity freed (estimate)",
                "detail": (f"{b['headcount']} position(s) in the role; {auto} of {n} reviewed tasks "
                           f"at H1-H2. {CAPACITY_METHOD}"),
                "grade": "hypothesis", "figure": f"{fte} FTE (estimate)",
                "relates_to": relates, "source_note": CAPACITY_METHOD,
            })

    packet = {
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source_app": SOURCE_APP, "engagement_key": eng.compass_key or "",
        "findings": role_findings + capacity_findings + findings,
    }
    return {"packet": packet, "meta": meta}


def to_json_bytes(result: Dict) -> bytes:
    return json.dumps(result["packet"], indent=2, ensure_ascii=False).encode("utf-8")


def to_text(result: Dict) -> str:
    """The same content as readable text (Capability Compass takes it as an uploaded document)."""
    p, m = result["packet"], result["meta"]
    key = p["engagement_key"]
    lines = [
        "AI ORG ADVISORY WORKBENCH - FINDINGS RETURN",
        f"Format: {p['format']} v{p['format_version']}   Generated: {p['generated_at']}",
        f"Engagement key: {key or '(none - this engagement is not linked to Capability Compass)'}",
        "",
        "What is in this file",
        f"- {m['tasks_included']} of {m['tasks_total']} task(s) are included.",
        f"- {m['excluded_unreviewed']} task(s) are left out because their AI score has not been "
        "reviewed yet (unreviewed AI content is never exported).",
        f"- {m['excluded_unscored']} task(s) have no AI score yet.",
        "- Grades: Confirmed = you would defend it to a sceptic; Indicated = a reasonable reading "
        "of limited evidence; Hypothesis = not yet tested, never drives a decision on its own.",
        "- No names of individual people appear; roles are job titles.",
    ]
    if m["roles_absent"]:
        lines.append("- No one in the seat (not analysed): " + ", ".join(m["roles_absent"]) + ".")
    if m["roles_unmatched"]:
        lines.append("- Compass roles not matched to the org file (not analysed): "
                     + ", ".join(m["roles_unmatched"]) + ".")
    sections = [("role_impact", "ROLE IMPACT"), ("capacity", "CAPACITY (ESTIMATES)"),
                ("task_disposition", "TASK DISPOSITIONS")]
    for kind, heading in sections:
        items = [f for f in p["findings"] if f["kind"] == kind]
        lines += ["", f"{heading} ({len(items)})", "-" * 60]
        if not items:
            lines.append("None.")
        for f in items:
            ref = f"{key}:{f['ref']}" if key and f["ref"].startswith("RL-") else f["ref"]
            lines.append(f"[{ref}] {f['title']}")
            lines.append(f"  Grade: {GRADE_LABELS.get(f['grade'], f['grade'])}"
                         + (f"   Figure: {f['figure']}" if f["figure"] else ""))
            lines.append(f"  {f['detail']}")
            if f["relates_to"]:
                lines.append("  Relates to: " + ", ".join(
                    f"{key}:{x}" if key else x for x in f["relates_to"]))
            lines.append(f"  Rests on: {f['source_note']}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
