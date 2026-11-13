"""PostgreSQL persistence adapter for CreateOrder and CancelOrder Sagas.

One database per logical service. Each transaction groups business state,
message inbox, outgoing outbox messages, and saga transitions atomically.
No domain/application class depends on SQLAlchemy.
"""
import json
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, MetaData, String,
    Table, Text, and_, create_engine, func, insert, select, update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert

metadata = MetaData()

inbox = Table('inbox', metadata,
    Column('event_id', String(64), primary_key=True),
    Column('received_at', DateTime(timezone=True), nullable=False, server_default=func.now()))

outbox = Table('outbox', metadata,
    Column('event_id', String(64), primary_key=True),
    Column('routing_key', String(128), nullable=False),
    Column('payload', Text, nullable=False),
    Column('sent', Boolean, nullable=False, server_default='false'),
    Column('held', Boolean, nullable=False, server_default='false'),
    Column('gate_order_id', String(64)),
    Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()))

command_results = Table('command_results', metadata,
    Column('order_id', String(64), primary_key=True),
    Column('action', String(64), primary_key=True),
    Column('result', String(64), nullable=False))

command_attempts = Table('command_attempts', metadata,
    Column('seq', Integer, primary_key=True, autoincrement=True),
    Column('order_id', String(64), nullable=False),
    Column('action', String(64), nullable=False),
    Column('attempt', Integer, nullable=False),
    Column('outcome', String(64), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()))

orders = Table('orders', metadata,
    Column('order_id', String(64), primary_key=True),
    Column('customer_id', String(128), nullable=False),
    Column('amount', Float, nullable=False),
    Column('status', String(40), nullable=False),
    Column('retry_demo', Boolean, nullable=False, server_default='false'),
    Column('ticket_failure', Boolean, nullable=False, server_default='false'),
    Column('isolation_mode', String(16), nullable=False, server_default='normal'),
    Column('version', Integer, nullable=False, server_default='0'))

sagas = Table('sagas', metadata,
    Column('order_id', String(64), ForeignKey('orders.order_id'), primary_key=True),
    Column('stage', String(64), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()))

saga_history = Table('saga_history', metadata,
    Column('seq', Integer, primary_key=True, autoincrement=True),
    Column('order_id', String(64), ForeignKey('orders.order_id'), nullable=False),
    Column('from_stage', String(64)),
    Column('event', String(64), nullable=False),
    Column('to_stage', String(64), nullable=False),
    Column('command', String(64)),
    Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()))

# One cancellation per order; cancellation is a second stateful Saga.
cancel_sagas = Table('cancel_sagas', metadata,
    Column('order_id', String(64), ForeignKey('orders.order_id'), primary_key=True),
    Column('stage', String(64), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()))

cancel_history = Table('cancel_history', metadata,
    Column('seq', Integer, primary_key=True, autoincrement=True),
    Column('order_id', String(64), ForeignKey('orders.order_id'), nullable=False),
    Column('from_stage', String(64)),
    Column('event', String(64), nullable=False),
    Column('to_stage', String(64), nullable=False),
    Column('command', String(64)),
    Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()))

# Gate is persisted, not a held RabbitMQ delivery or a long-running SQL tx.
approval_gates = Table('approval_gates', metadata,
    Column('order_id', String(64), ForeignKey('orders.order_id'), primary_key=True),
    Column('state', String(20), nullable=False))

tickets = Table('tickets', metadata,
    Column('order_id', String(64), primary_key=True),
    Column('state', String(40), nullable=False))

authorizations = Table('authorizations', metadata,
    Column('order_id', String(64), primary_key=True),
    Column('status', String(40), nullable=False))

ROLE_TABLES = {
    'orchestrator': (orders, sagas, saga_history, cancel_sagas, cancel_history, approval_gates),
    'consumer': (),
    'kitchen': (tickets,),
    'accounting': (authorizations,),
}
COMMON_TABLES = (inbox, outbox, command_results, command_attempts)


