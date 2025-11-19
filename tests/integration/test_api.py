"""
Integration tests for AlertIQ REST API.
Uses SQLite via conftest fixtures. Defines the API contract.
"""
from datetime import datetime, timedelta
import pytest


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_incident(client, sample_incident_payload):
    r = client.post("/incidents/", json=sample_incident_payload)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == "INC-001"
    assert body["service"] == "payment-service"
    assert body["severity_label"] == "critical"


def test_create_incident_duplicate_409(client, sample_incident_payload):
    client.post("/incidents/", json=sample_incident_payload)
    r = client.post("/incidents/", json=sample_incident_payload)
    assert r.status_code == 409


def test_get_incident(client, sample_incident_payload):
    client.post("/incidents/", json=sample_incident_payload)
    r = client.get("/incidents/INC-001")
    assert r.status_code == 200
    assert r.json()["id"] == "INC-001"


def test_get_incident_not_found(client):
    r = client.get("/incidents/NONEXISTENT")
    assert r.status_code == 404


def test_list_incidents(client, sample_incident_payload):
    client.post("/incidents/", json=sample_incident_payload)
    r = client.get("/incidents/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


def test_webhook_no_model_503(client):
    r = client.post("/webhook/alert", json={
        "alert_name": "HighCPU",
        "service": "auth-service",
        "environment": "prod",
        "alert_count_in_window": 1,
        "fired_at": datetime.utcnow().isoformat(),
    })
    assert r.status_code == 503


def test_incident_missing_required_field(client):
    r = client.post("/incidents/", json={"id": "INC-BAD", "alert_name": "x"})
    assert r.status_code == 422
