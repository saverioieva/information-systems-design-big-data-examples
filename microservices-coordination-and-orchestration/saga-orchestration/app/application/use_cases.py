"""Saga coordination and participants; no SQL/Pika imports."""
from uuid import uuid4
from app.domain.transitions import TRANSITIONS
from app.domain.policy import consumer_approved,card_authorized
from app.ports.storage import SagaStore

class SagaUseCases:
    def __init__(self,store:SagaStore,role:str):
        self.store,self.role=store,role

    def place_order(self,customer_id:str,amount:float) -> dict:
        oid=str(uuid4())
        with self.store.transaction() as tx:
            tx.create_order(oid,customer_id,amount)
            tx.enqueue('command.consumer',oid,action='VerifyConsumer',customerId=customer_id)
        return {'orderId':oid,'status':'APPROVAL_PENDING','stage':'VERIFY_CONSUMER'}

    def get_order(self,order_id:str) -> dict | None:
        with self.store.transaction() as tx: return tx.get_order(order_id)

    def handle_message(self,message:dict) -> None:
        mid=message['messageId']
        with self.store.transaction() as tx:
            if tx.seen(mid): return
            if self.role=='orchestrator': self._reply(tx,message)
            else: self._command(tx,message)
            tx.mark_seen(mid)

    def _reply(self,tx,message):
        oid=message['orderId']
        previous=tx.get_stage(oid)
        step=TRANSITIONS.get((previous,message['action']))
        if step is None: return  # stale/unknown reply, not a new saga step
        stage,route,action=step
        tx.set_stage(oid,stage)
        if route:
            data={'action':action}
            if action=='AuthorizeCard':data['amount']=tx.amount(oid)
            tx.enqueue(route,oid,**data)
        print(f'[orchestrator] {oid}: {previous} -> {stage}',flush=True)

    def _command(self,tx,message):
        oid,action=message['orderId'],message['action']
        if self.role=='consumer' and action=='VerifyConsumer':
            result='ConsumerVerified' if consumer_approved(message['customerId']) else 'ConsumerRejected'
        elif self.role=='kitchen' and action=='CreateTicket':
            tx.create_ticket(oid); result='TicketCreated'
        elif self.role=='kitchen' and action in ('ApproveTicket','RejectTicket'):
            tx.update_ticket(oid,'AWAITING_ACCEPTANCE' if action=='ApproveTicket' else 'REJECTED')
            result='TicketApproved' if action=='ApproveTicket' else 'TicketRejected'
        elif self.role=='accounting' and action=='AuthorizeCard':
            good=card_authorized(message['amount'])
            tx.authorize_card(oid,'AUTHORIZED' if good else 'DECLINED')
            result='CardAuthorized' if good else 'CardDeclined'
        else:
            raise ValueError(f'Unsupported command {action} for {self.role}')
        tx.enqueue('reply.orchestrator',oid,action=result)
