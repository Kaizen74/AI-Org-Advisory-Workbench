"""Pydantic request/response schemas for the engagement + diagnostics API (Phase 1)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ClientCreate(BaseModel):
    name: str
    industry: Optional[str] = None
    anonymization_default: bool = False


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    industry: Optional[str] = None
    anonymization_default: bool
    created_at: Optional[datetime] = None


class EngagementCreate(BaseModel):
    client_id: str
    name: str
    strategy_context: Optional[str] = None
    design_criteria: Optional[str] = None
    default_taxonomy_code: Optional[str] = None
    anonymized: bool = False


class EngagementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    client_id: str
    name: str
    strategy_context: Optional[str] = None
    design_criteria: Optional[str] = None
    default_taxonomy_code: Optional[str] = None
    anonymized: bool
    created_at: Optional[datetime] = None
    compass_key: Optional[str] = None  # set when imported from Capability Compass (D50)


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    engagement_id: str
    version: int
    filename: Optional[str] = None
    row_count: int
    validation_warnings: Optional[List[str]] = None
    created_at: Optional[datetime] = None


class MetricValueOut(BaseModel):
    metric_code: str
    scope: str
    scope_key: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None


class DiagnosticsSummary(BaseModel):
    dataset_id: str
    computed: bool
    metrics: dict  # metric_code -> value
    rows: List[MetricValueOut]
