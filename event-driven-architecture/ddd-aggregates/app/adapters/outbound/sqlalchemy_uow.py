"""Transaction adapter: one SQL transaction for state plus outgoing notifications."""
from dataclasses import asdict

from app.infrastructure.db import SessionLocal
from app.infrastructure.orm_models import IntegrationOutboxModel
from app.adapters.outbound.sqlalchemy_repository import SqlAlchemyOrderRepository


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def __enter__(self):
        self.session = self.session_factory()
        self.repo = SqlAlchemyOrderRepository(self.session)
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.session.rollback()
        self.session.close()

    def add_events(self, events):
        for event in events:
            self.session.add(IntegrationOutboxModel(
                event_id=event.event_id,
                aggregate_id=event.aggregate_id,
                event_type=type(event).__name__,
                payload=asdict(event),
            ))

    def commit(self):
        self.session.commit()

    def expire_all(self):
        self.session.expire_all()
