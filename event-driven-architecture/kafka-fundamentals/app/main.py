"""Kafka Fundamentals command-line adapter for the Docker Compose lab."""
import argparse
import os
import time

from app.application.publish_example import produce_examples
from app.domain.messages import parse_event


def consume_events(group: str, limit: int, idle: float):
    from confluent_kafka import Consumer, KafkaException
    conf = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP", "kafka:19092"),
        "group.id": group,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",  # only for groups with no committed offset
    }
    c = Consumer(conf)

    def assigned(_consumer, partitions):
        print(f"[consumer group={group}] assigned {partitions}", flush=True)

    c.subscribe([os.getenv("KAFKA_TOPIC", "orders.events")], on_assign=assigned)
    seen, last = 0, time.monotonic()
    try:
        while not limit or seen < limit:
            msg = c.poll(1.0)
            if msg is None:
                if idle and time.monotonic() - last >= idle:
                    print(f"[consumer] idle timeout ({idle}s); received={seen}")
                    break
                continue
            if msg.error():
                raise KafkaException(msg.error())
            event = parse_event(msg.value())
            print(f"[consumer group={group}] key={msg.key().decode() if msg.key() else '-'} "
                  f"partition={msg.partition()} offset={msg.offset()} "
                  f"eventId={event['eventId']} sequence={event.get('sequence')}", flush=True)
            # The teaching consumer handles then commits; a crash before commit can cause redelivery.
            c.commit(message=msg, asynchronous=False)
            seen += 1
            last = time.monotonic()
    except KeyboardInterrupt:
        print("[consumer] stopped by user")
    finally:
        c.close()


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prod = sub.add_parser("produce")
    prod.add_argument("--count", type=int, default=12)
    prod.add_argument("--prefix", default="DEMO")
    consume = sub.add_parser("consume")
    consume.add_argument("--group", default="order-processors")
    consume.add_argument("--limit", type=int, default=12, help="0 = unlimited")
    consume.add_argument("--idle", type=float, default=12, help="0 = no idle timeout")
    args = parser.parse_args()

    if args.command == "produce":
        if args.count < 1:
            parser.error("count must be > 0")
        from app.adapters.outbound.kafka_producer import KafkaEventProducer
        ids = produce_examples(KafkaEventProducer(), count=args.count, prefix=args.prefix)
        print(f"[producer] published {len(ids)} records")
    else:
        consume_events(group=args.group, limit=args.limit, idle=args.idle)


if __name__ == "__main__":
    main()
