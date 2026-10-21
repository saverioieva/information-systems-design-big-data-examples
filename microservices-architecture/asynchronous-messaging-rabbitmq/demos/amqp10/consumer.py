"""Consume messages over AMQP 1.0 with explicit delivery settlement."""

import json
import time

from demos.amqp10.settings import ADDRESS, connect


def unpack(message):
    """Both Proton text messages and Pika JSON bytes are accepted."""
    body = message.body
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    if not isinstance(body, str):
        raise ValueError(f"Expected a JSON string, got {type(body).__name__}")
    return json.loads(body)


def main():
    # Keep the service alive while RabbitMQ restarts; the container may also
    # be restarted by Docker Compose after transient failures.
    while True:
        conn = None
        try:
            conn = connect()
            receiver = conn.create_receiver(ADDRESS, credit=1)
            print(f"[Proton AMQP 1.0] listening on {ADDRESS}", flush=True)
            while True:
                message = receiver.receive(timeout=None)
                try:
                    payload = unpack(message)
                    print(
                        f"[Proton AMQP 1.0] received: {payload} "
                        f"(message.id={message.id!r})",
                        flush=True,
                    )
                except (UnicodeError, ValueError, TypeError) as exc:
                    print(f"[Proton AMQP 1.0] rejecting invalid JSON: {exc}", flush=True)
                    receiver.reject()
                    continue
                # Acknowledges successful processing: AMQP 1.0 ACCEPTED + settled.
                receiver.accept()
        except KeyboardInterrupt:
            print("[Proton AMQP 1.0] stopped", flush=True)
            break
        except Exception as exc:
            print(f"[Proton AMQP 1.0] disconnected: {exc}; retrying in 2s", flush=True)
            time.sleep(2)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
