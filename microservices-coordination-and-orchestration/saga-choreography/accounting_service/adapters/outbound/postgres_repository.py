"""SQLAlchemy persistence adapter for accounting saga prerequisites and pivot."""
import logging
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Table,Column,String,Boolean,Numeric,DateTime,select,update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from saga_common import engine,metadata,outbox,ensure_outbox_table,ensure_inbox_table,claim_message
from domain.policy import can_authorize
log=logging.getLogger('accounting_service')

prereq = Table(
    "prereq", metadata,
    Column("order_id",     String, primary_key=True),
    Column("have_order",   Boolean, nullable=False, default=False),
    Column("have_consumer",Boolean, nullable=False, default=False),
    Column("have_ticket",  Boolean, nullable=False, default=False),
)

credit_auth = Table(
    "credit_auth", metadata,
    Column("order_id", String, primary_key=True),
    Column("amount",   Numeric, nullable=False),
    Column("status",   String,  nullable=False),  # PENDING | AUTHORIZED | REJECTED
    Column("updated_at", DateTime, default=datetime.utcnow)
)

def try_authorize_if_ready(s: Session, order_id: str):
    """Se tutti i prerequisiti sono veri, esegue il pivot: autorizza/rigetta e pubblica evento."""
    flags = s.execute(
        select(prereq.c.have_order, prereq.c.have_consumer, prereq.c.have_ticket)
        .where(prereq.c.order_id == order_id)
    ).first()
    if not flags:
        return
    have_order, have_consumer, have_ticket = flags
    if not (have_order and have_consumer and have_ticket):
        return

    # Recupera amount (deve essere stato creato a order.created)
    row = s.execute(
        select(credit_auth.c.amount, credit_auth.c.status)
        .where(credit_auth.c.order_id == order_id)
    ).first()
    if not row:
        return
    amount, cur_status = row
    if cur_status != "PENDING":
        return

    # Regola demo: autorizza se amount <= 100.0
    authorized = can_authorize(amount)
    new_status = "AUTHORIZED" if authorized else "REJECTED"
    s.execute(
        update(credit_auth)
        .where(credit_auth.c.order_id == order_id)
        .values(status=new_status, updated_at=datetime.utcnow())
    )

    evt_type = "accounting.creditCardAuthorized" if authorized else "accounting.creditCardAuthorizationFailed"
    evt = {
        "type": "CreditCardAuthorized" if authorized else "CreditCardAuthorizationFailed",
        "orderId": order_id,
        "amount": float(amount),
        "messageId": str(uuid4()),
    }
    s.execute(outbox.insert().values(topic=evt_type, payload=evt))
    log.info(f"[pivot] orderId={order_id} amount={amount} -> {new_status} (-> outbox {evt_type})")

class PostgresAccountingRepository:
    def initialize(self):
        metadata.create_all(engine,tables=[prereq,credit_auth]);ensure_outbox_table();ensure_inbox_table()
    def apply_event(self,evt,properties,rk):
        oid=evt.get('orderId')
        with Session(engine) as s:
            if not claim_message(s, evt, properties):
                s.commit(); return
            if rk == "order.created":
                amount = evt.get("amount", 0.0)
                # prereq row (upsert)
                s.execute(
                    pg_insert(prereq)
                    .values(order_id=oid, have_order=True, have_consumer=False, have_ticket=False)
                    .on_conflict_do_update(
                        index_elements=[prereq.c.order_id],
                        set_={"have_order": True}
                    )
                )
                # credit_auth pending (upsert)
                s.execute(
                    pg_insert(credit_auth)
                    .values(order_id=oid, amount=amount, status="PENDING", updated_at=datetime.utcnow())
                    .on_conflict_do_update(
                        index_elements=[credit_auth.c.order_id],
                        set_={"amount": amount, "updated_at": datetime.utcnow()}
                    )
                )
                log.info(f"[flow] (<- AMQP) order.created orderId={oid} amount={amount} -> prereq.have_order=True, credit_auth=PENDING")
                try_authorize_if_ready(s, oid)

            elif rk == "consumer.verified":
                s.execute(
                    pg_insert(prereq)
                    .values(order_id=oid, have_order=False, have_consumer=True, have_ticket=False)
                    .on_conflict_do_update(
                        index_elements=[prereq.c.order_id],
                        set_={"have_consumer": True}
                    )
                )
                log.info(f"[flow] (<- AMQP) consumer.verified orderId={oid} -> prereq.have_consumer=True")
                try_authorize_if_ready(s, oid)

            elif rk == "consumer.verificationFailed":
                # Assicura prereq row
                s.execute(
                    pg_insert(prereq)
                    .values(order_id=oid, have_order=False, have_consumer=False, have_ticket=False)
                    .on_conflict_do_nothing(index_elements=[prereq.c.order_id])
                )
                # Recupera amount se presente, altrimenti prova a leggerlo da credit_auth
                amount = evt.get("amount")
                if amount is None:
                    row = s.execute(select(credit_auth.c.amount).where(credit_auth.c.order_id == oid)).first()
                    amount = float(row[0]) if row else 0.0

                # Marca pivot REJECTED (upsert)
                s.execute(
                    pg_insert(credit_auth)
                    .values(order_id=oid, amount=amount, status="REJECTED", updated_at=datetime.utcnow())
                    .on_conflict_do_update(
                        index_elements=[credit_auth.c.order_id],
                        set_={"status": "REJECTED", "updated_at": datetime.utcnow()}
                    )
                )
                # Pubblica esito pivot (l'unico che Order ascolta)
                fail_evt = {
                    "type": "CreditCardAuthorizationFailed",
                    "orderId": oid,
                    "amount": float(amount),
                    "reason": "CONSUMER_VERIFICATION_FAILED",
                    "messageId": str(uuid4()),
                }
                s.execute(outbox.insert().values(topic="accounting.creditCardAuthorizationFailed", payload=fail_evt))
                log.info(f"[pivot] consumer.verificationFailed -> orderId={oid} => REJECTED (-> outbox accounting.creditCardAuthorizationFailed)")

            else:  # kitchen.ticketCreated
                s.execute(
                    pg_insert(prereq)
                    .values(order_id=oid, have_order=False, have_consumer=False, have_ticket=True)
                    .on_conflict_do_update(
                        index_elements=[prereq.c.order_id],
                        set_={"have_ticket": True}
                    )
                )
                log.info(f"[flow] (<- AMQP) kitchen.ticketCreated orderId={oid} -> prereq.have_ticket=True")
                try_authorize_if_ready(s, oid)

            s.commit()
