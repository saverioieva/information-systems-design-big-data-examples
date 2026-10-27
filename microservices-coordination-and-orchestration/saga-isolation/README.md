# Saga Isolation Countermeasures — Deterministic Interleavings

This small, **dependency-free Python lab** complements the slides **Handling the Lack of Isolation in Sagas**, **Lost Updates**, **Semantic Lock**, **Commutative Updates**, **Reread Value**, and **Version**.

It uses deterministic interleavings rather than an actual SQL database to show *business-level anomalies between separately committed saga steps*. It **does not** demonstrate dirty reads of uncommitted PostgreSQL transactions or a real distributed race.

## Learning objectives

- See how a Create Order Saga can approve a previously canceled order if it makes a decision using stale information.
- Compare a **semantic lock** (`APPROVAL_PENDING`), **reread-value** validation, and **optimistic concurrency version** checks.
- Understand commutative updates and their limits for operations constrained by business invariants.

## Run

```bash
make demo
make test
```

Expected progression:

```text
Lost update: Create reads PENDING -> Cancel commits CANCELLED -> Create writes APPROVED (incorrect)
Semantic lock: Cancel is refused/deferred while Order is APPROVAL_PENDING
Reread value: Create checks state and refuses to overwrite CANCELLED
Version: compare-and-swap rejects a stale update
Commutative: +10 then -5 yields the same as -5 then +10 (without overdraft rules)
```

### Exercises

1. In `demo/scenarios.py`, identify the stale read in `run()`.
2. Modify `approve_naive()` to include the pending-state check and repeat the demo.
3. Remove the version check from `approve_with_version()` and see what breaks.
4. Add an overdraft restriction to `apply_credit_delta()`. Does operation order still not matter? Explain the difference between numerical commutativity and domain constraints.
5. Discuss why a semantic lock can mean **reject-and-retry** rather than holding a database transaction open for the duration of the saga.

## Source reading order

| File | Concept |
|---|---|
| `demo/scenarios.py` — `cancel_naive/approve_naive` | Lost update |
| `cancel_with_semantic_lock` | Semantic lock |
| `approve_with_reread` | Reread value |
| `approve_with_version` | Optimistic concurrency version |
| `apply_credit_delta` | Commutative update |
| `tests/test_scenarios.py` | Executable assertions |

**Scope:** this lab is intentionally *not* a replacement for actual database isolation tests, distributed tracing, or an implementation of a Cancel Order Saga. Fuzzy/nonrepeatable business-level reads are described conceptually, not simulated here.
