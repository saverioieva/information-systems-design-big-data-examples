"""Contract and pure application tests; no Docker services are needed."""
import json
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from app.contract import decode_message
from app.application.log_tail_relay import extract_outbox_messages, LogTailRelay


class Recorder:
    def __init__(self, fail=False):
        self.messages = []
        self.fail = fail
    def publish(self, event):
        if self.fail:
            raise ConnectionError('broker temporarily unreachable')
        self.messages.append(event)


def wal_batch(changes):
    return json.dumps({'xid': 12, 'change': changes})


def inserted(event_id='event-1', order_id='order-1'):
    payload = {'type': 'OrderCreated', 'eventId': event_id,
               'orderId': order_id, 'amount': 42.0}
    return {'kind': 'insert', 'schema': 'public', 'table': 'outbox_events',
            'columnnames': ['event_id','aggregate_type','aggregate_id','event_type','payload'],
            'columnvalues': [event_id, 'orders', order_id, 'OrderCreated', payload]}


class LogTailingTests(unittest.TestCase):
    def test_only_committed_outbox_inserts_are_selected(self):
        irrelevant = {'kind':'update','schema':'public','table':'orders',
                      'columnnames':[],'columnvalues':[]}
        events = extract_outbox_messages(wal_batch([irrelevant, inserted(),
                        {**inserted(event_id='event-2'), 'kind':'delete'}]))
        self.assertEqual([e['eventId'] for e in events], ['event-1'])

    def test_transaction_can_have_multiple_messages(self):
        recorder = Recorder()
        n = LogTailRelay(recorder).process_transaction(wal_batch([inserted(), inserted('event-2')]))
        self.assertEqual(n, 2)
        self.assertEqual(len(recorder.messages), 2)

    def test_broker_failure_not_swallowed(self):
        with self.assertRaises(ConnectionError):
            LogTailRelay(Recorder(fail=True)).process_transaction(wal_batch([inserted()]))

    def test_bad_row_rejected(self):
        row = inserted()
        row['columnvalues'][0] = 'different-id'
        with self.assertRaises(ValueError):
            extract_outbox_messages(wal_batch([row]))

    def test_payload_json_string(self):
        row = inserted()
        row['columnvalues'][4] = json.dumps(row['columnvalues'][4])
        self.assertEqual(extract_outbox_messages(wal_batch([row]))[0]['orderId'], 'order-1')

    def test_slot_bootstrap_before_api(self):
        compose = (BASE/'docker-compose.yml').read_text()
        self.assertIn('slot-init:', compose)
        self.assertIn('service_completed_successfully', compose)
        self.assertIn('postgresql-16-wal2json', (BASE/'db/Dockerfile').read_text())
        self.assertNotIn('debezium', compose.lower())
        self.assertNotIn('kafka', compose.lower())

    def test_source_transaction_atomic(self):
        repo = (BASE/'app/adapters/outbound/postgres_repository.py').read_text()
        self.assertIn('with self.engine.begin()', repo)
        self.assertIn('INSERT INTO outbox_events', repo)
        self.assertNotIn('UPDATE outbox_events', repo)

    def test_ack_after_publisher_confirm(self):
        reader = (BASE/'app/adapters/inbound/postgres_wal_reader.py').read_text()
        self.assertLess(reader.index('use_case.process_transaction(msg.payload)'),
                        reader.index('msg.cursor.send_feedback(flush_lsn='))
        publisher = (BASE/'app/adapters/outbound/rabbitmq_publisher.py').read_text()
        self.assertIn('confirm_delivery()', publisher)
        self.assertIn('mandatory=True', publisher)

    def test_message_contract(self):
        msg = b'{"eventId":"a","type":"OrderCreated","orderId":"b","amount":42}'
        self.assertEqual(decode_message(msg)['orderId'], 'b')

if __name__ == '__main__':
    unittest.main()
