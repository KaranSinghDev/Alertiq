"""
Dual-classifier trainer: severity (4-class) + auto-resolve (binary).
Both models are logged to MLflow under the same run and registered separately.
"""
import uuid
from datetime import datetime

import lightgbm as lgb
import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, roc_auc_score
from sqlalchemy.orm import Session

from alertiq.config import Settings
from alertiq.ml.data import get_labelled_incidents
from alertiq.ml.features import build_feature_dataframe, CATEGORICAL_FEATURES

# Canonical severity order — index used by LightGBM multiclass
SEVERITY_ORDER = ["critical", "high", "medium", "low"]

LGBM_SEVERITY_PARAMS = {
    "objective": "multiclass",
    "num_class": 4,
    "metric": "multi_logloss",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "n_estimators": 200,
    "class_weight": "balanced",
    "verbose": -1,
    "random_state": 42,
}

LGBM_AUTORESOLVE_PARAMS = {
    "objective": "binary",
    "metric": "auc",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "n_estimators": 200,
    "class_weight": "balanced",
    "verbose": -1,
    "random_state": 42,
}


def _encode_severity(labels: list[str]) -> np.ndarray:
    mapping = {s: i for i, s in enumerate(SEVERITY_ORDER)}
    return np.array([mapping.get(lbl, 3) for lbl in labels])  # unknown → low


def _make_version() -> str:
    return f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"


def train(session: Session, settings: Settings) -> dict:
    """
    Train severity + auto-resolve classifiers.

    Returns:
        {
            "severity_accuracy": float,   mean OOF accuracy across 5 folds
            "autoresolve_auc": float,     mean OOF AUC across 5 folds
            "mlflow_run_id": str,
            "n_samples": int,
            "model_version": str,
        }
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    incidents = get_labelled_incidents(session)
    df = build_feature_dataframe(incidents)
    y_severity = _encode_severity([i["severity_label"] for i in incidents])
    y_autoresolve = np.array([int(i["auto_resolved"]) for i in incidents])

    model_version = _make_version()

    with mlflow.start_run(run_name=model_version) as run:
        mlflow.log_param("n_samples", len(incidents))
        mlflow.log_param("model_version", model_version)

        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        # --- Severity classifier (4-class) ---
        severity_oof = np.zeros(len(y_severity))
        for tr_idx, val_idx in skf.split(df, y_severity):
            clf = lgb.LGBMClassifier(**LGBM_SEVERITY_PARAMS)
            clf.fit(df.iloc[tr_idx], y_severity[tr_idx],
                    categorical_feature=CATEGORICAL_FEATURES)
            severity_oof[val_idx] = clf.predict(df.iloc[val_idx])

        severity_acc = float(accuracy_score(y_severity, severity_oof))
        mlflow.log_metric("cv_severity_accuracy", severity_acc)

        severity_model = lgb.LGBMClassifier(**LGBM_SEVERITY_PARAMS)
        severity_model.fit(df, y_severity, categorical_feature=CATEGORICAL_FEATURES)
        mlflow.sklearn.log_model(
            severity_model,
            artifact_path="severity_model",
            registered_model_name=f"{settings.model_registry_name}-severity",
        )

        # --- Auto-resolve classifier (binary) ---
        autoresolve_oof = np.zeros(len(y_autoresolve))
        for tr_idx, val_idx in skf.split(df, y_autoresolve):
            clf2 = lgb.LGBMClassifier(**LGBM_AUTORESOLVE_PARAMS)
            clf2.fit(df.iloc[tr_idx], y_autoresolve[tr_idx],
                     categorical_feature=CATEGORICAL_FEATURES)
            autoresolve_oof[val_idx] = clf2.predict_proba(df.iloc[val_idx])[:, 1]

        autoresolve_auc = float(roc_auc_score(y_autoresolve, autoresolve_oof))
        mlflow.log_metric("cv_autoresolve_auc", autoresolve_auc)

        autoresolve_model = lgb.LGBMClassifier(**LGBM_AUTORESOLVE_PARAMS)
        autoresolve_model.fit(df, y_autoresolve, categorical_feature=CATEGORICAL_FEATURES)
        mlflow.sklearn.log_model(
            autoresolve_model,
            artifact_path="autoresolve_model",
            registered_model_name=f"{settings.model_registry_name}-autoresolve",
        )

    return {
        "severity_accuracy": severity_acc,
        "autoresolve_auc": autoresolve_auc,
        "mlflow_run_id": run.info.run_id,
        "n_samples": len(incidents),
        "model_version": model_version,
    }
