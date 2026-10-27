"""In-memory implementation of the storage port for fast broker-free tests.

It is NOT used by Docker or the application. Copy-on-write simulates an atomic
local transaction and verifies rollback without depending on PostgreSQL.
"""
import copy
import json
from contextlib import contextmanager
from uuid import uuid4


class FakeTransaction:
    def __init__(self, state):
        self.s = state

    def seen(self, mid): return mid in self.s['inbox']
    def mark_seen(self, mid): self.s['inbox'].add(mid)

    def enqueue(self, route, order_id, **payload):
        mid = str(uuid4())
        self.s['outbox'].append({'event_id':mid, 'routing_key':route, 'sent':False,
                                  'payload':json.dumps({'messageId':mid, 'orderId':order_id, **payload})})

    def create_order(self, oid, cid, amount, retry_demo=False, ticket_failure=False):
        assert oid not in self.s['orders']
        self.s['orders'][oid] = {'orderId':oid, 'customerId':cid, 'amount':amount,
                                 'status':'APPROVAL_PENDING', 'simulateRetry':bool(retry_demo),
                                 'simulateTicketFailure':bool(ticket_failure)}
        self.s['sagas'][oid] = 'VERIFY_CONSUMER'

    def get_order(self, oid):
        row=self.s['orders'].get(oid)
        return {**row, 'stage':self.s['sagas'][oid]} if row else None

    def get_stage(self, oid): return self.s['sagas'].get(oid)
    def set_stage(self, oid, stage): self.s['sagas'][oid] = stage

    def apply_order_status(self, oid, status):
        row=self.s['orders'].get(oid)
        if row is None or row['status'] not in ('APPROVAL_PENDING',status):
            raise ValueError(f'Cannot change order {oid} to {status}')
        row['status']=status

    def amount(self, oid): return self.s['orders'][oid]['amount']
    def retry_demo(self, oid): return self.s['orders'][oid]['simulateRetry']
    def ticket_failure(self, oid): return self.s['orders'][oid]['simulateTicketFailure']
    def create_ticket(self, oid): self.s['tickets'].setdefault(oid, 'CREATE_PENDING')

    def update_ticket(self, oid, state):
        if oid not in self.s['tickets']:
            raise ValueError('Unknown kitchen ticket')
        self.s['tickets'][oid] = state

    def authorize_card(self, oid, status): self.s['authorizations'].setdefault(oid, status)
    def completed_command(self, oid, action): return self.s['command_results'].get((oid,action))
    def record_completed_command(self, oid, action, result):
        self.s['command_results'].setdefault((oid,action),result)

    def record_attempt(self, oid, action, attempt, outcome):
        self.s['command_attempts'].append({'order_id':oid, 'action':action,
                                            'attempt':attempt, 'outcome':outcome})

    def record_transition(self, oid, prior, event, stage, command):
        self.s['saga_history'].append({'order_id':oid, 'fromStage':prior, 'event':event,
                                       'toStage':stage, 'command':command})

    def get_history(self, oid):
        return [dict(h) for h in self.s['saga_history'] if h['order_id']==oid]


class FakeSagaStore:
    def __init__(self, role):
        self.role=role
        self.state={key: value for key,value in (
            ('inbox',set()),('outbox',[]),('orders',{}),('sagas',{}),
            ('tickets',{}),('authorizations',{}),('command_results',{}),
            ('command_attempts',[]),('saga_history',[]))}

    def initialize(self): pass

    @contextmanager
    def transaction(self):
        copy_state=copy.deepcopy(self.state)
        yield FakeTransaction(copy_state)
        self.state=copy_state

    def pending(self):
        return next((dict(row) for row in self.state['outbox'] if not row['sent']),None)

    def mark_sent(self,mid):
        for row in self.state['outbox']:
            if row['event_id']==mid:
                row['sent']=True
