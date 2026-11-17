"""FastAPI composition root. One local Postgres transaction per write use case."""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import inspect
from app.infrastructure.db import Base, engine
import app.infrastructure.orm_models  # noqa: F401 - register SQLAlchemy metadata
from app.adapters.inbound.http_api import router as orders_router
from app.adapters.inbound.diagnostics_api import router as diagnostics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(1, 11):
        try:
            Base.metadata.create_all(bind=engine)
            columns = {column['name'] for column in inspect(engine).get_columns('orders')}
            if not {'delivery_street', 'delivery_city', 'delivery_postal_code',
                    'delivery_country'} <= columns:
                raise RuntimeError(
                    'Outdated DDD Aggregate schema. Back up the database and migrate '
                    'the orders table, or use `make reset` only if deleting data is acceptable.'
                )
            break
        except RuntimeError:
            raise
        except Exception:
            if attempt == 10:
                raise
            time.sleep(2)
    yield
    engine.dispose()


app = FastAPI(title="DDD Aggregates and Domain Events", lifespan=lifespan)
app.include_router(orders_router)
app.include_router(diagnostics_router)
