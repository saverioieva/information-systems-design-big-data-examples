"""Single source of truth for Saga Choreography RabbitMQ event routing.

Each bounded context owns one durable *topic exchange*. Routing keys describe
the event type; subscriber queues can bind to more than one exchange.
"""

TOPIC_EXCHANGES = {
    "order": "orders.events",
    "consumer": "consumers.events",
    "kitchen": "kitchen.events",
    "accounting": "accounting.events",
}

EVENT_EXCHANGES = {
    "order.created": TOPIC_EXCHANGES["order"],
    "order.approved": TOPIC_EXCHANGES["order"],
    "order.rejected": TOPIC_EXCHANGES["order"],
    "consumer.verified": TOPIC_EXCHANGES["consumer"],
    "consumer.verificationFailed": TOPIC_EXCHANGES["consumer"],
    "kitchen.ticketCreated": TOPIC_EXCHANGES["kitchen"],
    "kitchen.ticketRejected": TOPIC_EXCHANGES["kitchen"],
    "accounting.creditCardAuthorized": TOPIC_EXCHANGES["accounting"],
    "accounting.creditCardAuthorizationFailed": TOPIC_EXCHANGES["accounting"],
}

QUEUE_BINDINGS = {
    "consumer.q": ["order.created"],
    "kitchen.q": ["order.created", "accounting.creditCardAuthorized", "accounting.creditCardAuthorizationFailed"],
    "accounting.q": ["order.created", "consumer.verified", "consumer.verificationFailed", "kitchen.ticketCreated"],
    "order.q": ["accounting.creditCardAuthorized", "accounting.creditCardAuthorizationFailed"],
    "audit.q": ["order.approved", "order.rejected", "kitchen.ticketRejected"],
}

def exchange_for_route(routing_key: str) -> str:
    """Resolve a known event to its bounded-context exchange; fail on typos."""
    try:
        return EVENT_EXCHANGES[routing_key]
    except KeyError as exc:
        raise ValueError(f"Unknown saga routing key: {routing_key}") from exc
