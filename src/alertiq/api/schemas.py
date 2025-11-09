from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class IncidentCreate(BaseModel):
    id: str
    alert_name: str
    service: str
    environment: str
    severity_label: str
    root_cause_category: str | None = None
    started_at: datetime
    resolved_at: datetime | None = None
    resolution_time_min: float | None = None
    auto_resolved: bool = False
    alert_count_in_window: int = Field(default=1, ge=1)
    raw_labels: dict | None = None


class AlertWebhookPayload(BaseModel):
    """
    Prometheus AlertManager webhook format (v2).
    POST to /webhook/alert when an alert fires.
    """
    alert_name: str
    service: str
    environment: str = "prod"
    alert_count_in_window: int = Field(default=1, ge=1)
    fired_at: datetime


class AlertPredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    alert_name: str
    service: str
    predicted_severity: str
    predicted_category: str | None
    predicted_auto_resolve: bool
    severity_confidence: float
    model_version: str
    predicted_at: datetime


class TrainingRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_version: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    metrics: dict | None
    n_train_samples: int | None
