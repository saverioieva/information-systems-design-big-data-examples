"""Compose entry point for the inbound RabbitMQ adapter."""
from app.adapters.inbound.results_consumer import main

if __name__ == "__main__":
    main()
