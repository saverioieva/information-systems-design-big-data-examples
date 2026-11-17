"""Idempotent participant commands, with intentionally unsafe approval mode.

Only the *unsafe* isolation experiment permits ApproveOrder to overwrite a
cancelled order. Optimistic mode uses an atomic status+version compare-and-set.
Normal/semantic modes retain the guarded local transaction from Orchestration.
"""
from app.domain.policy import consumer_approved, card_authorized
from app.ports.storage import SagaStore

RETRIABLE_COMMANDS = {'ApproveTicket', 'ApproveOrder', 'SetCancelled', 'VoidAuthorization'}


class TransientCommandFailure(Exception):
    """Illustrative failure: local business transaction is rolled back."""


class SagaParticipantHandler:
    def __init__(self, store: SagaStore, role: str):
        self.store, self.role = store, role

    def handle_message(self, message: dict) -> None:
        mid, oid, action = message['messageId'], message['orderId'], message['action']
        try:
            self._process_in_transaction(message, mid, oid, action)
        except TransientCommandFailure:
            with self.store.transaction() as tx:
                if tx.seen(mid):
                    return
                tx.record_attempt(oid, action, 0, 'TRANSIENT_FAILURE')
                tx.enqueue(f'retry.command.{self.role}', oid, action=action,
                           attempt=1, retryDemo=True,
                           isolationMode=message.get('isolationMode', 'normal'),
                           expectedVersion=message.get('expectedVersion'),
                           sagaType=message.get('sagaType', 'create'))
                tx.mark_seen(mid)
            print(f'[flow] saga={oid} {self.role} {action} attempt=0 ROLLBACK; delayed retry scheduled', flush=True)

    def _process_in_transaction(self, message, mid, oid, action):
        with self.store.transaction() as tx:
            if tx.seen(mid):
                return
            if message.get('countermeasureType'):
                self._handle_countermeasure(tx, message, mid, action)
                return
            previous = tx.completed_command(oid, action)
            if previous:
                tx.enqueue('reply.orchestrator', oid, action=previous,
                           sagaType=message.get('sagaType', 'create'))
                tx.mark_seen(mid)
                print(f'[flow] saga={oid} {self.role} idempotent duplicate {action}', flush=True)
                return

            attempt = int(message.get('attempt', 0))
            if action in RETRIABLE_COMMANDS and message.get('retryDemo', False) and attempt == 0:
                tx.record_attempt(oid, action, attempt, 'ROLLED_BACK')
                raise TransientCommandFailure(f'simulated transient failure in {action}')

            if self.role == 'consumer' and action == 'VerifyConsumer':
                result = 'ConsumerVerified' if consumer_approved(message['customerId']) else 'ConsumerRejected'
            elif self.role == 'kitchen' and action == 'CreateTicket':
                if message.get('simulateTicketFailure', False):
                    result = 'TicketCreationFailed'
                else:
                    tx.create_ticket(oid)
                    result = 'TicketCreated'
            elif self.role == 'kitchen' and action in ('ApproveTicket', 'RejectTicket'):
                tx.update_ticket(oid, 'AWAITING_ACCEPTANCE' if action == 'ApproveTicket' else 'REJECTED')
                result = 'TicketApproved' if action == 'ApproveTicket' else 'TicketRejected'
            elif self.role == 'accounting' and action == 'AuthorizeCard':
                tx.authorize_card(oid, 'AUTHORIZED' if card_authorized(message['amount']) else 'DECLINED')
                result = 'CardAuthorized' if card_authorized(message['amount']) else 'CardDeclined'
            elif self.role == 'accounting' and action == 'VoidAuthorization':
                tx.void_authorization(oid)
                result = 'AuthorizationVoided'
            elif self.role == 'order' and action == 'SetCancelled':
                tx.set_cancelled_after_pivot(oid)
                result = 'OrderCancelled'
            elif self.role == 'order' and action == 'ApproveOrder':
                mode = message.get('isolationMode', 'normal')
                if mode == 'unsafe':
                    tx.unsafe_approve(oid)
                    result = 'OrderApproved'
                elif mode == 'optimistic':
                    applied = tx.optimistic_approve(oid, int(message['expectedVersion']))
                    result = 'OrderApproved' if applied else 'OrderApprovalSkipped'
                elif mode in ('reread', 'pessimistic'):
                    # Reread Value: check current status at update time, not when queued.
                    applied = tx.reread_approve(oid)
                    result = 'OrderApproved' if applied else 'OrderApprovalSkipped'
                else:
                    tx.apply_order_status(oid, 'APPROVED')
                    result = 'OrderApproved'
            elif self.role == 'order' and action == 'RejectOrder':
                tx.apply_order_status(oid, 'REJECTED')
                result = 'OrderRejected'
            else:
                raise ValueError(f'Unsupported command {action} for {self.role}')

            tx.record_attempt(oid, action, attempt, 'SUCCEEDED')
            tx.record_completed_command(oid, action, result)
            tx.enqueue('reply.orchestrator', oid, action=result,
                       sagaType=message.get('sagaType', 'create'))
            tx.mark_seen(mid)
            print(f'[flow] saga={oid} {self.role} {action} attempt={attempt} -> {result}', flush=True)

    def _handle_countermeasure(self, tx, message, mid, action):
        """Saga-style participant commands: no direct SQL from the HTTP caller."""
        kind = message['countermeasureType']
        if self.role == 'consumer' and action == 'VerifyConsumer':
            result = ('CountermeasureVerified' if
                      consumer_approved(message['customerId']) else 'CountermeasureRejected')
            detail = {}
        elif self.role == 'accounting' and kind == 'commutative' and action == 'AdjustCredit':
            account_id = message['accountId']
            tx.initialize_credit(account_id, int(message['openingBalance']))
            balance = tx.adjust_credit(account_id, message['operationId'], int(message['delta']))
            result = 'CountermeasureCreditAdjusted'
            detail = {'accountId': account_id, 'balance': balance, 'delta': int(message['delta'])}
        elif self.role == 'kitchen' and kind == 'version-file' and action == 'ApplyVersioned':
            detail = tx.apply_versioned(message['streamId'], int(message['sequence']),
                                        message['operation'], int(message['value']))
            result = 'CountermeasureVersionApplied'
        else:
            raise ValueError(f'Unsupported {kind} command {action} for {self.role}')
        tx.enqueue('reply.orchestrator', message['orderId'], action=result,
            countermeasureType=kind, runId=message['runId'],
            stepId=message.get('stepId'), sagaId=message['sagaId'], **detail)
        tx.mark_seen(mid)
        print(f'[flow] {kind} role={self.role} saga={message["sagaId"]} '
              f'{action} -> {result} {detail}', flush=True)
