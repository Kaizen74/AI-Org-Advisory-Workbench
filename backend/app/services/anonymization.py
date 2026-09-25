"""Anonymization helpers (Phase 7 / M7, designed-in from P1).

When an engagement is `anonymized`, each position gets a **stable salted pseudonym** generated at
ingest. All API responses and exports then surface the pseudonym; the real name lives only in
`positions.display_name` and is excluded from deliverables and can be purged on demand (PDPA).
"""
from __future__ import annotations

import hashlib
from typing import Optional

from ..config import settings


def pseudonym_for(engagement_id: str, employee_key: str, salt: Optional[str] = None) -> str:
    """Deterministic, non-reversible pseudonym for a position within an engagement."""
    s = salt if salt is not None else settings.ANON_SALT
    digest = hashlib.sha256(f"{s}:{engagement_id}:{employee_key}".encode("utf-8")).hexdigest()
    return f"EMP-{digest[:8].upper()}"


def display_label(*, anonymized: bool, display_name: Optional[str], pseudonym: Optional[str],
                  employee_key: str) -> str:
    """The safe-to-show label: pseudonym when anonymized, else the real display name."""
    if anonymized:
        return pseudonym or pseudonym_for("", employee_key)
    return display_name or employee_key
