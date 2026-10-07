from decimal import Decimal

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
