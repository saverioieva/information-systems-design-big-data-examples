"""Transaction adapter: handles commit/rollback/close for each use case."""
from app.infrastructure.db import SessionLocal
from app.adapters.outbound.sqlalchemy_repository import SqlAlchemyOrderRepository

class SqlAlchemyUnitOfWork:
    def __enter__(self):
        self.session=SessionLocal()
        self.repo=SqlAlchemyOrderRepository(self.session)
        return self
    def __exit__(self,exc_type,exc,tb):
        if exc_type: self.session.rollback()
        self.session.close()
    def commit(self): self.session.commit()
    def expire_all(self): self.session.expire_all()