class PostgresTransaction:
    """Transaction-scoped SQL implementations of SagaTransaction port methods."""

    def __init__(self, connection):
        self.db = connection

    def seen(self, mid):
        return self.db.execute(select(inbox.c.event_id).where(inbox.c.event_id == mid)).first() is not None

    def mark_seen(self, mid):
        self.db.execute(pg_insert(inbox).values(event_id=mid).on_conflict_do_nothing())

    def enqueue(self, route, order_id, **payload):
        held = bool(payload.pop('_hold', False))
        mid = str(uuid4())
        message = {'messageId': mid, 'orderId': order_id, **payload}
        self.db.execute(insert(outbox).values(event_id=mid, routing_key=route,
                                               payload=json.dumps(message), held=held,
                                               gate_order_id=order_id if held else None))

    def create_order(self, oid, cid, amount, retry_demo=False, ticket_failure=False,
                     isolation_mode='normal'):
        self.db.execute(insert(orders).values(order_id=oid, customer_id=cid, amount=amount,
                                               status='APPROVAL_PENDING', retry_demo=bool(retry_demo),
                                               ticket_failure=bool(ticket_failure),
                                               isolation_mode=isolation_mode, version=0))
        self.db.execute(insert(sagas).values(order_id=oid, stage='VERIFY_CONSUMER'))

    def get_order(self, oid):
        row = self.db.execute(select(orders.c.order_id.label('orderId'), orders.c.customer_id.label('customerId'),
                                     orders.c.amount, orders.c.status, sagas.c.stage,
                                     orders.c.retry_demo.label('simulateRetry'),
                                     orders.c.ticket_failure.label('simulateTicketFailure'),
                                     orders.c.isolation_mode.label('isolationMode'),
                                     orders.c.version,
                                     cancel_sagas.c.stage.label('cancelStage'))
                              .join(sagas, orders.c.order_id == sagas.c.order_id)
                              .outerjoin(cancel_sagas, orders.c.order_id == cancel_sagas.c.order_id)
                              .where(orders.c.order_id == oid)).mappings().first()
        return dict(row) if row else None

    def get_stage(self, oid):
        # Lock the saga row until inbox, state and outgoing command commit together.
        return self.db.execute(select(sagas.c.stage).where(sagas.c.order_id == oid)
                               .with_for_update()).scalar_one_or_none()

    def set_stage(self, oid, stage):
        self.db.execute(update(sagas).where(sagas.c.order_id == oid)
                        .values(stage=stage, updated_at=func.now()))

    def apply_order_status(self, oid, status):
        result = self.db.execute(update(orders).where(and_(orders.c.order_id == oid,
                                                           orders.c.status == 'APPROVAL_PENDING'))
                                 .values(status=status, version=orders.c.version + 1))
        if result.rowcount == 0:
            actual = self.db.execute(select(orders.c.status).where(orders.c.order_id == oid)).scalar_one_or_none()
            if actual != status:
                raise ValueError(f'Cannot change order {oid} to {status}')

    def get_order_locked(self, oid):
        row = self.db.execute(select(orders.c.order_id, orders.c.status,
                                     orders.c.isolation_mode.label('isolationMode'))
                              .where(orders.c.order_id == oid).with_for_update()).mappings().first()
        return dict(row) if row else None

    def isolation_mode(self, oid):
        return self.db.execute(select(orders.c.isolation_mode).where(
            orders.c.order_id == oid)).scalar_one()

    def get_version(self, oid):
        return self.db.execute(select(orders.c.version).where(orders.c.order_id == oid)).scalar_one()

    def pause_approval(self, oid):
        self.db.execute(insert(approval_gates).values(order_id=oid, state='PAUSED'))

    def approval_gate(self, oid):
        return self.db.execute(select(approval_gates.c.state).where(
            approval_gates.c.order_id == oid)).scalar_one_or_none() or 'NOT_REACHED'

    def release_approval(self, oid):
        result = self.db.execute(update(approval_gates)
                                 .where(and_(approval_gates.c.order_id == oid,
                                             approval_gates.c.state == 'PAUSED'))
                                 .values(state='RELEASED'))
        if result.rowcount != 1:
            raise ValueError('Approval gate not paused')
        # Outbox relay only selects non-held rows. The queued decision is now visible.
        self.db.execute(update(outbox).where(and_(outbox.c.gate_order_id == oid,
                                                  outbox.c.held.is_(True)))
                        .values(held=False))

    def unsafe_approve(self, oid):
        # DELIBERATELY UNSAFE: only enabled for the classroom anomaly scenario.
        result = self.db.execute(update(orders).where(orders.c.order_id == oid)
                                 .values(status='APPROVED', version=orders.c.version + 1))
        if result.rowcount != 1:
            raise ValueError('Unknown order')

    def optimistic_approve(self, oid, expected_version):
        result = self.db.execute(update(orders).where(and_(
            orders.c.order_id == oid, orders.c.status == 'APPROVAL_PENDING',
            orders.c.version == expected_version))
            .values(status='APPROVED', version=orders.c.version + 1))
        return result.rowcount == 1

    def get_cancel_stage(self, oid):
        return self.db.execute(select(cancel_sagas.c.stage)
                               .where(cancel_sagas.c.order_id == oid)
                               .with_for_update()).scalar_one_or_none()

    def start_cancellation(self, oid):
        result = self.db.execute(update(orders).where(and_(
            orders.c.order_id == oid,
            orders.c.status.in_(['APPROVAL_PENDING', 'APPROVED'])))
            .values(status='CANCELLATION_PENDING', version=orders.c.version + 1))
        if result.rowcount != 1:
            raise ValueError('Order is not cancellable')
        self.db.execute(insert(cancel_sagas).values(order_id=oid, stage='VOID_AUTHORIZATION'))

    def set_cancel_stage(self, oid, stage):
        self.db.execute(update(cancel_sagas).where(cancel_sagas.c.order_id == oid)
                        .values(stage=stage, updated_at=func.now()))

    def finish_cancellation(self, oid):
        result = self.db.execute(update(orders).where(and_(
            orders.c.order_id == oid, orders.c.status == 'CANCELLATION_PENDING'))
            .values(status='CANCELLED', version=orders.c.version + 1))
        if result.rowcount != 1:
            raise ValueError('Cannot complete cancellation; order was modified concurrently')

    def record_cancel_transition(self, oid, prior, event, stage, command):
        self.db.execute(insert(cancel_history).values(order_id=oid, from_stage=prior,
                                                   event=event, to_stage=stage, command=command))

    def get_cancel_history(self, oid):
        rows = self.db.execute(select(cancel_history.c.seq,
                                      cancel_history.c.from_stage.label('fromStage'),
                                      cancel_history.c.event,
                                      cancel_history.c.to_stage.label('toStage'),
                                      cancel_history.c.command,
                                      cancel_history.c.created_at.label('at'))
                               .where(cancel_history.c.order_id == oid)
                               .order_by(cancel_history.c.seq)).mappings()
        return [dict(r) for r in rows]

    def void_authorization(self, oid):
        result = self.db.execute(update(authorizations)
                                 .where(and_(authorizations.c.order_id == oid,
                                             authorizations.c.status == 'AUTHORIZED'))
                                 .values(status='VOIDED'))
        if result.rowcount == 0:
            current = self.db.execute(select(authorizations.c.status).where(
                authorizations.c.order_id == oid)).scalar_one_or_none()
            if current != 'VOIDED':
                raise ValueError(f'Cannot void authorization for order {oid}: {current}')

    def amount(self, oid):
        value = self.db.execute(select(orders.c.amount).where(orders.c.order_id == oid)).scalar_one_or_none()
        if value is None:
            raise ValueError('Unknown order')
        return float(value)

    def retry_demo(self, oid):
        value = self.db.execute(select(orders.c.retry_demo).where(orders.c.order_id == oid)).scalar_one_or_none()
        return bool(value)

    def ticket_failure(self, oid):
        value = self.db.execute(select(orders.c.ticket_failure).where(orders.c.order_id == oid)).scalar_one_or_none()
        return bool(value)

    def create_ticket(self, oid):
        self.db.execute(pg_insert(tickets).values(order_id=oid, state='CREATE_PENDING')
                        .on_conflict_do_nothing(index_elements=[tickets.c.order_id]))

    def update_ticket(self, oid, state):
        result = self.db.execute(update(tickets).where(tickets.c.order_id == oid).values(state=state))
        if result.rowcount == 0:
            raise ValueError(f'Unknown kitchen ticket for order {oid}')

    def authorize_card(self, oid, status):
        self.db.execute(pg_insert(authorizations).values(order_id=oid, status=status)
                        .on_conflict_do_nothing(index_elements=[authorizations.c.order_id]))

    def completed_command(self, oid, action):
        return self.db.execute(select(command_results.c.result).where(and_(
            command_results.c.order_id == oid, command_results.c.action == action))).scalar_one_or_none()

    def record_completed_command(self, oid, action, result):
        self.db.execute(pg_insert(command_results).values(order_id=oid, action=action, result=result)
                        .on_conflict_do_nothing(index_elements=[command_results.c.order_id,
                                                                 command_results.c.action]))

    def record_attempt(self, oid, action, attempt, outcome):
        self.db.execute(insert(command_attempts).values(order_id=oid, action=action,
                                                        attempt=attempt, outcome=outcome))

    def record_transition(self, oid, prior, event, stage, command):
        self.db.execute(insert(saga_history).values(order_id=oid, from_stage=prior, event=event,
                                                    to_stage=stage, command=command))

    def get_history(self, oid):
        rows = self.db.execute(select(saga_history.c.seq, saga_history.c.from_stage.label('fromStage'),
                                      saga_history.c.event, saga_history.c.to_stage.label('toStage'),
                                      saga_history.c.command, saga_history.c.created_at.label('at'))
                               .where(saga_history.c.order_id == oid)
                               .order_by(saga_history.c.seq)).mappings()
        return [dict(row) for row in rows]


class PostgresSagaStore:
    def __init__(self, role, database_url):
        if role not in ROLE_TABLES:
            raise ValueError(f'Unknown saga service role: {role}')
        self.role = role
        self.engine = create_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)

    @contextmanager
    def transaction(self):
        with self.engine.begin() as connection:
            yield PostgresTransaction(connection)

    def initialize(self):
        # Safe on restart: only the tables belonging to this service are created.
        metadata.create_all(self.engine, tables=[*COMMON_TABLES, *ROLE_TABLES[self.role]])

    def pending(self):
        with self.engine.connect() as connection:
            row = connection.execute(select(outbox.c.event_id, outbox.c.routing_key, outbox.c.payload)
                                     .where(and_(outbox.c.sent.is_(False), outbox.c.held.is_(False)))
                                     .order_by(outbox.c.created_at, outbox.c.event_id).limit(1)).mappings().first()
            return dict(row) if row else None

    def mark_sent(self, event_id):
        with self.transaction() as tx:
            tx.db.execute(update(outbox).where(outbox.c.event_id == event_id).values(sent=True))
