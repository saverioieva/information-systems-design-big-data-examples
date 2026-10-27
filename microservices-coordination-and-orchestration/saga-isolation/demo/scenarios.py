"""Deterministic saga interleavings; no database or message broker required.

This simulates observable business-level intermediate states across local commits.
It is NOT a demo of PostgreSQL's SQL isolation levels.
"""
from dataclasses import dataclass


@dataclass
class Order:
    state: str = "APPROVAL_PENDING"
    version: int = 0


class SemanticLockError(Exception):
    pass


class StaleReadError(Exception):
    pass


def cancel_naive(order: Order):
    order.state = "CANCELLED"
    order.version += 1


def approve_naive(order: Order):
    order.state = "APPROVED"  # ignores previously committed cancellation
    order.version += 1


def cancel_with_semantic_lock(order: Order):
    if order.state == "APPROVAL_PENDING":
        raise SemanticLockError("Order is part of an incomplete Create Order Saga")
    cancel_naive(order)


def approve_with_reread(order: Order):
    if order.state != "APPROVAL_PENDING":
        return False
    approve_naive(order)
    return True


def approve_with_version(order: Order, expected_version: int):
    if order.version != expected_version:
        raise StaleReadError("Order changed since the saga read it")
    if order.state != "APPROVAL_PENDING":
        raise StaleReadError("Order is not pending")
    approve_naive(order)


def apply_credit_delta(balance: int, delta: int) -> int:
    """Addition commutes; domain overdraft constraints are NOT modeled."""
    return balance + delta


def run():
    print("1. LOST UPDATE (unsafe last-write-wins)")
    order = Order()
    read_before = order.state
    cancel_naive(order)
    approve_naive(order)  # stale saga overwrites CANCELLED
    print(f"   Create saga read={read_before}; Cancel saga committed; final={order.state} (WRONG)")

    print("2. SEMANTIC LOCK (prevent cancellation during pending saga)")
    order = Order()
    try:
        cancel_with_semantic_lock(order)
    except SemanticLockError as exc:
        print("   Cancellation rejected:", exc)

    print("3. REREAD VALUE (verify state immediately before updating)")
    order = Order()
    cancel_naive(order)
    print("   Approved after cancel?", approve_with_reread(order), "final:", order.state)

    print("4. VERSION CHECK (optimistic concurrency)")
    order = Order()
    read_version = order.version
    cancel_naive(order)
    try:
        approve_with_version(order, read_version)
    except StaleReadError as exc:
        print("   Stale approval rejected:", exc)

    print("5. COMMUTATIVE OPERATIONS (order-independent balance deltas)")
    forward = apply_credit_delta(apply_credit_delta(100, 10), -5)
    backward = apply_credit_delta(apply_credit_delta(100, -5), 10)
    print(f"   credit(+10) then debit(-5) = {forward}; reverse order = {backward}")
    assert forward == backward == 105

if __name__ == '__main__':
    run()
