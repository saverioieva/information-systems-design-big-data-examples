from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

API_VERSION = "1.1.0"
MEDIA_TYPE = "application/vnd.ftgo.order.v1+json"

app = FastAPI(
    title="FTGO Order API v1",
    description="Backward-compatible evolution of the FTGO Order API v1 contract.",
    version=API_VERSION,
)

ORDERS = {
    "123": {
        "id": "123",
        "status": "CREATED",
        "total": 42.50,
        # Added in 1.1.0. Old v1 clients can ignore this optional field.
        "deliveryEta": "18:30",
    }
}


class OrderV1(BaseModel):
    id: str
    status: str
    total: float
    deliveryEta: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "apiVersion": API_VERSION}


@app.get("/contract")
def contract():
    return {
        "major": 1,
        "semanticVersion": API_VERSION,
        "mediaType": MEDIA_TYPE,
        "compatibility": "backward-compatible within v1",
        "fields": ["id", "status", "total", "deliveryEta?"],
    }


@app.get("/orders/{order_id}", response_model=OrderV1)
def get_order(order_id: str, request: Request, response: Response):
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # When this service was selected through content negotiation, return the
    # negotiated vendor media type and tell HTTP caches that Accept matters.
    if MEDIA_TYPE in request.headers.get("accept", ""):
        return JSONResponse(
            content=order,
            media_type=MEDIA_TYPE,
            headers={"X-API-Version": API_VERSION, "Vary": "Accept"},
        )

    response.headers["X-API-Version"] = API_VERSION
    return order
