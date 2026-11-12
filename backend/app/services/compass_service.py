"""Capability Compass hand-off (D50) — read `compass-handoff` v1.x, keep its IDs, order the work.

Import rules (the same in every app):
  1. Reject a file whose `format` is not `compass-handoff`, in plain language. Accept any 1.x and
     ignore unknown fields.
  2. Preview first; nothing is written until the consultant confirms (`apply`).
  3. Never overwrite something the consultant typed without asking.
  4. Keep the engagement key and every Compass ref on the records created from it.
  5. `readiness.ready == false` is a warning, not a block.
  6. No API key and no document text is stored or exported (only a whitelisted packet subset).

Capability Compass is OPTIONAL: every helper here degrades to "no Compass data" so the app works on
its own with no packet.
"""
from __future__ import annotations

import difflib
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Client, CompassRole, Dataset, Engagement, Position, Task

FORMAT = "compass-handoff"
ROUTES = ("critical", "dual", "specialist", "standard")
HIGH_TACIT_ROUTES = ("specialist", "dual")  # high tacit knowledge -> warn on low human agency
LOW_AGENCY_BANDS = ("H1", "H2")  # AI does most or all of the task
TACIT_WARNING = ("High tacit knowledge role (Compass route: {route}) — this task is proposed at a "
                 "low human-agency level ({band}). Check what judgement would be lost before automating.")
NEAR_MATCH_RATIO = 0.6


# ── Shared IDs: T-nnn task codes (never reused) ──────────────────────────────
async def ensure_task_codes(session: AsyncSession, dataset_id: str,
                            ordered: Optional[List[Task]] = None) -> int:
    """Give every task in a dataset a displayed `T-nnn` code if it has none. The counter lives on the
    engagement and only ever increases, so a code is never reused — even after a re-extract or a
    deleted dataset. Idempotent; returns how many codes were minted."""
    ds = await session.get(Dataset, dataset_id)
    if ds is None:
        return 0
    if ordered is not None:  # the caller knows the work order (e.g. Compass priority roles first)
        missing = [t for t in ordered if not t.code]
    else:
        missing = list(await session.scalars(
            select(Task).join(Position, Task.position_id == Position.id)
            .where(Position.dataset_id == dataset_id, Task.code.is_(None))
            .order_by(Task.created_at, Task.id)
        ))
    if not missing:
        return 0
    eng = await session.get(Engagement, ds.engagement_id)
    if eng is None:
        return 0
    seq = eng.task_seq or 0
    for t in missing:
        seq += 1
        t.code = f"T-{seq:03d}"
    eng.task_seq = seq
    await session.flush()
    return len(missing)


