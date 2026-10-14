from fastapi import FastAPI, HTTPException
from common.fault_control import FaultController

app = FastAPI(title="Payment Service")
faults = FaultController()

PAYMENTS = {
    "1001": {
        "orderId": "1001",
        "paymentId": "P-7001",
        "amount": 21.50,
        "currency": "EUR",
        "method": "CARD",
        "status": "PAID",
    },
    "1002": {
        "orderId": "1002",
        "paymentId": "P-7002",
        "amount": 9.90,
        "currency": "EUR",
        "method": "CASH",
        "status": "PENDING",
    },
}

@app.get("/payments/{order_id}")
async def get_payment(order_id: str):
    await faults.before_request()
    payment = PAYMENTS.get(order_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

@app.get("/health")
async def health():
    return {"status": "ok", "service": "payment"}

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
