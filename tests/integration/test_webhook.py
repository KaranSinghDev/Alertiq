"""
Integration tests for the webhook prediction route.
AlertPredictor is mocked so no MLflow server is required.
"""
from datetime import datetime
from unittest.mock import patch, MagicMock
import pytest


def _mock_predictor(severity="high", auto_resolve=False, confidence=0.82):
    mock = MagicMock()
    mock.is_loaded.return_value = True
    mock.model_version = "v-test"
    mock.predict.return_value = {
        "predicted_severity": severity,
        "predicted_category": None,
        "predicted_auto_resolve": auto_resolve,
        "severity_confidence": confidence,
    }
    return mock


WEBHOOK_PAYLOAD = {
    "alert_name": "HighMemoryUsage",
    "service": "payment-service",
    "environment": "prod",
    "alert_count_in_window": 5,
    "fired_at": "2024-03-01T14:30:00",
}


def test_webhook_returns_201_with_prediction(client):
    with patch("alertiq.api.routes.webhook.AlertPredictor.get", return_value=_mock_predictor()):
        resp = client.post("/webhook/alert", json=WEBHOOK_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["predicted_severity"] == "high"
    assert body["predicted_auto_resolve"] is False
    assert body["severity_confidence"] == pytest.approx(0.82)
    assert body["model_version"] == "v-test"


def test_webhook_stores_prediction_in_db(client, db_session):
    with patch("alertiq.api.routes.webhook.AlertPredictor.get", return_value=_mock_predictor()):
        resp = client.post("/webhook/alert", json=WEBHOOK_PAYLOAD)
    assert resp.status_code == 201
    from alertiq.db.models import AlertPrediction
    pred = db_session.get(AlertPrediction, resp.json()["id"])
    assert pred is not None
    assert pred.predicted_severity == "high"


def test_webhook_503_when_no_model(client):
    from alertiq.ml.predictor import ModelNotLoadedError
    mock = MagicMock()
    mock.is_loaded.return_value = False
    mock.predict.side_effect = ModelNotLoadedError("no model")
    with patch("alertiq.api.routes.webhook.AlertPredictor.get", return_value=mock):
        resp = client.post("/webhook/alert", json=WEBHOOK_PAYLOAD)
    assert resp.status_code == 503


def test_webhook_critical_alert(client):
    with patch("alertiq.api.routes.webhook.AlertPredictor.get",
               return_value=_mock_predictor(severity="critical", confidence=0.97)):
        resp = client.post("/webhook/alert", json=WEBHOOK_PAYLOAD)
    assert resp.status_code == 201
    assert resp.json()["predicted_severity"] == "critical"
