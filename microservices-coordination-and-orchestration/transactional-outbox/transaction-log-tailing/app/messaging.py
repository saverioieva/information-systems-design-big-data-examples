"""Stable CLI entry point to RabbitMQ inbound adapter."""
from app.adapters.inbound.rabbitmq_consumer import consumer, topology

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2 or sys.argv[1] not in {"topology", "consumer"}:
        raise SystemExit("Usage: python -m app.messaging topology|consumer")
    globals()[sys.argv[1]]()
