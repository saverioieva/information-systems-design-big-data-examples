"""CreateOrder and CancelOrder coordinators: application layer, no SQL/AMQP.

TEST-ONLY SCENARIO SYNCHRONIZATION (not a Saga isolation technique):
selected ApproveOrder and compensation commands can be durably held in the
Order Outbox until the scenario runner releases them. This controls message
delivery timing, not transaction isolation; no SQL transaction or RabbitMQ
consumer acknowledgement remains open while a message is held.
"""
from uuid import uuid4

from app.domain.state_machine import SagaStateMachine
from app.domain.cancel_state_machine import CancelOrderStateMachine
from app.domain.isolation_policy import select_isolation_mode
from app.ports.storage import SagaStore

MODES = {'normal', 'unsafe', 'semantic', 'optimistic', 'reread', 'pessimistic', 'by_value'}


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
        selected_mode = select_isolation_mode(amount) if isolation_mode == 'by_value' else isolation_mode
        order_id = str(uuid4())
        with self.store.transaction() as tx:
            tx.create_order(order_id, customer_id, amount, retry_demo, ticket_failure,
                            isolation_mode=selected_mode)
            tx.enqueue('command.consumer', order_id, action='VerifyConsumer', customerId=customer_id)
            tx.record_transition(order_id, None, 'SagaStarted', 'VERIFY_CONSUMER', 'VerifyConsumer')
        print(f'[flow] saga={order_id} START -> VERIFY_CONSUMER mode={selected_mode}', flush=True)
        return {'orderId': order_id, 'status': 'APPROVAL_PENDING', 'stage': 'VERIFY_CONSUMER',
                'isolationMode': selected_mode, 'requestedIsolationMode': isolation_mode}

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

    def cancellation_gate(self, order_id: str) -> dict | None:
        with self.store.transaction() as tx:
            if tx.get_order(order_id) is None:
                return None
            return {'orderId': order_id, 'gate': tx.cancellation_gate(order_id)}

    def release_cancellation(self, order_id: str) -> dict:
        with self.store.transaction() as tx:
            if tx.get_order(order_id) is None:
                raise LookupError('Order not found')
            if tx.cancellation_gate(order_id) != 'PAUSED':
                raise DomainConflict('Cancellation is not paused')
            tx.release_cancellation(order_id)
        return {'orderId': order_id, 'gate': 'RELEASED'}

    def cancel_order(self, order_id: str) -> dict:
        with self.store.transaction() as tx:
            row = tx.get_order_locked(order_id)
            if row is None:
                raise LookupError('Order not found')
            # Scenario restriction: only cancel after authorization and ticket
            # have been created, avoiding unrelated incomplete-workflow cases.
            if row['status'] == 'APPROVAL_PENDING':
                if row['isolationMode'] == 'semantic':
                    raise DomainConflict('Semantic lock: CreateOrder still in APPROVAL_PENDING')
                if row['isolationMode'] not in ('unsafe', 'optimistic', 'reread', 'pessimistic') or tx.approval_gate(order_id) != 'PAUSED':
                    raise DomainConflict('Wait for the scenario-control approval gate')
            elif row['status'] != 'APPROVED':
                raise DomainConflict(f'Order status {row["status"]} cannot be cancelled')
            if tx.get_cancel_stage(order_id) is not None:
                raise DomainConflict('Cancellation already requested')
            pessimistic = row['isolationMode'] == 'pessimistic'
            first_stage = 'REJECT_TICKET_PIVOT' if pessimistic else 'VOID_AUTHORIZATION'
            first_route = 'command.kitchen' if pessimistic else 'command.accounting'
            first_command = 'RejectTicket' if pessimistic else 'VoidAuthorization'
            tx.start_cancellation(order_id, initial_stage=first_stage)
            # Commit the pending state and the initial command in the same local
            # transaction. The Kitchen pivot must succeed before CANCELLED or
            # the final credit release is scheduled.
            tx.enqueue(first_route, order_id, action=first_command, sagaType='cancel')
            tx.record_cancel_transition(order_id, None, 'CancelRequested',
                                        first_stage, first_command)
        print(f'[isolation] saga={order_id} CANCEL START -> {first_stage}', flush=True)
        return {'orderId': order_id, 'status': 'CANCELLATION_PENDING',
                'cancelStage': first_stage}

    def handle_message(self, message: dict) -> None:
        if message.get('countermeasureType'):
            self.countermeasures.handle_message(message)
            return
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
                        command_data = {'action': transition.command, 'sagaType': 'cancel'}
                        if transition.command == 'SetCancelled':
                            # Post-pivot operation: transient failure is retried
                            # through the durable Order retry Outbox / TTL queue.
                            command_data.update(retryDemo=True, attempt=0)
                        if current == 'SET_CANCELLED' and transition.command == 'VoidAuthorization':
                            # Pessimistic View: CANCELLED is already committed;
                            # hold only the final credit release for observation.
                            tx.pause_cancellation(order_id)  # test-only gate
                            command_data.update(retryDemo=True, attempt=0, _hold=True)
                        tx.enqueue(transition.route, order_id, **command_data)
                    else:
                        if tx.isolation_mode(order_id) == 'pessimistic':
                            # Already committed by SetCancelled after the pivot.
                            if tx.get_order_locked(order_id)['status'] != 'CANCELLED':
                                raise ValueError('Post-pivot CANCELLED transition missing')
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
                                # TEST-ONLY synchronization; not an isolation countermeasure.
                                tx.pause_approval(order_id)
                                data['_hold'] = True
                        tx.enqueue(transition.route, order_id, **data)
                    print(f'[flow] saga={order_id} {current} --{reply}--> {transition.stage}'
                          + (f' / send {transition.command}' if transition.command else ''), flush=True)
                else:
                    print(f'[flow] saga={order_id} ignoring stale/unexpected reply {reply} in {current}', flush=True)
            tx.mark_seen(mid)
