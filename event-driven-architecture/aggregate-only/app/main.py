"""Composition root: choose the concrete outbound adapter here, not in routes."""
import time
from fastapi import FastAPI
from app.application.order_service import OrderService
from app.adapters.inbound.http_api import create_router
from app.adapters.outbound.sqlalchemy_uow import SqlAlchemyUnitOfWork
from app.infrastructure.db import Base, engine, SessionLocal
import app.infrastructure.orm_models  # noqa: F401


def create_app(service: OrderService | None = None) -> FastAPI:
    app = FastAPI(title="Order Service - Aggregate-Only (Hexagonal)")
    service = service or OrderService(lambda: SqlAlchemyUnitOfWork(SessionLocal))
    app.include_router(create_router(service))
    @app.on_event("startup")
    def on_startup():
        for attempt in range(1, 11):
            try:
                Base.metadata.create_all(bind=engine)
                return
            except Exception:
                if attempt == 10:
                    raise
                time.sleep(2)
    return app

app = create_app()
