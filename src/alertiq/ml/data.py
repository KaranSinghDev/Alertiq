"""
Data access for ML training: queries labelled incidents from PostgreSQL.
Pure DB layer — no ML logic here.
"""
from sqlalchemy.orm import Session
from alertiq.db.models import Incident

MIN_TRAINING_SAMPLES = 30


class InsufficientDataError(Exception):
    """Raised when there are not enough incident records to train a model."""


def get_labelled_incidents(session: Session) -> list[dict]:
    """
    Return all incidents (all have severity_label by schema constraint).
    Each dict contains feature fields + labels for both classifiers.

    Raises InsufficientDataError when < MIN_TRAINING_SAMPLES exist.
    Ingest incidents via POST /incidents/ or the CSV importer.
    """
    rows = session.query(Incident).all()
    if len(rows) < MIN_TRAINING_SAMPLES:
        raise InsufficientDataError(
            f"Need at least {MIN_TRAINING_SAMPLES} incidents to train, "
            f"got {len(rows)}. Ingest via POST /incidents/."
        )
    return [
        {
            "alert_name": i.alert_name,
            "service": i.service,
            "environment": i.environment,
            "alert_count_in_window": i.alert_count_in_window,
            "started_at": i.started_at,
            # Labels
            "severity_label": i.severity_label,
            "auto_resolved": bool(i.auto_resolved),
        }
        for i in rows
    ]
