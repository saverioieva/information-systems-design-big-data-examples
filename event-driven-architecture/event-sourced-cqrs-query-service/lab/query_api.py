"""Order History Service: live API Composition versus Kafka-fed MongoDB CQRS."""
from __future__ import annotations

import asyncio
import os
import time

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

ENDPOINTS = {
    "order": (os.getenv("ORDER_INTERNAL_URL", "http://order:8000"), "/internal/orders/"),
    "accounting": (os.getenv("ACCOUNTING_INTERNAL_URL", "http://accounting:8000"), "/internal/authorizations/"),
    "kitchen": (os.getenv("KITCHEN_INTERNAL_URL", "http://kitchen:8000"), "/internal/tickets/"),
}


@router.get("/find-order/{order_id}/composition")
async def find_order_by_composition(order_id: str):
    """Live synchronous fan-out; failure of a dependency affects this request."""
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=httpx.Timeout(1.5)) as client:
        async def fetch(name, base_url, suffix):
            try:
                response = await client.get(base_url + suffix + order_id)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                return name, None, f"{type(exc).__name__}"
            if response.status_code == 404:
                return name, None, None
            if response.status_code != 200:
                return name, None, f"HTTP {response.status_code}"
            return name, response.json(), None

        results = await asyncio.gather(*(fetch(name, *endpoint) for name, endpoint in ENDPOINTS.items()))
    views = {name: data for name, data, _ in results}
    failures = {name: error for name, _, error in results if error}
    if failures:
        raise HTTPException(status_code=503,
                            detail={"reason": "API Composition dependency unavailable",
                                    "failures": failures,
                                    "note": "The CQRS read model has no runtime dependency on these APIs"})
    order = views["order"]
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order_id,
        "consumer_id": order["consumer_id"],
        "restaurant_id": order["restaurant_id"],
        "total": order["total"],
        "order_status": order["status"],
        "payment_status": views["accounting"]["status"] if views["accounting"] else "NOT_STARTED",
        "kitchen_status": views["kitchen"]["status"] if views["kitchen"] else "NOT_STARTED",
        "strategy": "API_COMPOSITION",
        "queried_services": list(ENDPOINTS),
        "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
    }


@router.get("/find-order/{order_id}/cqrs")
def find_order_by_cqrs(order_id: str, request: Request):
    """One MongoDB document read; no synchronous dependency on the source APIs."""
    start = time.perf_counter()
    view = request.app.state.query_store.find_order(order_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Projection not built yet or order not found")
    return {**view, "strategy": "CQRS_PROJECTION", "queried_services": [],
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2)}


@router.get("/order-history/{order_id}")
def get_order_history(order_id: str, request: Request):
    """Event timeline projected from Order, Accounting and Kitchen notifications."""
    history = request.app.state.query_store.history(order_id)
    if history is None:
        raise HTTPException(status_code=404, detail="History not yet projected or order not found")
    return history


@router.post("/internal/reset-projection")
def reset_projection(request: Request):
    if os.getenv("LAB_ADMIN_ENABLED", "0") != "1":
        raise HTTPException(status_code=403, detail="Demo admin endpoint disabled")
    request.app.state.query_store.reset()
    return {"reset": True, "note": "Authoritative Event Stores were not changed"}


@router.get("/internal/projection-stats")
def projection_stats(request: Request):
    return request.app.state.query_store.stats()
