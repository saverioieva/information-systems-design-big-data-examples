"""Exercise the actual HTTP-facing coordinator and participant workflow logic.

Four independent in-memory stores emulate each service's local transaction
boundary; an explicit queue pump substitutes only for the RabbitMQ transport.
"""
import json
import unittest

from fake_store import FakeSagaStore
from app.application.countermeasure_workflows import CountermeasureWorkflows
from app.application.saga_coordinator import SagaCoordinator
from app.application.saga_participant_handler import SagaParticipantHandler


class DistributedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.stores = {role: FakeSagaStore(role) for role in
                       ('orchestrator', 'consumer', 'accounting', 'kitchen')}
        self.app = CountermeasureWorkflows(self.stores['orchestrator'])
        self.coordinator = SagaCoordinator(self.stores['orchestrator'])
        self.coordinator.countermeasures = self.app
        self.participants = {role: SagaParticipantHandler(self.stores[role], role)
                             for role in ('consumer', 'accounting', 'kitchen')}
        self.traces = []

    def pump(self, max_messages=100):
        processed = 0
        while processed < max_messages:
            current = None
            for role, store in self.stores.items():
                row = store.pending()
                if row is not None:
                    current = role, store, row
                    break
            if current is None:
                return
            role, store, row = current
            msg = json.loads(row['payload'])
            route = row['routing_key']
            self.assertFalse(row['held'])
            self.traces.append((role, route, msg))
            target = ('orchestrator' if route == 'reply.orchestrator'
                      else route.split('.')[-1])
            if target == 'orchestrator':
                self.coordinator.handle_message(msg)
            else:
                self.participants[target].handle_message(msg)
            store.mark_sent(row['event_id'])
            processed += 1
        self.fail(f'Message pump exceeded {max_messages} messages')

    def test_commutative_credit_adjustment_sagas_uses_consumer_and_accounting(self):
        run_id = self.app.start_commutative()['runId']
        self.pump()
        run = self.app.get(run_id)
        self.assertEqual(run['status'], 'COMPLETED')
        self.assertEqual(len(run['steps']), 6)  # 4 credit, duplicate, compensation
        self.assertTrue(all(s['status'] == 'DONE' for s in run['steps']))
        accounts = self.stores['accounting'].state['credit_balances']
        self.assertEqual(accounts[f'{run_id}-A'], 90)
        self.assertEqual(accounts[f'{run_id}-B'], 115)
        adjustments = self.stores['accounting'].state['credit_adjustments']
        self.assertEqual(len(adjustments), 5)  # duplicate not applied twice
        self.assertTrue(any(r == 'command.consumer' for _, r, _ in self.traces))
        self.assertTrue(any(r == 'command.accounting' for _, r, _ in self.traces))
        self.assertTrue(any(r == 'reply.orchestrator' for _, r, _ in self.traces))
        self.assertFalse(self.stores['orchestrator'].state['credit_balances'])
        self.assertEqual(len(self.stores['orchestrator'].state['countermeasure_runs']), 1)

    def test_version_file_commands_travel_over_kitchen_queue_in_arrival_order(self):
        run_id = self.app.start_version_file()['runId']
        self.pump()
        run = self.app.get(run_id)
        self.assertEqual(run['status'], 'COMPLETED')
        self.assertEqual(len(run['steps']), 3)
        by_seq = {s['data']['sequence']: s['result'] for s in run['steps']}
        self.assertEqual(by_seq[3], {'nextSequence': 1, 'total': 0, 'buffered': 1})
        self.assertEqual(by_seq[1], {'nextSequence': 2, 'total': 10, 'buffered': 1})
        self.assertEqual(by_seq[2], {'nextSequence': 4, 'total': 27, 'buffered': 0})
        arrival = [m['sequence'] for _, route, m in self.traces
                   if route == 'command.kitchen' and m['action'] == 'ApplyVersioned']
        self.assertEqual(arrival, [3, 1, 2])
        self.assertEqual(self.stores['kitchen'].state['version_file_states'][run_id]['total'], 27)
        self.assertNotIn(run_id, self.stores['orchestrator'].state['version_file_states'])
        self.assertTrue(any(route == 'command.consumer' for _, route, _ in self.traces))

    def test_duplicate_broker_delivery_is_idempotent(self):
        run_id = self.app.start_version_file()['runId']
        self.pump()
        before = self.app.get(run_id)
        previous = next(m for _, r, m in self.traces
                        if r == 'command.kitchen' and m['sequence'] == 3)
        self.participants['kitchen'].handle_message(previous)
        self.assertEqual(self.stores['kitchen'].state['version_file_states'][run_id]['total'], 27)
        self.assertEqual(self.app.get(run_id), before)

    def test_repeated_start_uses_independent_run_ids(self):
        a = self.app.start_commutative()['runId']
        b = self.app.start_commutative()['runId']
        self.assertNotEqual(a, b)
        self.pump(max_messages=200)
        self.assertEqual(self.app.get(a)['status'], 'COMPLETED')
        self.assertEqual(self.app.get(b)['status'], 'COMPLETED')


if __name__ == '__main__':
    unittest.main()
