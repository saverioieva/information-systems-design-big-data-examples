"""Application service: transitions and outbound commands, without SQL or AMQP."""
from uuid import uuid4

from app.domain.state_machine import SagaStateMachine
from app.ports.storage import SagaStore


class SagaCoordinator:
    def __init__(self, store: SagaStore, state_machine: SagaStateMachine | None = None):
        self.store = store
        self.state_machine = state_machine or SagaStateMachine()

    def place_order(self, customer_id: str, amount: float, retry_demo: bool = False, ticket_failure: bool = False) -> dict:
        order_id = str(uuid4())
        with self.store.transaction() as tx:
            tx.create_order(order_id, customer_id, amount, retry_demo, ticket_failure)
            tx.enqueue('command.consumer', order_id, action='VerifyConsumer', customerId=customer_id)
            tx.record_transition(order_id, None, 'SagaStarted', 'VERIFY_CONSUMER', 'VerifyConsumer')
        print(f'[flow] saga={order_id} START -> VERIFY_CONSUMER', flush=True)
        return {'orderId': order_id, 'status': 'APPROVAL_PENDING', 'stage': 'VERIFY_CONSUMER'}

    def get_order(self, order_id: str) -> dict | None:
        with self.store.transaction() as tx:
            return tx.get_order(order_id)

    def history(self, order_id: str) -> list[dict] | None:
        with self.store.transaction() as tx:
            if tx.get_order(order_id) is None:
                return None
            return tx.get_history(order_id)

    def handle_message(self, message: dict) -> None:
        with self.store.transaction() as tx:
            mid = message['messageId']
            if tx.seen(mid):
                return
            order_id, reply = message['orderId'], message['action']
            current_stage = tx.get_stage(order_id)
            transition = self.state_machine.advance(current_stage, reply)
            if transition:
                tx.set_stage(order_id, transition.stage)
                tx.record_transition(order_id, current_stage, reply,
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
                    tx.enqueue(transition.route, order_id, **data)
                print(f'[flow] saga={order_id} {current_stage} --{reply}--> {transition.stage}'
                      + (f' / send {transition.command}' if transition.command else ''), flush=True)
            else:
                print(f'[flow] saga={order_id} ignoring stale/unexpected reply {reply} in {current_stage}', flush=True)
            tx.mark_seen(mid)
