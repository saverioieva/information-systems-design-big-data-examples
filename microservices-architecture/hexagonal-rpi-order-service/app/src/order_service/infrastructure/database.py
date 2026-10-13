import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from order_service.adapters.outbound.postgres.models import Base


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://orders:orders@localhost:5432/orders",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def create_schema() -> None:
    Base.metadata.create_all(bind=engine)
