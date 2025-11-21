"""
Incident ingestion and training trigger routes.
POST /incidents/         — store a historical incident for training
GET  /incidents/{id}     — retrieve one incident
GET  /incidents/         — list incidents
POST /training/start     — start a model training run (runs inline, not via Celery)
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from alertiq.config import Settings, get_settings
from alertiq.db.session import get_db
from alertiq.db.models import Incident, TrainingRun
from alertiq.api.schemas import IncidentCreate, TrainingRunResponse
from alertiq.ml.predictor import AlertPredictor

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("/", status_code=201)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    if db.get(Incident, payload.id):
        raise HTTPException(status_code=409, detail="Incident already exists")
    incident = Incident(**payload.model_dump())
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/{incident_id}")
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("/")
def list_incidents(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Incident).order_by(Incident.started_at.desc()).limit(limit).all()


@router.post("/training/start", response_model=TrainingRunResponse, status_code=202)
def start_training(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Train severity + auto-resolve classifiers on all stored incidents.
    Runs synchronously (unlike ShipSentinel which uses Celery — AlertIQ is
    lighter-weight and training completes in seconds on typical incident volumes).
    Returns the completed TrainingRun record.
    """
    import uuid
    from alertiq.ml.trainer import train, InsufficientDataError as _IDE
    from alertiq.ml.data import InsufficientDataError

    run = TrainingRun(
        model_version=f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        result = train(session=db, settings=settings)
        run.status = "completed"
        run.metrics = {
            "severity_accuracy": result["severity_accuracy"],
            "autoresolve_auc": result["autoresolve_auc"],
        }
        run.n_train_samples = result["n_samples"]
        run.completed_at = datetime.utcnow()
        db.commit()
        AlertPredictor.reset()
    except InsufficientDataError as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=500, detail=f"Training failed: {exc}")

    db.refresh(run)
    return run
