"""End-to-end saga logic via the storage port and an in-process broker.

No SQLite or PostgreSQL is required for these application-level tests.
PostgreSQL-specific tests are in test_postgres_store.py.
"""
import json
import unittest
from uuid import uuid4

from app.application.saga_coordinator import SagaCoordinator
from app.application.saga_participant_handler import SagaParticipantHandler
from fake_store import FakeSagaStore


class SagaWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.stores = {role: FakeSagaStore(role) for role in
                       ('orchestrator','consumer','kitchen','accounting')}
        self.coordinator = SagaCoordinator(self.stores['orchestrator'])
        self.handlers = {role: SagaParticipantHandler(
            self.stores['orchestrator'] if role == 'order' else self.stores[role], role)
            for role in ('consumer','kitchen','accounting','order')}
        self.delivered = []

    def drain(self):
        destinations = {
            'command.consumer':'consumer', 'command.kitchen':'kitchen',
            'command.accounting':'accounting','command.order':'order',
            'reply.orchestrator':'orchestrator',
            # Fake broker models TTL expiry immediately.
            'retry.command.kitchen':'kitchen','retry.command.order':'order',
        }
        for _ in range(100):
            dispatched=0
            for store in self.stores.values():
                row=store.pending()
                if row:
                    self.delivered.append(row)
                    destination=destinations[row['routing_key']]
                    message=json.loads(row['payload'])
                    if destination == 'orchestrator':
                        self.coordinator.handle_message(message)
                    else:
                        self.handlers[destination].handle_message(message)
                    store.mark_sent(row['event_id'])
                    dispatched+=1
            if not dispatched:
                return
        raise AssertionError('Saga did not converge')

    def new_order(self, customer='CUST_OK', amount=25, retry_demo=False, ticket_failure=False):
        return self.coordinator.place_order(customer,amount,retry_demo,ticket_failure)['orderId']

    def test_success_matches_every_state_in_diagram(self):
        oid=self.new_order()
        self.drain()
        row=self.coordinator.get_order(oid)
        self.assertEqual((row['status'],row['stage']),('APPROVED','APPROVED'))
        history=self.coordinator.history(oid)
        self.assertEqual([h['toStage'] for h in history],
                         ['VERIFY_CONSUMER','CREATE_TICKET','AUTHORIZE_CARD',
                          'APPROVE_TICKET','APPROVE_ORDER','APPROVED'])
        self.assertEqual(history[-1]['event'],'OrderApproved')

    def test_declined_card_compensates_and_rejects_order(self):
        oid=self.new_order(amount=150)
        self.drain()
        row=self.coordinator.get_order(oid)
        self.assertEqual((row['status'],row['stage']),('REJECTED','REJECTED'))
        self.assertEqual([h['toStage'] for h in self.coordinator.history(oid)][-3:],
                         ['REJECT_TICKET','REJECT_ORDER','REJECTED'])
        self.assertEqual(self.stores['kitchen'].state['tickets'][oid],'REJECTED')

    def test_invalid_consumer_rejects_order_without_creating_ticket(self):
        oid=self.new_order(customer='CUST_INVALID')
        self.drain()
        self.assertEqual([h['toStage'] for h in self.coordinator.history(oid)],
                         ['VERIFY_CONSUMER','REJECT_ORDER','REJECTED'])
        self.assertFalse(self.stores['kitchen'].state['tickets'])

    def test_ticket_creation_failure_rejects_order(self):
        oid=self.new_order(ticket_failure=True)
        self.drain()
        self.assertEqual([h['toStage'] for h in self.coordinator.history(oid)],
                         ['VERIFY_CONSUMER','CREATE_TICKET','REJECT_ORDER','REJECTED'])
        self.assertFalse(self.stores['kitchen'].state['tickets'])

    def test_duplicate_message_id_is_idempotent(self):
        self.new_order()
        message=json.loads(self.stores['orchestrator'].pending()['payload'])
        self.handlers['consumer'].handle_message(message)
        self.handlers['consumer'].handle_message(message)
        state=self.stores['consumer'].state
        self.assertEqual(len(state['outbox']),1)
        self.assertEqual(len(state['command_results']),1)

    def test_duplicate_semantic_command_with_new_message_id_has_no_new_business_effect(self):
        self.new_order()
        message=json.loads(self.stores['orchestrator'].pending()['payload'])
        self.handlers['consumer'].handle_message(message)
        message['messageId']=str(uuid4())
        self.handlers['consumer'].handle_message(message)
        state=self.stores['consumer'].state
        self.assertEqual(len(state['command_results']),1)
        self.assertEqual(len(state['command_attempts']),1)

    def test_retriable_steps_fail_then_succeed_once(self):
        oid=self.new_order(retry_demo=True)
        self.drain()
        self.assertEqual(self.coordinator.get_order(oid)['status'],'APPROVED')
        for role, command in (('kitchen','ApproveTicket'),('orchestrator','ApproveOrder')):
            attempts=[(r['attempt'],r['outcome']) for r in self.stores[role].state['command_attempts']
                      if r['order_id']==oid and r['action']==command]
            self.assertEqual(attempts,[(0,'TRANSIENT_FAILURE'),(1,'SUCCEEDED')])
            self.assertEqual(sum(k==(oid,command) for k in self.stores[role].state['command_results']),1)
        self.assertEqual(len([h for h in self.coordinator.history(oid) if h['event']=='OrderApproved']),1)
        self.assertIn('retry.command.kitchen',[row['routing_key'] for row in self.delivered])
        self.assertIn('retry.command.order',[row['routing_key'] for row in self.delivered])

    def test_new_message_id_after_success_does_not_repeat_approve_order(self):
        oid=self.new_order()
        self.drain()
        duplicate={'messageId':str(uuid4()),'orderId':oid,'action':'ApproveOrder'}
        self.handlers['order'].handle_message(duplicate)
        state=self.stores['orchestrator'].state
        self.assertEqual(sum(r['action']=='ApproveOrder' and r['order_id']==oid
                             for r in state['command_attempts']),1)
        self.assertEqual(self.coordinator.get_order(oid)['status'],'APPROVED')


if __name__=='__main__':
    unittest.main()
