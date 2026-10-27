"""Pure domain policy: deciding the final order state."""
def order_status(consumer_check: str, restaurant_check: str) -> str:
    checks = (consumer_check, restaurant_check)
    if "FAIL" in checks:
        return "REJECTED"
    if checks == ("PASS", "PASS"):
        return "VALIDATED"
    return "PENDING"