# ── Packet validation ────────────────────────────────────────────────────────
def _s(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def packet_roles(packet: Dict) -> Tuple[List[Dict], bool]:
    """The roles written for this app (`for_apps.workbench.roles`), enriched with the full detail
    from the top-level `roles[]`. Falls back to the top-level list when the block is missing.
    Returns (roles, used_fallback)."""
    top = [r for r in (packet.get("roles") or []) if isinstance(r, dict)]
    detail = {_s(r.get("ref")): r for r in top}
    block = ((packet.get("for_apps") or {}).get("workbench") or {}) if isinstance(
        packet.get("for_apps"), dict) else {}
    listed = block.get("roles") if isinstance(block, dict) else None
    fallback = not isinstance(listed, list)
    out = []
    for r in (top if fallback else listed):
        if not isinstance(r, dict):
            continue
        d = detail.get(_s(r.get("ref")), {})
        out.append({
            "ref": _s(r.get("ref")), "title": _s(r.get("title")) or _s(d.get("title")),
            "cluster_ref": _s(r.get("cluster_ref")) or _s(d.get("cluster_ref")),
            "route": _s(r.get("route")) or _s(d.get("route")),
            "status": _s(r.get("status")) or _s(d.get("status")),
            "criticality_index": d.get("criticality_index"),
            "tacit_intensity": d.get("tacit_intensity"),
            "note": _s(d.get("note")),
        })
    return out, fallback


def validate_packet(packet) -> Tuple[List[str], List[str]]:
    """Plain-language (errors, warnings). Errors block the import; warnings are shown only."""
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(packet, dict):
        return (["This is not a Capability Compass hand-off file. Export the hand-off from "
                 "Capability Compass (a file named <key>_compass_handoff.json) and try again."], [])
    fmt = packet.get("format")
    if fmt != FORMAT:
        return ([f"This is not a Capability Compass hand-off file (its format is "
                 f"\"{fmt if fmt is not None else 'missing'}\", expected \"{FORMAT}\"). Nothing was "
                 "imported."], [])
    version = str(packet.get("format_version") or "")
    if not version.startswith("1."):
        errors.append(f"This hand-off file is version \"{version or 'missing'}\". This app reads "
                      "version 1.x only. Nothing was imported.")
    engagement = packet.get("engagement") if isinstance(packet.get("engagement"), dict) else {}
    if not _s(engagement.get("key")):
        errors.append("The file has no engagement key (engagement.key). Every record must carry the "
                      "key, so the file cannot be imported. Re-export it from Capability Compass.")

    cluster_refs = {_s(c.get("ref")) for c in (packet.get("clusters") or []) if isinstance(c, dict)}
    roles, fallback = packet_roles(packet)
    if fallback:
        warnings.append("The file has no block written for this app (for_apps.workbench); the full "
                        "role list was used instead.")
    seen = set()
    for r in roles:
        if not r["ref"] or not r["title"]:
            errors.append("A role in the file has no ID or no title, so it cannot be imported.")
            continue
        if r["ref"] in seen:
            errors.append(f"Role ID {r['ref']} appears more than once in the file.")
        seen.add(r["ref"])
        if r["cluster_ref"] and r["cluster_ref"] not in cluster_refs:
            errors.append(f"Role {r['ref']} ({r['title']}) points to capability cluster "
                          f"{r['cluster_ref']}, which is not in this file. Re-export the hand-off "
                          "from Capability Compass.")
        if r["route"] and r["route"] not in ROUTES:
            warnings.append(f"Role {r['ref']} has an unknown route \"{r['route']}\"; it is kept as "
                            "received but no tacit-knowledge warning will apply.")
    if not roles:
        warnings.append("The file lists no roles for this app.")

    readiness = packet.get("readiness") if isinstance(packet.get("readiness"), dict) else {}
    if readiness and readiness.get("ready") is False:
        open_items = [str(o) for o in (readiness.get("open") or [])][:5]
        warnings.append("Capability Compass marked this hand-off as NOT ready"
                        + (f" ({_s(readiness.get('verdict'))})" if _s(readiness.get("verdict")) else "")
                        + (": " + "; ".join(open_items) if open_items else "")
                        + ". You can still import it.")
    return errors, warnings


def engagement_name_of(packet: Dict) -> str:
    block = ((packet.get("for_apps") or {}).get("workbench") or {})
    name = _s(block.get("engagement_name")) if isinstance(block, dict) else ""
    if name:
        return name
    eng = packet.get("engagement") or {}
    return f"{_s(eng.get('key'))} {_s(eng.get('name'))}".strip()


def _scalars(d, keys) -> Dict:
    d = d if isinstance(d, dict) else {}
    return {k: d.get(k) for k in keys if isinstance(d.get(k), (str, int, float, bool))}


def stored_subset(packet: Dict) -> Dict:
    """The whitelisted part of the packet kept on the engagement. Only known, short fields — never an
    API key or document text (import rule 6). The two charter lists are stored for the later
    operating-system module (PRD section 3E); nothing reads them yet."""
    charter = packet.get("charter") if isinstance(packet.get("charter"), dict) else {}
    return {
        "format_version": str(packet.get("format_version") or ""),
        "generated_at": _s(packet.get("generated_at")),
        "source_app": _s(packet.get("source_app")),
        "imported_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "engagement": _scalars(packet.get("engagement"), [
            "key", "name", "organisation", "industry", "unit", "scope", "currency", "value_unit",
            "baseline_version", "working_version"]),
        "readiness": {
            "ready": bool((packet.get("readiness") or {}).get("ready", True)),
            "verdict": _s((packet.get("readiness") or {}).get("verdict")),
            "open": [str(o)[:300] for o in ((packet.get("readiness") or {}).get("open") or [])][:20],
        },
        "reference_model": [_scalars(c, ["ref", "name", "observable_test"])
                            for c in (charter.get("reference_model") or []) if isinstance(c, dict)],
        "leapfrog_gate": [_scalars(c, ["ref", "test"])
                          for c in (charter.get("leapfrog_gate") or []) if isinstance(c, dict)],
        "clusters": [_scalars(c, ["ref", "name"])
                     for c in (packet.get("clusters") or []) if isinstance(c, dict)],
        "pilots": [_scalars(c, ["ref", "cluster_ref", "name", "process_kpi"])
                   for c in (packet.get("pilots") or []) if isinstance(c, dict)],
    }


