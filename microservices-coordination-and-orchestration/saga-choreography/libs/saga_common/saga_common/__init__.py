import os, json, uuid, time, logging
import pika
from .routing import TOPIC_EXCHANGES, exchange_for_route
from sqlalchemy import create_engine, MetaData, Table, Column, String, DateTime, select, insert, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("saga")

# ---------------- AMQP config ----------------
AMQP_URL   = os.getenv("AMQP_URL", "amqp://guest:guest@rabbitmq:5672/%2F")
DLX        = os.getenv("DLX", "saga.dlx")

HEARTBEAT  = int(os.getenv("AMQP_HEARTBEAT", "120"))
BLOCKED_TO = int(os.getenv("AMQP_BLOCKED_TIMEOUT", "300"))
SOCK_TO    = int(os.getenv("AMQP_SOCKET_TIMEOUT", str(HEARTBEAT + 30)))
RETRY_MAX  = int(os.getenv("AMQP_MAX_RETRIES", "0"))   # 0 = infinite
RETRY_BASE = float(os.getenv("AMQP_RETRY_BASE_SEC", "0.5"))
RETRY_MAXS = float(os.getenv("AMQP_RETRY_MAX_SEC", "10"))

# ---------------- DB config ------------------
DATABASE_URL = os.getenv("DATABASE_URL")
engine   = create_engine(DATABASE_URL, pool_pre_ping=True)
metadata = MetaData()

