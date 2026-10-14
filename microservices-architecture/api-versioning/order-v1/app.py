import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

API_MAJOR_VERSION = "1"
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.1.1")
MEDIA_TYPE = "application/vnd.ftgo.order.v1+json"
SUPPORTED_SERVICE_VERSIONS = {"1.0.0", "1.1.0", "1.1.1"}

if SERVICE_VERSION not in SUPPORTED_SERVICE_VERSIONS:
    raise RuntimeError(
        f"Unsupported SERVICE_VERSION={SERVICE_VERSION!r}. "
        f"Expected one of {sorted(SUPPORTED_SERVICE_VERSIONS)}"
    )

app = FastAPI(
    title="FTGO Order API v1",
    description="Compatible releases of the FTGO Order API v1 contract.",
    version=SERVICE_VERSION,
)

BASE_ORDERS = {
    "123": {
        "id": "123",
        "status": "CREATED",
        "total": 42.50,
    }
}


def build_order(order_id: str) -> dict:
    order = BASE_ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    representation = dict(order)

    # 1.0.0: original v1 representation.
    # 1.1.0: backward-compatible MINOR addition, but with a formatting bug.
    # 1.1.1: PATCH fix; same fields and same public v1 contract as 1.1.0.
    if SERVICE_VERSION == "1.1.0":
        representation["deliveryEta"] = "8:05"
    elif SERVICE_VERSION == "1.1.1":
        representation["deliveryEta"] = "08:05"

    return representation


def response_headers() -> dict[str, str]:
    return {
        "X-API-Version": API_MAJOR_VERSION,
        "X-Service-Version": SERVICE_VERSION,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "apiVersion": API_MAJOR_VERSION,
        "serviceVersion": SERVICE_VERSION,
    }


@app.get("/contract")
def contract():
    fields = ["id", "status", "total"]
    if SERVICE_VERSION in {"1.1.0", "1.1.1"}:
        fields.append("deliveryEta?")

    release_change = {
        "1.0.0": "original v1 contract",
        "1.1.0": "MINOR: optional deliveryEta added; existing v1 clients remain compatible",
        "1.1.1": "PATCH: deliveryEta formatting bug fixed; response schema unchanged from 1.1.0",
    }[SERVICE_VERSION]

    return {
        "apiMajorVersion": API_MAJOR_VERSION,
        "serviceVersion": SERVICE_VERSION,
        "mediaType": MEDIA_TYPE,
        "compatibility": "backward-compatible within v1",
        "releaseChange": release_change,
        "fields": fields,
    }


@app.get("/orders/{order_id}")
def get_order(order_id: str, request: Request):
    order = build_order(order_id)
    headers = response_headers()

    # When selected through content negotiation, return the negotiated vendor
    # media type and make the response cache-aware with Vary: Accept.
    if MEDIA_TYPE in request.headers.get("accept", ""):
        headers["Vary"] = "Accept"
        return JSONResponse(content=order, media_type=MEDIA_TYPE, headers=headers)

    return JSONResponse(content=order, media_type="application/json", headers=headers)
