# Cohesion and Coupling

## Goal

Compare four small Python designs:

- high cohesion;
- low cohesion;
- tight coupling;
- loose coupling.

No third-party Python packages are required.

## Run with Python

```bash
cd cohesion-coupling
python app.py
```

The four cases produce similar results. The important difference is how the
classes are organized and how they depend on each other.

## High and low cohesion

`high_cohesion.py` keeps order, payment, and notification responsibilities in
separate classes.

`low_cohesion.py` puts all three responsibilities inside one `OrderManager`
class.

## Tight and loose coupling

`tight_coupling.py` creates a `CardPaymentService` directly inside
`CheckoutService`.

`loose_coupling.py` receives the payment service from outside, so the same
checkout code can use either card or cash payment.

## What to observe

- High cohesion keeps related behavior together.
- Low cohesion mixes responsibilities that can change for different reasons.
- Tight coupling depends directly on a concrete collaborator.
- Loose coupling makes a collaborator easier to replace.

## Run with Docker

```bash
docker compose up --build
```

The container prints the four cases and exits.

## Clean up

```bash
docker compose down
```
