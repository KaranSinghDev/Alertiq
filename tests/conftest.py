import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alertiq.main import app
from alertiq.db.session import Base, get_db


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    yield eng


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_incident_payload():
    now = datetime.utcnow()
    return {
        "id": "INC-001",
        "alert_name": "HighMemoryUsage",
        "service": "payment-service",
        "environment": "prod",
        "severity_label": "critical",
        "root_cause_category": "memory_leak",
        "started_at": now.isoformat(),
        "resolved_at": (now + timedelta(minutes=45)).isoformat(),
        "resolution_time_min": 45.0,
        "auto_resolved": False,
        "alert_count_in_window": 3,
    }
