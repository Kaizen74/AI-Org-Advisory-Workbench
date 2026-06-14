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


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — Scenario design (the redesign surface). Additive only.
# ══════════════════════════════════════════════════════════════════════════════


class Scenario(Base):
    """A named future-state design = baseline dataset + an ordered list of design moves.

    Immutable once `status == PRESENTED`; further edits fork a new scenario (`parent_scenario_id`).
    """

    __tablename__ = "scenarios"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    engagement_id = Column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id = Column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    status = Column(String(16), nullable=False, default="DRAFT")  # DRAFT | PRESENTED
    parent_scenario_id = Column(
        String(36), ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    moves = relationship(
        "DesignMove", back_populates="scenario", cascade="all, delete-orphan",
        order_by="DesignMove.seq",
    )
    metrics = relationship(
        "ScenarioMetric", back_populates="scenario", cascade="all, delete-orphan"
    )


class DesignMove(Base):
    """One ordered design move within a scenario. `params` is JSON (variable per move_type)."""

    __tablename__ = "design_moves"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scenario_id = Column(
        String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq = Column(Integer, nullable=False, default=0)
    move_type = Column(String(32), nullable=False)
    params = Column(JSON, nullable=True)
    rationale = Column(Text, nullable=True)
    activator_tag = Column(Integer, nullable=True)  # 1..5 (which activator this move serves)
    created_at = Column(DateTime, default=datetime.utcnow)

    scenario = relationship("Scenario", back_populates="moves")


class ScenarioMetric(Base):
    """A persisted scenario metric value + its delta vs the baseline dataset's metric_values."""

    __tablename__ = "scenario_metrics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scenario_id = Column(
        String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_code = Column(String(64), nullable=False)
    value = Column(Float, nullable=True)
    delta_vs_baseline = Column(Float, nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow)

    scenario = relationship("Scenario", back_populates="metrics")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — Workflow / value-stream mapping (follow the work). Additive only.
# ══════════════════════════════════════════════════════════════════════════════


class Process(Base):
    """A process / value stream within an engagement (the 'follow the work' view)."""

    __tablename__ = "processes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    engagement_id = Column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    value_stream = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    steps = relationship("ProcessStep", back_populates="process", cascade="all, delete-orphan",
                         order_by="ProcessStep.seq")


class ProcessStep(Base):
    """An ordered step within a process."""

    __tablename__ = "process_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    process_id = Column(
        String(36), ForeignKey("processes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq = Column(Integer, nullable=False, default=0)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    process = relationship("Process", back_populates="steps")
    task_links = relationship("TaskLink", back_populates="step", cascade="all, delete-orphan")


class TaskLink(Base):
    """Links a task (from M2) to a process step — the cross-org-box 'follow the work' join."""

    __tablename__ = "task_links"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    process_step_id = Column(
        String(36), ForeignKey("process_steps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    step = relationship("ProcessStep", back_populates="task_links")


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 6 — Deliverable Factory. Additive only.
# ══════════════════════════════════════════════════════════════════════════════


class Deliverable(Base):
    """A generated client deliverable (pptx/docx/xlsx). The file lives in backend/output/ (gitignored);
    `provenance_summary` records % of content by source tag + caveats (transparency as a feature)."""

    __tablename__ = "deliverables"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    engagement_id = Column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type = Column(String(32), nullable=False)  # PPTX_DIAGNOSTIC|PPTX_SCENARIOS|PPTX_AI_ROADMAP|DOCX_TOM|XLSX_METRICS|XLSX_TRANSITION
    template = Column(String(32), nullable=False, default="minimal")
    file_path = Column(String(1024), nullable=True)
    provenance_summary = Column(JSON, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)


class AppSetting(Base):
    """Global key/value app settings (LLM provider/key/models, brand palette + logo path).

    Lets the Anthropic key and a local-LLM endpoint be managed through the UI (D11) and the brand
    deck template be swapped (D12). Secret values are masked when read back over the API.
    """

    __tablename__ = "app_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
