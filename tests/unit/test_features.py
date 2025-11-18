"""
TDD unit tests for AlertIQ feature engineering.
Written before implementation — define the contract the code must satisfy.
"""
import pytest
from datetime import datetime
from alertiq.ml.features import (
    is_business_hours,
    extract_temporal_features,
    build_feature_row,
    build_feature_dataframe,
    ALL_FEATURES,
    CATEGORICAL_FEATURES,
)


def test_business_hours_weekday_morning():
    dt = datetime(2024, 1, 15, 10, 0, 0)  # Monday 10am
    assert is_business_hours(dt) == 1


def test_business_hours_weekday_evening():
    dt = datetime(2024, 1, 15, 20, 0, 0)  # Monday 8pm
    assert is_business_hours(dt) == 0


def test_business_hours_saturday():
    dt = datetime(2024, 1, 20, 11, 0, 0)  # Saturday 11am
    assert is_business_hours(dt) == 0


def test_temporal_sunday():
    dt = datetime(2024, 1, 21, 3, 0, 0)  # Sunday 3am
    r = extract_temporal_features(dt)
    assert r["day_of_week"] == 6
    assert r["is_weekend"] == 1
    assert r["is_business_hours"] == 0
    assert r["hour_of_day"] == 3


def _make_incident(hour=14, weekday_offset=0):
    base = datetime(2024, 3, 18, hour, 0, 0)  # Monday
    return {
        "alert_name": "HighMemoryUsage",
        "service": "payment-service",
        "environment": "prod",
        "alert_count_in_window": 5,
        "started_at": base,
    }


def test_feature_row_has_all_features():
    row = build_feature_row(_make_incident())
    for f in ALL_FEATURES:
        assert f in row, f"Missing: {f}"


def test_feature_dataframe_shape():
    df = build_feature_dataframe([_make_incident(), _make_incident(hour=2)])
    assert df.shape == (2, len(ALL_FEATURES))


def test_feature_dataframe_categorical_dtype():
    df = build_feature_dataframe([_make_incident()])
    for col in CATEGORICAL_FEATURES:
        assert str(df[col].dtype) == "category"


def test_feature_row_alert_count():
    incident = _make_incident()
    incident["alert_count_in_window"] = 10
    row = build_feature_row(incident)
    assert row["alert_count_in_window"] == 10


def test_feature_row_default_alert_count():
    incident = _make_incident()
    del incident["alert_count_in_window"]
    row = build_feature_row(incident)
    assert row["alert_count_in_window"] == 1
