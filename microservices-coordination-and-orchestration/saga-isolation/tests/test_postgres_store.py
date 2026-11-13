"""PostgreSQL adapter schema checks + optional real-database integration.

Run the optional integration test using an EMPTY disposable PostgreSQL database:
  TEST_DATABASE_URL=postgresql+psycopg://demo:demo@localhost:<published-port>/test_saga_db make test
To run it from the host, publish an unused PostgreSQL port in Docker Compose
(e.g. postgres_order: 5436:5432), create a disposable test_saga_db, and pass
its URL. Normal classroom tests do not require a running database.
"""
import os
import unittest
from uuid import uuid4
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.adapters.outbound.postgres_store import (
    PostgresSagaStore, COMMON_TABLES, ROLE_TABLES, command_attempts,
    command_results, orders, sagas, saga_history, inbox, outbox,
)


class PostgresSchemaTests(unittest.TestCase):
    def test_postgresql_schema_compiles(self):
        for role, tables in ROLE_TABLES.items():
            statements = [str(CreateTable(table).compile(dialect=postgresql.dialect()))
                          for table in (*COMMON_TABLES, *tables)]
            self.assertGreater(len(statements), 3, role)
            self.assertTrue(all('CREATE TABLE' in sql for sql in statements))
        self.assertTrue(any('FOREIGN KEY' in str(CreateTable(t).compile(dialect=postgresql.dialect()))
                            for t in (sagas, saga_history)))

    def test_unique_keys_and_outbox_tracking(self):
        self.assertTrue(inbox.primary_key.columns.contains_column(inbox.c.event_id))
        self.assertEqual({c.name for c in command_results.primary_key.columns}, {'order_id','action'})
        self.assertTrue(outbox.c.sent.nullable is False)
        self.assertIn('retry_demo',orders.c)
        self.assertIn('ticket_failure',orders.c)
        self.assertIn('attempt',command_attempts.c)


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'),
                     'Set TEST_DATABASE_URL to a disposable PostgreSQL database to run')
class PostgresIntegrationTests(unittest.TestCase):
    def test_real_postgres_commit_rollback_history(self):
        from sqlalchemy import delete
        url = os.environ['TEST_DATABASE_URL']
        store = PostgresSagaStore('orchestrator', url)
        store.initialize()
        oid = str(uuid4())
        try:
            with store.transaction() as tx:
                tx.create_order(oid, 'TEST', 12.5)
                tx.record_transition(oid,None,'SagaStarted','VERIFY_CONSUMER','VerifyConsumer')
                tx.enqueue('command.consumer', oid, action='VerifyConsumer', customerId='TEST')
            self.assertEqual(store.pending()['routing_key'], 'command.consumer')
            with store.transaction() as tx:
                self.assertEqual(tx.get_stage(oid),'VERIFY_CONSUMER')
                self.assertEqual(len(tx.get_history(oid)),1)
            try:
                with store.transaction() as tx:
                    tx.set_stage(oid,'SHOULD_ROLL_BACK')
                    raise RuntimeError('rollback probe')
            except RuntimeError:
                pass
            with store.transaction() as tx:
                self.assertEqual(tx.get_stage(oid),'VERIFY_CONSUMER')
        finally:
            with store.engine.begin() as connection:
                connection.execute(delete(saga_history).where(saga_history.c.order_id == oid))
                connection.execute(delete(sagas).where(sagas.c.order_id == oid))
                connection.execute(delete(orders).where(orders.c.order_id == oid))
                connection.execute(delete(outbox).where(outbox.c.payload.like(f'%{oid}%')))
            store.engine.dispose()


if __name__=='__main__':
    unittest.main()


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'),
                     'Set TEST_DATABASE_URL to a disposable PostgreSQL database to run')
class IsolationPostgresIntegrationTests(unittest.TestCase):
    def test_held_outbox_and_version_check_after_cancellation(self):
        """Optional actual PostgreSQL test of the race barrier and CAS SQL."""
        from sqlalchemy import delete, select
        from app.adapters.outbound.postgres_store import (
            approval_gates, cancel_sagas, cancel_history,
        )

        store = PostgresSagaStore('orchestrator', os.environ['TEST_DATABASE_URL'])
        store.initialize()
        oid = str(uuid4())
        try:
            with store.transaction() as tx:
                tx.create_order(oid, 'CUST_1', 42, isolation_mode='optimistic')
                tx.pause_approval(oid)
                tx.enqueue('command.order', oid, action='ApproveOrder',
                           isolationMode='optimistic', expectedVersion=0, _hold=True)
            with store.engine.connect() as conn:
                self.assertTrue(conn.execute(select(outbox.c.held).where(
                    outbox.c.gate_order_id == oid)).scalar_one())
            with store.transaction() as tx:
                self.assertEqual(tx.approval_gate(oid), 'PAUSED')
                tx.start_cancellation(oid)
                tx.set_cancel_stage(oid, 'CANCELLED')
                tx.finish_cancellation(oid)
            with store.transaction() as tx:
                self.assertFalse(tx.optimistic_approve(oid, 0))
                self.assertEqual(tx.get_order(oid)['status'], 'CANCELLED')
                self.assertEqual(tx.get_order(oid)['version'], 2)
                tx.release_approval(oid)
            with store.engine.connect() as conn:
                self.assertFalse(conn.execute(select(outbox.c.held).where(
                    outbox.c.gate_order_id == oid)).scalar_one())
        finally:
            with store.engine.begin() as conn:
                conn.execute(delete(cancel_history).where(cancel_history.c.order_id == oid))
                conn.execute(delete(approval_gates).where(approval_gates.c.order_id == oid))
                conn.execute(delete(cancel_sagas).where(cancel_sagas.c.order_id == oid))
                conn.execute(delete(saga_history).where(saga_history.c.order_id == oid))
                conn.execute(delete(sagas).where(sagas.c.order_id == oid))
                conn.execute(delete(outbox).where(outbox.c.gate_order_id == oid))
                conn.execute(delete(orders).where(orders.c.order_id == oid))
            store.engine.dispose()
