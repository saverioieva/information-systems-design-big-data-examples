from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

API_VERSION = "2.0.0"

app = FastAPI(
    title="FTGO Order API v2",
    description="Breaking v2 contract of the FTGO Order API.",
    version=API_VERSION,
)

ORDERS = {
    "123": {
        "id": "123",
        "orderStatus": "CREATED",
        "totalAmount": {"value": 42.50, "currency": "EUR"},
        "delivery": {"eta": "18:30"},
    }
}


class Money(BaseModel):
    value: float
    currency: str


class Delivery(BaseModel):
    eta: str | None = None


class OrderV2(BaseModel):
    id: str
    orderStatus: str
    totalAmount: Money
    delivery: Delivery


@app.get("/health")
def health():
    return {"status": "ok", "apiVersion": API_VERSION}


@app.get("/contract")
def contract():
    return {
        "major": 2,
        "semanticVersion": API_VERSION,
        "compatibility": "breaking change from v1",
        "changes": [
            "status renamed to orderStatus",
            "total changed from a number to totalAmount {value, currency}",
            "delivery data grouped under delivery",
        ],
    }


@app.get("/orders/{order_id}", response_model=OrderV2)
def get_order(order_id: str, response: Response):
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    response.headers["X-API-Version"] = API_VERSION
    return order
