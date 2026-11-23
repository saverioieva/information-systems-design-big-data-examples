"""HTTP entry points expose only data owned by the current service."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from time import sleep

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from lab.handlers import create_order
from lab.messaging import MessageWorker
from lab.storage import EventStore
from lab.read_model import QueryStore
from lab.query_api import router as query_router

ROLE = os.getenv("SERVICE_ROLE", "order")
log = logging.getLogger(__name__)


class Item(BaseModel):
    menu_item_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    quantity: int = Field(gt=0)


class CreateOrder(BaseModel):
    consumer_id: str = Field(min_length=1)
    restaurant_id: str = Field(min_length=1)
    items: list[Item] = Field(min_length=1)
    reject_kitchen: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = QueryStore() if ROLE == "query" else EventStore()
    for attempt in range(30):
        try:
            db.ensure_schema()
            break
        except Exception:
            if attempt == 29:
                raise
            sleep(1)
    worker = MessageWorker(ROLE, None if ROLE == "query" else db, db if ROLE == "query" else None)
    worker.start()
    if ROLE == "query":
        app.state.query_store = db
    else:
        app.state.event_store = db
    app.state.worker = worker
    yield
    worker.stop()


app = FastAPI(title=f"Event-Sourced Saga + CQRS — {ROLE}", lifespan=lifespan)
if ROLE == "query":
    app.include_router(query_router)


def _store() -> EventStore:
    return app.state.event_store


def _get(role: str, stream: str):
    state, history = _store().read(role, stream)
    if not state["exists"]:
        raise HTTPException(status_code=404, detail="Aggregate not found")
    return state, history


@app.get("/health")
def health():
    return {"status": "ok", "service": ROLE}


@app.post("/orders", status_code=201)
def post_order(payload: CreateOrder):
    if ROLE != "order":
        raise HTTPException(status_code=404)
    try:
        return create_order(_store(), payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/orders/{order_id}")
def order(order_id: str):
    if ROLE != "order":
        raise HTTPException(status_code=404)
    return _get("order", order_id)[0]


@app.get("/internal/orders/{order_id}")
def internal_order(order_id: str):
    if ROLE != "order":
        raise HTTPException(status_code=404)
    return _get("order", order_id)[0]


@app.get("/internal/authorizations/{order_id}")
def internal_authorization(order_id: str):
    if ROLE != "accounting":
        raise HTTPException(status_code=404)
    return _get("accounting", order_id)[0]


@app.get("/internal/tickets/{order_id}")
def internal_ticket(order_id: str):
    if ROLE != "kitchen":
        raise HTTPException(status_code=404)
    return _get("kitchen", order_id)[0]


@app.get("/sagas/{order_id}")
def saga(order_id: str):
    if ROLE != "orchestrator":
        raise HTTPException(status_code=404)
    return _get("orchestrator", f"saga:{order_id}")[0]


@app.get("/events/{order_id}")
def events(order_id: str):
    if ROLE == "query":
        raise HTTPException(status_code=404)
    if ROLE == "orchestrator":
        stream = f"saga:{order_id}"
    else:
        stream = order_id
    return {"service": ROLE, "aggregate_id": stream,
            "events": _get(ROLE, stream)[1]}


@app.get("/internal/stats")
def stats():
    if ROLE == "query":
        return {"service": ROLE, **app.state.query_store.stats()}
    return {"service": ROLE, **_store().stats()}


@app.post("/internal/requeue-integration")
def requeue_integration():
    if os.getenv("LAB_ADMIN_ENABLED", "0") != "1":
        raise HTTPException(status_code=403, detail="Demo admin endpoint disabled")
    return {"service": ROLE, "requeued": _store().requeue_integration()}
