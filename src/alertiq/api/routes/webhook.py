"""
Prometheus AlertManager / PagerDuty webhook endpoint.
Receives a firing alert and returns ML-powered severity + auto-resolve prediction.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from alertiq.config import Settings, get_settings
from alertiq.db.session import get_db
from alertiq.db.models import AlertPrediction
from alertiq.api.schemas import AlertWebhookPayload, AlertPredictionResponse
from alertiq.ml.features import build_feature_row
from alertiq.ml.predictor import AlertPredictor, ModelNotLoadedError

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/alert", response_model=AlertPredictionResponse, status_code=201)
def receive_alert(
    payload: AlertWebhookPayload,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Receive a firing alert and return severity + auto-resolve prediction.
    AlertManager calls this as a webhook_configs target.
    Returns 503 until at least one training run completes.
    """
    predictor = AlertPredictor.get()
    feature_row = build_feature_row({
        "alert_name": payload.alert_name,
        "service": payload.service,
        "environment": payload.environment,
        "alert_count_in_window": payload.alert_count_in_window,
        "started_at": payload.fired_at,
    })

    try:
        result = predictor.predict(feature_row, settings)
    except ModelNotLoadedError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No trained model available. Ingest incidents and POST /training/start. ({exc})",
        )

    prediction = AlertPrediction(
        alert_name=payload.alert_name,
        service=payload.service,
        environment=payload.environment,
        model_version=predictor.model_version,
        feature_snapshot=feature_row,
        **result,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction
