"""
Singleton alert predictor — loads severity + auto-resolve classifiers from MLflow.
Thread-safe via double-checked locking.
Call AlertPredictor.reset() after training so the next request reloads.
"""
import threading

import mlflow.sklearn
import numpy as np
import pandas as pd

from alertiq.config import Settings
from alertiq.ml.features import ALL_FEATURES, CATEGORICAL_FEATURES, SEVERITY_ORDER


class ModelNotLoadedError(Exception):
    """Raised when predict() cannot load models (registry empty)."""


class AlertPredictor:
    _instance: "AlertPredictor | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._severity_model = None      # LGBMClassifier (4-class)
        self._autoresolve_model = None   # LGBMClassifier (binary)
        self._model_version: str | None = None

    # --- Singleton lifecycle ---

    @classmethod
    def get(cls) -> "AlertPredictor":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Invalidate singleton so the next predict() reloads from registry."""
        with cls._lock:
            cls._instance = None

    # --- Model loading ---

    def load(self, settings: Settings) -> None:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        self._severity_model = mlflow.sklearn.load_model(
            f"models:/{settings.model_registry_name}-severity/latest"
        )
        self._autoresolve_model = mlflow.sklearn.load_model(
            f"models:/{settings.model_registry_name}-autoresolve/latest"
        )
        self._model_version = settings.model_registry_name

    def is_loaded(self) -> bool:
        return self._severity_model is not None and self._autoresolve_model is not None

    @property
    def model_version(self) -> str:
        return self._model_version or "unknown"

    # --- Inference ---

    def predict(self, feature_row: dict, settings: Settings) -> dict:
        """
        Returns prediction dict matching AlertPredictionResponse fields.
        Lazily loads models from MLflow on the first call.

        Raises ModelNotLoadedError if no registered models exist.
        """
        if not self.is_loaded():
            try:
                self.load(settings)
            except Exception as exc:
                raise ModelNotLoadedError(
                    f"Could not load models from MLflow: {exc}"
                ) from exc

        df = pd.DataFrame([feature_row])
        for col in CATEGORICAL_FEATURES:
            if col in df.columns:
                df[col] = df[col].astype("category")
        df = df[ALL_FEATURES]

        # Severity — 4-class, return highest-confidence class
        severity_idx = int(self._severity_model.predict(df)[0])
        severity_proba = self._severity_model.predict_proba(df)[0]
        predicted_severity = SEVERITY_ORDER[severity_idx]
        severity_confidence = float(np.max(severity_proba))

        # Auto-resolve — binary probability threshold
        autoresolve_prob = float(self._autoresolve_model.predict_proba(df)[0, 1])
        predicted_auto_resolve = autoresolve_prob >= settings.severity_threshold

        return {
            "predicted_severity": predicted_severity,
            "predicted_category": None,          # Phase 3: root-cause classifier
            "predicted_auto_resolve": predicted_auto_resolve,
            "severity_confidence": severity_confidence,
        }
