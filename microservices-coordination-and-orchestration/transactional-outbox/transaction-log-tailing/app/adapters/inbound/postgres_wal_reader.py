"""Inbound adapter: PostgreSQL logical replication from a durable WAL slot.

The slot's confirmed_flush_lsn is persisted by PostgreSQL. We only send WAL
feedback *after* RabbitMQ publisher confirms all events in the transaction.
This gives AT-LEAST-ONCE publishing, not an exactly-once guarantee.
"""
import os
import time
import psycopg2
from psycopg2.extras import LogicalReplicationConnection

from app.application.log_tail_relay import LogTailRelay
from app.adapters.outbound.rabbitmq_publisher import RabbitMQPublisher

DSN = os.getenv('REPLICATION_DSN', 'dbname=orders user=demo password=demo host=postgres_order port=5432')
SLOT = os.getenv('REPLICATION_SLOT', 'outbox_slot')


def connect_replication():
    return psycopg2.connect(DSN, connection_factory=LogicalReplicationConnection)


def ensure_slot():
    """Run at startup, before the API starts accepting INSERTs."""
    conn = connect_replication()
    try:
        cursor = conn.cursor()
        try:
            cursor.create_replication_slot(SLOT, output_plugin='wal2json')
            print(f'[slot-init] created logical replication slot {SLOT}', flush=True)
        except psycopg2.ProgrammingError as exc:
            # Duplicate object. Other failures are not safe to ignore.
            if exc.pgcode != '42710':
                raise
            print(f'[slot-init] logical replication slot {SLOT} already exists', flush=True)
    finally:
        conn.close()


def run():
    while True:
        conn = None
        publisher = None
        try:
            publisher = RabbitMQPublisher()
            conn = connect_replication()
            cursor = conn.cursor()
            cursor.start_replication(
                slot_name=SLOT, decode=True,
                options={'format-version': '1', 'add-tables': 'public.outbox_events'},
                status_interval=10,
            )
            use_case = LogTailRelay(publisher)
            print('[relay] tailing committed outbox inserts from PostgreSQL WAL', flush=True)

            def on_message(msg):
                published = use_case.process_transaction(msg.payload)
                # Transactional boundary: only advance the slot if *every*
                # publish to RabbitMQ has been confirmed.
                msg.cursor.send_feedback(flush_lsn=msg.data_start, reply=True)
                if published:
                    print(f'[relay] acknowledged WAL batch with {published} message(s)', flush=True)

            cursor.consume_stream(on_message, keepalive_interval=10)
        except (Exception, KeyboardInterrupt) as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            print(f'[relay] recovering from failure: {exc}', flush=True)
            time.sleep(3)
        finally:
            if publisher is not None:
                try: publisher.close()
                except Exception: pass
            if conn is not None:
                try: conn.close()
                except Exception: pass
