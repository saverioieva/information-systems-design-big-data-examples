"""Application service for idempotent local saga commands.

A simulated transient error on retriable commands is handled by inserting a new
command into the local OUTBOX with a delayed-retry routing key. No side effect
is committed on the first attempt. RabbitMQ TTL routes the retry back later.
"""
from app.domain.policy import consumer_approved, card_authorized
from app.ports.storage import SagaStore

RETRIABLE_COMMANDS = {'ApproveTicket', 'ApproveOrder'}


class TransientCommandFailure(Exception):
    """Illustrative transient failure; local business transaction must roll back."""


class SagaParticipantHandler:
    def __init__(self, store: SagaStore, role: str):
        self.store, self.role = store, role

    def handle_message(self, message: dict) -> None:
        mid, oid, action = message['messageId'], message['orderId'], message['action']
        try:
            self._process_in_transaction(message, mid, oid, action)
        except TransientCommandFailure:
            # The business transaction was rolled back. In a *separate* atomic
            # transaction, persist both the retry intent and the consumed ID.
            with self.store.transaction() as tx:
                if tx.seen(mid):
                    return
                tx.record_attempt(oid, action, 0, 'TRANSIENT_FAILURE')
                tx.enqueue(f'retry.command.{self.role}', oid, action=action,
                           attempt=1, retryDemo=True)
                tx.mark_seen(mid)
            print(f'[flow] saga={oid} {self.role} {action} attempt=0 ROLLBACK; delayed retry scheduled', flush=True)

    def _process_in_transaction(self, message, mid, oid, action):
        with self.store.transaction() as tx:
            if tx.seen(mid):
                return
            previous_result = tx.completed_command(oid, action)
            if previous_result:
                # Same business command, even with a different messageId:
                # do not repeat its side effect. A reply can safely be repeated.
                tx.enqueue('reply.orchestrator', oid, action=previous_result)
                tx.mark_seen(mid)
                print(f'[flow] saga={oid} {self.role} idempotent duplicate {action}', flush=True)
                return

            attempt = int(message.get('attempt', 0))
            if action in RETRIABLE_COMMANDS and message.get('retryDemo', False) and attempt == 0:
                # This insert is deliberately rolled back along with the transaction.
                tx.record_attempt(oid, action, attempt, 'ROLLED_BACK')
                raise TransientCommandFailure(f'simulated transient failure in {action}')

            if self.role == 'consumer' and action == 'VerifyConsumer':
                result = 'ConsumerVerified' if consumer_approved(message['customerId']) else 'ConsumerRejected'
            elif self.role == 'kitchen' and action == 'CreateTicket':
                # Explicit, deterministic failure path for the state diagram.
                if message.get('simulateTicketFailure', False):
                    result = 'TicketCreationFailed'
                else:
                    tx.create_ticket(oid)
                    result = 'TicketCreated'
            elif self.role == 'kitchen' and action in ('ApproveTicket', 'RejectTicket'):
                tx.update_ticket(oid, 'AWAITING_ACCEPTANCE' if action == 'ApproveTicket' else 'REJECTED')
                result = 'TicketApproved' if action == 'ApproveTicket' else 'TicketRejected'
            elif self.role == 'accounting' and action == 'AuthorizeCard':
                ok = card_authorized(message['amount'])
                tx.authorize_card(oid, 'AUTHORIZED' if ok else 'DECLINED')
                result = 'CardAuthorized' if ok else 'CardDeclined'
            elif self.role == 'order' and action in ('ApproveOrder', 'RejectOrder'):
                tx.apply_order_status(oid, 'APPROVED' if action == 'ApproveOrder' else 'REJECTED')
                result = 'OrderApproved' if action == 'ApproveOrder' else 'OrderRejected'
            else:
                raise ValueError(f'Unsupported command {action} for {self.role}')

            tx.record_attempt(oid, action, attempt, 'SUCCEEDED')
            tx.record_completed_command(oid, action, result)
            tx.enqueue('reply.orchestrator', oid, action=result)
            tx.mark_seen(mid)
            print(f'[flow] saga={oid} {self.role} {action} attempt={attempt} -> {result}', flush=True)