# ── Job-title matching (never a silent guess) ────────────────────────────────
def normalise_title(title: Optional[str]) -> str:
    t = (title or "").lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def match_title(title: str, job_titles: List[str]) -> Tuple[Optional[str], List[str]]:
    """(exact match or None, near-match candidates best-first). Exact = same words after tidying
    case/punctuation. Near-matches are only ever SUGGESTED — the consultant decides."""
    target = normalise_title(title)
    by_norm: Dict[str, str] = {}
    for jt in job_titles:
        by_norm.setdefault(normalise_title(jt), jt)
    if target and target in by_norm:
        return by_norm[target], []
    t_tokens = set(target.split())
    scored = []
    for norm, original in by_norm.items():
        if not norm:
            continue
        ratio = difflib.SequenceMatcher(None, target, norm).ratio()
        tokens = set(norm.split())
        small, big = (t_tokens, tokens) if len(t_tokens) <= len(tokens) else (tokens, t_tokens)
        contained = len(small) >= 2 and small <= big
        if ratio >= NEAR_MATCH_RATIO or contained:
            scored.append((max(ratio, 0.75 if contained else 0.0), original))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return None, [o for _, o in scored[:3]]


async def _latest_dataset_id(session: AsyncSession, engagement_id: str) -> Optional[str]:
    return await session.scalar(
        select(Dataset.id).where(Dataset.engagement_id == engagement_id)
        .order_by(Dataset.version.desc()).limit(1)
    )


async def _title_counts(session: AsyncSession, dataset_id: Optional[str]) -> Dict[str, int]:
    """job title -> number of positions, for one dataset ({} when there is no dataset)."""
    if not dataset_id:
        return {}
    rows = await session.execute(
        select(Position.job_title, func.count(Position.id))
        .where(Position.dataset_id == dataset_id).group_by(Position.job_title)
    )
    return {jt: n for jt, n in rows.all() if jt}


async def _stored_roles(session: AsyncSession, engagement_id: str) -> List[CompassRole]:
    return list(await session.scalars(
        select(CompassRole).where(CompassRole.engagement_id == engagement_id)
        .order_by(CompassRole.seq, CompassRole.ref)
    ))


# ── Preview / apply ──────────────────────────────────────────────────────────
async def _resolve_target(session: AsyncSession, packet: Dict,
                          engagement_id: Optional[str]) -> Tuple[Optional[Engagement], Optional[str]]:
    """The engagement an import would update (None = a new one is created). (engagement, error)."""
    if engagement_id:
        eng = await session.get(Engagement, engagement_id)
        if eng is None:
            return None, "The engagement you chose no longer exists."
        return eng, None
    key = _s((packet.get("engagement") or {}).get("key"))
    eng = await session.scalar(
        select(Engagement).where(Engagement.compass_key == key)
        .order_by(Engagement.created_at.desc()).limit(1)
    )
    return eng, None


