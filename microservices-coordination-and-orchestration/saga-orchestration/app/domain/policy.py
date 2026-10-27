"""Pure participant business decisions."""
def consumer_approved(customer_id: str) -> bool:
    return customer_id != 'CUST_INVALID'

def card_authorized(amount: float) -> bool:
    return float(amount) <= 100.0
