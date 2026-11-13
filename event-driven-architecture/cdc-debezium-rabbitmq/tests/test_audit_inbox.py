import tempfile
import unittest
from pathlib import Path
from audit.inbox import AuditInbox


class InboxTests(unittest.TestCase):
    def test_deduplication_across_independent_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'audit.sqlite3')
            first, second = AuditInbox(path), AuditInbox(path)
            event = {'eventId':'e1','type':'OrderCreated','orderId':'o1'}
            self.assertTrue(first.record(event))
            self.assertFalse(second.record(event))
            self.assertEqual(len(second.list_records()),1)

    def test_rejects_bad_event(self):
        with tempfile.TemporaryDirectory() as directory:
            inbox = AuditInbox(str(Path(directory)/'db.sqlite3'))
            with self.assertRaises(ValueError):
                inbox.record({'type':'OrderCreated'})


if __name__ == '__main__':
    unittest.main()