async def preview(session: AsyncSession, packet, engagement_id: Optional[str] = None,
                  dataset_id: Optional[str] = None) -> Dict:
    """What an import WOULD create or change. Writes nothing."""
    errors, warnings = validate_packet(packet)
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}
    target, err = await _resolve_target(session, packet, engagement_id)
    if err:
        return {"ok": False, "errors": [err], "warnings": warnings}

    eng_block = packet.get("engagement") or {}
    key = _s(eng_block.get("key"))
    name = engagement_name_of(packet)
    client_name = _s(eng_block.get("organisation")) or _s(eng_block.get("name")) or key
    changes: List[str] = []
    asks: List[Dict] = []
    if target is None:
        action = "create"
        existing_client = await session.scalar(
            select(Client).where(func.lower(Client.name) == client_name.lower()))
        changes.append(f"Create engagement \"{name}\" with key {key} under "
                       + (f"existing client \"{existing_client.name}\"." if existing_client
                          else f"a new client \"{client_name}\"."))
    else:
        action = "update"
        changes.append(f"Update engagement \"{target.name}\" and store key {key} on it.")
        if target.compass_key and target.compass_key != key:
            asks.append({"field": "confirm_key_change",
                         "question": f"This engagement already carries the key "
                                     f"{target.compass_key}. Replace it with {key}?"})
        if target.name != name:
            asks.append({"field": "overwrite_name",
                         "question": f"Rename the engagement from \"{target.name}\" to \"{name}\"? "
                                     "(Left as it is unless you tick this.)"})
        dataset_id = dataset_id or await _latest_dataset_id(session, target.id)

    title_counts = await _title_counts(session, dataset_id)
    job_titles = sorted(title_counts)
    if not job_titles:
        warnings.append("No org file is loaded for this engagement yet, so roles cannot be matched "
                        "to positions. Import now, upload the org CSV, then set the matches in the "
                        "Compass roles panel.")
    stored = {r.ref: r for r in (await _stored_roles(session, target.id) if target else [])}
    cluster_names = {_s(c.get("ref")): _s(c.get("name"))
                     for c in (packet.get("clusters") or []) if isinstance(c, dict)}
    roles_out = []
    roles, _ = packet_roles(packet)
    for r in roles:
        exact, candidates = match_title(r["title"], job_titles)
        prior = stored.get(r["ref"])
        note = ""
        if r["status"] == "absent":
            state, proposed = "absent", None
            if exact:
                note = (f"Compass says no one is in this seat, but the org file has "
                        f"{title_counts.get(exact, 0)} position(s) titled \"{exact}\". Not analysed "
                        "unless you choose a match.")
        elif prior is not None and prior.matched_job_title and (
                not job_titles or prior.matched_job_title in title_counts):
            state, proposed = prior.match_state, prior.matched_job_title  # keep what was set before
            note = "Kept from the earlier import."
        elif exact:
            state, proposed = "matched", exact
        elif candidates:
            state, proposed = "near", None
            note = "Similar job titles found — choose one or leave unmatched."
        else:
            state, proposed = "missed", None
        roles_out.append({
            **{k: r[k] for k in ("ref", "title", "cluster_ref", "route", "status")},
            "cluster_name": cluster_names.get(r["cluster_ref"], ""),
            "match_state": state, "matched_job_title": proposed, "candidates": candidates,
            "positions": title_counts.get(proposed, 0) if proposed else 0, "note": note,
        })
    removed = sorted(set(stored) - {r["ref"] for r in roles})
    if removed:
        changes.append("Remove role(s) no longer in the file: " + ", ".join(removed) + ".")
    subset = stored_subset(packet)
    changes.append(f"Store {len(roles_out)} role(s) with their Compass IDs, routes and clusters.")
    changes.append(f"Store the operating-system reference model ({len(subset['reference_model'])} "
                   f"components) and the leapfrog gate ({len(subset['leapfrog_gate'])} tests) for a "
                   "later module. Nothing uses them yet.")
    counts: Dict[str, int] = {}
    for r in roles_out:
        counts[r["match_state"]] = counts.get(r["match_state"], 0) + 1
    return {
        "ok": True, "errors": [], "warnings": warnings,
        "engagement": {"action": action, "id": target.id if target else None, "key": key,
                       "name": name, "current_name": target.name if target else None,
                       "client_name": client_name},
        "dataset_id": dataset_id, "job_titles": job_titles,
        "roles": roles_out, "match_counts": counts, "changes": changes, "asks": asks,
        "readiness": subset["readiness"],
    }


