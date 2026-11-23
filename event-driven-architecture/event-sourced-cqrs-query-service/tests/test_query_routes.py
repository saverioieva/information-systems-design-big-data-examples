import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from lab import query_api


def test_api_composition_makes_three_live_calls(monkeypatch):
    touched = []

    def respond(req):
        touched.append(req.url.host)
        if req.url.host == "order":
            return httpx.Response(200, json={"consumer_id": "c", "restaurant_id": "r", "total": 18,
                                             "status": "APPROVED"})
        if req.url.host == "accounting":
            return httpx.Response(200, json={"status": "AUTHORIZED"})
        return httpx.Response(200, json={"status": "ACCEPTED"})

    original = httpx.AsyncClient
    monkeypatch.setattr(query_api.httpx, "AsyncClient", lambda **kwargs: original(
        transport=httpx.MockTransport(respond), **kwargs))
    result = asyncio.run(query_api.find_order_by_composition("order-1"))
    assert sorted(touched) == ["accounting", "kitchen", "order"]
    assert result["order_status"] == "APPROVED"
    assert result["strategy"] == "API_COMPOSITION"


def test_api_composition_fails_if_kitchen_api_is_down(monkeypatch):
    def respond(req):
        if req.url.host == "kitchen":
            raise httpx.ConnectError("Kitchen unavailable")
        if req.url.host == "order":
            return httpx.Response(200, json={"consumer_id": "c", "restaurant_id": "r", "total": 18,
                                             "status": "APPROVED"})
        return httpx.Response(200, json={"status": "AUTHORIZED"})

    original = httpx.AsyncClient
    monkeypatch.setattr(query_api.httpx, "AsyncClient", lambda **kwargs: original(
        transport=httpx.MockTransport(respond), **kwargs))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(query_api.find_order_by_composition("order-1"))
    assert exc.value.status_code == 503
    assert "kitchen" in exc.value.detail["failures"]


def test_cqrs_uses_only_its_local_database():
    class StubReadDB:
        def find_order(self, oid):
            assert oid == "order-1"
            return {"order_id": oid, "order_status": "APPROVED", "payment_status": "AUTHORIZED",
                    "kitchen_status": "ACCEPTED", "source_versions": {"order": 2}}

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(query_store=StubReadDB())))
    response = query_api.find_order_by_cqrs("order-1", request)
    assert response["strategy"] == "CQRS_PROJECTION"
    assert response["queried_services"] == []
