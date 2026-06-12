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


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Reference layer (engagement-independent; seeded once) + task tables.
# Additive only. The AI overlay joins to tasks LOGICALLY by onet_task_code (D1) — no hard FK.
# ══════════════════════════════════════════════════════════════════════════════


class TaxonomySource(Base):
    """A pluggable taxonomy (SFw / O*NET / WORKBank / ESCO). Natural key: `code`."""

    __tablename__ = "taxonomy_source"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    region = Column(String(16), nullable=True)
    version = Column(String(64), nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    license_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("TaxonomyTask", back_populates="source", cascade="all, delete-orphan")


class TaxonomyTask(Base):
    """A reference task/role row in a taxonomy. Natural key: `task_ref`."""

    __tablename__ = "taxonomy_task"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_id = Column(
        String(36), ForeignKey("taxonomy_source.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_ref = Column(String(128), unique=True, nullable=False, index=True)
    role_label = Column(String(255), nullable=True)
    track = Column(String(255), nullable=True)
    function = Column(String(255), nullable=True)
    task_text = Column(Text, nullable=False)
    task_code = Column(String(64), nullable=True)  # e.g. O*NET occupation code
    skills = Column(JSON, nullable=True)  # list[str]
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("TaxonomySource", back_populates="tasks")


class TaxonomyCrosswalk(Base):
    """A mapping from one taxonomy task to another taxonomy's code (e.g. SFw -> O*NET).

    Carries `method` and `confidence`; `review_state` defaults to unreviewed when confidence < 0.70
    (Build Spec B0 — even CURATED seed rows; the starter ships one at 0.40).
    """

    __tablename__ = "taxonomy_crosswalk"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    from_source_id = Column(
        String(36), ForeignKey("taxonomy_source.id", ondelete="CASCADE"), nullable=True, index=True
    )
    from_task_id = Column(
        String(36), ForeignKey("taxonomy_task.id", ondelete="CASCADE"), nullable=True, index=True
    )
    to_source_code = Column(String(64), nullable=False)
    to_task_code = Column(String(64), nullable=False)
    confidence = Column(Float, nullable=True)
    method = Column(String(32), nullable=False, default="CURATED")  # CURATED|MODEL_INFERRED|CURATED_BY_CONSULTANT
    review_state = Column(String(16), nullable=False, default="unreviewed")
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TaskAIOverlay(Base):
    """WORKBank-style AI overlay, joined to tasks LOGICALLY by `onet_task_code` (D1 — no hard FK).

    `desire_score_us` is US worker preference (never local). `has_level` and `capability_score` are
    INDEPENDENT (A4). Natural key: `onet_task_code`.
    """

    __tablename__ = "task_ai_overlay"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    onet_task_code = Column(String(64), unique=True, nullable=False, index=True)
    onet_task_text = Column(Text, nullable=True)
    occupation = Column(String(255), nullable=True)
    has_level = Column(Integer, nullable=True)  # 1..5, independent of capability
    desire_score_us = Column(Float, nullable=True)  # US preference (seed desire_score maps here)
    desire_score_local = Column(Float, nullable=True)  # populated only by the M2 pulse instrument
    capability_score = Column(Float, nullable=True)
    zone = Column(String(32), nullable=True)
    source = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    """A task extracted from a position's free-text work activities."""

    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    position_id = Column(
        String(36), ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_text = Column(Text, nullable=False)
    batch_id = Column(String(64), nullable=True, index=True)
    extraction_source = Column(String(64), nullable=True)  # e.g. model-inferred
    created_at = Column(DateTime, default=datetime.utcnow)

    benchmarks = relationship("TaskBenchmark", back_populates="task", cascade="all, delete-orphan")
    ai_scores = relationship("TaskAIScore", back_populates="task", cascade="all, delete-orphan")


class TaskBenchmark(Base):
    """A task's benchmark match against a taxonomy. Provenance fields are mandatory (A4)."""

    __tablename__ = "task_benchmarks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    taxonomy_source_code = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, default="MATCHED")  # MATCHED|MISSING|EXTRA
    matched_taxonomy_task_id = Column(
        String(36), ForeignKey("taxonomy_task.id", ondelete="SET NULL"), nullable=True
    )
    onet_task_code = Column(String(64), nullable=True)
    source = Column(String(32), nullable=False, default="model-inferred")
    confidence = Column(Float, nullable=True)
    review_state = Column(String(16), nullable=False, default="unreviewed")
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="benchmarks")


class TaskAIScore(Base):
    """A task's AI-opportunity score. Provenance fields mandatory (A4). Dual desire scores kept
    separate; HAS and capability independent."""

    __tablename__ = "task_ai_scores"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    has_level = Column(Integer, nullable=True)
    zone = Column(String(32), nullable=True)
    desire_score_us = Column(Float, nullable=True)
    desire_score_local = Column(Float, nullable=True)
    capability_score = Column(Float, nullable=True)
    ai_opportunity_level = Column(String(8), nullable=True)  # L0|L1|L2|L3
    rationale = Column(Text, nullable=True)
    source = Column(String(32), nullable=False, default="model-inferred")
    confidence = Column(Float, nullable=True)
    review_state = Column(String(16), nullable=False, default="unreviewed")
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="ai_scores")


class DesirePulseResponse(Base):
    """A local-workforce automation-desire rating (1-5) for a task, by an anonymized respondent."""

    __tablename__ = "desire_pulse_responses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    engagement_id = Column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_ref = Column(String(128), nullable=True, index=True)
    respondent_hash = Column(String(64), nullable=True)
    desire_rating = Column(Integer, nullable=True)  # 1..5
    created_at = Column(DateTime, default=datetime.utcnow)
