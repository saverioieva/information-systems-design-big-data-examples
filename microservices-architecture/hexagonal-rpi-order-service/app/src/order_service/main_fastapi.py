from contextlib import asynccontextmanager

from fastapi import FastAPI

from order_service.adapters.inbound.fastapi.routes import build_order_router
from order_service.adapters.outbound.postgres.repository import PostgresOrderRepository
from order_service.application.services.order_service import OrderApplicationService
from order_service.infrastructure.database import SessionFactory, create_schema


# Composition root for the FastAPI inbound adapter.
repository = PostgresOrderRepository(SessionFactory)
order_service = OrderApplicationService(repository)


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    yield


app = FastAPI(
    title="Order Service API - FastAPI Adapter",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(build_order_router(order_service))


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok", "adapter": "fastapi"}
