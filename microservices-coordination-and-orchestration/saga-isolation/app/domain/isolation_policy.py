"""Risk-based selection (By Value) from the isolation lecture.

This simplified policy selects between local saga countermeasures; it does NOT
implement a distributed ACID transaction or a payment risk model.
"""
RISK_THRESHOLD = 75.0


def select_isolation_mode(amount: float) -> str:
    """High-value orders serialize cancellation; lower-value orders recheck state."""
    return 'semantic' if amount >= RISK_THRESHOLD else 'reread'