class ImportRefused(Exception):
    """Raised by `apply` with plain-language reasons; nothing was written."""

    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


async def apply(session: AsyncSession, packet, *, engagement_id: Optional[str] = None,
                dataset_id: Optional[str] = None, matches: Optional[Dict[str, Optional[str]]] = None,
                overwrite_name: bool = False, confirm_key_change: bool = False) -> Dict:
    """Apply a previewed import. `matches` is the consultant's confirmed {role ref: job title or
    null}; a role not listed keeps the preview's proposal (exact or earlier match only — a
    near-match is never applied on its own)."""
    pv = await preview(session, packet, engagement_id=engagement_id, dataset_id=dataset_id)
    if not pv["ok"]:
        raise ImportRefused(pv["errors"])
    info = pv["engagement"]
    target = await session.get(Engagement, info["id"]) if info["id"] else None
    if target is not None and target.compass_key and target.compass_key != info["key"] \
            and not confirm_key_change:
        raise ImportRefused([f"This engagement already carries the key {target.compass_key}. "
                             f"Confirm the change to {info['key']} to import."])
    if target is None:
        client = await session.scalar(
            select(Client).where(func.lower(Client.name) == info["client_name"].lower()))
        if client is None:
            client = Client(name=info["client_name"],
                            industry=_s((packet.get("engagement") or {}).get("industry")) or None)
            session.add(client)
            await session.flush()
        target = Engagement(client_id=client.id, name=info["name"],
                            anonymized=bool(client.anonymization_default))
        session.add(target)
        await session.flush()
    elif overwrite_name:
        target.name = info["name"]
    target.compass_key = info["key"]
    target.compass_packet = stored_subset(packet)

    matches = matches or {}
    detail = {r["ref"]: r for r in packet_roles(packet)[0]}
    await session.execute(delete(CompassRole).where(CompassRole.engagement_id == target.id))
    for seq, pr in enumerate(pv["roles"]):
        d = detail[pr["ref"]]
        chosen, state = pr["matched_job_title"], pr["match_state"]
        if pr["ref"] in matches:
            chosen = _s(matches[pr["ref"]]) or None
            exact, _ = match_title(pr["title"], pv["job_titles"])
            if chosen is None:
                state = "absent" if pr["status"] == "absent" else "missed"
            elif chosen == pr["matched_job_title"] and state in ("matched", "manual"):
                pass  # unchanged from the proposal
            else:
                state = "matched" if chosen == exact else "manual"
        elif state == "near":
            state = "missed"
        session.add(CompassRole(
            engagement_id=target.id, seq=seq, ref=pr["ref"], title=pr["title"],
            cluster_ref=pr["cluster_ref"] or None, route=pr["route"] or None,
            status=pr["status"] or None, criticality_index=d.get("criticality_index"),
            tacit_intensity=d.get("tacit_intensity"), note=d.get("note") or None,
            matched_job_title=chosen, match_state=state,
        ))
    await session.flush()
    return {"engagement_id": target.id, "client_id": target.client_id, "name": target.name,
            "key": target.compass_key, "roles": len(pv["roles"]), "warnings": pv["warnings"]}


# ── Stored state (works with no packet) ──────────────────────────────────────
def _role_dict(r: CompassRole) -> Dict:
    return {"ref": r.ref, "title": r.title, "cluster_ref": r.cluster_ref, "route": r.route,
            "status": r.status, "criticality_index": r.criticality_index,
            "tacit_intensity": r.tacit_intensity, "note": r.note,
            "matched_job_title": r.matched_job_title, "match_state": r.match_state}


