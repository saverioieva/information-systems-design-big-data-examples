from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="FTGO Courier Service — DDD Example",
    description="Courier bounded context with its own model and vocabulary.",
    version="1.0.0",
)

couriers: dict[int, dict] = {}


class CourierCreate(BaseModel):
    name: str


class AvailabilityUpdate(BaseModel):
    available: bool


@app.get("/architecture")
def architecture():
    return {
        "strategy": "decompose by subdomain / bounded context",
        "subdomain": "Courier",
        "service": "Courier Service",
        "domain_concepts": ["Courier", "Availability", "DeliveryAssignment"],
    }


@app.post("/couriers")
def create_courier(payload: CourierCreate):
    courier_id = len(couriers) + 1
    courier = {"id": courier_id, "name": payload.name, "available": False}
    couriers[courier_id] = courier
    return courier


@app.patch("/couriers/{courier_id}/availability")
def update_availability(courier_id: int, payload: AvailabilityUpdate):
    courier = couriers.get(courier_id)
    if courier is None:
        raise HTTPException(status_code=404, detail="Courier not found")
    courier["available"] = payload.available
    return courier


@app.get("/couriers/{courier_id}")
def get_courier(courier_id: int):
    courier = couriers.get(courier_id)
    if courier is None:
        raise HTTPException(status_code=404, detail="Courier not found")
    return courier
