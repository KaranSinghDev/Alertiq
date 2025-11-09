from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from alertiq.db.session import get_db
from alertiq.db.models import Incident
from alertiq.api.schemas import IncidentCreate

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
