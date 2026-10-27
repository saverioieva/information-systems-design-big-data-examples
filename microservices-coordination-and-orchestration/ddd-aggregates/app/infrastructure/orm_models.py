# app/infrastructure/orm_models.py

from sqlalchemy import (
    Column,
    String,
    Enum as PgEnum,
    ForeignKey,
    Integer,
    Float,
)
from sqlalchemy.orm import relationship

from .db import Base
from app.domain.models import OrderState


class OrderModel(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    consumer_id = Column(String, nullable=False)
    restaurant_id = Column(String, nullable=False)
    state = Column(PgEnum(OrderState), nullable=False)

    # Explicit application-managed optimistic concurrency counter.
    version_id = Column(Integer, nullable=False, default=1)

    line_items = relationship(
        "OrderLineItemModel",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="joined",
    )


class OrderLineItemModel(Base):
    __tablename__ = "order_line_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)

    order = relationship("OrderModel", back_populates="line_items")
