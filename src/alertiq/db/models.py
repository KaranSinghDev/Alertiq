from datetime import datetime
from sqlalchemy import String, Float, Boolean, DateTime, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from alertiq.db.session import Base


class Incident(Base):
    """
    Historical incident record — ground truth for model training.
    Sourced from PagerDuty/OpsGenie CSV exports or webhook ingestion.
    """
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    alert_name: Mapped[str] = mapped_column(String(256))
    service: Mapped[str] = mapped_column(String(128))
    environment: Mapped[str] = mapped_column(String(64))          # prod | staging | dev
    severity_label: Mapped[str] = mapped_column(String(32))       # critical | high | medium | low
    root_cause_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_time_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    auto_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_count_in_window: Mapped[int] = mapped_column(Integer, default=1)
    raw_labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertPrediction(Base):
    """
    Real-time prediction for an incoming alert before it resolves.
    Written when webhook fires; used by on-call to prioritise.
    """
    __tablename__ = "alert_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_name: Mapped[str] = mapped_column(String(256))
    service: Mapped[str] = mapped_column(String(128))
    environment: Mapped[str] = mapped_column(String(64))
    predicted_severity: Mapped[str] = mapped_column(String(32))
    predicted_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    predicted_auto_resolve: Mapped[bool] = mapped_column(Boolean)
    severity_confidence: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(64))
    predicted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    feature_snapshot: Mapped[dict] = mapped_column(JSON)


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(64), unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    n_train_samples: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "running")
        super().__init__(**kwargs)
