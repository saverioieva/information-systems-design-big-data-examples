"""Integration over SQLite: both writes use one local SQLAlchemy transaction."""
import unittest
from dataclasses import replace
import os
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db import Base
from app.infrastructure.orm_models import IntegrationOutboxModel, OrderModel
from app.adapters.outbound.sqlalchemy_uow import SqlAlchemyUnitOfWork
from app.application.order_service import OrderService


class OutboxPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.service = OrderService(lambda: SqlAlchemyUnitOfWork(self.session_factory))

    def tearDown(self):
        self.engine.dispose()

    def test_created_and_approved_both_have_publication_intents(self):
        order = self.service.create('c', 'r', [
            {'menu_item_id': 'p', 'name': 'Pizza', 'price': 10, 'quantity': 2}])
        self.service.approve(order.id, expected_version=1)
        with self.session_factory() as session:
            saved = session.get(OrderModel, order.id)
            events = session.scalars(select(IntegrationOutboxModel)
                                     .order_by(IntegrationOutboxModel.created_at)).all()
        self.assertEqual(saved.state.value, 'APPROVED')
        self.assertEqual({e.event_type for e in events}, {'OrderCreated', 'OrderApproved'})
        self.assertEqual(len(events), 2)

    def test_failed_outbox_insert_rolls_back_order_state(self):
        first = self.service.create('c', 'r', [
            {'menu_item_id': 'p', 'name': 'Pizza', 'price': 7, 'quantity': 1}])
        with self.session_factory() as session:
            existing_id = session.scalar(select(IntegrationOutboxModel.event_id))
        from app.domain.models import Order, OrderLineItem
        other = Order.create('c', 'r', [OrderLineItem('x', 'Item', 3, 1)])
        with self.assertRaises(Exception):
            with SqlAlchemyUnitOfWork(self.session_factory) as uow:
                uow.repo.add(other)
                duplicate = replace(other.collect_domain_events()[0], event_id=existing_id)
                uow.add_events([duplicate])
                uow.commit()  # duplicate event_id -> integrity error; both writes roll back
        with self.session_factory() as session:
            self.assertIsNone(session.get(OrderModel, other.id))
            self.assertIsNotNone(session.get(OrderModel, first.id))

    def test_failure_does_not_emit_approval(self):
        order = self.service.create('c', 'r', [
            {'menu_item_id': 'p', 'name': 'Pizza', 'price': 10, 'quantity': 2}])
        self.service.approve(order.id, expected_version=1)
        with self.assertRaises(ValueError):
            self.service.approve(order.id, expected_version=2)
        # A second approval fails; event persisted only once.
        with self.session_factory() as session:
            count = session.query(IntegrationOutboxModel).count()
        self.assertEqual(count, 2)


if __name__ == '__main__':
    unittest.main()
