"""Engagement-core SQLAlchemy models (Phase 1, Build Spec B1).

All tables: uuid string PK via `generate_uuid`, a `created_at` timestamp, and FK cascade *within an
engagement* so a purge is clean (PRD §5). JSON columns are used only where the structure is
genuinely variable (validation warnings); analytical values are typed columns.

Later phases ADD tables/columns only — never alter these destructively (Part A additive-only rule).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base, generate_uuid


class Client(Base):
    """A client organization. Holds the anonymization default for its engagements."""

    __tablename__ = "clients"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, index=True)
    industry = Column(String(255), nullable=True)
    anonymization_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    engagements = relationship(
        "Engagement", back_populates="client", cascade="all, delete-orphan"
    )


class Engagement(Base):
    """A consulting engagement for a client. Root of all engagement-scoped data."""

    __tablename__ = "engagements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    client_id = Column(
        String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    strategy_context = Column(Text, nullable=True)
    design_criteria = Column(Text, nullable=True)
    default_taxonomy_code = Column(String(64), nullable=True)
    anonymized = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="engagements")
    datasets = relationship(
        "Dataset", back_populates="engagement", cascade="all, delete-orphan"
    )


class Dataset(Base):
    """A versioned org-CSV upload under an engagement. Analyses pin to a version."""

    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    engagement_id = Column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version = Column(Integer, nullable=False, default=1)
    filename = Column(String(512), nullable=True)
    row_count = Column(Integer, nullable=False, default=0)
    validation_warnings = Column(JSON, nullable=True)  # list[str] — variable structure
    created_at = Column(DateTime, default=datetime.utcnow)

    engagement = relationship("Engagement", back_populates="datasets")
    positions = relationship(
        "Position", back_populates="dataset", cascade="all, delete-orphan"
    )
    metric_values = relationship(
        "MetricValue", back_populates="dataset", cascade="all, delete-orphan"
    )


class Position(Base):
    """One org position. The graph is keyed on `employee_key` (Employee ID or surrogate),
    NEVER on name (PRD M1 breaking fix). `manager_key` references another position's employee_key.
    """

    __tablename__ = "positions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_key = Column(String(255), nullable=False, index=True)  # Employee ID or surrogate
    display_name = Column(String(255), nullable=True)  # real name; excluded from anon exports
    pseudonym = Column(String(255), nullable=True)  # stable salted hash when anonymized (P7)
    job_title = Column(String(255), nullable=True)
    grade = Column(String(64), nullable=True)
    level = Column(Integer, nullable=True)
    manager_key = Column(String(255), nullable=True, index=True)  # employee_key of the manager
    department = Column(String(255), nullable=True)
    salary = Column(Float, nullable=True)
    work_activities = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset = relationship("Dataset", back_populates="positions")


class MetricValue(Base):
    """A single typed metric value (not a JSON blob) so metrics are queryable/trendable (PRD M1)."""

    __tablename__ = "metric_values"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_code = Column(String(64), nullable=False, index=True)
    scope = Column(String(32), nullable=False, default="org")  # org | department
    scope_key = Column(String(255), nullable=True)  # e.g. department name when scope=department
    value = Column(Float, nullable=True)
    unit = Column(String(32), nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow)

    dataset = relationship("Dataset", back_populates="metric_values")
