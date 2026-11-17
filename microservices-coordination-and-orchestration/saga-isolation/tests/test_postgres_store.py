"""PostgreSQL adapter schema checks + optional real-database integration.

Run the optional integration test using an EMPTY disposable PostgreSQL database:
  TEST_DATABASE_URL=postgresql+psycopg://demo:demo@localhost:<published-port>/test_saga_db make test
To run it from the host, publish an unused PostgreSQL port in Docker Compose
(e.g. postgres_order: 5436:5432), create a disposable test_saga_db, and pass
its URL. The default offline tests do not require a running database.
"""
import os
import unittest
from uuid import uuid4
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.adapters.outbound.postgres_store import (
    PostgresSagaStore, COMMON_TABLES, ROLE_TABLES, command_attempts,
    command_results, orders, sagas, saga_history, inbox, outbox,
    cancel_gates, credit_balances, credit_adjustments,
    version_file_events, version_file_states, countermeasure_runs, countermeasure_steps,
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
        self.assertIn('held', outbox.c)
        self.assertIn('state', cancel_gates.c)
        self.assertIn('delta', credit_adjustments.c)
        self.assertIn('next_sequence', version_file_states.c)
        self.assertIn('applied', version_file_events.c)
        self.assertIn('operation', version_file_events.c)
        self.assertIn('value', version_file_events.c)
        self.assertIn('run_id', countermeasure_runs.c)
        self.assertIn('step_id', countermeasure_steps.c)


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
    def test_post_pivot_cancelled_is_guarded_and_idempotent(self):
        """Optional real-PostgreSQL guard for SetCancelled after Kitchen pivot."""
        from sqlalchemy import delete
        from app.adapters.outbound.postgres_store import (
            cancel_sagas, cancel_history,
        )
        store = PostgresSagaStore('orchestrator', os.environ['TEST_DATABASE_URL'])
        store.initialize()
        oid = str(uuid4())
        try:
            with store.transaction() as tx:
                tx.create_order(oid, 'CUST_1', 42, isolation_mode='pessimistic')
                tx.start_cancellation(oid, initial_stage='REJECT_TICKET_PIVOT')
            with self.assertRaisesRegex(ValueError, 'completed Kitchen pivot'):
                with store.transaction() as tx:
                    tx.set_cancelled_after_pivot(oid)
            with store.transaction() as tx:
                tx.set_cancel_stage(oid, 'SET_CANCELLED')
                tx.set_cancelled_after_pivot(oid)
                tx.set_cancelled_after_pivot(oid)
                order = tx.get_order(oid)
                self.assertEqual((order['status'], order['version']), ('CANCELLED', 2))
        finally:
            with store.engine.begin() as conn:
                conn.execute(delete(cancel_history).where(cancel_history.c.order_id == oid))
                conn.execute(delete(cancel_sagas).where(cancel_sagas.c.order_id == oid))
                conn.execute(delete(saga_history).where(saga_history.c.order_id == oid))
                conn.execute(delete(sagas).where(sagas.c.order_id == oid))
                conn.execute(delete(outbox).where(outbox.c.gate_order_id == oid))
                conn.execute(delete(orders).where(orders.c.order_id == oid))
            store.engine.dispose()

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


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'),
                     'Set TEST_DATABASE_URL to a disposable PostgreSQL database to run')
class CountermeasurePostgresIntegrationTests(unittest.TestCase):
    def test_participant_owned_credit_and_version_file_are_durable(self):
        # This single optional test DB is disposable; each role creates its
        # own tables. In Docker, these roles use *different* PostgreSQLs.
        from sqlalchemy import delete
        url = os.environ['TEST_DATABASE_URL']
        accounting = PostgresSagaStore('accounting', url)
        kitchen = PostgresSagaStore('kitchen', url)
        accounting.initialize()
        kitchen.initialize()
        account_id, stream_id = str(uuid4()), str(uuid4())
        try:
            with accounting.transaction() as tx:
                tx.initialize_credit(account_id, 100)
                self.assertEqual(tx.adjust_credit(account_id, 'credit-' + account_id, 25), 125)
            with accounting.transaction() as tx:
                self.assertEqual(tx.adjust_credit(account_id, 'credit-' + account_id, 25), 125)
                self.assertEqual(tx.adjust_credit(account_id, 'debit-' + account_id, -10), 115)
            with kitchen.transaction() as tx:
                self.assertEqual(tx.apply_versioned(stream_id, 3, 'ADD', 7)['buffered'], 1)
                self.assertEqual(tx.apply_versioned(stream_id, 1, 'SET', 10)['total'], 10)
            with kitchen.transaction() as tx:
                self.assertEqual(tx.apply_versioned(stream_id, 2, 'MULTIPLY', 2),
                                 {'nextSequence': 4, 'total': 27, 'buffered': 0})
                self.assertEqual(tx.apply_versioned(stream_id, 3, 'ADD', 7)['total'], 27)
        finally:
            with accounting.engine.begin() as conn:
                conn.execute(delete(credit_adjustments).where(
                    credit_adjustments.c.account_id == account_id))
                conn.execute(delete(credit_balances).where(
                    credit_balances.c.account_id == account_id))
            with kitchen.engine.begin() as conn:
                conn.execute(delete(version_file_events).where(
                    version_file_events.c.stream_id == stream_id))
                conn.execute(delete(version_file_states).where(
                    version_file_states.c.stream_id == stream_id))
            accounting.engine.dispose()
            kitchen.engine.dispose()
