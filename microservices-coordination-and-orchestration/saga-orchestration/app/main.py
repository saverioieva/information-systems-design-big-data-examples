"""Composition root: FastAPI, durable outbox relay, and message consumers."""
import os
import threading
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.application.saga_coordinator import SagaCoordinator
from app.application.saga_participant_handler import SagaParticipantHandler
from app.domain.state_machine import SagaStateMachine
from app.adapters.outbound.postgres_store import PostgresSagaStore
from app.adapters.outbound.rabbitmq_transport import connect, RabbitPublisher
from app.adapters.inbound.rabbitmq_consumer import consume

ROLE = os.getenv('ROLE', 'orchestrator')
DATABASE_URL = os.environ['DATABASE_URL']
store = PostgresSagaStore(ROLE, DATABASE_URL)
coordinator = SagaCoordinator(store) if ROLE == 'orchestrator' else None
participant = SagaParticipantHandler(store, ROLE) if ROLE != 'orchestrator' else None
app = FastAPI(title='Create Order Saga — State Machine and Hexagonal Architecture')


def relay_loop():
    delay = 1
    while True:
        try:
            conn = connect()
            publisher = RabbitPublisher(conn)
            delay = 1
            try:
                while True:
                    row = store.pending()
                    if row is None:
                        conn.sleep(0.25)
                        continue
                    publisher.publish(row)
                    store.mark_sent(row['event_id'])
            finally:
                if conn.is_open:
                    conn.close()
        except Exception as exc:
            print(f'[flow] role={ROLE} outbox relay reconnect: {exc}', flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 10)


def start_components():
    store.initialize()
    threading.Thread(target=relay_loop, daemon=True).start()
    if ROLE == 'orchestrator':
        threading.Thread(target=consume, args=('orchestrator', coordinator), daemon=True).start()
        # Order Command Handler: same Order Service and same local database.
        order_handler = SagaParticipantHandler(store, 'order')
        threading.Thread(target=consume, args=('order', order_handler), daemon=True).start()
    else:
        threading.Thread(target=consume, args=(ROLE, participant), daemon=True).start()


class NewOrder(BaseModel):
    customerId: str = Field(min_length=1)
    amount: float = Field(gt=0)
    simulateRetry: bool = False
    simulateTicketFailure: bool = False


@app.on_event('startup')
def on_start():
    start_components()


@app.post('/orders', status_code=202)
def place_order(payload: NewOrder):
    if coordinator is None:
        raise HTTPException(404, 'Only the Order Service exposes this API')
    return coordinator.place_order(payload.customerId, payload.amount,
                                   payload.simulateRetry, payload.simulateTicketFailure)


@app.get('/orders/{order_id}')
def get_order(order_id: str):
    if coordinator is None:
        raise HTTPException(404, 'Only the Order Service exposes this API')
    found = coordinator.get_order(order_id)
    if not found:
        raise HTTPException(404, 'Order not found')
    return found


@app.get('/orders/{order_id}/history')
def get_history(order_id: str):
    if coordinator is None:
        raise HTTPException(404, 'Only the Order Service exposes this API')
    result = coordinator.history(order_id)
    if result is None:
        raise HTTPException(404, 'Order not found')
    return {'orderId': order_id, 'history': result}


@app.get('/saga/transitions')
def transitions():
    return SagaStateMachine().as_rows()


if __name__ == '__main__':
    store.initialize()
    threading.Thread(target=relay_loop, daemon=True).start()
    consume(ROLE, participant)
