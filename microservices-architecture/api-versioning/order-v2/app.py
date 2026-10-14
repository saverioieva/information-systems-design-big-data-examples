from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

API_MAJOR_VERSION = "2"
SERVICE_VERSION = "2.0.0"
MEDIA_TYPE = "application/vnd.ftgo.order.v2+json"

app = FastAPI(
    title="FTGO Order API v2",
    description="Breaking v2 contract of the FTGO Order API.",
    version=SERVICE_VERSION,
)

ORDERS = {
    "123": {
        "id": "123",
        "orderStatus": "CREATED",
        "totalAmount": {"value": 42.50, "currency": "EUR"},
        "delivery": {"eta": "08:05"},
    }
}


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
    return {
        "apiMajorVersion": API_MAJOR_VERSION,
        "serviceVersion": SERVICE_VERSION,
        "mediaType": MEDIA_TYPE,
        "compatibility": "breaking change from v1",
        "changes": [
            "status renamed to orderStatus",
            "total changed from a number to totalAmount {value, currency}",
            "delivery data grouped under delivery",
        ],
    }


@app.get("/orders/{order_id}")
def get_order(order_id: str, request: Request):
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    headers = response_headers()
    if MEDIA_TYPE in request.headers.get("accept", ""):
        headers["Vary"] = "Accept"
        return JSONResponse(content=order, media_type=MEDIA_TYPE, headers=headers)

    return JSONResponse(content=order, media_type="application/json", headers=headers)
