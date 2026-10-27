"""RabbitMQ routing contract shared by the publisher and consumer adapters."""
EXCHANGE = "outbox.events"
QUEUE = "outbox.audit"
ROUTING_KEY = "order.created"
