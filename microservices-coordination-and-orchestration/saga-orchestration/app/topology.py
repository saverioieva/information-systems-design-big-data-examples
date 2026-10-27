"""One-off topology provisioning before producer and consumer processes start."""
from app.adapters.outbound.rabbitmq_transport import connect, EXCHANGE

conn = connect()
ch = conn.channel()
ch.exchange_declare(exchange=EXCHANGE,exchange_type="topic",durable=True)
for name, key in [("orchestrator","reply.orchestrator"),("consumer","command.consumer"),
                  ("kitchen","command.kitchen"),("accounting","command.accounting")]:
    queue=f"saga.{name}"
    ch.queue_declare(queue=queue,durable=True)
    ch.queue_bind(exchange=EXCHANGE,queue=queue,routing_key=key)
    print(f"declared {queue} binding {key}")
conn.close()
