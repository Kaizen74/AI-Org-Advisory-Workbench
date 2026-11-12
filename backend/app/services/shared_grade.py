"""Shared evidence grade (D50) — the three words used by all four apps.

Confirmed / Indicated / Hypothesis (keys `confirmed`, `indicated`, `hypothesis`). This app keeps its
own provenance vocabulary (`source`, `confidence`, `review_state`) and shows the shared grade
ALONGSIDE it. The grade is the assessor's judgement — it is never computed from a count of sources:

  * unreviewed / rejected content, and anything not yet looked at by a person that is AI output or
    below 0.70 confidence                                  -> Hypothesis
  * approved or edited in the Validation Queue              -> Indicated
  * raised by the consultant (stored `grade_override`)      -> Confirmed

A Hypothesis never drives a decision on its own; the export-block rule (A4/M6) is unchanged.
"""
from __future__ import annotations

from typing import Optional

GRADE_KEYS = ("hypothesis", "indicated", "confirmed")
GRADE_LABELS = {"hypothesis": "Hypothesis", "indicated": "Indicated", "confirmed": "Confirmed"}
CONFIDENCE_FLOOR = 0.70


def human_reviewed(source: Optional[str], review_state: Optional[str], reviewed_at=None) -> bool:
    """True when a person has actually judged this row (not merely auto-routed by confidence)."""
    if review_state == "edited":
        return True
    return review_state == "approved" and (reviewed_at is not None or source == "consultant-approved")


def shared_grade(*, source: Optional[str], confidence: Optional[float],
                 review_state: Optional[str], reviewed_at=None,
                 grade_override: Optional[str] = None) -> str:
    """The shared grade key for one AI mapping or score."""
    if review_state not in ("approved", "edited"):
        return "hypothesis"
    if human_reviewed(source, review_state, reviewed_at):
        return "confirmed" if grade_override == "confirmed" else "indicated"
    # Auto-approved by the confidence router, never seen by a person.
    if source == "model-inferred" or confidence is None or confidence < CONFIDENCE_FLOOR:
        return "hypothesis"
    return "indicated"


def grade_of(row) -> str:
    """Shared grade for an ORM row carrying the provenance fields (None -> hypothesis)."""
    if row is None:
        return "hypothesis"
    return shared_grade(
        source=getattr(row, "source", None), confidence=getattr(row, "confidence", None),
        review_state=getattr(row, "review_state", None),
        reviewed_at=getattr(row, "reviewed_at", None),
        grade_override=getattr(row, "grade_override", None),
    )


def weakest(grades) -> str:
    """The weakest grade in a set (a roll-up is only as strong as its weakest input)."""
    present = [g for g in grades if g in GRADE_KEYS]
    if not present:
        return "hypothesis"
    return min(present, key=GRADE_KEYS.index)
