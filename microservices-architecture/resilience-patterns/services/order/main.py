from fastapi import FastAPI, HTTPException
from common.fault_control import FaultController

app = FastAPI(title="Order Service")
faults = FaultController()

ORDERS = {
    "1001": {
        "orderId": "1001",
        "items": [
            {"sku": "PIZZA_MARGHERITA", "qty": 1},
            {"sku": "COLA_CAN", "qty": 2},
        ],
        "status": "CONFIRMED",
    },
    "1002": {
        "orderId": "1002",
        "items": [{"sku": "BURGER_CLASSIC", "qty": 1}],
        "status": "PREPARING",
    },
}

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    await faults.before_request()
    order = ORDERS.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/health")
async def health():
    return {"status": "ok", "service": "order"}

@app.get("/admin/state")
async def admin_state():
    return faults.snapshot()

@app.post("/admin/reset")
async def admin_reset():
    return await faults.reset()

@app.post("/admin/delay/{delay_ms}")
async def admin_delay(delay_ms: int):
    return await faults.set_delay(delay_ms)

@app.post("/admin/fail-next/{count}")
async def admin_fail_next(count: int):
    return await faults.fail_next(count)
