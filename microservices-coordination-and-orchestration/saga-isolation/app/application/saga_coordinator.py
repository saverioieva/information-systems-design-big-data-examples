"""CreateOrder and CancelOrder coordinators: application layer, no SQL/AMQP.

For isolation experiments only, the ApproveOrder command is *durably held*
in Order's outbox until the instructor explicitly releases it. This holds a
message, not a SQL transaction or a RabbitMQ consumer acknowledgment.
"""
from uuid import uuid4

from app.domain.state_machine import SagaStateMachine
from app.domain.cancel_state_machine import CancelOrderStateMachine
from app.ports.storage import SagaStore

MODES = {'normal', 'unsafe', 'semantic', 'optimistic'}


class DomainConflict(ValueError):
    """Request is valid HTTP but conflicts with the current business state."""


class SagaCoordinator:
    def __init__(self, store: SagaStore, state_machine: SagaStateMachine | None = None):
        self.store = store
        self.state_machine = state_machine or SagaStateMachine()
        self.cancel_machine = CancelOrderStateMachine()

    def place_order(self, customer_id: str, amount: float, retry_demo: bool = False,
                    ticket_failure: bool = False, isolation_mode: str = 'normal') -> dict:
        if isolation_mode not in MODES:
            raise ValueError(f'Unknown isolation mode: {isolation_mode}')
        order_id = str(uuid4())
        with self.store.transaction() as tx:
            tx.create_order(order_id, customer_id, amount, retry_demo, ticket_failure,
                            isolation_mode=isolation_mode)
            tx.enqueue('command.consumer', order_id, action='VerifyConsumer', customerId=customer_id)
            tx.record_transition(order_id, None, 'SagaStarted', 'VERIFY_CONSUMER', 'VerifyConsumer')
        print(f'[flow] saga={order_id} START -> VERIFY_CONSUMER mode={isolation_mode}', flush=True)
        return {'orderId': order_id, 'status': 'APPROVAL_PENDING', 'stage': 'VERIFY_CONSUMER',
                'isolationMode': isolation_mode}

    def get_order(self, order_id: str) -> dict | None:
        with self.store.transaction() as tx:
            return tx.get_order(order_id)

    def history(self, order_id: str) -> list[dict] | None:
        with self.store.transaction() as tx:
            if tx.get_order(order_id) is None:
                return None
            return tx.get_history(order_id)

    def cancellation_history(self, order_id: str) -> list[dict] | None:
        with self.store.transaction() as tx:
            if tx.get_order(order_id) is None:
                return None
            return tx.get_cancel_history(order_id)

    def gate(self, order_id: str) -> dict | None:
        with self.store.transaction() as tx:
            if tx.get_order(order_id) is None:
                return None
            return {'orderId': order_id, 'gate': tx.approval_gate(order_id)}

    def release_approval(self, order_id: str) -> dict:
        with self.store.transaction() as tx:
            if tx.get_order(order_id) is None:
                raise LookupError('Order not found')
            if tx.approval_gate(order_id) != 'PAUSED':
                raise DomainConflict('Approval is not paused (or has already been released)')
            tx.release_approval(order_id)
        print(f'[isolation] saga={order_id} HELD ApproveOrder released', flush=True)
        return {'orderId': order_id, 'gate': 'RELEASED'}

    def cancel_order(self, order_id: str) -> dict:
        with self.store.transaction() as tx:
            row = tx.get_order_locked(order_id)
            if row is None:
                raise LookupError('Order not found')
            # This isolated demo only cancels after the authorization and ticket
            # have been created, avoiding unrelated incomplete-workflow cases.
            if row['status'] == 'APPROVAL_PENDING':
                if row['isolationMode'] == 'semantic':
                    raise DomainConflict('Semantic lock: CreateOrder still in APPROVAL_PENDING')
                if row['isolationMode'] not in ('unsafe', 'optimistic') or tx.approval_gate(order_id) != 'PAUSED':
                    raise DomainConflict('Wait for the ApproveOrder demonstration gate')
            elif row['status'] != 'APPROVED':
                raise DomainConflict(f'Order status {row["status"]} cannot be cancelled')
            if tx.get_cancel_stage(order_id) is not None:
                raise DomainConflict('Cancellation already requested')
            tx.start_cancellation(order_id)
            tx.enqueue('command.accounting', order_id, action='VoidAuthorization', sagaType='cancel')
            tx.record_cancel_transition(order_id, None, 'CancelRequested',
                                        'VOID_AUTHORIZATION', 'VoidAuthorization')
        print(f'[isolation] saga={order_id} CANCEL START -> VOID_AUTHORIZATION', flush=True)
        return {'orderId': order_id, 'status': 'CANCELLATION_PENDING',
                'cancelStage': 'VOID_AUTHORIZATION'}

    def handle_message(self, message: dict) -> None:
        with self.store.transaction() as tx:
            mid = message['messageId']
            if tx.seen(mid):
                return
            order_id, reply = message['orderId'], message['action']
            if message.get('sagaType') == 'cancel':
                current = tx.get_cancel_stage(order_id)
                transition = self.cancel_machine.advance(current, reply)
                if transition:
                    tx.set_cancel_stage(order_id, transition.stage)
                    tx.record_cancel_transition(order_id, current, reply,
                                                transition.stage, transition.command)
                    if transition.route:
                        tx.enqueue(transition.route, order_id, action=transition.command,
                                   sagaType='cancel')
                    else:
                        tx.finish_cancellation(order_id)
                    print(f'[flow] CANCEL saga={order_id} {current} --{reply}--> {transition.stage}', flush=True)
                else:
                    print(f'[flow] CANCEL saga={order_id} ignoring unexpected reply {reply} in {current}', flush=True)
            else:
                current = tx.get_stage(order_id)
                transition = self.state_machine.advance(current, reply)
                if transition:
                    tx.set_stage(order_id, transition.stage)
                    tx.record_transition(order_id, current, reply,
                                         transition.stage, transition.command)
                    if transition.route:
                        data = {'action': transition.command}
                        if transition.command == 'CreateTicket':
                            data['simulateTicketFailure'] = tx.ticket_failure(order_id)
                        if transition.command == 'AuthorizeCard':
                            data['amount'] = tx.amount(order_id)
                        if transition.command in ('ApproveTicket', 'ApproveOrder'):
                            data['retryDemo'] = tx.retry_demo(order_id)
                            data['attempt'] = 0
                        if transition.command == 'ApproveOrder':
                            mode = tx.isolation_mode(order_id)
                            data['isolationMode'] = mode
                            data['expectedVersion'] = tx.get_version(order_id)
                            if mode != 'normal':
                                tx.pause_approval(order_id)
                                data['_hold'] = True
                        tx.enqueue(transition.route, order_id, **data)
                    print(f'[flow] saga={order_id} {current} --{reply}--> {transition.stage}'
                          + (f' / send {transition.command}' if transition.command else ''), flush=True)
                else:
                    print(f'[flow] saga={order_id} ignoring stale/unexpected reply {reply} in {current}', flush=True)
            tx.mark_seen(mid)
