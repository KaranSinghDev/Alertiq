"""
Feature engineering for alert severity/category prediction.
Pure functions — no IO, fully unit-testable.
"""
from datetime import datetime
import pandas as pd

# Canonical severity order — index position used by LightGBM multiclass encoding
SEVERITY_ORDER = ["critical", "high", "medium", "low"]

CATEGORICAL_FEATURES = ["alert_name", "service", "environment"]
NUMERIC_FEATURES = [
    "alert_count_in_window", "hour_of_day", "day_of_week",
    "is_weekend", "is_business_hours",
]
ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

BUSINESS_HOURS_START = 9
BUSINESS_HOURS_END = 18


def is_business_hours(dt: datetime) -> int:
    """1 if alert fired during business hours (9-18, Mon-Fri), else 0."""
    if dt.weekday() >= 5:
        return 0
    return int(BUSINESS_HOURS_START <= dt.hour < BUSINESS_HOURS_END)


def extract_temporal_features(dt: datetime) -> dict:
    return {
        "hour_of_day": dt.hour,
        "day_of_week": dt.weekday(),
        "is_weekend": int(dt.weekday() >= 5),
        "is_business_hours": is_business_hours(dt),
    }


def build_feature_row(incident: dict) -> dict:
    """
    Convert an incident/alert dict to a flat feature dict.
    Expected keys: alert_name, service, environment, alert_count_in_window, started_at.
    """
    return {
        "alert_name": incident["alert_name"],
        "service": incident["service"],
        "environment": incident["environment"],
        "alert_count_in_window": incident.get("alert_count_in_window", 1),
        **extract_temporal_features(incident["started_at"]),
    }


def build_feature_dataframe(incidents: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame([build_feature_row(i) for i in incidents])
    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype("category")
    return df[ALL_FEATURES]
