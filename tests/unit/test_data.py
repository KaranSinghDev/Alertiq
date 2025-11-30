"""
Unit tests for ml/data.py.
"""
import pytest
from datetime import datetime
from alertiq.ml.data import get_labelled_incidents, InsufficientDataError, MIN_TRAINING_SAMPLES


def _add_incident(db, suffix: str):
    from alertiq.db.models import Incident
    i = Incident(
        id=f"INC-{suffix}",
        alert_name="HighMemoryUsage",
        service="payment-service",
        environment="prod",
        severity_label="high",
        started_at=datetime(2024, 3, 1, 14, 0),
        auto_resolved=False,
    )
    db.add(i)
    db.flush()
    return i


def test_insufficient_data_raises(db):
    for i in range(MIN_TRAINING_SAMPLES - 1):
        _add_incident(db, str(i))
    with pytest.raises(InsufficientDataError):
        get_labelled_incidents(db)


def test_returns_feature_and_label_keys(db):
    for i in range(MIN_TRAINING_SAMPLES):
        _add_incident(db, str(i))
    rows = get_labelled_incidents(db)
    required = {"alert_name", "service", "environment", "alert_count_in_window",
                "started_at", "severity_label", "auto_resolved"}
    for row in rows:
        assert required <= set(row.keys())


def test_auto_resolved_is_bool(db):
    for i in range(MIN_TRAINING_SAMPLES):
        _add_incident(db, str(i))
    rows = get_labelled_incidents(db)
    assert all(isinstance(r["auto_resolved"], bool) for r in rows)
