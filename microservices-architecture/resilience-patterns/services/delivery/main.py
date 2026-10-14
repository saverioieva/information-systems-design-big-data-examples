from fastapi import FastAPI, HTTPException
from common.fault_control import FaultController

app = FastAPI(title="Delivery Service")
faults = FaultController()

DELIVERIES = {
    "1001": {
        "orderId": "1001",
        "deliveryId": "D-5001",
        "etaMinutes": 25,
        "status": "PICKED_UP",
    }
}

@app.get("/deliveries/{order_id}")
async def get_delivery(order_id: str):
    await faults.before_request()
    delivery = DELIVERIES.get(order_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery

@app.get("/health")
async def health():
    return {"status": "ok", "service": "delivery"}

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
