from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Consumer-First API Example",
    description="A small teaching example showing how API responses can be shaped around consumer needs.",
    version="1.0.0",
)

# Internal application data. Some fields are implementation details and should
# not automatically become part of a public consumer contract.
CUSTOMERS = {
    42: {
        "id": 42,
        "first_name": "Alice",
        "last_name": "Brown",
        "email": "alice@example.com",
        "birth_date": "1990-05-20",
        "internal_risk_score": 73,
        "database_version": 18,
        "policy_id": "P123",
        "policy_status": "ACTIVE",
        "next_payment_eur": 120.00,
    }
}


def get_customer(customer_id: int) -> dict:
    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@app.get("/implementation-first/customers/{customer_id}")
def implementation_first(customer_id: int):
    """Bad teaching example: expose the internal data structure directly."""
    return get_customer(customer_id)


@app.get("/consumer-first/mobile/customers/{customer_id}")
def mobile_customer_summary(customer_id: int):
    """Response shaped around the information needed by the mobile UI."""
    customer = get_customer(customer_id)
    return {
        "name": f"{customer['first_name']} {customer['last_name']}",
        "policy_status": customer["policy_status"],
        "next_payment_eur": customer["next_payment_eur"],
    }


@app.get("/consumer-first/support/customers/{customer_id}")
def support_customer_view(customer_id: int):
    """Response shaped around the information needed by a support operator."""
    customer = get_customer(customer_id)
    return {
        "customer_id": customer["id"],
        "name": f"{customer['first_name']} {customer['last_name']}",
        "email": customer["email"],
        "policy_id": customer["policy_id"],
        "policy_status": customer["policy_status"],
    }
