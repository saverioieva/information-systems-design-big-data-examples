from fastapi import FastAPI, HTTPException
from common.fault_control import FaultController

app = FastAPI(title="Kitchen Service")
faults = FaultController()

TICKETS = {
    "1001": {
        "orderId": "1001",
        "ticketId": "K-9001",
        "status": "IN_PREP",
        "station": "PIZZA",
    },
    "1002": {
        "orderId": "1002",
        "ticketId": "K-9002",
        "status": "QUEUED",
        "station": "GRILL",
    },
}

@app.get("/tickets/{order_id}")
async def get_ticket(order_id: str):
    await faults.before_request()
    ticket = TICKETS.get(order_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@app.get("/health")
async def health():
    return {"status": "ok", "service": "kitchen"}

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
