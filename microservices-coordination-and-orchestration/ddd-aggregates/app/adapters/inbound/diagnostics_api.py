"""Read-only teaching endpoint: inspect publication intents (not a broker)."""
from fastapi import APIRouter
from sqlalchemy import select
from app.infrastructure.db import SessionLocal
from app.infrastructure.orm_models import IntegrationOutboxModel

router = APIRouter(prefix="/lab", tags=["lab-observability"])

@router.get("/outbox")
def get_outbox():
    with SessionLocal() as session:
        records = session.execute(
            select(IntegrationOutboxModel).order_by(IntegrationOutboxModel.created_at)
        ).scalars().all()
        return [
            {
                "eventId": item.event_id,
                "aggregateId": item.aggregate_id,
                "eventType": item.event_type,
                "payload": item.payload,
                "createdAt": item.created_at.isoformat(),
            }
            for item in records
        ]
