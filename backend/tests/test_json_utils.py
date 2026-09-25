"""Tests for the ported JSON parse/repair helpers (Build Spec B0 — _json_utils port).

These lock the behaviour carried over from the legacy `work_activities_service.py` so a future
phase cannot silently change it (Part A additive-only rule).
"""
from __future__ import annotations

from app.services._json_utils import (
    extract_partial_data,
    parse_ai_json,
    repair_truncated_json,
)


def test_parse_fenced_json_block():
    """A ```json fenced block is extracted and parsed."""
    text = 'Here is the result:\n```json\n{"a": 1, "b": [2, 3]}\n```\nDone.'
    assert parse_ai_json(text) == {"a": 1, "b": [2, 3]}


def test_parse_raw_json_object():
    """A raw {...} span with surrounding prose is parsed."""
    text = 'prose before {"x": "y"} prose after'
    assert parse_ai_json(text) == {"x": "y"}


def test_parse_no_json_returns_error_envelope():
    """Text with no JSON returns the legacy error envelope, never raises."""
    result = parse_ai_json("no json here at all")
    assert result["error"] == "Could not parse response"
    assert result["raw_response"] == "no json here at all"


def test_repair_truncated_json_closes_braces_and_brackets():
    """An unterminated object/array is repaired by closing open braces/brackets."""
    truncated = '{"items": [1, 2, 3'
    repaired = repair_truncated_json(truncated)
    assert repaired is not None
    import json

    assert json.loads(repaired) == {"items": [1, 2, 3]}


def test_repair_returns_none_when_balanced():
    """Balanced JSON needs no repair."""
    assert repair_truncated_json('{"ok": true}') is None


def test_parse_truncated_with_no_closing_brace_returns_error():
    """Legacy contract: raw-JSON extraction needs a closing `}`. With none, it short-circuits to
    the error envelope (it never reaches the repair path)."""
    text = '{"items": [1, 2, 3], "summary": "partial'  # no closing brace anywhere
    result = parse_ai_json(text)
    assert result["error"] == "Could not parse response"


def test_parse_repairs_unbalanced_span_and_flags_it():
    """When the extracted `{...}` span is unbalanced (an inner object closed but the outer not),
    parse_ai_json repairs it and tags `_json_repaired` — mirroring legacy."""
    text = '{"items": [1, 2, 3], "nested": {"a": 1}'  # outer brace unclosed; inner `}` present
    result = parse_ai_json(text)
    assert result.get("_json_repaired") is True
    assert result["items"] == [1, 2, 3]
    assert result["nested"] == {"a": 1}


def test_extract_partial_data_pulls_executive_summary():
    """Partial extraction recovers an executive_summary from malformed text."""
    text = 'garbage {"executive_summary": "Key finding here."} more garbage'
    result = extract_partial_data(text)
    assert result["executive_summary"] == "Key finding here."
    assert "parse_warning" in result
