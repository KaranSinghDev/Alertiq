from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from alertiq.db.session import get_db
from alertiq.api.schemas import AlertWebhookPayload, AlertPredictionResponse

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/alert", response_model=AlertPredictionResponse)
def receive_alert(payload: AlertWebhookPayload, db: Session = Depends(get_db)):
    """
    Prometheus AlertManager / PagerDuty webhook endpoint.
    Receives a firing alert and returns a severity prediction.
    Predictor wired in Phase 2.
    """
    raise HTTPException(status_code=503, detail="No trained model available")
