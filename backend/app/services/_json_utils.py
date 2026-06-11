"""JSON parse/repair helpers for Claude responses.

PORTED in Phase 0 from the legacy v1 app's
`legacy/backend/app/services/work_activities_service.py` (methods `_parse_response`,
`_repair_truncated_json`, `_extract_partial_data`), per Build Spec B0. The logic is preserved
byte-for-byte in behaviour; the only change is lifting the three methods out of the
`WorkActivitiesAnalysisService` class into standalone module functions so every feature service
can share one strict-JSON parser (Build Spec B2: "strict JSON prompts parsed via `_json_utils`").

Do not change behaviour here without a DECISIONS.md entry + regression test (Part A, A2 additive-
only rule once a phase is merged).
"""
from __future__ import annotations

import json
import re
from typing import Optional


def parse_ai_json(response_text: str) -> dict:
    """Parse a Claude response and extract the JSON payload.

    Handles three cases, in order: a ```json fenced block, a raw `{...}` span, and (on failure)
    a truncated-JSON repair followed by partial extraction. Mirrors the legacy `_parse_response`.
    """
    try:
        # Try to find JSON code block first
        json_start = response_text.find("```json")
        if json_start != -1:
            json_end = response_text.find("```", json_start + 7)
            if json_end != -1:
                json_str = response_text[json_start + 7:json_end].strip()
            else:
                json_str = response_text[json_start + 7:].strip()
        else:
            # Try to find raw JSON
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end > start:
                json_str = response_text[start:end]
            else:
                return {
                    "error": "Could not parse response",
                    "raw_response": response_text,
                }

        # Try to parse
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try to repair truncated JSON
            repaired = repair_truncated_json(json_str)
            if repaired:
                try:
                    result = json.loads(repaired)
                    result["_json_repaired"] = True
                    return result
                except json.JSONDecodeError:
                    pass

            # Extract what we can
            return extract_partial_data(response_text)

    except Exception as e:  # noqa: BLE001 - mirror legacy behaviour (never raise to caller)
        return {
            "error": f"JSON parse error: {str(e)}",
            "raw_response": response_text,
        }


def repair_truncated_json(json_str: str) -> Optional[str]:
    """Attempt to repair truncated JSON by closing open braces/brackets. Mirrors legacy."""
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")

    if open_braces <= 0 and open_brackets <= 0:
        return None

    repaired = json_str.rstrip()

    # Remove incomplete string
    if repaired.count('"') % 2 == 1:
        last_quote = repaired.rfind('"')
        prev_quote = repaired.rfind('"', 0, last_quote)
        if prev_quote != -1:
            repaired = repaired[:prev_quote]

    # Clean trailing
    repaired = repaired.rstrip()
    while repaired and repaired[-1] in ',:"':
        repaired = repaired[:-1].rstrip()

    # Recount and close
    open_braces = repaired.count("{") - repaired.count("}")
    open_brackets = repaired.count("[") - repaired.count("]")

    repaired += "]" * open_brackets
    repaired += "}" * open_braces

    return repaired if open_braces > 0 or open_brackets > 0 else None


def extract_partial_data(response_text: str) -> dict:
    """Extract partial data when full JSON parsing fails. Mirrors legacy `_extract_partial_data`."""
    result = {
        "parse_warning": "Partial data extracted due to response format issues",
        "raw_response": response_text,
    }

    # Try to extract executive summary
    exec_match = re.search(r'"executive_summary"\s*:\s*"((?:[^"\\]|\\.)*)"', response_text)
    if exec_match:
        result["executive_summary"] = (
            exec_match.group(1).replace('\\"', '"').replace("\\n", "\n")
        )

    return result
