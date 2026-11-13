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
        held = bool(payload.pop('_hold', False))
        mid = str(uuid4())
        self.s['outbox'].append({'event_id':mid, 'routing_key':route, 'sent':False,
                                  'held':held, 'gate_order_id':order_id if held else None,
                                  'payload':json.dumps({'messageId':mid, 'orderId':order_id, **payload})})

    def create_order(self, oid, cid, amount, retry_demo=False, ticket_failure=False,
                     isolation_mode='normal'):
        assert oid not in self.s['orders']
        self.s['orders'][oid] = {'orderId':oid, 'customerId':cid, 'amount':amount,
                                 'status':'APPROVAL_PENDING', 'simulateRetry':bool(retry_demo),
                                 'simulateTicketFailure':bool(ticket_failure),
                                 'isolationMode':isolation_mode, 'version':0, 'cancelStage':None}
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
        if row['status'] != status:
            row['status']=status
            row['version']+=1

    def get_order_locked(self, oid):
        row=self.s['orders'].get(oid)
        return {'order_id':oid, 'status':row['status'],
                'isolationMode':row['isolationMode']} if row else None

    def isolation_mode(self, oid): return self.s['orders'][oid]['isolationMode']
    def get_version(self, oid): return self.s['orders'][oid]['version']
    def pause_approval(self, oid): self.s['approval_gates'][oid]='PAUSED'
    def approval_gate(self, oid): return self.s['approval_gates'].get(oid, 'NOT_REACHED')

    def release_approval(self, oid):
        assert self.approval_gate(oid)=='PAUSED'
        self.s['approval_gates'][oid]='RELEASED'
        for row in self.s['outbox']:
            if row['gate_order_id']==oid and row['held']:
                row['held']=False

    def unsafe_approve(self, oid):
        row=self.s['orders'][oid]
        row['status']='APPROVED'
        row['version']+=1

    def optimistic_approve(self, oid, expected_version):
        row=self.s['orders'][oid]
        if row['status']!='APPROVAL_PENDING' or row['version']!=expected_version:
            return False
        row['status']='APPROVED'
        row['version']+=1
        return True

    def get_cancel_stage(self, oid): return self.s['cancel_sagas'].get(oid)

    def start_cancellation(self, oid):
        self.s['orders'][oid]['status']='CANCELLATION_PENDING'
        self.s['orders'][oid]['version']+=1
        self.s['cancel_sagas'][oid]='VOID_AUTHORIZATION'
        self.s['orders'][oid]['cancelStage']='VOID_AUTHORIZATION'

    def set_cancel_stage(self, oid, stage):
        self.s['cancel_sagas'][oid]=stage
        self.s['orders'][oid]['cancelStage']=stage

    def finish_cancellation(self, oid):
        row=self.s['orders'][oid]
        if row['status']!='CANCELLATION_PENDING':
            raise ValueError('Cannot finish cancellation')
        row['status']='CANCELLED'
        row['version']+=1

    def record_cancel_transition(self, oid, prior, event, stage, command):
        self.s['cancel_history'].append({'order_id':oid, 'fromStage':prior,
                'event':event, 'toStage':stage, 'command':command})

    def get_cancel_history(self, oid):
        return [dict(h) for h in self.s['cancel_history'] if h['order_id']==oid]

    def void_authorization(self, oid):
        value=self.s['authorizations'].get(oid)
        if value!='AUTHORIZED' and value!='VOIDED':
            raise ValueError('Authorization missing')
        self.s['authorizations'][oid]='VOIDED'

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
            ('command_attempts',[]),('saga_history',[]),
            ('approval_gates',{}),('cancel_sagas',{}),('cancel_history',[]))}

    def initialize(self): pass

    @contextmanager
    def transaction(self):
        copy_state=copy.deepcopy(self.state)
        yield FakeTransaction(copy_state)
        self.state=copy_state

    def pending(self):
        return next((dict(row) for row in self.state['outbox'] if not row['sent'] and not row['held']),None)

    def mark_sent(self,mid):
        for row in self.state['outbox']:
            if row['event_id']==mid:
                row['sent']=True
