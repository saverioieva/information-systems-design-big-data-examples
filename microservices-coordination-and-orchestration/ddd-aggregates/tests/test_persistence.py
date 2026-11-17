"""SQLite-backed integration tests for repository, version and local Outbox atomicity."""
import unittest

from sqlalchemy import select

from app.adapters.outbound.sqlalchemy_uow import SqlAlchemyUnitOfWork
from app.application.order_service import OrderService
from app.domain.models import ConcurrencyError
from app.infrastructure.orm_models import IntegrationOutboxModel, OrderLineModel, OrderModel
from tests.common import address, create_payload, line_payload, sqlite_sessions


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.sessions = sqlite_sessions()
        self.service = OrderService(lambda: SqlAlchemyUnitOfWork(self.sessions))

    def tearDown(self):
        self.engine.dispose()

    def create(self):
        payload = create_payload()
        return self.service.create(payload['consumer_id'], payload['restaurant_id'], payload['lines'])

    def test_create_commits_aggregate_and_domain_fact_together(self):
        saved = self.create()
        self.assertEqual(saved.row_version, 1)
        with self.sessions() as session:
            self.assertEqual(session.query(OrderModel).count(), 1)
            self.assertEqual(session.query(OrderLineModel).count(), 1)
            events = session.scalars(select(IntegrationOutboxModel)).all()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].event_type, 'OrderCreated')
            self.assertEqual(events[0].aggregate_id, saved.id)

    def test_line_identity_and_address_survive_roundtrip(self):
        saved = self.create()
        line_id = saved.lines[0].line_id
        saved = self.service.change_quantity(saved.id, line_id, 3, expected_version=1)
        self.assertEqual(saved.row_version, 2)
        self.assertEqual(saved.lines[0].line_id, line_id)
        saved = self.service.change_address(saved.id, address().__dict__, expected_version=2)
        self.assertEqual(saved.row_version, 3)
        self.assertEqual(saved.address, address())
        self.assertEqual(saved.total.as_dict()['amount'], '30.00')

    def test_approve_writes_order_and_outbox_in_same_transaction(self):
        saved = self.create()
        self.service.change_address(saved.id, address().__dict__)
        approved = self.service.approve(saved.id, expected_version=2)
        self.assertEqual(approved.state.value, 'APPROVED')
        with self.sessions() as session:
            events = session.scalars(select(IntegrationOutboxModel).order_by(
                IntegrationOutboxModel.created_at, IntegrationOutboxModel.event_type)).all()
            self.assertEqual({event.event_type for event in events},
                             {'OrderCreated', 'DeliveryAddressChanged', 'OrderApproved'})

    def test_stale_sql_version_rejected(self):
        saved = self.create()
        stale = self.service.get(saved.id)
        self.service.change_quantity(saved.id, saved.lines[0].line_id, 3)
        stale.change_line_quantity(stale.lines[0].line_id, 4)
        with self.assertRaises(ConcurrencyError):
            with SqlAlchemyUnitOfWork(self.sessions) as uow:
                uow.repo.save(stale)
                uow.commit()
        self.assertEqual(self.service.get(saved.id).lines[0].quantity, 3)

    def test_failed_invariant_does_not_change_database_or_outbox(self):
        saved = self.create()
        with self.assertRaises(ValueError):
            self.service.change_quantity(saved.id, saved.lines[0].line_id, 40)
        current = self.service.get(saved.id)
        self.assertEqual((current.lines[0].quantity, current.row_version), (2, 1))
        with self.sessions() as session:
            self.assertEqual(session.query(IntegrationOutboxModel).count(), 1)

    def test_transaction_rolls_back_state_and_outbox_on_failure(self):
        class FailAfterFlush(SqlAlchemyUnitOfWork):
            def commit(self):
                self.session.flush()
                raise RuntimeError('Simulated failure before commit')
        failing_service = OrderService(lambda: FailAfterFlush(self.sessions))
        payload = create_payload()
        with self.assertRaisesRegex(RuntimeError, 'Simulated failure'):
            failing_service.create(payload['consumer_id'], payload['restaurant_id'], payload['lines'])
        with self.sessions() as session:
            self.assertEqual(session.query(OrderModel).count(), 0)
            self.assertEqual(session.query(IntegrationOutboxModel).count(), 0)

    def test_no_op_does_not_advance_row_version(self):
        saved = self.create()
        saved = self.service.change_address(saved.id, address().__dict__)
        same = self.service.change_address(saved.id, address().__dict__)
        self.assertEqual(same.row_version, saved.row_version)
        with self.sessions() as session:
            self.assertEqual(session.query(IntegrationOutboxModel).count(), 2)


if __name__ == '__main__':
    unittest.main()
