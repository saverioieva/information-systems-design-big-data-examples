"""SQLAlchemy adapter: repository and session in a single transaction."""
from app.adapters.outbound.sqlalchemy_repository import SqlAlchemyOrderRepository

class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def __enter__(self):
        self.session = self.session_factory()
        self.orders = SqlAlchemyOrderRepository(self.session)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.session.rollback()  # rollback any uncommitted work, including on errors
        finally:
            self.session.close()

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()