async def state(session: AsyncSession, engagement_id: str,
                dataset_id: Optional[str] = None) -> Optional[Dict]:
    """The engagement's Compass data + live counts for a dataset. `imported: false` when the
    engagement was never linked to Compass (the app is then simply standalone)."""
    eng = await session.get(Engagement, engagement_id)
    if eng is None:
        return None
    packet = eng.compass_packet or {}
    dataset_id = dataset_id or await _latest_dataset_id(session, engagement_id)
    title_counts = await _title_counts(session, dataset_id)
    job_titles = sorted(title_counts)
    task_counts: Dict[str, int] = {}
    if dataset_id:
        rows = await session.execute(
            select(Position.job_title, func.count(Task.id))
            .join(Task, Task.position_id == Position.id)
            .where(Position.dataset_id == dataset_id).group_by(Position.job_title)
        )
        task_counts = {jt: n for jt, n in rows.all() if jt}
    roles = []
    for r in await _stored_roles(session, engagement_id):
        d = _role_dict(r)
        d["positions"] = title_counts.get(r.matched_job_title, 0) if r.matched_job_title else 0
        d["tasks"] = task_counts.get(r.matched_job_title, 0) if r.matched_job_title else 0
        d["suggestion"], d["candidates"] = None, []
        if not r.matched_job_title and r.status != "absent":
            d["suggestion"], d["candidates"] = match_title(r.title, job_titles)
        d["seat"] = "no one in the seat" if r.status == "absent" else (r.status or "")
        roles.append(d)
    return {
        "engagement_id": engagement_id, "imported": bool(eng.compass_key),
        "key": eng.compass_key, "generated_at": packet.get("generated_at"),
        "imported_at": packet.get("imported_at"), "readiness": packet.get("readiness"),
        "reference_model": packet.get("reference_model", []),
        "leapfrog_gate": packet.get("leapfrog_gate", []),
        "clusters": packet.get("clusters", []), "pilots": packet.get("pilots", []),
        "dataset_id": dataset_id, "job_titles": job_titles, "roles": roles,
    }


async def set_role_match(session: AsyncSession, engagement_id: str, ref: str,
                         job_title: Optional[str]) -> Optional[Dict]:
    """The consultant corrects one role's match (None/blank clears it). None if no such role."""
    role = await session.scalar(select(CompassRole).where(
        CompassRole.engagement_id == engagement_id, CompassRole.ref == ref))
    if role is None:
        return None
    chosen = _s(job_title) or None
    role.matched_job_title = chosen
    role.match_state = "manual" if chosen else ("absent" if role.status == "absent" else "missed")
    await session.flush()
    return _role_dict(role)


# ── Role context for tasks (badges, ordering, tacit-knowledge warning) ───────
async def role_index(session: AsyncSession, engagement_id: Optional[str]) -> Dict[str, Dict]:
    """normalised job title -> Compass role (first in packet order wins). {} with no packet."""
    if not engagement_id:
        return {}
    index: Dict[str, Dict] = {}
    for r in await _stored_roles(session, engagement_id):
        if r.matched_job_title:
            index.setdefault(normalise_title(r.matched_job_title), {**_role_dict(r), "seq": r.seq})
    return index


async def role_index_for_dataset(session: AsyncSession, dataset_id: Optional[str]) -> Dict[str, Dict]:
    ds = await session.get(Dataset, dataset_id) if dataset_id else None
    return await role_index(session, ds.engagement_id) if ds is not None else {}


def role_fields(index: Dict[str, Dict], job_title: Optional[str], band: Optional[str]) -> Dict:
    """The Compass fields shown on a task or role row. All None/False when there is no packet or the
    role is not a Compass role — callers can attach this unconditionally."""
    role = index.get(normalise_title(job_title)) if index and job_title else None
    route = role["route"] if role else None
    warn = bool(role) and route in HIGH_TACIT_ROUTES and band in LOW_AGENCY_BANDS
    return {
        "compass_ref": role["ref"] if role else None,
        "compass_route": route,
        "compass_cluster_ref": role["cluster_ref"] if role else None,
        "tacit_warning": TACIT_WARNING.format(route=route, band=band) if warn else None,
    }


def compass_rank(index: Dict[str, Dict], job_title: Optional[str]) -> int:
    """Sort key: Compass roles first, in packet order; everything else after."""
    role = index.get(normalise_title(job_title)) if index and job_title else None
    return role["seq"] if role else 10_000
