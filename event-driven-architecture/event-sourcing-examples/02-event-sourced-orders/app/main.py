"""Composition root: API -> service -> port -> eventsourcing framework adapter."""
from fastapi import FastAPI
from app.application.order_service import OrderService
from app.adapters.inbound.http_api import create_router
from app.adapters.outbound.eventsourcing_store import EventsourcingOrderStore


def create_app(service: OrderService | None = None) -> FastAPI:
    service = service or OrderService(EventsourcingOrderStore())
    app = FastAPI(title="Orders Event Sourcing Service (Hexagonal)")
    app.include_router(create_router(service))
    return app

app = create_app()
