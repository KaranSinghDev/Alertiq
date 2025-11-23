"""
Unit tests for ingestion/csv_importer.py.
"""
import pytest
from alertiq.ingestion.csv_importer import import_pagerduty_csv, import_generic_csv

VALID_PD_CSV = """\
Incident Number,Title,Status,Urgency,Created At,Resolved At,Service,Teams
101,HighMemoryUsage,resolved,high,2024-03-01T10:00:00Z,2024-03-01T10:03:00Z,payment-service,
102,PodCrashLooping,resolved,low,2024-03-02T02:00:00Z,2024-03-02T02:10:00Z,auth-service,
103,NetworkLatencyHigh,triggered,high,2024-03-03T15:00:00Z,,api-gateway,
"""

MISSING_COL_CSV = """\
ID,Title,Priority
1,Disk Full,P1
"""


def test_pagerduty_import_happy_path(db_session):
    result = import_pagerduty_csv(VALID_PD_CSV, db_session)
    assert result["imported"] == 3
    assert result["skipped_duplicates"] == 0
    assert result["skipped_invalid"] == 0


def test_pagerduty_deduplication(db_session):
    import_pagerduty_csv(VALID_PD_CSV, db_session)
    result2 = import_pagerduty_csv(VALID_PD_CSV, db_session)
    assert result2["imported"] == 0
    assert result2["skipped_duplicates"] == 3


def test_pagerduty_severity_mapping(db_session):
    from alertiq.db.models import Incident
    import_pagerduty_csv(VALID_PD_CSV, db_session)
    inc = db_session.get(Incident, "pd-101")
    assert inc.severity_label == "critical"      # urgency=high → critical


def test_pagerduty_auto_resolve_within_5min(db_session):
    from alertiq.db.models import Incident
    import_pagerduty_csv(VALID_PD_CSV, db_session)
    inc = db_session.get(Incident, "pd-101")
    assert inc.auto_resolved is True     # resolved in 3 min


def test_pagerduty_missing_columns_raises(db_session):
    with pytest.raises(ValueError, match="missing required columns"):
        import_pagerduty_csv(MISSING_COL_CSV, db_session)


def test_generic_import_with_column_map(db_session):
    csv_content = "my_id,my_name,my_svc,my_env,sev,ts\n" \
                  "G-001,DiskFull,storage,prod,critical,2024-03-01T12:00:00Z\n"
    column_map = {
        "id": "my_id",
        "alert_name": "my_name",
        "service": "my_svc",
        "environment": "my_env",
        "severity_label": "sev",
        "started_at": "ts",
    }
    result = import_generic_csv(csv_content, column_map, db_session)
    assert result["imported"] == 1
