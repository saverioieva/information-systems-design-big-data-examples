"""Create RabbitMQ topology through AMQP 0-9-1, before using AMQP 1.0.

For v2 /queues/<name> addresses, RabbitMQ requires the queue to exist.
This helper is run by Makefile.services and does not send any messages.
"""

from demos.common import connection
from demos.amqp10.settings import QUEUE_NAME


def main():
    conn = connection()
    try:
        channel = conn.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        print(f"[setup: Pika / AMQP 0-9-1] declared durable queue {QUEUE_NAME}", flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
