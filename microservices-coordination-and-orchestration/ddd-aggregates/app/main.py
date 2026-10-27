# app/main.py

import time
from fastapi import FastAPI

from app.infrastructure.db import Base, engine
import app.infrastructure.orm_models  # noqa: F401
from app.adapters.inbound.http_api import router as orders_router

app = FastAPI(title="DDD Aggregates — Hexagonal Order Service (version_id optimistic locking)")


@app.on_event("startup")
def on_startup():
    """Initialize database schema with simple retry logic."""
    max_retries = 10
    delay_seconds = 2

    for attempt in range(1, max_retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database schema created/verified.")
            break
        except Exception as exc:
            print(f"DB not ready yet (attempt {attempt}/{max_retries}): {exc}")
            if attempt == max_retries:
                # Last attempt: re-raise so we see the real error
                raise
            time.sleep(delay_seconds)


app.include_router(orders_router)
