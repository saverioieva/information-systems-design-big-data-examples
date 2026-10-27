"""Compose entry point for the inbound RabbitMQ adapter."""
from app.adapters.inbound.validation_consumer import main

if __name__ == "__main__":
    main()
