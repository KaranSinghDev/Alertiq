"""
Bulk incident importer for PagerDuty and generic CSV exports.
Designed to seed the training dataset without manually POSTing incidents one by one.

PagerDuty CSV column names (from Incidents export):
    Incident Number, Title, Status, Urgency, Created At, Resolved At, Service, Teams

Generic CSV column mapping is user-configurable via the `column_map` dict.
"""
import csv
import io
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from alertiq.db.models import Incident

# PagerDuty urgency → AlertIQ severity_label
_PD_URGENCY_MAP = {
    "high": "critical",
    "low": "medium",
}

# Expected PagerDuty CSV headers (lowercase, stripped)
_PD_HEADERS = {"incident number", "title", "status", "urgency", "created at", "service"}


def _parse_dt(value: str) -> datetime | None:
    """Try common datetime formats from PagerDuty exports."""
    if not value or value.strip() == "":
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def import_pagerduty_csv(csv_content: str, session: Session) -> dict:
    """
    Parse a PagerDuty incident CSV export and bulk-insert Incident records.
    Skips rows where the incident ID already exists in the DB.

    Returns:
        {"imported": int, "skipped_duplicates": int, "skipped_invalid": int}
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    if not reader.fieldnames:
        return {"imported": 0, "skipped_duplicates": 0, "skipped_invalid": 0}

    # Normalise header names for resilience
    normalised = {h.strip().lower(): h for h in reader.fieldnames}
    missing = _PD_HEADERS - set(normalised)
    if missing:
        raise ValueError(f"PagerDuty CSV missing required columns: {missing}")

    imported = 0
    skipped_dup = 0
    skipped_invalid = 0

    for row in reader:
        # Normalise row keys
        row = {k.strip().lower(): (v or "").strip() for k, v in row.items()}

        incident_id = f"pd-{row.get('incident number', uuid.uuid4().hex)}"
        if session.get(Incident, incident_id):
            skipped_dup += 1
            continue

        started_at = _parse_dt(row.get("created at", ""))
        if started_at is None:
            skipped_invalid += 1
            continue

        resolved_at = _parse_dt(row.get("resolved at", ""))
        resolution_min: float | None = None
        if resolved_at and started_at:
            resolution_min = (resolved_at - started_at).total_seconds() / 60

        urgency = row.get("urgency", "low").lower()
        severity = _PD_URGENCY_MAP.get(urgency, "low")
        auto_resolved = row.get("status", "").lower() == "resolved" and resolution_min is not None and resolution_min < 5

        incident = Incident(
            id=incident_id,
            alert_name=row.get("title", "unknown") or "unknown",
            service=row.get("service", "unknown") or "unknown",
            environment="prod",           # PagerDuty doesn't export env; default prod
            severity_label=severity,
            started_at=started_at,
            resolved_at=resolved_at,
            resolution_time_min=resolution_min,
            auto_resolved=auto_resolved,
        )
        session.add(incident)
        imported += 1

    session.commit()
    return {"imported": imported, "skipped_duplicates": skipped_dup, "skipped_invalid": skipped_invalid}


def import_generic_csv(csv_content: str, column_map: dict, session: Session) -> dict:
    """
    Import incidents from any CSV using a user-provided column mapping.

    column_map keys:
        id, alert_name, service, environment, severity_label,
        started_at, resolved_at, resolution_time_min, auto_resolved,
        alert_count_in_window  (all optional except alert_name, service, started_at)
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    if not reader.fieldnames:
        return {"imported": 0, "skipped_duplicates": 0, "skipped_invalid": 0}

    imported = 0
    skipped_dup = 0
    skipped_invalid = 0

    for row in reader:
        def get(field: str, default=None):
            col = column_map.get(field)
            return row.get(col, default) if col else default

        started_at = _parse_dt(get("started_at", ""))
        if started_at is None:
            skipped_invalid += 1
            continue

        incident_id = get("id") or uuid.uuid4().hex
        if session.get(Incident, incident_id):
            skipped_dup += 1
            continue

        incident = Incident(
            id=incident_id,
            alert_name=get("alert_name") or "unknown",
            service=get("service") or "unknown",
            environment=get("environment") or "prod",
            severity_label=get("severity_label") or "low",
            started_at=started_at,
            resolved_at=_parse_dt(get("resolved_at", "")),
            resolution_time_min=float(get("resolution_time_min") or 0) or None,
            auto_resolved=str(get("auto_resolved", "false")).lower() == "true",
            alert_count_in_window=int(get("alert_count_in_window") or 1),
        )
        session.add(incident)
        imported += 1

    session.commit()
    return {"imported": imported, "skipped_duplicates": skipped_dup, "skipped_invalid": skipped_invalid}
