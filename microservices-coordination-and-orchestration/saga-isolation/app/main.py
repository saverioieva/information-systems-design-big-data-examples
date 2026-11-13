"""Composition root for standalone isolation lab (4 services, 4 PostgreSQLs)."""
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.application.saga_coordinator import DomainConflict, SagaCoordinator
from app.application.saga_participant_handler import SagaParticipantHandler
from app.domain.state_machine import SagaStateMachine
from app.domain.cancel_state_machine import CancelOrderStateMachine
from app.adapters.outbound.postgres_store import PostgresSagaStore
from app.adapters.outbound.rabbitmq_transport import connect, RabbitPublisher
from app.adapters.inbound.rabbitmq_consumer import consume

ROLE = os.getenv('ROLE', 'orchestrator')
DATABASE_URL = os.environ['DATABASE_URL']
store = PostgresSagaStore(ROLE, DATABASE_URL)
coordinator = SagaCoordinator(store) if ROLE == 'orchestrator' else None
participant = SagaParticipantHandler(store, ROLE) if ROLE != 'orchestrator' else None


def relay_loop():
    delay = 1
    while True:
        try:
            conn = connect()
            publisher = RabbitPublisher(conn)
            delay = 1
            try:
                while True:
                    row = store.pending()  # Deliberately excludes held ApproveOrder rows.
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
        # The Order Command Handler belongs to the same Order Service and DB.
        order_handler = SagaParticipantHandler(store, 'order')
        threading.Thread(target=consume, args=('order', order_handler), daemon=True).start()
    else:
        threading.Thread(target=consume, args=(ROLE, participant), daemon=True).start()


class NewOrder(BaseModel):
    customerId: str = Field(min_length=1)
    amount: float = Field(gt=0)
    simulateRetry: bool = False
    simulateTicketFailure: bool = False
    isolationMode: Literal['normal', 'unsafe', 'semantic', 'optimistic'] = 'normal'


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_components()
    yield


app = FastAPI(title='Saga Isolation — CreateOrder and CancelOrder', lifespan=lifespan)


def order_api_only():
    if coordinator is None:
        raise HTTPException(404, 'Only the Order Service exposes this API')
    return coordinator


@app.post('/orders', status_code=202)
def place_order(payload: NewOrder):
    return order_api_only().place_order(payload.customerId, payload.amount,
        payload.simulateRetry, payload.simulateTicketFailure, payload.isolationMode)


@app.get('/orders/{order_id}')
def get_order(order_id: str):
    found = order_api_only().get_order(order_id)
    if not found:
        raise HTTPException(404, 'Order not found')
    return found


@app.get('/orders/{order_id}/history')
def get_history(order_id: str):
    result = order_api_only().history(order_id)
    if result is None:
        raise HTTPException(404, 'Order not found')
    return {'orderId': order_id, 'history': result}


@app.get('/orders/{order_id}/cancel/history')
def get_cancel_history(order_id: str):
    result = order_api_only().cancellation_history(order_id)
    if result is None:
        raise HTTPException(404, 'Order not found')
    return {'orderId': order_id, 'history': result}


@app.post('/orders/{order_id}/cancel', status_code=202)
def cancel_order(order_id: str):
    try:
        return order_api_only().cancel_order(order_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except DomainConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get('/orders/{order_id}/gate')
def approval_gate(order_id: str):
    result = order_api_only().gate(order_id)
    if result is None:
        raise HTTPException(404, 'Order not found')
    return result


@app.post('/orders/{order_id}/release')
def release_approval(order_id: str):
    try:
        return order_api_only().release_approval(order_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except DomainConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get('/saga/transitions')
def transitions():
    return {'createOrder': SagaStateMachine().as_rows(),
            'cancelOrder': CancelOrderStateMachine().as_rows()}


if __name__ == '__main__':
    # Participants run as standalone command consumers; orchestrator uses Uvicorn.
    store.initialize()
    threading.Thread(target=relay_loop, daemon=True).start()
    consume(ROLE, participant)