# ---------------- Outbox table ---------------
# Service-local outgoing events are buffered in an outbox before publication.
outbox = Table(
    "outbox", metadata,
    Column("id", String, primary_key=True, default=lambda: str(uuid.uuid4())),
    Column("topic", String, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("status", String, nullable=False, default="PENDING"),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("sent_at", DateTime, nullable=True),
)

def ensure_outbox_table():
    metadata.create_all(engine, tables=[outbox])

# ------------- AMQP helpers (con retry) -------------

def retry_delay(attempt):
    """Bounded exponential backoff; no unbounded 2**attempt computation."""
    return min(RETRY_BASE * (2 ** min(max(attempt - 1, 0), 16)), RETRY_MAXS)


def flow(service, action, route=None, order_id=None, message_id=None, detail=None):
    """Uniform, greppable audit trace for the classroom exercise."""
    fields = [f"[flow] service={service}", f"action={action}"]
    if route:
        fields.append(f"route={route}")
    if order_id:
        fields.append(f"orderId={order_id}")
    if message_id:
        fields.append(f"messageId={message_id}")
    if detail:
        fields.append(f"detail={detail}")
    log.info(" ".join(fields))


def _connect():
    params = pika.URLParameters(AMQP_URL)
    params.heartbeat = HEARTBEAT
    params.blocked_connection_timeout = BLOCKED_TO
    params.socket_timeout = SOCK_TO
    conn = pika.BlockingConnection(params)
    try:
        ch = conn.channel()
        for topic_exchange in TOPIC_EXCHANGES.values():
            ch.exchange_declare(exchange=topic_exchange, exchange_type="topic", durable=True)
        ch.exchange_declare(exchange=DLX, exchange_type="direct", durable=True)
        return conn, ch
    except Exception:
        conn.close()
        raise


def _connect_with_retry():
    attempt = 0
    while True:
        try:
            return _connect()
        except (pika.exceptions.AMQPError, OSError) as exc:
            attempt += 1
            if RETRY_MAX and attempt > RETRY_MAX:
                raise
            delay = retry_delay(attempt)
            log.warning("[retry] AMQP connect failed: %s; retry=%.1fs attempt=%s", exc, delay, attempt)
            time.sleep(delay)


def queue_args(queue):
    return {"x-dead-letter-exchange": DLX, "x-dead-letter-routing-key": queue}


def declare_and_bind(ch, queue, keys):
    """The topology init and consumers declare exactly matching queue arguments."""
    ch.exchange_declare(exchange=DLX, exchange_type="direct", durable=True)
    ch.queue_declare(queue=queue + ".dlq", durable=True)
    ch.queue_bind(exchange=DLX, queue=queue + ".dlq", routing_key=queue)
    q = ch.queue_declare(queue=queue, durable=True, arguments=queue_args(queue)).method.queue
    for rk in keys:
        ch.queue_bind(exchange=exchange_for_route(rk), queue=q, routing_key=rk)
    return q


def run_consumer(service_name, queue, keys, handler):
    """Inbound RabbitMQ adapter: ack after DB commit; failures -> per-service DLQ.

    The handler uses its own DB transaction and commits before returning.
    If a connection breaks before ack, RabbitMQ may redeliver; inbox IDs make
    processing idempotent. Messages that cannot be processed are quarantined,
    not retried forever in a tight requeue loop.
    """
    attempt = 0
    while True:
        conn = None
        try:
            conn, ch = _connect()
            q = declare_and_bind(ch, queue, keys)
            ch.basic_qos(prefetch_count=1)
            attempt = 0
            flow(service_name, "consumer-ready", detail=q)

            def on_message(channel, method, properties, body):
                route = method.routing_key
                order_id = None
                msg_id = getattr(properties, 'message_id', None)
                try:
                    event = json.loads(body)
                    if not isinstance(event, dict):
                        raise ValueError('Message payload must be a JSON object')
                    order_id = event.get('orderId')
                    msg_id = event.get('messageId') or msg_id
                    flow(service_name, "received", route, order_id, msg_id)
                    handler(event, properties, route)  # synchronous; commits before return
                except Exception as exc:
                    flow(service_name, "dead-letter", route, order_id, msg_id, type(exc).__name__)
                    log.exception("[error] handler failed service=%s route=%s", service_name, route)
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    return
                # Ack is separate: a dropped AMQP connection must trigger reconnect,
                # not be falsely reported as a handler failure / successful DLQ move.
                channel.basic_ack(delivery_tag=method.delivery_tag)
                flow(service_name, "processed", route, order_id, msg_id)

            ch.basic_consume(queue=q, on_message_callback=on_message, auto_ack=False)
            ch.start_consuming()
            raise RuntimeError('Consumer stopped unexpectedly')
        except (pika.exceptions.AMQPError, OSError, RuntimeError) as exc:
            attempt += 1
            delay = retry_delay(attempt)
            log.warning("[retry] consumer=%s connection lost: %s; retry=%.1fs", service_name, exc, delay)
            time.sleep(delay)
        finally:
            if conn and conn.is_open:
                try:
                    conn.close()
                except (pika.exceptions.AMQPError, OSError):
                    pass

# Incoming message IDs are recorded in the SAME local transaction as the handler.
from sqlalchemy.dialects.postgresql import insert as pg_insert
inbox = Table("inbox", metadata, Column("message_id", String, primary_key=True))

def ensure_inbox_table():
    metadata.create_all(engine, tables=[inbox])

def claim_message(session, event, properties):
    event_id = (event.get("messageId") or getattr(properties, "message_id", None))
    if not event_id:
        raise ValueError("Incoming event missing messageId")
    result = session.execute(pg_insert(inbox).values(message_id=event_id)
                             .on_conflict_do_nothing(index_elements=[inbox.c.message_id])
                             .returning(inbox.c.message_id)).scalar_one_or_none()
    return result is not None

# One polling relay per service; publisher confirms mean SENT is recorded only
# after RabbitMQ confirms receipt. Duplicates remain possible after a crash.

def publish_outbox_forever():
    """One publisher thread per service; at-least-once publish with confirms."""
    service = os.getenv("SERVICE_NAME", "service")
    attempt = 0
    while True:
        conn = None
        try:
            conn, ch = _connect()
            ch.confirm_delivery()
            attempt = 0
            flow(service, "publisher-ready")
            while True:
                with Session(engine) as s:
                    rows = s.execute(
                        select(outbox.c.id, outbox.c.topic, outbox.c.payload)
                        .where(outbox.c.status == "PENDING")
                        .order_by(outbox.c.created_at).limit(1)
                    ).all()
                if not rows:
                    conn.sleep(0.3)
                    continue
                oid, topic, payload = rows[0]
                ch.basic_publish(
                    exchange=exchange_for_route(topic), routing_key=topic, mandatory=True,
                    properties=pika.BasicProperties(
                        content_type="application/json", delivery_mode=2,
                        message_id=payload.get("messageId"),
                        correlation_id=payload.get("orderId")
                    ),
                    body=json.dumps(payload).encode()
                )
                # A crash between broker confirmation and SENT may republish;
                # this is intentionally at-least-once, with inbox deduplication.
                with Session(engine) as s:
                    s.execute(update(outbox).where(outbox.c.id == oid, outbox.c.status == "PENDING")
                              .values(status="SENT", sent_at=datetime.utcnow()))
                    s.commit()
                flow(service, "published", topic, payload.get("orderId"), payload.get("messageId"))
        except (pika.exceptions.AMQPError, OSError, SQLAlchemyError) as exc:
            attempt += 1
            delay = retry_delay(attempt)
            log.warning("[retry] publisher=%s lost connection: %s; retry=%.1fs", service, exc, delay)
            time.sleep(delay)
        finally:
            if conn and conn.is_open:
                try:
                    conn.close()
                except (pika.exceptions.AMQPError, OSError):
                    pass
