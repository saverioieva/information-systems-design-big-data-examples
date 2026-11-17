"""Broker-free, deterministic end-to-end application tests for two competing Sagas.

The fake store implements the same transaction port as PostgreSQL. The
ApproveOrder gate is held in the local outbox; all other messages keep flowing.
"""
import json
import unittest

from app.application.saga_coordinator import DomainConflict, SagaCoordinator
from uuid import uuid4
from app.application.saga_participant_handler import SagaParticipantHandler
from app.domain.cancel_state_machine import CancelOrderStateMachine
from fake_store import FakeSagaStore

ROUTES = {
    'command.consumer': 'consumer', 'command.kitchen': 'kitchen',
    'command.accounting': 'accounting', 'command.order': 'order',
    'reply.orchestrator': 'orchestrator',
    'retry.command.kitchen': 'kitchen', 'retry.command.order': 'order',
    'retry.command.accounting': 'accounting',
}


class CompetingSagasTest(unittest.TestCase):
    def setUp(self):
        self.stores = {role: FakeSagaStore(role) for role in
                       ('orchestrator', 'consumer', 'kitchen', 'accounting')}
        self.coordinator = SagaCoordinator(self.stores['orchestrator'])
        self.handlers = {role: SagaParticipantHandler(
            self.stores['orchestrator'] if role == 'order' else self.stores[role], role)
            for role in ('consumer', 'kitchen', 'accounting', 'order')}

    def drain(self):
        # The fake broker sees the same dispatch rules as PostgresSagaStore.pending().
        for _ in range(100):
            delivered = 0
            for store in self.stores.values():
                row = store.pending()
                if row:
                    message = json.loads(row['payload'])
                    role = ROUTES[row['routing_key']]
                    if role == 'orchestrator':
                        self.coordinator.handle_message(message)
                    else:
                        self.handlers[role].handle_message(message)
                    store.mark_sent(row['event_id'])
                    delivered += 1
            if not delivered:
                return
        self.fail('Application failed to converge')

    def paused(self, mode):
        oid = self.coordinator.place_order('CUST_1', 42, isolation_mode=mode)['orderId']
        self.drain()
        order = self.coordinator.get_order(oid)
        self.assertEqual(order['stage'], 'APPROVE_ORDER')
        self.assertEqual(order['status'], 'APPROVAL_PENDING')
        self.assertEqual(self.coordinator.gate(oid)['gate'], 'PAUSED')
        self.assertEqual(self.stores['kitchen'].state['tickets'][oid], 'AWAITING_ACCEPTANCE')
        self.assertEqual(self.stores['accounting'].state['authorizations'][oid], 'AUTHORIZED')
        self.assertTrue(any(r['held'] and r['routing_key'] == 'command.order'
                            for r in self.stores['orchestrator'].state['outbox']))
        return oid

    def completed_cancellation(self, oid):
        self.drain()
        row = self.coordinator.get_order(oid)
        self.assertEqual((row['status'], row['cancelStage']), ('CANCELLED', 'CANCELLED'))
        self.assertEqual(self.stores['accounting'].state['authorizations'][oid], 'VOIDED')
        self.assertEqual(self.stores['kitchen'].state['tickets'][oid], 'REJECTED')
        self.assertEqual([x['toStage'] for x in self.coordinator.cancellation_history(oid)],
                         ['VOID_AUTHORIZATION', 'REJECT_TICKET', 'CANCELLED'])

    def test_unsafe_overwrites_cancelled_even_though_local_transactions_commit(self):
        oid = self.paused('unsafe')
        self.coordinator.cancel_order(oid)
        self.completed_cancellation(oid)
        self.assertEqual(self.coordinator.get_order(oid)['version'], 2)
        self.coordinator.release_approval(oid)
        self.drain()
        row = self.coordinator.get_order(oid)
        self.assertEqual((row['status'], row['stage'], row['cancelStage']),
                         ('APPROVED', 'APPROVED', 'CANCELLED'))
        self.assertEqual(row['version'], 3)
        self.assertEqual(self.stores['accounting'].state['authorizations'][oid], 'VOIDED')

    def test_optimistic_compare_and_set_rejects_stale_command(self):
        oid = self.paused('optimistic')
        self.coordinator.cancel_order(oid)
        self.completed_cancellation(oid)
        self.coordinator.release_approval(oid)
        self.drain()
        row = self.coordinator.get_order(oid)
        self.assertEqual((row['status'], row['stage'], row['cancelStage']),
                         ('CANCELLED', 'SUPERSEDED', 'CANCELLED'))
        self.assertEqual(row['version'], 2)
        self.assertEqual(self.coordinator.history(oid)[-1]['event'], 'OrderApprovalSkipped')
        self.assertEqual(len([r for r in self.stores['orchestrator'].state['command_attempts']
                              if r['action'] == 'ApproveOrder']), 1)

    def test_reread_value_rechecks_live_status_without_queued_version(self):
        oid = self.paused('reread')
        self.coordinator.cancel_order(oid)
        self.completed_cancellation(oid)
        self.coordinator.release_approval(oid)
        self.drain()
        row = self.coordinator.get_order(oid)
        self.assertEqual((row['status'], row['stage']), ('CANCELLED', 'SUPERSEDED'))
        self.assertEqual(self.coordinator.history(oid)[-1]['event'], 'OrderApprovalSkipped')

    def test_pessimistic_view_uses_pivot_then_cancelled_then_void(self):
        oid = self.paused('pessimistic')
        started = self.coordinator.cancel_order(oid)
        # First transaction is compensatable: no external cancellation yet.
        before = self.coordinator.get_order(oid)
        self.assertEqual((started['status'], started['cancelStage']),
                         ('CANCELLATION_PENDING', 'REJECT_TICKET_PIVOT'))
        self.assertEqual((before['status'], before['cancelStage']),
                         ('CANCELLATION_PENDING', 'REJECT_TICKET_PIVOT'))
        self.assertEqual(self.coordinator.cancellation_gate(oid)['gate'], 'NOT_REACHED')
        self.assertEqual(self.stores['kitchen'].state['tickets'][oid], 'AWAITING_ACCEPTANCE')
        self.assertEqual(self.stores['accounting'].state['authorizations'][oid], 'AUTHORIZED')
        first = self.stores['orchestrator'].pending()
        self.assertEqual(json.loads(first['payload'])['action'], 'RejectTicket')
        self.assertFalse(any(json.loads(row['payload']).get('action') == 'VoidAuthorization'
                             for row in self.stores['orchestrator'].state['outbox']))

        # Kitchen confirms the pivot. SetCancelled retries once through the
        # Order retry queue, then the final Accounting command is held.
        self.drain()
        after_pivot = self.coordinator.get_order(oid)
        self.assertEqual((after_pivot['status'], after_pivot['cancelStage']),
                         ('CANCELLED', 'VOID_AUTHORIZATION_RETRIABLE'))
        self.assertEqual(after_pivot['version'], 2)
        self.assertEqual(self.coordinator.cancellation_gate(oid)['gate'], 'PAUSED')
        self.assertEqual(self.stores['kitchen'].state['tickets'][oid], 'REJECTED')
        self.assertEqual(self.stores['accounting'].state['authorizations'][oid], 'AUTHORIZED')
        self.assertTrue(any(row['held'] and row['routing_key'] == 'command.accounting'
                            and json.loads(row['payload'])['action'] == 'VoidAuthorization'
                            for row in self.stores['orchestrator'].state['outbox']))
        stages = [row['toStage'] for row in self.coordinator.cancellation_history(oid)]
        self.assertEqual(stages, ['REJECT_TICKET_PIVOT', 'SET_CANCELLED',
                                  'VOID_AUTHORIZATION_RETRIABLE'])
        attempts = [(r['attempt'], r['outcome']) for r in
                    self.stores['orchestrator'].state['command_attempts']
                    if r['order_id'] == oid and r['action'] == 'SetCancelled']
        self.assertEqual(attempts, [(0, 'TRANSIENT_FAILURE'), (1, 'SUCCEEDED')])

        # Distinct message IDs for an already completed retriable command
        # must not repeat the business state change or increment its version.
        self.handlers['order'].handle_message({'messageId': str(uuid4()),
            'orderId': oid, 'action': 'SetCancelled', 'sagaType': 'cancel'})
        self.drain()
        self.assertEqual(self.coordinator.get_order(oid)['version'], 2)

        # The stale CreateOrder approval is independently rejected by Reread.
        self.coordinator.release_approval(oid)
        self.drain()
        self.assertEqual(self.coordinator.get_order(oid)['stage'], 'SUPERSEDED')
        self.assertEqual(self.stores['accounting'].state['authorizations'][oid], 'AUTHORIZED')

        self.coordinator.release_cancellation(oid)
        self.drain()
        final = self.coordinator.get_order(oid)
        self.assertEqual((final['status'], final['cancelStage']), ('CANCELLED', 'CANCELLED'))
        self.assertEqual(final['version'], 2)
        self.assertEqual(self.stores['accounting'].state['authorizations'][oid], 'VOIDED')
        attempts = [(r['attempt'], r['outcome']) for r in
                    self.stores['accounting'].state['command_attempts']
                    if r['order_id'] == oid and r['action'] == 'VoidAuthorization']
        self.assertEqual(attempts, [(0, 'TRANSIENT_FAILURE'), (1, 'SUCCEEDED')])
        self.assertEqual([r['toStage'] for r in self.coordinator.cancellation_history(oid)],
                         ['REJECT_TICKET_PIVOT', 'SET_CANCELLED',
                          'VOID_AUTHORIZATION_RETRIABLE', 'CANCELLED'])
        with self.assertRaises(DomainConflict):
            self.coordinator.release_cancellation(oid)

    def test_set_cancelled_requires_the_completed_kitchen_pivot(self):
        oid = self.paused('pessimistic')
        self.coordinator.cancel_order(oid)
        with self.assertRaisesRegex(ValueError, 'completed Kitchen pivot'):
            with self.stores['orchestrator'].transaction() as tx:
                tx.set_cancelled_after_pivot(oid)
        self.assertEqual(self.coordinator.get_order(oid)['status'], 'CANCELLATION_PENDING')

    def test_by_value_selects_policy_by_amount_and_persists_effective_mode(self):
        low = self.coordinator.place_order('CUST_1', 42, isolation_mode='by_value')
        high = self.coordinator.place_order('CUST_1', 90, isolation_mode='by_value')
        self.assertEqual(low['isolationMode'], 'reread')
        self.assertEqual(high['isolationMode'], 'semantic')
        self.assertEqual(low['requestedIsolationMode'], 'by_value')
        self.assertEqual(self.coordinator.get_order(high['orderId'])['isolationMode'], 'semantic')
        self.drain()
        with self.assertRaisesRegex(DomainConflict, 'Semantic lock'):
            self.coordinator.cancel_order(high['orderId'])
        self.coordinator.cancel_order(low['orderId'])
        self.completed_cancellation(low['orderId'])
        self.coordinator.release_approval(low['orderId'])
        self.drain()
        self.assertEqual(self.coordinator.get_order(low['orderId'])['stage'], 'SUPERSEDED')
        self.coordinator.release_approval(high['orderId'])
        self.drain()
        self.assertEqual(self.coordinator.get_order(high['orderId'])['status'], 'APPROVED')

    def test_semantic_lock_refuses_concurrent_cancel_then_allows_later(self):
        oid = self.paused('semantic')
        with self.assertRaisesRegex(DomainConflict, 'Semantic lock'):
            self.coordinator.cancel_order(oid)
        self.assertIsNone(self.coordinator.get_order(oid)['cancelStage'])
        self.coordinator.release_approval(oid)
        self.drain()
        self.assertEqual(self.coordinator.get_order(oid)['status'], 'APPROVED')
        self.coordinator.cancel_order(oid)
        self.completed_cancellation(oid)
        self.assertEqual(self.coordinator.get_order(oid)['stage'], 'APPROVED')

    def test_gate_cannot_release_before_paused_or_twice(self):
        oid = self.coordinator.place_order('CUST_1', 42, isolation_mode='optimistic')['orderId']
        with self.assertRaises(DomainConflict):
            self.coordinator.release_approval(oid)
        self.drain()
        self.coordinator.release_approval(oid)
        with self.assertRaises(DomainConflict):
            self.coordinator.release_approval(oid)

    def test_unsafe_not_default_and_normal_saga_is_guarded(self):
        oid = self.coordinator.place_order('CUST_1', 42)['orderId']
        self.drain()
        self.assertEqual(self.coordinator.get_order(oid)['status'], 'APPROVED')
        self.assertEqual(self.coordinator.gate(oid)['gate'], 'NOT_REACHED')
        self.assertFalse(any(r['held'] for r in self.stores['orchestrator'].state['outbox']))

    def test_cancel_machine_ignores_out_of_order_reply(self):
        machine = CancelOrderStateMachine()
        self.assertIsNone(machine.advance('VOID_AUTHORIZATION', 'TicketRejected'))
        self.assertEqual(machine.advance('REJECT_TICKET', 'TicketRejected').stage, 'CANCELLED')
        self.assertEqual(machine.advance('REJECT_TICKET_PIVOT', 'TicketRejected').stage, 'SET_CANCELLED')
        self.assertEqual(machine.advance('SET_CANCELLED', 'OrderCancelled').stage, 'VOID_AUTHORIZATION_RETRIABLE')
        self.assertEqual(machine.advance('VOID_AUTHORIZATION_RETRIABLE', 'AuthorizationVoided').stage, 'CANCELLED')

    def test_duplicate_cancel_is_rejected(self):
        oid = self.paused('optimistic')
        self.coordinator.cancel_order(oid)
        with self.assertRaises(DomainConflict):
            self.coordinator.cancel_order(oid)

    def test_held_approval_does_not_block_other_outbox_messages(self):
        oid = self.paused('optimistic')
        self.coordinator.cancel_order(oid)
        row = self.stores['orchestrator'].pending()
        self.assertIsNotNone(row)
        self.assertEqual(json.loads(row['payload'])['action'], 'VoidAuthorization')


if __name__ == '__main__':
    unittest.main()
