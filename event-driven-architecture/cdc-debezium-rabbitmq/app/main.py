"""Composition root for FastAPI and SQL adapter; broker publishing is NOT in this process."""
import os
from fastapi import FastAPI
from app.adapters.outbound.postgres_store import PostgresOrderStore
from app.adapters.inbound.http_api import make_router
from app.application.order_service import OrderService

store = PostgresOrderStore(os.getenv('DATABASE_URL','postgresql+psycopg://demo:demo@postgres:5432/orders'))
service = OrderService(store)
app = FastAPI(title='Chapter 5 CDC and Integration Events')
app.include_router(make_router(service))
